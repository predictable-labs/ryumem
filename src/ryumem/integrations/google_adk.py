"""
Google ADK Integration for Ryumem.

This module provides zero-boilerplate memory integration with Google's Agent Developer Kit.
No need to write custom search/save functions - just call enable_memory() and you're done!

Architecture:
- ryumem_customer_id: Identifies your company/app using Ryumem (required)
- user_id: Identifies end users of your app - each user gets isolated memory (optional per-session)
- session_id: Tracks individual conversation threads (handled by Google ADK)

Example:
    ```python
    from google import genai
    from ryumem.integrations import enable_memory

    agent = genai.Agent(
        name="assistant",
        model="gemini-2.0-flash",
        instruction="You are a helpful assistant with memory."
    )

    # One line to enable memory for your company's agent!
    enable_memory(
        agent,
        ryumem_customer_id="my_company",  # Your company using Ryumem
        db_path="./memory.db"
    )

    # The agent will use user_id from each session's runner.run(user_id=...) call
    ```
"""

from typing import Optional, Dict, Any, List
import logging

from ryumem import Ryumem

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
        auto_save: bool = False
    ):
        self.ryumem = ryumem
        self.ryumem_customer_id = ryumem_customer_id
        self.user_id = user_id  # Default user_id, can be None
        self.auto_save = auto_save

        logger.info(f"Initialized RyumemGoogleADK for customer: {ryumem_customer_id}, default_user: {user_id or 'dynamic'}")

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
                group_id=self.ryumem_customer_id,
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

    def save_memory(self, content: str, user_id: Optional[str] = None, source: str = "text") -> Dict[str, Any]:
        """
        Auto-generated save function for persisting memories.

        This function is automatically registered as a tool with the agent.

        Args:
            content: Information to save to memory
            user_id: User identifier (optional - uses instance default if not provided)
            source: Episode type - must be "text", "message", or "json"

        Returns:
            Dict with status and episode_id
        """
        # Use provided user_id or fall back to instance default
        effective_user_id = user_id or self.user_id

        logger.info(f"Saving memory for user '{effective_user_id}': {content[:50]}...")

        try:
            # Validate source type
            valid_sources = ["text", "message", "json"]
            if source not in valid_sources:
                source = "text"  # Default to text if invalid

            episode_id = self.ryumem.add_episode(
                content=content,
                group_id=self.ryumem_customer_id,
                user_id=effective_user_id,
                source=source,
                metadata={"integration": "google_adk"}
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
                group_id=self.ryumem_customer_id,
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


def enable_memory(
    agent,
    ryumem_customer_id: str,
    user_id: Optional[str] = None,
    db_path: str = "./memory.db",
    ryumem_instance: Optional[Ryumem] = None,
    track_tools: bool = False,
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
        **kwargs: Additional arguments for Ryumem constructor (llm_provider, llm_model)
                  and tool tracking config (sampling_rate, etc.)

    Returns:
        RyumemGoogleADK instance for advanced usage (optional)

    Example - Multi-user scenario (recommended):
        ```python
        from google import genai
        from ryumem.integrations import enable_memory

        agent = genai.Agent(
            name="assistant",
            model="gemini-2.0-flash",
            instruction=\"\"\"You are a helpful assistant with memory.
            When using memory tools, always pass the current user_id parameter.\"\"\"
        )

        # Enable memory for your company's agent
        enable_memory(
            agent,
            ryumem_customer_id="my_company"  # Your company
            # user_id is None - will be provided per tool call
        )

        # Each session uses a different user_id
        # runner.run(user_id="alice", ...) - Alice's memories
        # runner.run(user_id="bob", ...) - Bob's memories
        ```

    Example - Single user scenario with tool tracking:
        ```python
        # Enable memory + automatic tool tracking
        enable_memory(
            agent,
            ryumem_customer_id="my_company",
            user_id="alice",
            track_tools=True,  # Track all tool usage!
            llm_provider="openai",
            llm_model="gpt-4o-mini"
        )
        ```
    """
    # Separate Ryumem kwargs from tool tracking kwargs
    ryumem_kwargs = {}
    tool_tracking_kwargs = {}

    # Known Ryumem parameters
    ryumem_params = {'llm_provider', 'llm_model', 'openai_api_key', 'ollama_base_url', 'embedding_provider', 'embedding_model'}

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
        user_id=user_id
    )

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

        # Store tracker reference in memory object for advanced usage
        memory.tracker = tracker

    return memory
