"""
Tool Usage Tracking for Google ADK

This module provides automatic tracking of tool executions in Google ADK agents,
storing usage patterns, success rates, and task associations in the knowledge graph.

Example:
    ```python
    from google import genai
    from ryumem.integrations import enable_memory, enable_tool_tracking

    agent = genai.Agent(name="assistant", model="gemini-2.0-flash")
    memory = enable_memory(agent, ryumem_customer_id="my_company")

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
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from ryumem import Ryumem

logger = logging.getLogger(__name__)

# Shared thread pool for blocking operations
_thread_pool = ThreadPoolExecutor(max_workers=4)

# Blacklist of Ryumem memory tools to prevent circular dependencies
RYUMEM_TOOL_BLACKLIST = {
    "search_memory",
    "save_memory",
    "get_entity_context",
}


class ToolTracker:
    """
    Automatic tool usage tracker for Google ADK agents.

    Captures tool executions, classifies tasks using LLM, and stores
    everything in the knowledge graph for later analysis.

    Args:
        ryumem: Ryumem instance for storing tool usage data
        ryumem_customer_id: Customer/company identifier
        async_classification: If True, classification doesn't block tool execution
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
        async_classification: bool = True,
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
        self.async_classification = async_classification
        self.classification_model = classification_model
        self.summarize_large_outputs = summarize_large_outputs
        self.max_output_length = max_output_length
        self.max_context_messages = max_context_messages
        self.sanitize_pii = sanitize_pii
        self.exclude_params = exclude_params or ["password", "api_key", "secret", "token"]
        self.sampling_rate = sampling_rate
        self.fail_open = fail_open

        # Store background tasks to prevent garbage collection
        self._background_tasks = set()

        self._execution_count = 0

        logger.info(
            f"Initialized ToolTracker for customer: {ryumem_customer_id}, "
            f"sampling: {sampling_rate*100}%, async: {async_classification}"
        )

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

    async def _classify_task_async(
        self,
        tool_name: str,
        tool_description: str,
        input_params: Dict[str, Any],
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Use LLM to classify the task type from tool and context information.

        Returns:
            Dict with 'task_type', 'description', and 'confidence'
        """
        # Build classification prompt
        prompt = f"""Analyze this tool execution and classify the task type.

Tool Name: {tool_name}
Tool Description: {tool_description or 'No description provided'}
Input Parameters: {json.dumps(input_params, indent=2)}

Recent Conversation Context:
{context or 'No context available'}

Based on this information, classify the task into one of these categories:
- information_retrieval (searching, fetching data)
- data_transformation (processing, converting, formatting)
- calculation (mathematical, statistical operations)
- external_api (calling external services)
- file_operation (reading, writing files)
- database_operation (queries, updates)
- communication (sending messages, emails)
- automation (scheduled tasks, workflows)
- analysis (data analysis, insights)
- other (specify)

Respond with ONLY a JSON object in this format:
{{
    "task_type": "category_name",
    "description": "brief description of what this tool execution accomplishes",
    "confidence": 0.0-1.0
}}"""

        try:
            print(f"[CLASSIFY] Starting classification for {tool_name}")
            # Use Ryumem's LLM client for classification
            # Format as messages array for OpenAI API
            messages = [
                {"role": "user", "content": prompt}
            ]

            print(f"[CLASSIFY] Calling LLM for {tool_name}")
            # We're in a background task - just call it directly
            # The task itself is async, so this won't block the main event loop
            response = self.ryumem.llm_client.generate(
                messages,
                temperature=0.3,
                max_tokens=200,
            )
            print(f"[CLASSIFY] LLM responded for {tool_name}")

            # Parse JSON response from content
            content = response.get("content", "")
            print(f"[CLASSIFY] Parsing JSON response for {tool_name}: {content[:100]}")
            result = json.loads(content.strip())

            print(f"[CLASSIFY] ✅ Classification complete for {tool_name}: {result.get('task_type')}")
            return {
                "task_type": result.get("task_type", "unknown"),
                "description": result.get("description", ""),
                "confidence": result.get("confidence", 0.0),
            }

        except Exception as e:
            print(f"[CLASSIFY ERROR] Task classification failed for {tool_name}: {e}")
            logger.error(f"Task classification failed: {e}")
            return {
                "task_type": "unknown",
                "description": f"Classification failed: {str(e)}",
                "confidence": 0.0,
            }

    def _classify_task_sync(
        self,
        tool_name: str,
        tool_description: str,
        input_params: Dict[str, Any],
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Synchronous wrapper for task classification."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self._classify_task_async(tool_name, tool_description, input_params, context)
            )
        finally:
            loop.close()

    def _create_tool_entities(
        self,
        tool_name: str,
        tool_description: Optional[str],
        task_type: str,
        task_description: str,
        success: bool,
        duration_ms: int,
    ) -> None:
        """
        Directly create TOOL and TASK_TYPE entities in the knowledge graph.

        This bypasses LLM-based entity extraction and creates structured entities
        from tool tracking metadata.

        Args:
            tool_name: Name of the tool
            tool_description: Tool's docstring/description
            task_type: Classified task type
            task_description: Description of the task
            success: Whether execution succeeded
            duration_ms: Execution duration
        """
        from uuid import uuid4
        from ryumem.core.models import EntityNode

        try:
            print(f"[ENTITY] Creating TOOL entity for {tool_name}")
            # Create or update TOOL entity
            print(f"[ENTITY] Getting embedding for {tool_name}")
            tool_embedding = self.ryumem.embedding_client.embed(tool_name)
            print(f"[ENTITY] Got embedding for {tool_name}")

            # Search for existing tool entity
            print(f"[ENTITY] Searching for existing TOOL entity")
            similar_tools = self.ryumem.db.search_similar_entities(
                embedding=tool_embedding,
                group_id=self.ryumem_customer_id,
                threshold=0.9,  # High threshold for exact tool match
                limit=1,
            )
            print(f"[ENTITY] Search complete, found {len(similar_tools)} similar tools")

            if similar_tools:
                # Update existing tool entity (increment mentions)
                tool_entity = similar_tools[0]
                tool_uuid = tool_entity["uuid"]
                tool_mentions = tool_entity.get("mentions", 0) + 1

                logger.debug(f"Updating existing TOOL entity: {tool_name} (mentions: {tool_mentions})")
            else:
                # Create new TOOL entity
                tool_uuid = str(uuid4())
                tool_mentions = 1

                logger.debug(f"Creating new TOOL entity: {tool_name}")

            # Save/update tool entity
            # Note: Omit user_id entirely for group-level entities instead of None
            tool_entity_node = EntityNode(
                uuid=tool_uuid,
                name=tool_name,
                entity_type="TOOL",
                summary=tool_description or f"Tool: {tool_name}",
                name_embedding=tool_embedding,
                mentions=tool_mentions,
                group_id=self.ryumem_customer_id,
            )
            self.ryumem.db.save_entity(tool_entity_node)

            # Create or update TASK_TYPE entity
            task_embedding = self.ryumem.embedding_client.embed(task_type)

            similar_tasks = self.ryumem.db.search_similar_entities(
                embedding=task_embedding,
                group_id=self.ryumem_customer_id,
                threshold=0.9,
                limit=1,
            )

            if similar_tasks:
                # Update existing task type entity
                task_entity = similar_tasks[0]
                task_uuid = task_entity["uuid"]
                task_mentions = task_entity.get("mentions", 0) + 1

                logger.debug(f"Updating existing TASK_TYPE entity: {task_type} (mentions: {task_mentions})")
            else:
                # Create new TASK_TYPE entity
                task_uuid = str(uuid4())
                task_mentions = 1

                logger.debug(f"Creating new TASK_TYPE entity: {task_type}")

            # Save/update task type entity
            # Note: Omit user_id entirely for group-level entities instead of None
            task_entity_node = EntityNode(
                uuid=task_uuid,
                name=task_type,
                entity_type="TASK_TYPE",
                summary=task_description or f"Task type: {task_type}",
                name_embedding=task_embedding,
                mentions=task_mentions,
                group_id=self.ryumem_customer_id,
            )
            self.ryumem.db.save_entity(task_entity_node)

            # Create relationship: TOOL -[USED_FOR]-> TASK_TYPE
            from ryumem.core.models import EntityEdge

            relationship_metadata = {
                "success": success,
                "duration_ms": duration_ms,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Create EntityEdge for the USED_FOR relationship
            edge = EntityEdge(
                uuid=str(uuid4()),
                source_node_uuid=tool_uuid,
                target_node_uuid=task_uuid,
                name="USED_FOR",
                fact=f"{tool_name} is used for {task_type}",
                fact_embedding=self.ryumem.embedding_client.embed(f"{tool_name} used for {task_type}"),
                episodes=[],
                mentions=1,
                group_id=self.ryumem_customer_id,
                attributes=relationship_metadata,
            )

            self.ryumem.db.save_entity_edge(
                edge=edge,
                source_uuid=tool_uuid,
                target_uuid=task_uuid,
            )

            logger.debug(
                f"Created entities and relationship: {tool_name} -[USED_FOR]-> {task_type}"
            )

        except Exception as e:
            logger.error(f"Failed to create tool entities: {e}")
            # Don't fail the tracking if entity creation fails
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
        """Store tool execution as an episode in the knowledge graph."""
        try:
            print(f"[STORE] Starting async storage for {tool_name}")
            # Classify task type
            print(f"[STORE] Classifying task for {tool_name}")
            classification = await self._classify_task_async(
                tool_name, tool_description, input_params, context
            )
            print(f"[STORE] Classified {tool_name} as: {classification['task_type']}")

            # Sanitize and summarize data
            sanitized_params = self._sanitize_params(input_params)
            output_summary = self._summarize_output(output) if success else None

            # Build episode content
            content = (
                f"Tool execution: {tool_name} for {classification['task_type']}. "
                f"{classification['description']}"
            )

            # Build metadata
            metadata = {
                "tool_name": tool_name,
                "tool_description": tool_description,
                "task_type": classification["task_type"],
                "task_description": classification["description"],
                "task_confidence": classification["confidence"],
                "input_params": sanitized_params,
                "output_summary": output_summary,
                "success": success,
                "error": error,
                "duration_ms": duration_ms,
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": user_id,
                "session_id": session_id,
            }

            # Store as episode (use 'json' source since we have structured metadata)
            print(f"[STORE] Storing episode for {tool_name}")
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                _thread_pool,
                lambda: self.ryumem.add_episode(
                    content=content,
                    group_id=self.ryumem_customer_id,
                    user_id=user_id,
                    source="json",
                    metadata=metadata,
                )
            )
            print(f"[STORE] Episode stored for {tool_name}")

            # Create TOOL and TASK_TYPE entities directly
            print(f"[STORE] Creating entities for {tool_name}")
            await loop.run_in_executor(
                _thread_pool,
                lambda: self._create_tool_entities(
                    tool_name=tool_name,
                    tool_description=tool_description,
                    task_type=classification["task_type"],
                    task_description=classification["description"],
                    success=success,
                    duration_ms=duration_ms,
                )
            )
            print(f"[STORE] Entities created for {tool_name}")

            logger.info(
                f"Tracked tool execution: {tool_name} ({classification['task_type']}) "
                f"- {'success' if success else 'failure'} in {duration_ms}ms"
            )
            print(f"[STORE] ✅ Successfully stored tracking data for {tool_name}")

        except Exception as e:
            print(f"[STORE ERROR] Failed to store {tool_name}: {e}")
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
            print(f"[TRACK] {tool_name} run_async called with args: {args}")
            start_time = time.time()
            success = True
            error = None
            output = None

            try:
                # Call original run_async
                output = await original_run_async(args=args, tool_context=tool_context)
                print(f"[TRACK] {tool_name} completed successfully")
                return output
            except Exception as e:
                success = False
                error = str(e)
                print(f"[TRACK] {tool_name} failed with error: {e}")
                raise
            finally:
                duration_ms = int((time.time() - start_time) * 1000)

                # Extract user_id and session_id if available in tool_context
                user_id = getattr(tool_context, 'user_id', None)
                session_id = getattr(tool_context, 'session_id', None)

                print(f"[TRACK] Calling track_execution for {tool_name}")
                # We're already in an async context, so create a background task directly
                try:
                    # Create background task for storage (don't await - fire and forget)
                    task = asyncio.create_task(
                        self._store_tool_execution_async(
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
                    )
                    # Keep reference to prevent garbage collection
                    self._background_tasks.add(task)
                    task.add_done_callback(self._background_tasks.discard)
                    print(f"[TRACK] Background task created for {tool_name}")
                except Exception as track_error:
                    print(f"[TRACK ERROR] Tracking failed for {tool_name}: {track_error}")
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

    DEPRECATED: Use enable_memory(..., track_tools=True) instead for simpler API.

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
        from ryumem.integrations import enable_memory, enable_tool_tracking

        agent = genai.Agent(name="assistant", model="gemini-2.0-flash")
        memory = enable_memory(agent, ryumem_customer_id="my_company")

        # Old way (still works but deprecated)
        tracker = enable_tool_tracking(
            agent,
            ryumem=memory.ryumem,
            sampling_rate=0.1,
            async_classification=True
        )
        ```

    Recommended (NEW):
        ```python
        from ryumem.integrations import enable_memory

        # New simpler way - one function call!
        memory = enable_memory(
            agent,
            ryumem_customer_id="my_company",
            track_tools=True,
            sampling_rate=0.1,
            async_classification=True
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
