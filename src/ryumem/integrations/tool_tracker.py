"""
Tool Usage Tracking for Google ADK

This module provides automatic tracking of tool executions in Google ADK agents,
storing usage patterns, success rates, and task associations in the knowledge graph.

Example:
    ```python
    from google import genai
    from ryumem.integrations import add_memory_to_agent, enable_tool_tracking

    agent = genai.Agent(name="assistant", model="gemini-2.0-flash")
    memory = add_memory_to_agent(agent, ryumem_customer_id="my_company")

    # One line to enable automatic tool tracking!
    enable_tool_tracking(agent, ryumem=memory.ryumem)

    # All non-Ryumem tools are now automatically tracked
    # Query later: "Which tools work best for data analysis?"
    ```
"""

from typing import Optional, Dict, Any, List, Callable, Union
import logging
import time
import json
import inspect
import functools
import asyncio
import threading
import contextvars
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from ryumem import Ryumem

logger = logging.getLogger(__name__)

# Shared thread pool for blocking operations
_thread_pool = ThreadPoolExecutor(max_workers=4)

# Context variable for parent episode tracking (async-safe)
# This allows tool executions to be linked to their triggering user query
# Uses contextvars instead of threading.local for proper async context propagation
_query_episode_context = contextvars.ContextVar('query_episode_id', default=None)

# Fallback: Session-based storage for episode tracking
# Used when contextvars don't propagate correctly across async boundaries
# Key: (session_id, user_id), Value: episode_id
# Protected by lock for thread safety
_session_episode_map: Dict[tuple, str] = {}
_session_episode_lock = threading.RLock()

# Blacklist of Ryumem memory tools to prevent circular dependencies
RYUMEM_TOOL_BLACKLIST = {
    "search_memory",
    "save_memory",
    "get_entity_context",
}


def set_current_query_episode(episode_id: str, session_id: Optional[str] = None, user_id: Optional[str] = None) -> None:
    """
    Set the current query episode ID in context variable storage.

    This is called when a user query is processed, allowing subsequent
    tool executions to link back to the query that triggered them.

    Uses dual storage: contextvars (primary) + session map (fallback)

    Args:
        episode_id: UUID of the user query episode
        session_id: Optional session ID for fallback storage
        user_id: Optional user ID for fallback storage
    """
    # Primary: Set in context variable
    _query_episode_context.set(episode_id)

    # Fallback: Store in session map for contexts where contextvars don't propagate
    if session_id and user_id:
        with _session_episode_lock:
            _session_episode_map[(session_id, user_id)] = episode_id
        logger.debug(f"Set query episode in both contextvar and session map: {episode_id}")
    else:
        logger.debug(f"Set query episode in contextvar only (no session/user): {episode_id}")


def get_current_query_episode(session_id: Optional[str] = None, user_id: Optional[str] = None) -> Optional[str]:
    """
    Get the current query episode ID from context variable storage or session map.

    Tries contextvars first, falls back to session map if not found.

    Args:
        session_id: Optional session ID for fallback lookup
        user_id: Optional user ID for fallback lookup

    Returns:
        Episode ID of the current query, or None if not set
    """
    # Try contextvar first (primary mechanism)
    episode_id = _query_episode_context.get()

    if episode_id:
        return episode_id

    # Fallback: Try session map (thread-safe)
    with _session_episode_lock:
        # Try exact match first: (session_id, user_id)
        if session_id and user_id:
            episode_id = _session_episode_map.get((session_id, user_id))
            if episode_id:
                logger.debug(f"Retrieved query episode from session map (contextvar was None): {episode_id}")
                return episode_id

        # If session_id is None (tool_context doesn't provide it), try finding by user_id alone
        # This happens when Google ADK's tool_context doesn't include session_id
        if user_id and not session_id:
            # Search for any entry with matching user_id
            for (sid, uid), ep_id in _session_episode_map.items():
                if uid == user_id:
                    logger.debug(f"Retrieved query episode from session map by user_id only (session_id was None): {ep_id}")
                    return ep_id

    return None


def clear_current_query_episode(session_id: Optional[str] = None, user_id: Optional[str] = None) -> None:
    """
    Clear the current query episode from context variable storage and session map.

    Args:
        session_id: Optional session ID for clearing from session map
        user_id: Optional user ID for clearing from session map
    """
    # Clear from contextvar
    _query_episode_context.set(None)

    # Clear from session map (thread-safe)
    if session_id and user_id:
        with _session_episode_lock:
            _session_episode_map.pop((session_id, user_id), None)
        logger.debug(f"Cleared query episode from both contextvar and session map")
    else:
        logger.debug("Cleared query episode from contextvar only")


class ToolTracker:
    """
    Automatic tool usage tracker for Google ADK agents.

    Captures tool executions, classifies tasks using LLM, and stores
    everything in the knowledge graph for later analysis.

    Args:
        ryumem: Ryumem instance for storing tool usage data
        ryumem_customer_id: Customer/company identifier
        default_user_id: Default user ID to use when tool context doesn't provide one
        classification_model: LLM model to use for task classification
        summarize_large_outputs: Automatically summarize outputs >max_output_length
        max_output_length: Maximum length for output storage (chars)
        max_context_messages: Number of recent messages to include for classification
        sanitize_pii: Remove PII (emails, phones) from stored data
        exclude_params: List of parameter names to exclude from storage
        sampling_rate: Fraction of tool calls to track (0.0-1.0)
        fail_open: If True, tool executes even if tracking fails
    """

    def __init__(
        self,
        ryumem: Ryumem,
        ryumem_customer_id: str,
        default_user_id: Optional[str] = None,
        classification_model: str = "gpt-4o-mini",
        summarize_large_outputs: bool = True,
        max_output_length: int = 1000,
        max_context_messages: int = 5,
        sanitize_pii: bool = True,
        exclude_params: Optional[List[str]] = None,
        sampling_rate: float = 1.0,
        fail_open: bool = True,
    ):
        self.ryumem = ryumem
        self.ryumem_customer_id = ryumem_customer_id
        self.default_user_id = default_user_id
        self.classification_model = classification_model
        self.summarize_large_outputs = summarize_large_outputs
        self.max_output_length = max_output_length
        self.max_context_messages = max_context_messages
        self.sanitize_pii = sanitize_pii
        self.exclude_params = exclude_params or ["password", "api_key", "secret", "token"]
        self.sampling_rate = sampling_rate
        self.fail_open = fail_open
        self._execution_count = 0

        # Background task management
        self.async_classification = True  # Enable async classification by default
        self._background_tasks = set()    # Track background tasks

        logger.info(
            f"Initialized ToolTracker for customer: {ryumem_customer_id}, "
            f"sampling: {sampling_rate*100}%"
        )

    def register_tools(self, tools: List[Dict[str, str]]) -> None:
        """
        Register tools in the database at startup.

        Only generates descriptions for new tools (doesn't re-process existing ones).

        Args:
            tools: List of tool dicts with 'name' and 'description' keys
        """
        try:
            for tool in tools:
                tool_name = tool.get("name")
                tool_description = tool.get("description", "")

                if not tool_name:
                    logger.warning(f"Skipping tool with no name: {tool}")
                    continue

                # Check if tool already exists
                existing_tool = self.ryumem.db.get_tool_by_name(tool_name)
                if existing_tool:
                    logger.debug(f"Tool already registered: {tool_name}")
                    continue

                # New tool - generate enhanced description using LLM
                enhanced_description = tool_description
                if tool_description:
                    enhanced_description = self._generate_tool_description(
                        tool_name=tool_name,
                        base_description=tool_description
                    )

                # Create embedding for tool name
                tool_embedding = self.ryumem.embedding_client.embed(tool_name)

                # Save tool to database
                self.ryumem.db.save_tool(
                    tool_name=tool_name,
                    description=enhanced_description or f"Tool: {tool_name}",
                    name_embedding=tool_embedding,
                )

                logger.debug(f"Registered new tool: {tool_name}")

        except Exception as e:
            logger.error(f"Failed to register tools: {e}")
            if not self.fail_open:
                raise

    def _generate_tool_description(self, tool_name: str, base_description: str) -> str:
        """
        Use LLM to generate an enhanced, user-friendly description of the tool.

        Args:
            tool_name: Name of the tool
            base_description: Base description from the tool's docstring

        Returns:
            Enhanced description suitable for UI display
        """
        prompt = f"""Generate a clear, user-friendly description of this tool for display in a UI.

Tool Name: {tool_name}
Technical Description: {base_description}

Provide a concise description (1-2 sentences, max 150 characters) that explains:
1. What the tool does
2. When it should be used

Make it user-friendly and avoid technical jargon. Just return the description text, nothing else.
"""

        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.ryumem.llm_client.generate(
                messages,
                temperature=0.3,
                max_tokens=100,
            )

            description = response.get("content", "").strip()
            return description or base_description

        except Exception as e:
            logger.error(f"Tool description generation failed for {tool_name}: {e}")
            return base_description

    def _should_track(self) -> bool:
        """Determine if this execution should be tracked based on sampling rate."""
        import random
        return random.random() < self.sampling_rate

    def _sanitize_value(self, value: Any) -> Any:
        """Remove PII from values if sanitization is enabled."""
        if not self.sanitize_pii:
            return value

        if not isinstance(value, str):
            return value

        # Simple PII patterns (can be enhanced with NER)
        import re

        # Email pattern
        value = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', value)

        # Phone pattern (US format)
        value = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', value)

        # SSN pattern
        value = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', value)

        # Credit card pattern (basic)
        value = re.sub(r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b', '[CARD]', value)

        return value

    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize parameters by excluding sensitive fields and removing PII."""
        sanitized = {}
        for key, value in params.items():
            # Skip excluded parameters
            if key.lower() in [p.lower() for p in self.exclude_params]:
                sanitized[key] = "[REDACTED]"
                continue

            # Sanitize PII if enabled
            sanitized[key] = self._sanitize_value(value)

        return sanitized

    def _summarize_output(self, output: Any) -> str:
        """Summarize large outputs to reduce storage size."""
        output_str = str(output)

        if len(output_str) <= self.max_output_length:
            return self._sanitize_value(output_str)

        if self.summarize_large_outputs:
            # Truncate and add indicator
            truncated = output_str[:self.max_output_length]
            return self._sanitize_value(f"{truncated}... [truncated, total length: {len(output_str)}]")

        return self._sanitize_value(output_str[:self.max_output_length])

    def _update_episode_with_tool_execution(
        self,
        episode_id: str,
        tool_execution: Dict[str, Any],
    ) -> None:
        """
        Update an episode's metadata to append a tool execution record.

        Args:
            episode_id: UUID of the parent query episode
            tool_execution: Dictionary containing tool execution details
        """
        try:
            import json

            # Fetch current metadata
            query_fetch = """
            MATCH (e:Episode {uuid: $episode_id})
            RETURN e.metadata AS metadata
            """
            result = self.ryumem.db.execute(query_fetch, {"episode_id": episode_id})

            if not result:
                logger.error(f"Episode {episode_id} not found")
                return

            # Parse existing metadata
            current_metadata_str = result[0].get('metadata', '{}')
            current_metadata = json.loads(current_metadata_str) if isinstance(current_metadata_str, str) else current_metadata_str

            # Initialize tools_used array if it doesn't exist
            if 'tools_used' not in current_metadata:
                current_metadata['tools_used'] = []

            # Append new tool execution
            current_metadata['tools_used'].append(tool_execution)

            # Update episode with new metadata
            query_update = """
            MATCH (e:Episode {uuid: $episode_id})
            SET e.metadata = $metadata
            RETURN e.uuid
            """

            self.ryumem.db.execute(query_update, {
                "episode_id": episode_id,
                "metadata": json.dumps(current_metadata)
            })

            logger.debug(
                f"Updated episode {episode_id} with tool execution: {tool_execution['tool_name']}"
            )

        except Exception as e:
            logger.error(f"Failed to update episode with tool execution: {e}")
            if not self.fail_open:
                raise

    async def _store_tool_execution_async(
        self,
        tool_name: str,
        tool_description: str,
        input_params: Dict[str, Any],
        output: Any,
        success: bool,
        error: Optional[str],
        duration_ms: int,
        user_id: Optional[str],
        session_id: Optional[str],
        context: Optional[str],
    ) -> None:
        """Store tool execution by updating the parent query episode's metadata."""
        try:
            # Sanitize and summarize data
            sanitized_params = self._sanitize_params(input_params)
            output_summary = self._summarize_output(output) if success else None

            # Get parent query episode ID from multiple sources (priority order):
            # 1. Context variable (primary - works for same async context)
            # 2. Session map (fallback - works cross-context)
            # 3. Runner instance (most reliable - always available via ToolTracker)
            parent_episode_id = get_current_query_episode(session_id=session_id, user_id=user_id)

            # If not found in context/session, try getting from runner instance
            if parent_episode_id is None and hasattr(self, '_runner'):
                parent_episode_id = getattr(self._runner, '_ryumem_query_episode', None)
                if parent_episode_id:
                    logger.debug(f"Retrieved query episode from runner instance: {parent_episode_id}")

            # Defensive logging for debugging context propagation issues
            if parent_episode_id is None:
                logger.warning(
                    f"⚠️  Tool execution '{tool_name}' has no parent query episode. "
                    f"Session: {session_id}, User: {user_id}. "
                    "This means the query context was not set or was cleared too early. "
                    "Tool executions will not be tracked."
                )
                return

            logger.info(f"✓ Recording tool execution '{tool_name}' in query episode: {parent_episode_id}")

            # Build tool execution record
            tool_execution = {
                "tool_name": tool_name,
                "input_params": sanitized_params,
                "output_summary": output_summary,
                "success": success,
                "error": error,
                "duration_ms": duration_ms,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Update parent episode's metadata (append to tools_used array)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                _thread_pool,
                lambda: self._update_episode_with_tool_execution(
                    episode_id=parent_episode_id,
                    tool_execution=tool_execution
                )
            )

            logger.info(
                f"Tracked tool execution: {tool_name} "
                f"- {'success' if success else 'failure'} in {duration_ms}ms "
                f"[in query: {parent_episode_id}]"
            )

        except Exception as e:
            logger.error(f"Failed to store tool execution: {e}")
            if not self.fail_open:
                raise

    def _store_tool_execution_sync(self, *args, **kwargs) -> None:
        """Synchronous wrapper for storing tool execution."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._store_tool_execution_async(*args, **kwargs))
        finally:
            loop.close()

    def track_execution(
        self,
        tool_name: str,
        tool_description: str,
        input_params: Dict[str, Any],
        output: Any,
        success: bool,
        error: Optional[str],
        duration_ms: int,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        context: Optional[str] = None,
    ) -> None:
        """
        Track a tool execution.

        This is the main entry point for recording tool usage.
        Can be called synchronously or asynchronously.
        """
        # Check if we should track this execution
        if not self._should_track():
            logger.debug(f"Skipping tracking for {tool_name} (sampling)")
            return

        self._execution_count += 1

        # Store execution (async or sync based on configuration)
        if self.async_classification:
            # Fire and forget - don't block
            # Check if there's a running event loop
            try:
                loop = asyncio.get_running_loop()
                # We're already in an async context, create task
                print(f"[TRACK] Creating async task for {tool_name}")
                task = asyncio.create_task(
                    self._store_tool_execution_async(
                        tool_name, tool_description, input_params,
                        output, success, error, duration_ms,
                        user_id, session_id, context
                    )
                )
                # Keep reference to prevent garbage collection
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)
                print(f"[TRACK] Async task created for {tool_name}")
            except RuntimeError as e:
                # No running loop - we're in sync context, use threading
                print(f"[TRACK] No event loop, using thread for {tool_name}: {e}")
                import threading
                thread = threading.Thread(
                    target=self._store_tool_execution_sync,
                    args=(tool_name, tool_description, input_params,
                          output, success, error, duration_ms,
                          user_id, session_id, context)
                )
                thread.daemon = True  # Don't block program exit
                thread.start()
                print(f"[TRACK] Thread started for {tool_name}")
        else:
            # Synchronous - blocks until stored
            self._store_tool_execution_sync(
                tool_name, tool_description, input_params,
                output, success, error, duration_ms,
                user_id, session_id, context
            )

    def create_wrapper(
        self,
        func: Callable,
        tool_name: Optional[str] = None,
        tool_description: Optional[str] = None,
    ) -> Callable:
        """
        Create a wrapper for a tool function to automatically track executions.

        Handles both synchronous and asynchronous functions.

        Args:
            func: The tool function to wrap
            tool_name: Override for tool name (defaults to function name)
            tool_description: Tool description for classification

        Returns:
            Wrapped function that tracks executions
        """
        _tool_name = tool_name or func.__name__
        _tool_description = tool_description or func.__doc__ or ""

        # Check if function is async
        is_async = inspect.iscoroutinefunction(func)

        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                success = True
                error = None
                output = None

                try:
                    output = await func(*args, **kwargs)
                    return output
                except Exception as e:
                    success = False
                    error = str(e)
                    raise
                finally:
                    duration_ms = int((time.time() - start_time) * 1000)

                    # Extract user_id and session_id from kwargs if available
                    user_id = kwargs.get('user_id')
                    session_id = kwargs.get('session_id')

                    # Build input params (exclude internal params)
                    input_params = {
                        k: v for k, v in kwargs.items()
                        if k not in ['user_id', 'session_id']
                    }

                    # Track execution (fire and forget)
                    try:
                        self.track_execution(
                            tool_name=_tool_name,
                            tool_description=_tool_description,
                            input_params=input_params,
                            output=output,
                            success=success,
                            error=error,
                            duration_ms=duration_ms,
                            user_id=user_id,
                            session_id=session_id,
                        )
                    except Exception as track_error:
                        logger.error(f"Tracking failed for {_tool_name}: {track_error}")
                        if not self.fail_open:
                            raise

            return async_wrapper

        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                success = True
                error = None
                output = None

                try:
                    output = func(*args, **kwargs)
                    return output
                except Exception as e:
                    success = False
                    error = str(e)
                    raise
                finally:
                    duration_ms = int((time.time() - start_time) * 1000)

                    # Extract user_id and session_id from kwargs if available
                    user_id = kwargs.get('user_id')
                    session_id = kwargs.get('session_id')

                    # Build input params
                    input_params = {
                        k: v for k, v in kwargs.items()
                        if k not in ['user_id', 'session_id']
                    }

                    # Track execution
                    try:
                        self.track_execution(
                            tool_name=_tool_name,
                            tool_description=_tool_description,
                            input_params=input_params,
                            output=output,
                            success=success,
                            error=error,
                            duration_ms=duration_ms,
                            user_id=user_id,
                            session_id=session_id,
                        )
                    except Exception as track_error:
                        logger.error(f"Tracking failed for {_tool_name}: {track_error}")
                        if not self.fail_open:
                            raise

            return sync_wrapper

    def wrap_agent_tools(
        self,
        agent,
        include_tools: Optional[List[str]] = None,
        exclude_tools: Optional[List[str]] = None,
    ) -> int:
        """
        Wrap all tools in a Google ADK agent for automatic tracking.

        For FunctionTool objects, wraps the run_async method instead of the func attribute
        since that's where the actual execution happens.

        Args:
            agent: Google ADK Agent instance
            include_tools: Optional whitelist of tool names to track
            exclude_tools: Optional additional tools to exclude (beyond Ryumem tools)

        Returns:
            Number of tools wrapped
        """
        # Get agent tools
        if not hasattr(agent, 'tools') or not agent.tools:
            logger.warning("Agent has no tools to track")
            return 0

        # Build exclusion list
        excluded = set(RYUMEM_TOOL_BLACKLIST)
        if exclude_tools:
            excluded.update(exclude_tools)

        # Try to import FunctionTool (may not be available)
        try:
            from google.adk.tools import FunctionTool
            has_function_tool = True
        except ImportError:
            has_function_tool = False
            logger.debug("google.adk.tools.FunctionTool not available, will only wrap raw functions")

        # Wrap each tool
        wrapped_count = 0
        for i, tool in enumerate(agent.tools):
            # Determine if this is a FunctionTool object or raw function
            is_function_tool = has_function_tool and isinstance(tool, FunctionTool)

            # Get the actual function to inspect
            func = tool.func if is_function_tool else tool

            # Get tool name
            tool_name = getattr(func, '__name__', f'tool_{i}')

            # Check blacklist
            if tool_name in excluded:
                logger.debug(f"Skipping blacklisted tool: {tool_name}")
                continue

            # Check whitelist if provided
            if include_tools and tool_name not in include_tools:
                logger.debug(f"Skipping non-whitelisted tool: {tool_name}")
                continue

            # Get tool description
            tool_description = getattr(func, '__doc__', None)

            # Update the agent's tool list based on type
            if is_function_tool:
                # For FunctionTool objects, wrap the run_async method
                # This is where the actual execution happens in ADK
                self._wrap_run_async(tool, tool_name, tool_description)
                logger.debug(f"Wrapped FunctionTool.run_async for tracking: {tool_name}")
            else:
                # For raw functions, wrap and replace in the list
                wrapped_func = self.create_wrapper(
                    func,
                    tool_name=tool_name,
                    tool_description=tool_description
                )
                agent.tools[i] = wrapped_func
                logger.debug(f"Wrapped raw function for tracking: {tool_name}")

            wrapped_count += 1

        logger.info(
            f"Tool tracking enabled: {wrapped_count} tools wrapped, "
            f"{len(excluded)} excluded (Ryumem memory tools)"
        )

        return wrapped_count

    def _wrap_run_async(
        self,
        tool,
        tool_name: str,
        tool_description: Optional[str],
    ) -> None:
        """
        Wrap a FunctionTool's run_async method to track executions.

        This is the correct place to intercept tool calls in Google ADK,
        since run_async is where the actual function execution happens.

        Args:
            tool: FunctionTool instance
            tool_name: Name of the tool
            tool_description: Tool's description/docstring
        """
        # Store reference to original run_async
        original_run_async = tool.run_async

        # Create tracking wrapper
        async def tracking_run_async(*, args, tool_context):
            start_time = time.time()
            success = True
            error = None
            output = None

            try:
                # Call original run_async
                output = await original_run_async(args=args, tool_context=tool_context)
                return output
            except Exception as e:
                success = False
                error = str(e)
                raise
            finally:
                duration_ms = int((time.time() - start_time) * 1000)

                # Extract user_id and session_id if available in tool_context
                # Fall back to default_user_id if tool_context doesn't provide one
                user_id = getattr(tool_context, 'user_id', None) or self.default_user_id
                session_id = getattr(tool_context, 'session_id', None)

                try:
                    # Store tracking data synchronously
                    await self._store_tool_execution_async(
                        tool_name=tool_name,
                        tool_description=tool_description,
                        input_params=args,
                        output=output,
                        success=success,
                        error=error,
                        duration_ms=duration_ms,
                        user_id=user_id,
                        session_id=session_id,
                        context=None,
                    )
                except Exception as track_error:
                    logger.error(f"Tracking failed for {tool_name}: {track_error}")
                    if not self.fail_open:
                        raise

        # Replace the method
        tool.run_async = tracking_run_async


def enable_tool_tracking(
    agent,
    ryumem: Ryumem,
    ryumem_customer_id: Optional[str] = None,
    include_tools: Optional[List[str]] = None,
    exclude_tools: Optional[List[str]] = None,
    **tracker_kwargs
) -> ToolTracker:
    """
    Enable automatic tool tracking for a Google ADK agent.

    DEPRECATED: Use add_memory_to_agent(..., track_tools=True) instead for simpler API.

    This function wraps all non-Ryumem tools in the agent to automatically
    track their executions in the knowledge graph.

    Args:
        agent: Google ADK Agent instance
        ryumem: Ryumem instance for storage
        ryumem_customer_id: Optional customer ID (uses ryumem's default if not provided)
        include_tools: Optional whitelist of tool names to track
        exclude_tools: Optional additional tools to exclude (beyond Ryumem tools)
        **tracker_kwargs: Additional arguments for ToolTracker

    Returns:
        ToolTracker instance for advanced usage

    Example (DEPRECATED):
        ```python
        from google import genai
        from ryumem.integrations import add_memory_to_agent, enable_tool_tracking

        agent = genai.Agent(name="assistant", model="gemini-2.0-flash")
        memory = add_memory_to_agent(agent, ryumem_customer_id="my_company")

        # Old way (still works but deprecated)
        tracker = enable_tool_tracking(
            agent,
            ryumem=memory.ryumem,
            sampling_rate=0.1
        )
        ```

    Recommended (NEW):
        ```python
        from ryumem.integrations import add_memory_to_agent

        # New simpler way - one function call!
        memory = add_memory_to_agent(
            agent,
            ryumem_customer_id="my_company",
            track_tools=True,
            sampling_rate=0.1
        )
        ```
    """
    # Determine customer ID
    if ryumem_customer_id is None:
        # Try to get from ryumem config or use default
        ryumem_customer_id = "default_customer"

    # Create tracker
    tracker = ToolTracker(
        ryumem=ryumem,
        ryumem_customer_id=ryumem_customer_id,
        **tracker_kwargs
    )

    # Use the new wrap_agent_tools method
    tracker.wrap_agent_tools(
        agent,
        include_tools=include_tools,
        exclude_tools=exclude_tools
    )

    return tracker
