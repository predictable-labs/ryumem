"""
Tool Usage Tracking for Google ADK

This module provides automatic tracking of tool executions in Google ADK agents,
storing usage patterns, success rates, and task associations in the knowledge graph.

Example:
    ```python
    from google import genai
    from ryumem.integrations import add_memory_to_agent

    agent = genai.Agent(name="assistant", model="gemini-2.0-flash")
    memory = add_memory_to_agent(agent, ryumem_instance=ryumem, track_tools=True)

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
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

logger = logging.getLogger(__name__)

# Module-level context variable - tracks the currently executing tool
_current_tool: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    '_current_tool',
    default=None
)

def _set_current_tool(tool_name: str) -> contextvars.Token:
    """Set the currently executing tool, returns token for cleanup."""
    return _current_tool.set(tool_name)

def _clear_current_tool(token: contextvars.Token) -> None:
    """Clear the current tool using token."""
    _current_tool.reset(token)

def _get_parent_tool() -> Optional[str]:
    """Get the name of the parent tool if one is currently executing."""
    return _current_tool.get()


class ToolTracker:
    """
    Automatic tool usage tracker for Google ADK agents.

    Captures tool executions, classifies tasks using LLM, and stores
    everything in the knowledge graph for later analysis.

    All configuration is read from the ryumem instance's config.

    Args:
        ryumem: Ryumem instance for storing tool usage data (contains config)
    """

    def __init__(
        self,
        ryumem: Ryumem,
    ):
        self.ryumem = ryumem
        self._execution_count = 0

        # Background task management
        self.async_classification = True  # Enable async classification by default
        self._background_tasks = set()    # Track background tasks

        logger.info(
            f"Initialized ToolTracker "
            f"sampling: {self.ryumem.config.tool_tracking.sample_rate*100}%"
        )

    def register_tools(self, tools: List[Dict[str, str]]) -> None:
        """
        Register tools in the database at startup using batch endpoint.

        Efficiently registers multiple tools in a single API call.
        Backend handles duplicate detection automatically.

        Args:
            tools: List of tool dicts with 'name' and 'description' keys
        """
        try:
            if not tools:
                return

            # Prepare batch of tools with embeddings
            tools_batch = []
            for tool in tools:
                tool_name = tool.get("name")
                tool_description = tool.get("description", "")

                if not tool_name:
                    logger.warning(f"Skipping tool with no name: {tool}")
                    continue

                # Generate enhanced description using LLM if enabled
                enhanced_description = tool_description
                if tool_description and self.ryumem.config.tool_tracking.enhance_descriptions:
                    enhanced_description = self._generate_tool_description(
                        tool_name=tool_name,
                        base_description=tool_description
                    )

                # Add to batch (no embeddings needed for batch operation)
                tools_batch.append({
                    "tool_name": tool_name,
                    "description": enhanced_description or f"Tool: {tool_name}",
                    "name_embedding": None
                })

            if not tools_batch:
                logger.warning("No valid tools to register")
                return

            # Batch save all tools in one API call
            result = self.ryumem.batch_save_tools(tools_batch)

            logger.info(
                f"Batch tool registration: {result.get('saved', 0)} new, "
                f"{result.get('updated', 0)} updated, {result.get('failed', 0)} failed"
            )

            # Log any errors
            if result.get('errors'):
                for error in result['errors']:
                    logger.error(f"Tool registration error: {error}")

        except Exception as e:
            logger.error(f"Failed to register tools: {e}")
            if not self.ryumem.config.tool_tracking.ignore_errors:
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
        return random.random() < self.ryumem.config.tool_tracking.sample_rate

    def _sanitize_value(self, value: Any) -> Any:
        """Remove PII from values if sanitization is enabled."""
        if not self.ryumem.config.tool_tracking.sanitize_pii:
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
        exclude_params = ["password", "api_key", "secret", "token"]
        sanitized = {}
        for key, value in params.items():
            # Skip excluded parameters
            if key.lower() in [p.lower() for p in exclude_params]:
                sanitized[key] = "[REDACTED]"
                continue

            # Sanitize PII if enabled
            sanitized[key] = self._sanitize_value(value)

        return sanitized

    def _summarize_output(self, output: Any) -> str:
        """Summarize large outputs to reduce storage size."""
        output_str = str(output)
        max_length = self.ryumem.config.tool_tracking.max_output_chars

        if len(output_str) <= max_length:
            return self._sanitize_value(output_str)

        if self.ryumem.config.tool_tracking.summarize_outputs:
            # Truncate and add indicator
            truncated = output_str[:max_length]
            return self._sanitize_value(f"{truncated}... [truncated, total length: {len(output_str)}]")

        return self._sanitize_value(output_str[:max_length])

    def _update_episode_with_tool_execution(
        self,
        episode_id: str,
        session_id: str,
        tool_execution: Dict[str, Any],
    ) -> None:
        """
        Update an episode's metadata to append a tool execution record.

        Args:
            episode_id: UUID of the parent query episode
            session_id: Session ID to find the correct run
            tool_execution: Dictionary containing tool execution details
        """
        try:
            import json
            from ryumem.core.metadata_models import EpisodeMetadata, ToolExecution

            # Fetch current episode via API
            episode = self.ryumem.get_episode_by_uuid(episode_id)

            if not episode:
                logger.error(f"Episode {episode_id} not found")
                return

            # Parse existing metadata
            metadata_dict = episode.metadata if episode.metadata else {}

            # Parse into Pydantic model
            episode_metadata = EpisodeMetadata(**metadata_dict)

            # Create ToolExecution model
            tool_exec = ToolExecution(**tool_execution)

            # Append to latest run in this session
            latest_run = episode_metadata.get_latest_run(session_id)
            if latest_run:
                latest_run.tools_used.append(tool_exec)

                # Update episode with new metadata via API
                self.ryumem.update_episode_metadata(
                    episode_uuid=episode_id,
                    metadata=episode_metadata.model_dump()
                )

                logger.debug(
                    f"Updated episode {episode_id} session {session_id[:8]} with tool: {tool_execution['tool_name']}"
                )
            else:
                logger.warning(f"No run found for session {session_id} in episode {episode_id}")

        except Exception as e:
            logger.error(f"Failed to update episode with tool execution: {e}")
            if not self.ryumem.config.tool_tracking.ignore_errors:
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
        parent_tool_name: Optional[str] = None,  # NEW parameter
    ) -> None:
        """Store tool execution with optional parent by updating the parent query episode's metadata."""
        try:
            # Sanitize and summarize data
            sanitized_params = self._sanitize_params(input_params)
            output_summary = self._summarize_output(output) if success else None

            episode = self.ryumem.get_episode_by_session_id(session_id)
            if episode is None:
                logger.error(f"Failed to find episode related to session {session_id} to store tool execution for tool {tool_name}")
                return

            # Build tool execution record
            tool_execution = {
                "tool_name": tool_name,  # Already in dot notation
                "input_params": sanitized_params,
                "output_summary": output_summary or "",  # Ensure string, not None
                "success": success,
                "error": error,
                "duration_ms": duration_ms,
                "timestamp": datetime.utcnow().isoformat(),
                "parent_tool_name": parent_tool_name,  # NEW FIELD
            }

            # Update parent episode's metadata (append to tools_used array)
            if not session_id:
                error_msg = f"session_id is required for tool tracking but was None for tool '{tool_name}'"
                logger.error(error_msg)
                if not self.ryumem.config.tool_tracking.ignore_errors:
                    raise ValueError(error_msg)
                return

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._update_episode_with_tool_execution(
                    episode_id=episode.uuid,
                    session_id=session_id,
                    tool_execution=tool_execution
                )
            )

            logger.info(
                f"Tracked tool execution: {tool_name} "
                f"- {'success' if success else 'failure'} in {duration_ms}ms "
                f"[in query: {session_id}]"
            )

        except Exception as e:
            logger.error(f"Failed to store tool execution: {e}")
            if not self.ryumem.config.tool_tracking.ignore_errors:
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
        parent_tool_name: Optional[str] = None,
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
                        user_id, session_id, context, parent_tool_name
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
                          user_id, session_id, context, parent_tool_name)
                )
                thread.daemon = True  # Don't block program exit
                thread.start()
                print(f"[TRACK] Thread started for {tool_name}")
        else:
            # Synchronous - blocks until stored
            self._store_tool_execution_sync(
                tool_name, tool_description, input_params,
                output, success, error, duration_ms,
                user_id, session_id, context, parent_tool_name
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

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Check for parent tool
            parent_tool = _get_parent_tool()
            display_name = f"{parent_tool}.{_tool_name}" if parent_tool else _tool_name

            # Set as current tool
            token = _set_current_tool(_tool_name)

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
                # Clear current tool
                _clear_current_tool(token)

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
                        tool_name=display_name,  # Use dot notation
                        tool_description=_tool_description,
                        input_params=input_params,
                        output=output,
                        success=success,
                        error=error,
                        duration_ms=duration_ms,
                        user_id=user_id,
                        session_id=session_id,
                        parent_tool_name=parent_tool  # NEW parameter
                    )
                except Exception as track_error:
                    logger.error(f"Tracking failed for {display_name}: {track_error}")
                    if not self.ryumem.config.tool_tracking.ignore_errors:
                        raise

        return sync_wrapper

    def _wrap_mcp_toolset(self, toolset: McpToolset) -> None:
        """
        Wrap McpToolset.get_tools() to track all MCP tool executions.

        Args:
            toolset: McpToolset instance to wrap
        """
        original_get_tools = toolset.get_tools

        async def tracked_get_tools(readonly_context=None):
            # Get original tools from MCP server
            tools = await original_get_tools(readonly_context)

            # Wrap each individual MCP tool's run_async for tracking
            for tool in tools:
                self._wrap_run_async(tool, tool.name, tool.description)

            return tools

        # Replace get_tools with tracked version
        toolset.get_tools = tracked_get_tools
        logger.debug("Wrapped McpToolset.get_tools() for tracking")

    def wrap_agent_tools(
        self,
        agent,
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
            # Handle McpToolset
            if isinstance(tool, McpToolset):
                if self.ryumem.config.tool_tracking.track_mcp_toolsets:
                    self._wrap_mcp_toolset(tool)
                    logger.debug(f"Wrapped McpToolset at index {i} for tracking")
                else:
                    logger.debug(f"Skipping McpToolset at index {i} (tracking disabled)")
                continue

            # Determine if this is a FunctionTool object or raw function
            is_function_tool = has_function_tool and isinstance(tool, FunctionTool)

            # Get the actual function to inspect
            func = tool.func if is_function_tool else tool

            # Extract tool name using same logic as registration:
            # For FunctionTool objects, check tool.name first (handles LangChain tools with _run)
            # This matches how registration works in google_adk.py
            if is_function_tool:
                tool_name = getattr(tool, 'name', getattr(func, '__name__', f'tool_{i}'))
            else:
                tool_name = getattr(func, '__name__', f'tool_{i}')

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

        logger.info(f"Tool tracking enabled: {wrapped_count} tools wrapped.")
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
        original_run_async = tool.run_async

        async def tracking_run_async(*, args, tool_context):
            parent_tool = _get_parent_tool()

            display_name = f"{parent_tool}.{tool_name}" if parent_tool else tool_name

            token = _set_current_tool(tool_name)

            start_time = time.time()
            success = True
            error = None
            output = None

            try:
                output = await original_run_async(args=args, tool_context=tool_context)
                return output
            except Exception as e:
                success = False
                error = str(e)
                raise
            finally:
                _clear_current_tool(token)

                duration_ms = int((time.time() - start_time) * 1000)

                user_id = None
                session_id = None

                if 'user_id' in args:
                    user_id = args.get('user_id')
                    session_id = args.get('session_id')
                else:
                    if tool_context and hasattr(self, '_memory_ref') and self._memory_ref:
                        user_id, session_id = self._memory_ref._get_user_id_from_context(tool_context)

                input_params = args

                if not user_id:
                    raise ValueError(f"tool_context.session.user_id is required but was None for tool '{tool_name}'")
                if not session_id:
                    raise ValueError(f"tool_context.session.id is required but was None for tool '{tool_name}'")

                try:
                    self.track_execution(
                        tool_name=display_name,
                        tool_description=tool_description,
                        input_params=input_params,
                        output=output,
                        success=success,
                        error=error,
                        duration_ms=duration_ms,
                        user_id=user_id,
                        session_id=session_id,
                        context=None,
                        parent_tool_name=parent_tool
                        )
                except Exception as track_error:
                    logger.error(f"Tracking failed for {display_name}: {track_error}")
                    if not self.ryumem.config.tool_tracking.ignore_errors:
                        raise

        tool.run_async = tracking_run_async


