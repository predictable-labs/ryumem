"""
Google ADK Integration for Ryumem.

This module provides zero-boilerplate memory integration with Google's Agent Developer Kit.
No need to write custom search/save functions - just call add_memory_to_agent() and you're done!

Architecture:
- ryumem_customer_id: Identifies your company/app using Ryumem (required)
- user_id: Identifies end users of your app - each user gets isolated memory (optional per-session)
- session_id: Tracks individual conversation threads (handled by Google ADK)

Example:
    ```python
    from google import genai
    from ryumem.integrations import add_memory_to_agent

    agent = genai.Agent(
        name="assistant",
        model="gemini-2.0-flash",
        instruction="You are a helpful assistant with memory."
    )

    # One line to enable memory for your company's agent!
    add_memory_to_agent(
        agent,
        ryumem_customer_id="my_company",  # Your company using Ryumem
        db_path="./memory.db"
    )

    # The agent will use user_id from each session's runner.run(user_id=...) call
    ```
"""

from typing import Optional, Dict, Any, List
import logging
import json

from ryumem import EpisodeType, Ryumem, RyumemConfig
from ryumem.core.metadata_models import EpisodeMetadata, QueryRun

logger = logging.getLogger(__name__)


class RyumemGoogleADK:
    """
    Auto-generates memory tools for Google ADK agents.

    This class creates search and save functions that can be automatically
    registered as tools with Google ADK agents, eliminating boilerplate code.

    Multi-tenancy Architecture:
    - ryumem_customer_id: Identifies the company/app using Ryumem (required)
    - user_id: Identifies individual end users - each gets isolated memory (optional, can be per-session)
    - session_id: Tracks conversation threads (handled by Google ADK sessions)

    Args:
        ryumem: Initialized Ryumem instance
        ryumem_customer_id: Customer/app identifier (your company using Ryumem)
        user_id: Default user identifier (optional - can be provided per tool call)
        auto_save: If True, automatically save all queries (default: False)
    """

    def __init__(
        self,
        ryumem: Ryumem,
        ryumem_customer_id: str,
        user_id: Optional[str] = None,
        auto_save: bool = False,
        extract_entities: Optional[bool] = None
    ):
        self.ryumem = ryumem
        self.ryumem_customer_id = ryumem_customer_id
        self.user_id = user_id  # Default user_id, can be None
        self.auto_save = auto_save
        self.extract_entities = extract_entities  # Default entity extraction override

        logger.info(f"Initialized RyumemGoogleADK for customer: {ryumem_customer_id}, default_user: {user_id or 'dynamic'}, extract_entities: {extract_entities if extract_entities is not None else 'config default'}")

    def search_memory(self, query: str, session_id: str, user_id: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
        """
        Auto-generated search function for retrieving memories.

        This function is automatically registered as a tool with the agent.

        Args:
            query: Natural language query to search memories
            session_id: Session identifier (required)
            user_id: User identifier (optional - uses instance default if not provided)
            limit: Maximum number of memories to return

        Returns:
            Dict with status and memories or no_memories indicator
        """
        # Use provided user_id or fall back to instance default
        effective_user_id = user_id or self.user_id

        logger.info(f"Searching memory for user '{effective_user_id}' session '{session_id}': {query}")

        try:
            results = self.ryumem.search(
                query=query,
                user_id=effective_user_id,
                session_id=session_id,
                strategy="hybrid",
                limit=limit
            )

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
                logger.info(f"Found {len(memories)} memories for user '{effective_user_id}'")
                return {
                    "status": "success",
                    "count": len(memories),
                    "memories": memories
                }
            else:
                logger.info(f"No memories found for user '{effective_user_id}'")
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

    def save_memory(self, content: str, session_id: str, user_id: Optional[str] = None, source: str = "text", extract_entities: Optional[bool] = None) -> Dict[str, Any]:
        """
        Auto-generated save function for persisting memories.

        This function is automatically registered as a tool with the agent.

        Args:
            content: Information to save to memory
            session_id: Session identifier (required)
            user_id: User identifier (optional - uses instance default if not provided)
            source: Episode type - must be "text", "message", or "json"
            extract_entities: Override config/instance setting for entity extraction (None uses instance/config default)

        Returns:
            Dict with status and episode_id
        """
        # Use provided user_id or fall back to instance default
        effective_user_id = user_id or self.user_id

        logger.info(f"Saving memory for user '{effective_user_id}' session '{session_id}': {content[:50]}...")

        try:
            # Fallback: Create new episode
            effective_extract_entities = extract_entities if extract_entities is not None else self.extract_entities

            valid_sources = ["text", "message", "json"]
            if source not in valid_sources:
                source = "text"

            episode_id = self.ryumem.add_episode(
                content=content,
                user_id=effective_user_id,
                session_id=session_id,
                source=source,
                metadata={"integration": "google_adk"},
                extract_entities=effective_extract_entities
            )
            logger.info(f"Saved memory for user '{effective_user_id}' with episode_id: {episode_id}")
            return {
                "status": "success",
                "episode_id": episode_id,
                "message": "Memory saved successfully"
            }

            # Fallback: Create new episode
            effective_extract_entities = extract_entities if extract_entities is not None else self.extract_entities

            valid_sources = ["text", "message", "json"]
            if source not in valid_sources:
                source = "text"

            episode_id = self.ryumem.add_episode(
                content=content,
                user_id=effective_user_id,
                source=source,
                metadata={"integration": "google_adk"},
                extract_entities=effective_extract_entities
            )
            logger.info(f"Saved memory for user '{effective_user_id}' with episode_id: {episode_id}")
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

    def _update_episode_with_memory(self, episode_id: str, session_id: str, content: str) -> None:
        """Update episode metadata to append saved memory."""
        episode = self.ryumem.db.get_episode_by_uuid(episode_id)
        if not episode:
            raise ValueError(f"Episode {episode_id} not found")

        metadata_dict = json.loads(episode['metadata']) if isinstance(episode['metadata'], str) else episode['metadata']
        episode_metadata = EpisodeMetadata(**metadata_dict)

        latest_run = episode_metadata.get_latest_run(session_id)
        if not latest_run:
            raise ValueError(f"No run found for session {session_id} in episode {episode_id}")

        if latest_run.llm_saved_memory:
            latest_run.llm_saved_memory += "\n" + content
        else:
            latest_run.llm_saved_memory = content

        self.ryumem.db.update_episode_metadata(episode_id, episode_metadata.model_dump())
        logger.debug(f"Appended memory to episode {episode_id} session {session_id[:8]}")

    def get_entity_context(self, entity_name: str, session_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Auto-generated function to get full context about an entity.

        Args:
            entity_name: Name of the entity to look up
            session_id: Session identifier (required)
            user_id: User identifier (optional - uses instance default if not provided)

        Returns:
            Dict with entity information and related facts
        """
        # Use provided user_id or fall back to instance default
        effective_user_id = user_id or self.user_id

        logger.info(f"Getting context for entity '{entity_name}' for user '{effective_user_id}'")

        try:
            context = self.ryumem.get_entity_context(
                entity_name=entity_name,
                user_id=effective_user_id,
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
        return [
            self.search_memory,
            self.save_memory,
            self.get_entity_context
        ]

def _register_and_track_tools(
    agent,
    ryumem: Ryumem,
    memory: RyumemGoogleADK,
    ryumem_customer_id: str,
    user_id: Optional[str],
    tool_tracking_kwargs: Dict[str, Any]
):
    """Setup tool tracking and register tools in database."""
    from .tool_tracker import ToolTracker

    tracker = ToolTracker(
        ryumem=ryumem,
        ryumem_customer_id=ryumem_customer_id,
        default_user_id=user_id,
        **tool_tracking_kwargs
    )
    tracker.wrap_agent_tools(agent)
    logger.info(f"Tool tracking enabled for agent: {agent.name if hasattr(agent, 'name') else 'unnamed'}")

    # Register all tools in database
    tools_to_register = [
        {
            'name': getattr(tool, 'name', getattr(tool, '__name__', 'unknown')),
            'description': getattr(tool, 'description', getattr(tool, '__doc__', '')) or f"Tool: {getattr(tool, 'name', 'unknown')}"
        }
        for tool in agent.tools
    ]

    if tools_to_register:
        tracker.register_tools(tools_to_register)
        logger.info(f"Registered {len(tools_to_register)} tools in database")

    memory.tracker = tracker


def add_memory_to_agent(
    agent,
    ryumem_customer_id: str,
    user_id: Optional[str] = None,
    ryumem_instance: Optional[Ryumem] = None,
    track_tools: bool = True,
    track_queries: bool = True,
    augment_queries: bool = True,
    similarity_threshold: float = 0.3,
    top_k_similar: int = 5,
    extract_entities: Optional[bool] = None,
    **kwargs
) -> RyumemGoogleADK:
    """
    One-line function to enable memory for a Google ADK agent.

    This is the primary entry point for integrating Ryumem with Google ADK.
    It automatically creates and registers memory tools with your agent.

    Multi-tenancy Architecture:
    - ryumem_customer_id: Identifies your company/app (required) - all your users' data is grouped here
    - user_id: Identifies individual end users (optional) - can be set as default or passed per tool call
    - session_id: Conversation threads (handled by Google ADK sessions)

    Args:
        agent: Google ADK Agent instance to add memory to
        ryumem_customer_id: Customer/app identifier (your company using Ryumem)
        user_id: Optional default user identifier. If None, user_id must be passed to each tool call
        db_path: Path to SQLite database file (default: "./memory.db")
        ryumem_instance: Optional pre-configured Ryumem instance
        track_tools: If True, automatically track all tool usage for analytics (default: False)
        track_queries: If True, automatically track user queries as episodes (default: True)
                      Note: Requires calling wrap_runner_with_tracking() on your Runner instance
        augment_queries: If True, augment incoming queries with historical context (default: True)
                        Only applies when track_queries=True. Configuration is passed to wrap_runner_with_tracking()
        similarity_threshold: Minimum similarity score for query matching (0.0-1.0, default: 0.3)
                            Lower = more matches, higher = stricter matches
        top_k_similar: Number of similar queries to consider for augmentation (default: 5, -1 for all)
        extract_entities: Override config setting for entity extraction (None uses config default, False disables, True enables)
                         This controls whether episodes trigger entity/relationship extraction (reduces token usage when False)
        **kwargs: Additional arguments for Ryumem constructor (llm_provider, llm_model, enable_entity_extraction)
                  and tool tracking config (sampling_rate, etc.)

    Returns:
        RyumemGoogleADK instance for advanced usage (optional)
        Note: To enable query augmentation, pass augmentation config to wrap_runner_with_tracking()

    Example - Minimal (only GOOGLE_API_KEY needed):
        ```python
        from google import genai
        from ryumem.integrations import add_memory_to_agent

        # Set environment variable
        # export GOOGLE_API_KEY="your-key"

        agent = genai.Agent(
            name="assistant",
            model="gemini-2.0-flash-exp",
            instruction="You are a helpful assistant with memory."
        )

        # Auto-detects GOOGLE_API_KEY and uses Gemini for both LLM and embeddings
        add_memory_to_agent(agent, ryumem_customer_id="my_company")
        ```

    Example - Multi-user scenario (recommended):
        ```python
        from google import genai
        from ryumem.integrations import add_memory_to_agent

        agent = genai.Agent(
            name="assistant",
            model="gemini-2.0-flash",
            instruction=\"\"\"You are a helpful assistant with memory.
            When using memory tools, always pass the current user_id parameter.\"\"\"
        )

        # Enable memory for your company's agent
        add_memory_to_agent(
            agent,
            ryumem_customer_id="my_company"  # Your company
            # user_id is None - will be provided per tool call
        )

        # Each session uses a different user_id
        # runner.run(user_id="alice", ...) - Alice's memories
        # runner.run(user_id="bob", ...) - Bob's memories
        ```

    Example - With Ollama override:
        ```python
        # Ollama overrides Google for LLM, but Gemini still used for embeddings
        add_memory_to_agent(
            agent,
            ryumem_customer_id="my_company",
            llm_provider="ollama",
            llm_model="qwen2.5:7b"
        )
        ```
    """
    import os

    # Separate tool tracking kwargs from other params
    tool_tracking_kwargs = {}

    # Known tool tracking parameters
    tracking_params = {'summarize_large_outputs', 'max_output_length',
                      'sanitize_pii', 'sampling_rate', 'fail_open', 'include_tools', 'exclude_tools'}

    for key, value in kwargs.items():
        if key in tracking_params:
            tool_tracking_kwargs[key] = value
    
    if ryumem_instance is None:
        config = RyumemConfig()
        config.auto_configure_google_adk_settings()
        ryumem = Ryumem(config=config)
        logger.info("Using provided Ryumem instance")
    else:
        ryumem = ryumem_instance

    # Create memory integration
    memory = RyumemGoogleADK(
        ryumem=ryumem,
        ryumem_customer_id=ryumem_customer_id,
        user_id=user_id,
        extract_entities=extract_entities
    )

    # Store augmentation config for use by wrap_runner_with_tracking()
    memory.augmentation_config = {
        'augment_queries': augment_queries,
        'similarity_threshold': similarity_threshold,
        'top_k_similar': top_k_similar,
    }

    # Store query tracking configuration
    memory.track_queries = track_queries

    # Auto-inject tools into agent
    if not hasattr(agent, 'tools'):
        agent.tools = []
        logger.warning("Agent doesn't have 'tools' attribute, creating new list")

    # Add memory tools
    agent.tools.extend(memory.tools)
    logger.info(f"Added {len(memory.tools)} memory tools to agent: {agent.name if hasattr(agent, 'name') else 'unnamed'}")

    # Enable tool tracking if requested
    if track_tools:
        _register_and_track_tools(agent, ryumem, memory, ryumem_customer_id, user_id, tool_tracking_kwargs)

    # Always enhance agent instructions with memory guidance
    # Add tool guidance only if track_tools=True
    _enhance_agent_instruction(
        agent,
        ryumem,
        include_memory_guidance=True,
        include_tool_guidance=track_tools
    )

    # Log query tracking status
    if track_queries:
        logger.info("Query tracking enabled - wrap your Runner with wrap_runner_with_tracking()")

    return memory


def _find_similar_query_episodes(
    query_text: str,
    memory: RyumemGoogleADK,
    user_id: str,
    similarity_threshold: float,
    top_k: int
) -> List[Dict[str, Any]]:
    """Find and filter similar query episodes above threshold."""
    search_results = memory.ryumem.search(
        query=query_text,
        user_id=user_id,
        strategy="semantic",
        limit=top_k if top_k > 0 else 100
    )

    if not search_results.episodes:
        logger.debug("No similar query episodes found")
        return []

    logger.info(f"Search returned {len(search_results.episodes)} episodes for query: '{query_text[:50]}...'")

    similar_queries = []
    for episode in search_results.episodes:
        score = search_results.scores.get(episode.uuid, 0.0)

        # Exact match handling
        if score == 0.0 and episode.content == query_text:
            score = 1.0

        # Filter by threshold and source type
        if score >= similarity_threshold and episode.source == EpisodeType.message:
            similar_queries.append({
                "content": episode.content,
                "score": score,
                "uuid": episode.uuid,
                "metadata": episode.metadata,
            })

    logger.info(f"Found {len(similar_queries)} similar queries above threshold {similarity_threshold}")
    return similar_queries


def _get_linked_tool_executions(query_uuid: str, memory: RyumemGoogleADK) -> List[Dict[str, Any]]:
    """Query database for tool executions linked to a query episode."""
    tool_query = """
    MATCH (query_ep:Episode {uuid: $query_uuid})-[r:TRIGGERED]->(tool_ep:Episode)
    WHERE tool_ep.source = 'json'
      AND tool_ep.metadata IS NOT NULL
    RETURN tool_ep.content AS content,
           tool_ep.metadata AS metadata
    LIMIT 10
    """

    try:
        return memory.ryumem.db.execute(tool_query, {"query_uuid": query_uuid})
    except Exception as e:
        logger.warning(f"Failed to query tool executions: {e}")
        return []


def _build_context_section(query_text: str, similar_queries: List[Dict[str, Any]], memory: RyumemGoogleADK, top_k: int) -> str:
    """Build historical context string from similar queries and their tool executions."""

    # Template for query augmentation
    AUGMENTATION_TEMPLATE = """
[Previous Attempt Summary]

Your previous approach was:
{agent_response}

Tools previously used:
{tool_summary}

Using this memory, improve your next attempt.

***IMPORTANT — REQUIRED BEHAVIOR***
You MUST reuse any **concrete facts, results, conclusions, or discovered information** from the previous attempt if they are relevant. 
Do NOT ignore previously known truths. 
Treat the previous attempt as authoritative memory, not optional context.

In your response, briefly include:
1. What you learned last time (1–2 bullets).
2. What you will change or improve (1–2 bullets).
3. Then continue with your improved reasoning (explicitly applying relevant past information).

IMPORTANT:
If the previous attempt already contains the correct final answer, or fully solves the task, you MUST NOT re-solve it. 
Instead, directly use or return the final answer from memory.

Using this information, answer the query: {query_text}
"""

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

            # Fill template
            return AUGMENTATION_TEMPLATE.format(
                agent_response=agent_response or "No previous response recorded",
                tool_summary=tool_summary or "No tools used",
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
    similarity_threshold: float = 0.1,
    top_k: int = 5,
) -> str:
    """
    Augment an incoming query with historical context from similar past queries.

    Searches for similar query episodes, retrieves their linked tool executions,
    and appends a summary of tool usage patterns to the query.

    Args:
        query_text: The incoming user query
        memory: RyumemGoogleADK instance with access to Ryumem
        user_id: User identifier for scoped search
        similarity_threshold: Minimum similarity score (0.0-1.0)
        top_k: Number of similar queries to consider (-1 for all)

    Returns:
        Augmented query with historical context appended
    """
    try:
        similar_queries = _find_similar_query_episodes(
            query_text, memory, user_id, similarity_threshold, top_k
        )

        if not similar_queries:
            return query_text

        augmented_query = _build_context_section(query_text, similar_queries, memory, top_k)

        logger.info(f"Augmented query with {len(similar_queries)} similar queries")
        return augmented_query

    except Exception as e:
        logger.error(f"Query augmentation failed: {e}")
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
    import json

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
    augment_queries: bool,
    similarity_threshold: float,
    top_k_similar: int,
    memory: RyumemGoogleADK
) -> str:
    """Create episode for user query with metadata."""
    import datetime

    # Create query run using Pydantic model
    query_run = QueryRun(
        run_id=run_id,
        user_id=user_id,
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
        user_id=user_id,
        source="message",
        metadata=episode_metadata.model_dump(),
        extract_entities=memory.extract_entities
    )

    _insert_run_information_in_episode(query_episode_id, run_id, session_id, query_run, memory)
    logger.info(f"Created query episode: {query_episode_id} for user: {user_id}, session: {session_id}")

    return query_episode_id


def _prepare_query_and_episode(
    new_message,
    user_id: str,
    session_id: str,
    memory: RyumemGoogleADK,
    augment_queries: bool,
    similarity_threshold: float,
    top_k_similar: int,
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
        augment_queries: Whether to augment with historical context
        similarity_threshold: Minimum similarity for augmentation
        top_k_similar: Number of similar queries to use
        original_runner: The runner instance for storing context

    Returns:
        Tuple of (original_query_text, augmented_message, query_episode_id, run_id)
        Returns (None, new_message, None, None) if no query text found
    """
    import uuid as uuid_module
    import datetime
    from google.genai import types

    # Extract query text
    query_text = _extract_query_text(new_message)
    if not query_text:
        return None, new_message, None, None

    original_query_text = query_text
    augmented_message = new_message

    # Augment query with historical context if enabled
    if augment_queries:
        augmented_query_text = _augment_query_with_history(
            query_text, memory, user_id, similarity_threshold, top_k_similar
        )

        # Update message if context was added (query text might be same but context added)
        if augmented_query_text != original_query_text:
            logger.info(f"Query augmented (+{len(augmented_query_text) - len(original_query_text)} chars)")
            augmented_message = types.Content(
                role='user',
                parts=[types.Part(text=augmented_query_text)]
            )
        else:
            # Query text unchanged, but make sure to use it in message anyway
            augmented_query_text = original_query_text
    else:
        augmented_query_text = original_query_text

    # Check if session already has an episode
    existing_episode = memory.ryumem.db.get_episode_by_session_id(session_id)
    run_id = str(uuid_module.uuid4())

    if existing_episode:
        # Session already linked to an episode - reuse it and add new run
        query_episode_id = existing_episode.uuid
        logger.info(f"Reusing existing episode {query_episode_id} for session {session_id}")

        # Create query run for this session
        query_run = QueryRun(
            run_id=run_id,
            user_id=user_id,
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
            user_id=user_id,
            session_id=session_id,
            run_id=run_id,
            augmented_query_text=augmented_query_text,
            augment_queries=augment_queries,
            similarity_threshold=similarity_threshold,
            top_k_similar=top_k_similar,
            memory=memory
        )

    # Store context on runner instance for tool tracker
    original_runner._ryumem_current_run_id = run_id
    original_runner._ryumem_query_episode = query_episode_id
    original_runner._ryumem_session_id = session_id
    original_runner._ryumem_user_id = user_id

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

    import json

    try:
        agent_response = ' '.join(agent_response_parts)
        logger.debug(f"Captured agent response ({len(agent_response)} chars) for query {query_episode_id}")

        # Get existing episode
        existing_episode = memory.ryumem.db.execute(
            "MATCH (e:Episode {uuid: $uuid}) RETURN e.metadata AS metadata",
            {"uuid": query_episode_id}
        )

        if existing_episode:
            metadata_str = existing_episode[0].get("metadata", "{}")
            metadata_dict = json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str

            # Parse into Pydantic model
            episode_metadata = EpisodeMetadata(**metadata_dict)

            # Update agent response in latest run for this session
            latest_run = episode_metadata.get_latest_run(session_id)
            if latest_run:
                latest_run.agent_response = agent_response

                # Save back to database
                memory.ryumem.db.execute(
                    "MATCH (e:Episode {uuid: $uuid}) SET e.metadata = $metadata",
                    {"uuid": query_episode_id, "metadata": json.dumps(episode_metadata.model_dump())}
                )
                logger.info(f"Saved agent response to episode {query_episode_id} session {session_id[:8]}")
    except Exception as e:
        logger.warning(f"Failed to save agent response: {e}")





def wrap_runner_with_tracking(
    original_runner,
    memory: RyumemGoogleADK,
    track_queries: bool = True,
    augment_queries: bool = True,
    similarity_threshold: float = 0.3,
    top_k_similar: int = 5,
):
    """
    Wrap a Google ADK Runner to automatically track user queries as episodes
    and optionally augment queries with historical context.

    This wrapper intercepts both runner.run() and runner.run_async() calls to:
    1. Augment incoming queries with similar past queries and their tool usage (if enabled)
    2. Create episodes for user queries before they're processed by the agent
    3. Link tool executions to these query episodes for hierarchical tracking

    Args:
        original_runner: The original Google ADK Runner instance
        memory: RyumemGoogleADK instance for storing episodes
        track_queries: Whether to track user queries (default: True)
        augment_queries: Whether to augment queries with historical context (default: True)
        similarity_threshold: Minimum similarity score for query matching (0.0-1.0, default: 0.3)
        top_k_similar: Number of similar queries to consider for augmentation (default: 5, -1 for all)

    Returns:
        Wrapped runner with query tracking and augmentation enabled for both sync and async methods

    Example:
        ```python
        runner = Runner(agent=agent, app_name="my_app", session_service=session_service)

        # Enable query tracking and augmentation
        runner = wrap_runner_with_tracking(
            runner,
            memory,
            augment_queries=True,      # Enable augmentation
            similarity_threshold=0.3,  # Match queries with 30%+ similarity
            top_k_similar=5            # Use top 5 similar queries
        )

        # Use runner normally - works with both sync and async
        runner.run(user_id="user123", session_id="session456", new_message=content)
        # OR
        await runner.run_async(user_id="user123", session_id="session456", new_message=content)
        ```
    """
    if not track_queries:
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
                augment_queries=augment_queries,
                similarity_threshold=similarity_threshold,
                top_k_similar=top_k_similar,
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

    augmentation_status = "enabled" if augment_queries else "disabled"
    logger.info(f"Runner wrapped for query tracking (augmentation: {augmentation_status})")

    return original_runner


def _enhance_agent_instruction(
    agent,
    ryumem,
    agent_type: str = "google_adk",
    include_memory_guidance: bool = True,
    include_tool_guidance: bool = False
):
    """
    Enhances agent.instruction with memory and optional tool guidance.
    Checks if instruction already exists in DB before saving.

    Args:
        agent: Agent instance to enhance
        ryumem: Ryumem instance
        agent_type: Type of agent (default: "google_adk")
        include_memory_guidance: Whether to include basic memory usage guidance (default: True)
        include_tool_guidance: Whether to include tool selection guidance (default: False)
    """
    old_instruction = agent.instruction or ""

    # Build instruction parts
    instruction_parts = []
    if old_instruction:
        instruction_parts.append(old_instruction)

    # Memory guidance block (always included by default)
    memory_block = """MEMORY USAGE:
Use search_memory to find relevant context before answering questions.
Use save_memory to store important information for future reference.
"""

    # Tool guidance block (only when tracking tools)
    tool_block = """TOOL SELECTION:
Before selecting which tool to use, search_memory for past tool usage patterns and success rates.
Use queries like "tool execution for [task type]" to find which tools worked well for similar tasks.
"""

    # Add memory guidance if not already present
    if include_memory_guidance and "search_memory" not in old_instruction and "MEMORY USAGE" not in old_instruction:
        instruction_parts.append(memory_block)

    # Add tool guidance if requested and not already present
    if include_tool_guidance and "tool usage patterns" not in old_instruction and "TOOL SELECTION" not in old_instruction:
        instruction_parts.append(tool_block)

    # Combine all parts
    new_instruction = "\n\n".join(instruction_parts)

    # Determine instruction type based on what's included
    if include_tool_guidance:
        instruction_type = "tool_tracking"
        description = "Memory and tool tracking guidance"
    else:
        instruction_type = "memory_usage"
        description = "Memory usage guidance"

    # --- Check if this instruction already exists in DB ---
    try:
        existing_uuid = ryumem.get_instruction_by_text(
            instruction_text=new_instruction,
            agent_type=agent_type,
            instruction_type=instruction_type
        )
    except Exception:
        existing_uuid = None

    # --- If instruction doesn't exist in DB, save it ---
    if not existing_uuid:
        try:
            ryumem.save_agent_instruction(
                instruction_text=new_instruction,
                original_user_request=old_instruction,
                agent_type=agent_type,
                instruction_type=instruction_type,
                description=description
            )
        except Exception:
            # if DB save fails, continue but do not crash
            pass

    # --- Update agent instruction ---
    agent.instruction = new_instruction
