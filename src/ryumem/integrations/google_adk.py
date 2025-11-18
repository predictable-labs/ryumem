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

from ryumem import EpisodeType, Ryumem

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

    def search_memory(self, query: str, user_id: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
        """
        Auto-generated search function for retrieving memories.

        This function is automatically registered as a tool with the agent.

        Args:
            query: Natural language query to search memories
            user_id: User identifier (optional - uses instance default if not provided)
            limit: Maximum number of memories to return

        Returns:
            Dict with status and memories or no_memories indicator
        """
        # Use provided user_id or fall back to instance default
        effective_user_id = user_id or self.user_id

        logger.info(f"Searching memory for user '{effective_user_id}': {query}")

        try:
            results = self.ryumem.search(
                query=query,
                user_id=effective_user_id,
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

    def save_memory(self, content: str, user_id: Optional[str] = None, source: str = "text", extract_entities: Optional[bool] = None) -> Dict[str, Any]:
        """
        Auto-generated save function for persisting memories.

        This function is automatically registered as a tool with the agent.

        Args:
            content: Information to save to memory
            user_id: User identifier (optional - uses instance default if not provided)
            source: Episode type - must be "text", "message", or "json"
            extract_entities: Override config/instance setting for entity extraction (None uses instance/config default)

        Returns:
            Dict with status and episode_id
        """
        # Use provided user_id or fall back to instance default
        effective_user_id = user_id or self.user_id

        # Use provided extract_entities or fall back to instance default
        effective_extract_entities = extract_entities if extract_entities is not None else self.extract_entities

        logger.info(f"Saving memory for user '{effective_user_id}': {content[:50]}... (extract_entities={effective_extract_entities if effective_extract_entities is not None else 'config default'})")

        try:
            # Validate source type
            valid_sources = ["text", "message", "json"]
            if source not in valid_sources:
                source = "text"  # Default to text if invalid

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

    def get_entity_context(self, entity_name: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Auto-generated function to get full context about an entity.

        Args:
            entity_name: Name of the entity to look up
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
                user_id=effective_user_id
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


def add_memory_to_agent(
    agent,
    ryumem_customer_id: str,
    user_id: Optional[str] = None,
    db_path: str = "./data/memory.db",
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

    # Separate Ryumem kwargs from tool tracking kwargs
    ryumem_kwargs = {}
    tool_tracking_kwargs = {}

    # Known Ryumem parameters
    ryumem_params = {'llm_provider', 'llm_model', 'openai_api_key', 'gemini_api_key', 'ollama_base_url', 'embedding_provider', 'embedding_model'}

    # Known tool tracking parameters
    tracking_params = {'summarize_large_outputs', 'max_output_length',
                      'sanitize_pii', 'sampling_rate', 'fail_open', 'include_tools', 'exclude_tools'}

    for key, value in kwargs.items():
        if key in ryumem_params:
            ryumem_kwargs[key] = value
        elif key in tracking_params:
            tool_tracking_kwargs[key] = value
        else:
            # Default to Ryumem kwargs for unknown parameters
            ryumem_kwargs[key] = value

    # AUTO-DETECTION LOGIC for Google ADK integration
    # Only applies if Ryumem instance is not provided
    if ryumem_instance is None:
        # Check if Ollama is explicitly configured (highest priority)
        ollama_configured = 'llm_provider' in ryumem_kwargs and ryumem_kwargs['llm_provider'] == 'ollama'

        if not ollama_configured:
            # Check for GOOGLE_API_KEY in environment
            google_api_key = os.getenv("GOOGLE_API_KEY")

            if not google_api_key:
                raise ValueError(
                    "Google ADK integration requires GOOGLE_API_KEY environment variable. "
                    "Set it with: export GOOGLE_API_KEY='your-key' "
                    "OR use llm_provider='ollama' to override."
                )

            # Auto-configure for Gemini if not explicitly set
            if 'llm_provider' not in ryumem_kwargs:
                ryumem_kwargs['llm_provider'] = 'gemini'
                ryumem_kwargs['llm_model'] = 'gemini-2.0-flash-exp'
                logger.info("🔍 Auto-detected GOOGLE_API_KEY, using Gemini for LLM")

            if 'gemini_api_key' not in ryumem_kwargs:
                ryumem_kwargs['gemini_api_key'] = google_api_key

            # Set embedding provider based on key availability
            if 'embedding_provider' not in ryumem_kwargs:
                openai_api_key = ryumem_kwargs.get('openai_api_key') or os.getenv("OPENAI_API_KEY")

                if openai_api_key:
                    # Prefer OpenAI for embeddings if available
                    ryumem_kwargs['embedding_provider'] = 'openai'
                    ryumem_kwargs['embedding_model'] = 'text-embedding-3-large'
                    ryumem_kwargs['openai_api_key'] = openai_api_key
                    logger.info("📊 Using OpenAI for embeddings (better quality)")
                else:
                    # Fallback to Gemini for embeddings
                    ryumem_kwargs['embedding_provider'] = 'gemini'
                    ryumem_kwargs['embedding_model'] = 'text-embedding-004'
                    logger.info("📊 Using Gemini for embeddings")

    # Create or use existing Ryumem instance
    if ryumem_instance is None:
        ryumem = Ryumem(db_path=db_path, **ryumem_kwargs)
        logger.info(f"Created new Ryumem instance at: {db_path}")
    else:
        ryumem = ryumem_instance
        logger.info("Using provided Ryumem instance")

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
        from .tool_tracker import ToolTracker

        tracker = ToolTracker(
            ryumem=ryumem,
            ryumem_customer_id=ryumem_customer_id,
            default_user_id=user_id,  # Pass default user_id to tracker
            **tool_tracking_kwargs
        )
        tracker.wrap_agent_tools(agent)
        logger.info(f"Tool tracking enabled for agent: {agent.name if hasattr(agent, 'name') else 'unnamed'}")

        # Register all agent tools in the database
        tools_to_register = []
        for tool in agent.tools:
            tool_name = getattr(tool, 'name', getattr(tool, '__name__', 'unknown'))
            tool_description = getattr(tool, 'description', getattr(tool, '__doc__', ''))
            tools_to_register.append({
                'name': tool_name,
                'description': tool_description or f"Tool: {tool_name}"
            })

        if tools_to_register:
            tracker.register_tools(tools_to_register)
            logger.info(f"Registered {len(tools_to_register)} tools in database")

        # Store tracker reference in memory object for advanced usage
        memory.tracker = tracker

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
        import json

        # Search for similar query episodes
        search_results = memory.ryumem.search(
            query=query_text,
            user_id=user_id,
            strategy="semantic",
            limit=top_k if top_k > 0 else 100  # Cap at 100 for -1
        )

        if not search_results.episodes:
            logger.debug("No similar query episodes found for augmentation")
            return query_text

        logger.debug(f"Search returned {len(search_results.episodes)} episodes")

        # Filter by similarity threshold and source type (message = user queries)
        similar_queries = []
        for episode in search_results.episodes:
            # score = search_results.scores.get(episode.uuid, 0.0)
            episode_similarity = episode.metadata.get("augmentation_config", {}).get("similarity_threshold", 0.0)

            # Only include episodes that are:
            # 1. Above similarity threshold
            # 2. From 'message' source (user queries, not tool executions)
            # 3. Not the exact same query (to avoid self-reference)
            if (episode_similarity >= similarity_threshold and
                episode.source == EpisodeType.message and
                episode.content != query_text):

                similar_queries.append({
                    "content": episode.content,
                    "score": episode_similarity,
                    "uuid": episode.uuid,
                })
                logger.debug(f"  ✓ Added as similar query")
            else:
                reasons = []
                if episode_similarity < similarity_threshold:
                    reasons.append(f"score {episode_similarity:.3f} < threshold {similarity_threshold}")
                if episode.source != EpisodeType.message:
                    reasons.append(f"source is '{episode.source}' not 'message'")
                if episode.content == query_text:
                    reasons.append("exact same query")
                logger.debug(f"  ✗ Filtered out: {', '.join(reasons)}")

        if not similar_queries:
            logger.debug(f"No queries above threshold {similarity_threshold} after filtering")
            return query_text

        logger.info(f"Found {len(similar_queries)} similar queries for augmentation")

        # Build historical context by finding tool executions for similar queries
        context_parts = ["\n\n[Historical Context from Similar Queries:"]

        for idx, similar in enumerate(similar_queries[:top_k if top_k > 0 else len(similar_queries)], 1):
            # Extract query content and score
            query_content = similar["content"]
            query_uuid = similar["uuid"]
            similarity_score = similar["score"]

            context_parts.append(f"\n{idx}. Similar Query (similarity: {similarity_score:.2f}): \"{query_content}\"")

            # Search for tool execution episodes linked to this query via UUID
            # Use Cypher query to find TRIGGERED relationships
            tool_query = """
            MATCH (query_ep:Episode {uuid: $query_uuid})-[r:TRIGGERED]->(tool_ep:Episode)
            WHERE tool_ep.source = 'json'
              AND tool_ep.metadata IS NOT NULL
            RETURN tool_ep.content AS content,
                   tool_ep.metadata AS metadata
            LIMIT 10
            """

            try:
                tool_results = memory.ryumem.db.execute(tool_query, {
                    "query_uuid": query_uuid  # Use exact UUID for matching
                })

                if tool_results:
                    context_parts.append("   Tools Used:")
                    for tool_result in tool_results:
                        try:
                            metadata = json.loads(tool_result['metadata']) if isinstance(tool_result['metadata'], str) else tool_result['metadata']
                            tool_name = metadata.get('tool_name', 'unknown')
                            task_type = metadata.get('task_type', 'unknown')
                            success = metadata.get('success', False)
                            duration_ms = metadata.get('duration_ms', 0)
                            input_params = metadata.get('input_params', {})
                            output_summary = metadata.get('output_summary', 'N/A')

                            status = "✓ Success" if success else "✗ Failed"
                            context_parts.append(f"   • {tool_name}({', '.join([f'{k}={v}' for k, v in input_params.items()])})")
                            context_parts.append(f"     {status} ({duration_ms}ms) | Task: {task_type}")
                            context_parts.append(f"     Output: {output_summary[:100]}...")
                        except Exception as e:
                            logger.warning(f"Failed to parse tool metadata: {e}")
                            continue
            except Exception as e:
                logger.warning(f"Failed to query tool executions: {e}")
                continue

        context_parts.append("]\n")

        # Combine original query with context
        augmented_query = query_text + ''.join(context_parts)

        logger.info(f"✨ Augmented query with {len(similar_queries)} similar queries")
        return augmented_query

    except Exception as e:
        logger.error(f"Query augmentation failed: {e}")
        # Return original query if augmentation fails
        return query_text


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

    This wrapper intercepts runner.run() calls to:
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
        Wrapped runner with query tracking and augmentation enabled

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

        # Use runner normally - augmentation happens automatically
        runner.run(user_id="user123", session_id="session456", new_message=content)
        ```
    """
    if not track_queries:
        return original_runner

    from .tool_tracker import set_current_query_episode, clear_current_query_episode
    from google.genai import types

    # Store reference to original run method
    original_run = original_runner.run

    def wrapped_run(*, user_id, session_id, new_message, **kwargs):
        """Wrapped run method that augments queries and tracks them as episodes."""
        query_episode_id = None
        original_query_text = None
        augmented_query_text = None

        # Extract query text from new_message
        if new_message and hasattr(new_message, 'parts'):
            query_text = ' '.join([
                p.text for p in new_message.parts
                if hasattr(p, 'text') and p.text
            ])

            if query_text:
                original_query_text = query_text

                # Augment query with historical context if enabled
                if augment_queries:
                    augmented_query_text = _augment_query_with_history(
                        query_text=query_text,
                        memory=memory,
                        user_id=user_id,
                        similarity_threshold=similarity_threshold,
                        top_k=top_k_similar,
                    )

                    # Check if query was actually augmented
                    if augmented_query_text != original_query_text:
                        logger.info(f"Query augmented with historical context (added {len(augmented_query_text) - len(original_query_text)} chars)")

                        # Update new_message with augmented query
                        new_message = types.Content(
                            role='user',
                            parts=[types.Part(text=augmented_query_text)]
                        )
                    else:
                        logger.debug(f"No augmentation occurred - no similar queries found above threshold")
                        # Keep augmented_query_text as original query for metadata tracking

                # Create episode for user query (store ORIGINAL query, not augmented)
                # Use memory.extract_entities setting if available
                query_episode_id = memory.ryumem.add_episode(
                    content=original_query_text,  # Store original for similarity matching
                    user_id=user_id,
                    source="message",
                    metadata={
                        "session_id": session_id,
                        "integration": "google_adk",
                        "type": "user_query",
                        "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
                        "augmented": augmented_query_text is not None and augmented_query_text != original_query_text,
                        "augmented_query": augmented_query_text if augmented_query_text else None,
                        "augmentation_config": {
                            "enabled": augment_queries,
                            "similarity_threshold": similarity_threshold,
                            "top_k_similar": top_k_similar,
                        } if augment_queries else None,
                    },
                    extract_entities=memory.extract_entities  # Use memory's default setting
                )

                # Store in multiple places for maximum reliability:
                # 1. Context variable (for same-context async tasks)
                # 2. Session map (for cross-context/thread scenarios)
                # 3. Runner instance (always accessible, Google ADK propagates this)
                set_current_query_episode(query_episode_id, session_id=session_id, user_id=user_id)

                # Store on runner instance for reliable access from tools
                # This works because ADK passes the runner context through to tools
                original_runner._ryumem_query_episode = query_episode_id
                original_runner._ryumem_session_id = session_id
                original_runner._ryumem_user_id = user_id

                logger.info(f"📝 Created query episode: {query_episode_id} for user: {user_id}")

        # Run original_run() inside a copied context to ensure contextvars propagate
        # to any new async tasks spawned by Google ADK
        import contextvars
        ctx = contextvars.copy_context()

        # Execute original_run within the copied context
        # This ensures that any tasks created by ADK inherit the contextvar values
        event_generator = ctx.run(
            lambda: original_run(
                user_id=user_id,
                session_id=session_id,
                new_message=new_message,
                **kwargs
            )
        )

        # Wrap the generator to clear context AFTER all events are consumed
        def context_aware_generator():
            """Generator wrapper that clears context after all events are yielded."""
            try:
                # Yield all events from the original generator
                # Tool executions happen during this iteration - context is still set!
                yield from event_generator
            finally:
                # Clear context AFTER all events have been consumed
                # This ensures tool executions can access the parent query episode
                if query_episode_id:
                    logger.debug(f"Clearing query episode context: {query_episode_id}")
                    clear_current_query_episode(session_id=session_id, user_id=user_id)
                    # Also clear from runner instance
                    if hasattr(original_runner, '_ryumem_query_episode'):
                        delattr(original_runner, '_ryumem_query_episode')
                    if hasattr(original_runner, '_ryumem_session_id'):
                        delattr(original_runner, '_ryumem_session_id')
                    if hasattr(original_runner, '_ryumem_user_id'):
                        delattr(original_runner, '_ryumem_user_id')

        # Return the wrapped generator
        return context_aware_generator()

    # Replace the run method
    original_runner.run = wrapped_run

    # Store runner reference in memory object so tool tracker can access it
    if hasattr(memory, 'tracker'):
        memory.tracker._runner = original_runner
        logger.debug("Stored runner reference in tool tracker for episode ID lookup")

    augmentation_status = "enabled" if augment_queries else "disabled"
    logger.info(f"🚀 Runner wrapped for query tracking (augmentation: {augmentation_status})")

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
