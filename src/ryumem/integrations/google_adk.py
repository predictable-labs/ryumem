"""
Google ADK Integration for Ryumem.

This module provides zero-boilerplate memory integration with Google's Agent Developer Kit.

Example - Basic Memory:
    ```python
    from google import genai
    from ryumem import Ryumem
    from ryumem.integrations import add_memory_to_agent

    ryumem = Ryumem()
    agent = genai.Agent(model="gemini-2.0-flash")

    # Add memory capabilities (modifies agent in-place)
    agent = add_memory_to_agent(agent, ryumem)

    # Agent now has search_memory and save_memory tools
    ```

Example - With Query Tracking:
    ```python
    from google import genai
    from ryumem import Ryumem
    from ryumem.integrations import add_memory_to_agent, wrap_runner_with_tracking

    ryumem = Ryumem()
    agent = genai.Agent(model="gemini-2.0-flash")
    agent = add_memory_to_agent(agent, ryumem)

    runner = genai.Runner(agent=agent)
    runner = wrap_runner_with_tracking(runner, agent)

    # Runner now tracks queries and augments them with history
    ```
"""

import datetime
import json
import logging
import uuid as uuid_module
from typing import Optional, Dict, Any, List

from google.adk.tools.tool_context import ToolContext
from google.genai import types
from ryumem import EpisodeType, Ryumem, RyumemConfig
from ryumem.core.metadata_models import EpisodeMetadata, QueryRun, ToolExecution

from .tool_tracker import ToolTracker

logger = logging.getLogger(__name__)


# ===== Default Prompt Blocks =====

DEFAULT_MEMORY_BLOCK = """MEMORY USAGE:
Use search_memory to find relevant context before answering questions.
Use save_memory to store important information for future reference.
"""

DEFAULT_TOOL_BLOCK = """TOOL SELECTION:
Before selecting which tool to use, search_memory for past tool usage patterns and success rates.
Use queries like "tool execution for [task type]" to find which tools worked well for similar tasks.
"""

DEFAULT_AUGMENTATION_TEMPLATE = """[Previous Attempt Summary]

Your previous approach was:
{agent_response}

Tools previously used:
{simplified_tool_summary}

Last Session Details:
{last_session}

Using this memory, improve your next attempt.

***IMPORTANT — REQUIRED BEHAVIOR***
You MUST reuse any **concrete facts, results, conclusions, or discovered information** from the previous attempt if they are relevant.
Do NOT ignore previously known truths.
Treat the previous attempt as authoritative memory, not optional context.

In your response, briefly include:
1. What you learned last time (1-2 bullets).
2. What you will change or improve (1-2 bullets).
3. Then continue with your improved reasoning (explicitly applying relevant past information).

IMPORTANT:
If the previous attempt already contains the correct final answer, or fully solves the task, you MUST NOT re-solve it.
Instead, directly use or return the final answer from memory.

Using this information, answer the query: {query_text}
"""


class RyumemGoogleADK:
    """
    Auto-generates memory tools for Google ADK agents.

    This class creates search and save functions that are automatically
    registered as tools with Google ADK agents, eliminating boilerplate code.

    All configuration is read from the ryumem instance's config.

    Args:
        agent: Google ADK Agent instance
        ryumem: Initialized Ryumem instance (contains config and custom_tool_summary_fn)
    """

    def __init__(
        self,
        agent: Any,
        ryumem: Ryumem
    ):
        self.agent = agent
        self.ryumem = ryumem
        # Store per-session user_id overrides
        self._session_user_overrides: Dict[str, str] = {}

        logger.info(f"Initialized RyumemGoogleADK extract_entities: {ryumem.config.entity_extraction.enabled}")

    def set_session_user_override(self, session_id: str, user_id_override: str) -> None:
        """
        Override the user_id for a specific session.

        All subsequent tool calls in this session will use the override user_id
        instead of the one from tool_context.session.user_id.

        Args:
            session_id: The session ID to override
            user_id_override: The user_id to use for this session
        """
        self._session_user_overrides[session_id] = user_id_override
        logger.info(f"Set user_id override for session {session_id[:8]}: {user_id_override}")

    def clear_session_user_override(self, session_id: str) -> None:
        """
        Clear the user_id override for a session.

        Args:
            session_id: The session ID to clear override for
        """
        if session_id in self._session_user_overrides:
            del self._session_user_overrides[session_id]
            logger.info(f"Cleared user_id override for session {session_id[:8]}")

    def get_session_user_override(self, session_id: str) -> Optional[str]:
        """
        Get the user_id override for a session, if any.

        Args:
            session_id: The session ID to check

        Returns:
            The override user_id, or None if no override is set
        """
        return self._session_user_overrides.get(session_id)

    def _get_user_id_from_context(self, tool_context: ToolContext) -> tuple[Optional[str], Optional[str]]:
        """
        Extract user_id and session_id from tool context, applying any overrides.

        Args:
            tool_context: Google ADK tool context containing session info

        Returns:
            Tuple of (user_id, session_id)
        """
        if not hasattr(tool_context, 'session') or not tool_context.session:
            return None, None

        session = tool_context.session
        session_id = getattr(session, 'id', None)

        # Check for session-specific user_id override
        if session_id and session_id in self._session_user_overrides:
            user_id = self._session_user_overrides[session_id]
            logger.debug(f"Using user_id override for session {session_id[:8]}: {user_id}")
        else:
            user_id = getattr(session, 'user_id', None)

        return user_id, session_id

    async def search_memory(self, tool_context: ToolContext, query: str, limit: int = 5) -> Dict[str, Any]:
        """
        This function is automatically registered as a tool with the agent.

        Args:
            tool_context: Google ADK tool context containing session info
            query: Natural language query to search memories
            limit: Maximum number of memories to return (default: 5)

        Returns:
            Dict with status and memories or no_memories indicator
        """
        # Extract session info from tool_context (with override support)
        user_id, session_id = self._get_user_id_from_context(tool_context)

        if not user_id or not session_id:
            return {
                "status": "error",
                "message": "user_id and session_id are required in session context"
            }

        logger.info(f"Searching memory for user '{user_id}' session '{session_id}': {query}")

        try:
            results = self.ryumem.search(
                query=query,
                user_id=user_id,
                session_id=session_id,
                strategy="hybrid",
                limit=limit,
                kinds=['memory'],  # Only search memory episodes
                min_bm25_score=0.001,  # Very low threshold for BM25 #TODO Use config
                min_rrf_score=0.0  # Disable RRF filtering #TODO Use config
            )

            # Collect all results: edges (facts), episodes (content), and entities
            memories = []
            episodes_list = []
            entities_list = []

            # Add edges as memories (facts/relationships)
            if results.edges:
                memories = [
                    {
                        "fact": edge.fact,
                        "score": results.scores.get(edge.uuid, 0.0),
                        "source_uuid": edge.source_node_uuid,
                        "target_uuid": edge.target_node_uuid
                    }
                    for edge in results.edges
                ]

            # Add episodes (content)
            if results.episodes:
                episodes_list = [
                    {
                        "content": episode.content,
                        "score": results.scores.get(episode.uuid, 0.0),
                        "uuid": episode.uuid,
                        "created_at": str(episode.created_at)
                    }
                    for episode in results.episodes
                ]

            # Add entities
            if results.entities:
                entities_list = [
                    {
                        "name": entity.name,
                        "type": entity.entity_type,
                        "score": results.scores.get(entity.uuid, 0.0),
                        "uuid": entity.uuid
                    }
                    for entity in results.entities
                ]

            # Return results if we found anything
            if memories or episodes_list or entities_list:
                logger.info(f"Found {len(memories)} memories, {len(episodes_list)} episodes, {len(entities_list)} entities for user '{user_id}'")
                return {
                    "status": "success",
                    "count": len(memories) + len(episodes_list) + len(entities_list),
                    "memories": memories,
                    "episodes": episodes_list,
                    "entities": entities_list
                }
            else:
                logger.info(f"No memories found for user '{user_id}'")
                return {
                    "status": "no_memories",
                    "message": "No relevant memories found for this query"
                }

        except Exception as e:
            logger.error(f"Error searching memory: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def save_memory(self, tool_context: ToolContext, content: str, source: str = "text") -> Dict[str, Any]:
        """
        Auto-generated save function for persisting memories.

        This function is automatically registered as a tool with the agent.

        Args:
            tool_context: Google ADK tool context containing session info
            content: Information to save to memory
            source: Episode type - must be "text", "message", or "json" (default: "text")

        Returns:
            Dict with status and episode_id
        """
        # Extract session info from tool_context (with override support)
        user_id, session_id = self._get_user_id_from_context(tool_context)

        if not user_id or not session_id:
            return {
                "status": "error",
                "message": "user_id and session_id are required in session context"
            }

        logger.info(f"Saving memory for user '{user_id}' session '{session_id}': {content[:50]}...")

        try:
            # Validate source
            valid_sources = ["text", "message", "json"]
            if source not in valid_sources:
                source = "text"

            # Create separate memory episode with kind='memory'
            episode_id = self.ryumem.add_episode(
                content=content,
                user_id=user_id,
                session_id=session_id,
                source=source,
                kind='memory',  # NEW: Mark as memory episode
            )

            logger.info(f"Saved memory episode for user '{user_id}' with episode_id: {episode_id}")

            return {
                "status": "success",
                "episode_id": episode_id,
                "message": "Memory saved successfully"
            }
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def get_entity_context(self, tool_context: ToolContext, entity_name: str) -> Dict[str, Any]:
        """
        Auto-generated function to get full context about an entity.

        Args:
            entity_name: Name of the entity to look up
            tool_context: Google ADK tool context containing session info

        Returns:
            Dict with entity information and related facts
        """
        # Extract session info from tool_context (with override support)
        user_id, session_id = self._get_user_id_from_context(tool_context)

        if not user_id or not session_id:
            return {
                "status": "error",
                "message": "user_id and session_id are required in session context"
            }

        logger.info(f"Getting context for entity '{entity_name}' for user '{user_id}'")

        try:
            context = self.ryumem.get_entity_context(
                entity_name=entity_name,
                user_id=user_id,
                session_id=session_id
            )

            if context:
                return {
                    "status": "success",
                    "entity": entity_name,
                    "context": context
                }
            else:
                return {
                    "status": "not_found",
                    "message": f"Entity '{entity_name}' not found in memory"
                }
        except Exception as e:
            logger.error(f"Error getting entity context: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    @property
    def tools(self) -> List:
        """
        Returns list of auto-generated tool functions.

        These can be directly passed to Google ADK Agent's tools parameter.
        """

        tools = []
        if self.ryumem.config.agent.memory_enabled:
            tools.append(self.search_memory)
            tools.append(self.save_memory)

        if self.ryumem.config.entity_extraction.enabled:
            tools.append(self.get_entity_context)

        return tools

def add_memory_to_agent(
    agent,
    ryumem_instance: Ryumem,
):
    """
    Add Ryumem memory capabilities to a Google ADK agent.

    Modifies the agent in-place by:
    - Adding search_memory and save_memory tools
    - Enhancing instructions with memory usage guidance
    - Storing RyumemGoogleADK interface as agent._ryumem_memory

    All configuration comes from the Ryumem instance's config.

    Args:
        agent: Google ADK Agent to enhance
        ryumem_instance: Ryumem instance (contains all config)

    Returns:
        The same agent object (for chaining)

    Example:
        ryumem = Ryumem()  # Config from env/database
        agent = genai.Agent(model="gemini-2.0-flash")
        agent = add_memory_to_agent(agent, ryumem)
    """
    # Initialize Tool Tracker if enabled
    tool_tracker = None
    if ryumem_instance.config.tool_tracking.track_tools:
        try:
            tool_tracker = ToolTracker(ryumem=ryumem_instance)

            # Only wrap tools if not already wrapped (check if instruction was already enhanced)
            current_instruction = agent.instruction or ""
            already_enhanced = DEFAULT_TOOL_BLOCK in current_instruction

            if not already_enhanced and hasattr(agent, 'tools') and agent.tools:
                tool_tracker.wrap_agent_tools(agent)
                logger.info(f"Tool tracking enabled for agent: {agent.name if hasattr(agent, 'name') else 'unnamed'}")

        except Exception as e:
            logger.error(f"Failed to initialize tool tracking: {e}")
            if not ryumem_instance.config.tool_tracking.ignore_errors:
                raise

    # Create memory integration
    memory = RyumemGoogleADK(
        agent=agent,
        ryumem=ryumem_instance
    )

    # Store memory reference in tool_tracker for override support
    if tool_tracker:
        tool_tracker._memory_ref = memory

    # 5. Auto-inject tools into agent
    if not hasattr(agent, 'tools'):
        agent.tools = []
        logger.warning("Agent doesn't have 'tools' attribute, creating new list")

    # Remove existing memory tools to prevent duplicates
    # Get tool names from the new memory instance
    new_memory_tool_names = {getattr(tool, '__name__', None) for tool in memory.tools}
    agent.tools = [
        tool for tool in agent.tools
        if getattr(tool, '__name__', None) not in new_memory_tool_names
    ]

    # Collect existing tools before adding memory tools
    existing_tools = list(agent.tools) if hasattr(agent, 'tools') else []

    # Add memory tools
    agent.tools.extend(memory.tools)
    logger.info(f"Added {len(memory.tools)} memory tools to agent")

    # Register ALL tools (existing + memory) in ONE call
    # register_tools() will skip any that already exist in database
    if tool_tracker:
        try:
            all_tools = existing_tools + memory.tools
            tools_to_register = [
                {
                    'name': getattr(tool, 'name', getattr(tool, '__name__', 'unknown')),
                    'description': getattr(tool, 'description', getattr(tool, '__doc__', '')) or f"Tool: {getattr(tool, 'name', 'unknown')}"
                }
                for tool in all_tools
            ]
            if tools_to_register:
                tool_tracker.register_tools(tools_to_register)
                logger.info(f"Registered {len(tools_to_register)} tools in database (skips duplicates)")
        except Exception as e:
            logger.error(f"Failed to register tools: {e}")
            if not ryumem_instance.config.tool_tracking.ignore_errors:
                raise

    # Resolve and enhance instruction using server-side logic
    # The server handles all enhancement and will check if there's an updated instruction in the DB
    current_instruction = agent.instruction or ""
    try:
        resolved = ryumem_instance.list_agent_instructions(
            agent_type="google_adk",
            current_instruction=current_instruction,
            limit=1
        )

        if resolved:
            # Use enhanced instruction and query template from server
            base_instruction = resolved[0].get("base_instruction", current_instruction)
            enhanced_instruction = resolved[0].get("enhanced_instruction", base_instruction)
            query_augmentation_template = resolved[0].get("query_augmentation_template", "")
            agent.instruction = enhanced_instruction
            logger.info(f"Resolved instruction from server: {base_instruction[:50]}...")
        else:
            # Fallback - should not happen if server is working
            base_instruction = current_instruction
            enhanced_instruction = current_instruction
            query_augmentation_template = ""
            logger.warning("Server returned no instructions, using current instruction as fallback")
    except Exception as e:
        # Fallback on error
        logger.error(f"Failed to resolve instruction from server: {e}")
        base_instruction = current_instruction
        enhanced_instruction = current_instruction
        query_augmentation_template = ""

    # Store augmentation prompt from server
    memory._augmentation_prompt = query_augmentation_template

    # Store memory interface on agent and return agent (builder pattern)
    agent._ryumem_memory = memory

    return agent


def _find_similar_query_episodes(
    query_text: str,
    memory: RyumemGoogleADK,
    user_id: str,
    session_id: str,
) -> List[Dict[str, Any]]:
    """Find and filter similar query episodes above threshold."""
    threshold = memory.ryumem.config.tool_tracking.similarity_threshold
    logger.info(f"Searching with strategy={memory.ryumem.config.tool_tracking.similarity_strategy}, threshold={threshold}")

    # Check for session user override - use override user_id if set
    effective_user_id = memory.get_session_user_override(session_id) or user_id
    if effective_user_id != user_id:
        logger.info(f"Using session override user_id: {effective_user_id} (original: {user_id})")

    # Search across ALL sessions for this user (not just current session)
    # This allows learning from past game sessions
    search_results = memory.ryumem.search(
        query=query_text,
        user_id=effective_user_id,
        session_id=None,  # Don't filter by session - search across all user's past queries
        strategy=memory.ryumem.config.tool_tracking.similarity_strategy,
        similarity_threshold=memory.ryumem.config.tool_tracking.similarity_threshold,
        limit=memory.ryumem.config.tool_tracking.top_k_similar,
        min_rrf_score=0.0  # Disable RRF filtering - rely on similarity_threshold instead
    )

    if not search_results.episodes:
        logger.info("Search returned 0 episodes - no past queries exist yet")
        return []

    logger.info(f"Search returned {len(search_results.episodes)} episodes for query: '{query_text[:50]}...'")

    similar_queries = []
    for episode in search_results.episodes:
        score = search_results.scores.get(episode.uuid, 0.0)

        # Exact match handling
        if score == 0.0 and episode.content == query_text:
            score = 1.0

        # Filter by threshold and source type
        if score >= memory.ryumem.config.tool_tracking.similarity_threshold and episode.source == EpisodeType.message:
            similar_queries.append({
                "content": episode.content,
                "score": score,
                "uuid": episode.uuid,
                "metadata": episode.metadata,
            })

    logger.info(f"Found {len(similar_queries)} similar queries above threshold {memory.ryumem.config.tool_tracking.similarity_threshold}")
    return similar_queries

def _get_last_session_details(similar_queries: List[Dict[str, Any]]) -> str:
    """Extract details from the most recent session across all similar queries."""

    most_recent_session = None
    most_recent_timestamp = None
    most_recent_session_id = None

    # Find the most recent session across all similar queries
    for similar in similar_queries:
        query_metadata = similar.get("metadata")

        try:
            if not query_metadata:
                continue

            metadata_dict = json.loads(query_metadata) if isinstance(query_metadata, str) else query_metadata
            episode_metadata = EpisodeMetadata(**metadata_dict)

            # Check all sessions in this episode
            for session_id, runs in episode_metadata.sessions.items():
                if not runs:
                    continue

                # Get the latest timestamp from this session
                latest_run = max(runs, key=lambda r: r.timestamp)
                session_timestamp = datetime.datetime.fromisoformat(latest_run.timestamp)

                if most_recent_timestamp is None or session_timestamp > most_recent_timestamp:
                    most_recent_timestamp = session_timestamp
                    most_recent_session = runs
                    most_recent_session_id = session_id

        except Exception as e:
            logger.warning(f"Failed to parse session metadata: {e}")
            continue

    # Format the most recent session details
    if not most_recent_session:
        return "No previous session found"

    session_details = []
    session_details.append(f"Session ID: {most_recent_session_id}")
    session_details.append(f"\nRuns in this session: {len(most_recent_session)}")

    for idx, run in enumerate(most_recent_session, 1):
        session_details.append(f"\n--- Run {idx} ---")
        session_details.append(f"Timestamp: {run.timestamp}")
        session_details.append(f"Query: {run.query}")

        if run.augmented_query:
            session_details.append(f"Augmented Query: {run.augmented_query[:200]}...")

        if run.agent_response:
            session_details.append(f"Agent Response: {run.agent_response}")

        if run.tools_used:
            session_details.append(f"Tools Used ({len(run.tools_used)}):")
            for tool in run.tools_used:
                tool_info = f"  - {tool.tool_name}"
                if tool.input_params:
                    params_str = ', '.join([f"{k}={v}" for k, v in tool.input_params.items()])
                    tool_info += f" with [{params_str}]"
                if tool.output_summary:
                    tool_info += f" -> {tool.output_summary[:100]}"
                if tool.error:
                    tool_info += f" [ERROR: {tool.error}]"
                tool_info += f" (success: {tool.success}, duration: {tool.duration_ms}ms)"
                session_details.append(tool_info)

    return '\n'.join(session_details)


def _build_context_section(query_text: str, similar_queries: List[Dict[str, Any]], memory: RyumemGoogleADK, top_k: int) -> str:
    """Build historical context string from similar queries and their tool executions."""

    # Use locally stored augmentation prompt
    augmentation_template = memory._augmentation_prompt

    for idx, similar in enumerate(similar_queries[:top_k if top_k > 0 else len(similar_queries)], 1):
        query_metadata = similar.get("metadata")

        try:
            if not query_metadata:
                continue

            metadata_dict = json.loads(query_metadata) if isinstance(query_metadata, str) else query_metadata
            episode_metadata = EpisodeMetadata(**metadata_dict)

            # Get agent response
            agent_response = None
            for runs in episode_metadata.sessions.values():
                for run in runs:
                    if run.agent_response:
                        agent_response = run.agent_response
                        break
                if agent_response:
                    break

            # Get tool summary
            tool_summary = episode_metadata.get_tool_usage_summary()
            simplified_tool_summary = episode_metadata.get_simple_tool_usage_summary()

            # Build custom tool summary if function provided
            custom_tool_summary = "No tools used"
            if memory.ryumem.custom_tool_summary_fn:
                all_tools = episode_metadata.get_all_tools_used()
                if all_tools:
                    tool_summaries = [memory.ryumem.custom_tool_summary_fn(tool) for tool in all_tools]
                    custom_tool_summary = ', '.join(tool_summaries)

            # Get last session details
            last_session = _get_last_session_details(similar_queries)

            # Fill template
            return augmentation_template.format(
                agent_response=agent_response or "No previous response recorded",
                tool_summary=tool_summary or "No tools used",
                simplified_tool_summary=simplified_tool_summary or "No tools used",
                custom_tool_summary=custom_tool_summary,
                last_session=last_session,
                query_text=query_text
            )

        except Exception as e:
            logger.warning(f"Failed to parse query metadata: {e}")
            continue

    return ""


def _augment_query_with_history(
    query_text: str,
    memory: RyumemGoogleADK,
    user_id: str,
    session_id: str,
) -> str:
    """
    Augment an incoming query with historical context from similar past queries.

    Searches for similar query episodes, retrieves their linked tool executions,
    and appends a summary of tool usage patterns to the query.

    Args:
        query_text: The incoming user query
        memory: RyumemGoogleADK instance with access to Ryumem
        user_id: User identifier for scoped search
        session_id: Session identifier (required)
        similarity_threshold: Minimum similarity score (0.0-1.0)
        top_k: Number of similar queries to consider (-1 for all)

    Returns:
        Augmented query with historical context appended
    """
    try:
        logger.info(f"Searching for similar queries to: {query_text[:50]}...")
        similar_queries = _find_similar_query_episodes(
            query_text, memory, user_id, session_id
        )

        if not similar_queries:
            logger.info("No similar queries found for augmentation")
            return query_text

        logger.info(f"Found {len(similar_queries)} similar queries")
        top_k = memory.ryumem.config.tool_tracking.top_k_similar
        augmented_query = _build_context_section(query_text, similar_queries, memory, top_k)
        logger.info(f"Augmented query: {augmented_query}")

        if augmented_query and augmented_query != query_text:
            logger.info(f"Augmented query with {len(similar_queries)} similar queries")
            return augmented_query
        else:
            logger.info("Context section was empty or unchanged")
            return query_text

    except Exception as e:
        logger.error(f"Query augmentation failed: {e}", exc_info=True)
        return query_text


def _extract_query_text(new_message) -> Optional[str]:
    """Extract query text from Google ADK message."""
    if not new_message or not hasattr(new_message, 'parts'):
        return None

    query_text = ' '.join([
        p.text for p in new_message.parts
        if hasattr(p, 'text') and p.text
    ])

    return query_text if query_text else None


def _insert_run_information_in_episode(
    query_episode_id: str,
    run_id: str,
    session_id: str,
    query_run: QueryRun,
    memory: RyumemGoogleADK
):
    """Check for duplicate episodes and append run if needed."""

    existing_episode = memory.ryumem.get_episode_by_uuid(query_episode_id)

    if not existing_episode:
        return

    metadata_str = existing_episode.get('metadata', '{}')
    metadata_dict = json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str

    # Parse into Pydantic model
    episode_metadata = EpisodeMetadata(**metadata_dict)

    # Check if this session already has runs
    if session_id in episode_metadata.sessions:
        existing_runs = episode_metadata.sessions[session_id]
        if existing_runs and existing_runs[-1].run_id != run_id:
            logger.info(f"Duplicate query detected - appending run to session {session_id[:8]} in episode {query_episode_id[:8]}")
            episode_metadata.add_query_run(session_id, query_run)
            memory.ryumem.update_episode_metadata(query_episode_id, episode_metadata.model_dump())
            logger.info(f"Episode {query_episode_id[:8]} session {session_id[:8]} now has {len(episode_metadata.sessions[session_id])} runs")
    else:
        # New session - add it to the episode
        logger.info(f"Linking new session {session_id[:8]} to existing episode {query_episode_id[:8]}")
        episode_metadata.add_query_run(session_id, query_run)
        memory.ryumem.update_episode_metadata(query_episode_id, episode_metadata.model_dump())
        logger.info(f"Episode {query_episode_id[:8]} now has session {session_id[:8]} with 1 run")


def _create_query_episode(
    query_text: str,
    user_id: str,
    session_id: str,
    run_id: str,
    augmented_query_text: str,
    memory: RyumemGoogleADK
) -> str:
    """Create episode for user query with metadata."""

    # Check for session user override - use override user_id if set
    effective_user_id = memory.get_session_user_override(session_id) or user_id
    if effective_user_id != user_id:
        logger.info(f"Creating episode with session override user_id: {effective_user_id} (original: {user_id})")

    # Create query run using Pydantic model
    query_run = QueryRun(
        run_id=run_id,
        user_id=effective_user_id,
        timestamp=datetime.datetime.utcnow().isoformat(),
        query=query_text,
        augmented_query=augmented_query_text if augmented_query_text != query_text else None,
        agent_response="",
        tools_used=[]
    )

    # Create episode metadata with sessions map
    episode_metadata = EpisodeMetadata(integration="google_adk")
    episode_metadata.add_query_run(session_id, query_run)

    query_episode_id = memory.ryumem.add_episode(
        content=query_text,
        user_id=effective_user_id,
        session_id=session_id,
        source="message",
        metadata=episode_metadata.model_dump(),
        extract_entities=memory.ryumem.config.entity_extraction.enabled
    )

    _insert_run_information_in_episode(query_episode_id, run_id, session_id, query_run, memory)
    logger.info(f"Created query episode: {query_episode_id} for user: {effective_user_id}, session: {session_id}")

    return query_episode_id


def _prepare_query_and_episode(
    new_message,
    user_id: str,
    session_id: str,
    memory: RyumemGoogleADK,
    original_runner
):
    """
    Helper function to extract query text, augment it, and create an episode.

    This is shared between sync and async wrappers to avoid code duplication.

    Args:
        new_message: The incoming message content
        user_id: User identifier
        session_id: Session identifier
        memory: RyumemGoogleADK instance
        original_runner: The runner instance for storing context

    Returns:
        Tuple of (original_query_text, augmented_message, query_episode_id, run_id)
        Returns (None, new_message, None, None) if no query text found
    """
    # Extract query text
    query_text = _extract_query_text(new_message)
    if not query_text:
        return None, new_message, None, None

    original_query_text = query_text
    augmented_message = new_message

    # Augment query with historical context if enabled
    augment_enabled = memory.ryumem.config.tool_tracking.augment_queries
    logger.info(f"Query augmentation enabled: {augment_enabled}")

    if augment_enabled:
        logger.info(f"Attempting to augment query: {query_text[:50]}...")
        augmented_query_text = _augment_query_with_history(
            query_text, memory, user_id, session_id
        )

        # Update message if context was added (query text might be same but context added)
        if augmented_query_text != original_query_text:
            logger.info(f"Query augmented (+{len(augmented_query_text) - len(original_query_text)} chars)")
            augmented_message = types.Content(
                role='user',
                parts=[types.Part(text=augmented_query_text)]
            )
        else:
            logger.debug("Query text unchanged after augmentation attempt")
            # Query text unchanged, but make sure to use it in message anyway
            augmented_query_text = original_query_text
    else:
        logger.debug("Query augmentation is disabled in config")
        augmented_query_text = original_query_text

    # Check if session already has an episode
    existing_episode = memory.ryumem.get_episode_by_session_id(session_id)
    run_id = str(uuid_module.uuid4())

    # Check for session user override - use override user_id if set
    effective_user_id = memory.get_session_user_override(session_id) or user_id
    if effective_user_id != user_id:
        logger.info(f"Using session override user_id in _prepare_query_and_episode: {effective_user_id} (original: {user_id})")

    if existing_episode:
        # Session already linked to an episode - reuse it and add new run
        query_episode_id = existing_episode.uuid
        logger.info(f"Reusing existing episode {query_episode_id} for session {session_id}")

        # Create query run for this session
        query_run = QueryRun(
            run_id=run_id,
            user_id=effective_user_id,
            timestamp=datetime.datetime.utcnow().isoformat(),
            query=original_query_text,
            augmented_query=augmented_query_text if augmented_query_text != original_query_text else None,
            agent_response="",
            tools_used=[]
        )

        # Add run to episode metadata
        _insert_run_information_in_episode(query_episode_id, run_id, session_id, query_run, memory)
    else:
        # Create new episode for this session
        query_episode_id = _create_query_episode(
            query_text=original_query_text,
            user_id=effective_user_id,
            session_id=session_id,
            run_id=run_id,
            augmented_query_text=augmented_query_text,
            memory=memory
        )

    return original_query_text, augmented_message, query_episode_id, run_id


def _save_agent_response_to_episode(
    query_episode_id: str,
    session_id: str,
    agent_response_parts: List[str],
    memory: RyumemGoogleADK
):
    """
    Helper function to save agent response to episode metadata.

    Shared between sync and async wrappers.

    Args:
        query_episode_id: The UUID of the query episode
        session_id: The session ID to find the correct run
        agent_response_parts: List of text parts from agent response
        memory: RyumemGoogleADK instance
    """
    if not query_episode_id or not agent_response_parts:
        return

    try:
        agent_response = ' '.join(agent_response_parts)
        logger.debug(f"Captured agent response ({len(agent_response)} chars) for query {query_episode_id}")

        # Get existing episode via API
        episode = memory.ryumem.get_episode_by_uuid(query_episode_id)

        if episode:
            metadata_dict = episode.metadata if episode.metadata else {}

            # Parse into Pydantic model
            episode_metadata = EpisodeMetadata(**metadata_dict)

            # Update agent response in latest run for this session
            latest_run = episode_metadata.get_latest_run(session_id)
            if latest_run:
                latest_run.agent_response = agent_response

                # Save back to database via API
                memory.ryumem.update_episode_metadata(
                    episode_uuid=query_episode_id,
                    metadata=episode_metadata.model_dump()
                )
                logger.info(f"Saved agent response to episode {query_episode_id} session {session_id[:8]}")
    except Exception as e:
        logger.warning(f"Failed to save agent response: {e}")


def wrap_runner_with_tracking(
    original_runner,
    agent_with_memory,
):
    """
    Wrap a Google ADK runner with query tracking and augmentation.

    Modifies the runner in-place by:
    - Intercepting queries before they reach the agent
    - Augmenting queries with historical context
    - Tracking queries and responses as episodes

    All configuration comes from the agent's ryumem instance.

    Args:
        original_runner: Google ADK Runner instance
        agent_with_memory: Agent that has been enhanced with add_memory_to_agent()

    Returns:
        The same runner object (for chaining)

    Example:
        ryumem = Ryumem()
        agent = add_memory_to_agent(genai.Agent(...), ryumem)
        runner = genai.Runner(agent=agent)
        runner = wrap_runner_with_tracking(runner, agent)
    """
    # Extract memory interface from agent
    if not hasattr(agent_with_memory, '_ryumem_memory'):
        raise ValueError(
            "agent_with_memory must be an agent enhanced with add_memory_to_agent(). "
            f"Got {type(agent_with_memory)} without ._ryumem_memory attribute."
        )

    memory: RyumemGoogleADK = agent_with_memory._ryumem_memory
    if not memory.ryumem.config.tool_tracking.track_queries:
        return original_runner

    # NOTE: Google ADK's Runner.run() internally calls run_async() in a thread.
    # We only need to wrap run_async() - wrapping both would cause double execution.
    # Wrap run_async if it exists
    if hasattr(original_runner, 'run_async'):
        original_run_async = original_runner.run_async

        async def wrapped_run_async(*, user_id, session_id, new_message, **kwargs):
            """Wrapped run_async method that augments queries and tracks them as episodes - returns async generator."""
            # Prepare query and episode using shared helper
            _, augmented_message, query_episode_id, _ = _prepare_query_and_episode(
                new_message=new_message,
                user_id=user_id,
                session_id=session_id,
                memory=memory,
                original_runner=original_runner
            )

            # Call original run_async - it returns an async generator directly
            # Log what we're actually sending to the agent
            if hasattr(augmented_message, 'parts') and augmented_message.parts:
                msg_text = ''.join([p.text for p in augmented_message.parts if hasattr(p, 'text')])
                logger.info(f"Sending to agent: {msg_text[:300]}...")

            event_stream = original_run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=augmented_message,
                **kwargs
            )

            # Yield events from the async generator while capturing responses
            agent_response_parts = []
            try:
                async for event in event_stream:
                    # Capture agent text responses
                    if hasattr(event, 'content') and hasattr(event.content, 'parts'):
                        for part in event.content.parts:
                            if hasattr(part, 'text') and part.text:
                                agent_response_parts.append(part.text)
                    yield event
            finally:
                _save_agent_response_to_episode(query_episode_id, session_id, agent_response_parts, memory)

        # Replace the run_async method
        original_runner.run_async = wrapped_run_async
        logger.info("Wrapped run_async for query tracking (run() will automatically use it)")
    else:
        logger.warning("run_async not found on runner - query tracking may not work")

    # Store runner reference in memory object so tool tracker can access it
    if hasattr(memory, 'tracker'):
        memory.tracker._runner = original_runner
        logger.debug("Stored runner reference in tool tracker for episode ID lookup")

    return original_runner

