"""
Google ADK Integration for Ryumem.

This module provides zero-boilerplate memory integration with Google's Agent Developer Kit.
No need to write custom search/save functions - just call enable_memory() and you're done!

Example:
    ```python
    from google import genai
    from ryumem.integrations import enable_memory

    agent = genai.Agent(
        name="assistant",
        model="gemini-2.0-flash",
        instruction="You are a helpful assistant with memory."
    )

    # One line to enable memory!
    enable_memory(agent, user_id="user_123", db_path="./memory.db")
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

    Args:
        ryumem: Initialized Ryumem instance
        user_id: User identifier for memory isolation
        group_id: Optional group identifier (defaults to user_id)
        auto_save: If True, automatically save all queries (default: False)
    """

    def __init__(
        self,
        ryumem: Ryumem,
        user_id: str,
        group_id: Optional[str] = None,
        auto_save: bool = False
    ):
        self.ryumem = ryumem
        self.user_id = user_id
        self.group_id = group_id or user_id
        self.auto_save = auto_save

        logger.info(f"Initialized RyumemGoogleADK for user: {user_id}")

    def search_memory(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """
        Auto-generated search function for retrieving memories.

        This function is automatically registered as a tool with the agent.

        Args:
            query: Natural language query to search memories
            limit: Maximum number of memories to return

        Returns:
            Dict with status and memories or no_memories indicator
        """
        logger.info(f"Searching memory for: {query}")

        try:
            results = self.ryumem.search(
                query=query,
                group_id=self.group_id,
                strategy="hybrid",
                limit=limit
            )

            if results.edges:
                memories = [
                    {
                        "fact": edge.fact,
                        "score": edge.score,
                        "source": edge.source_node,
                        "target": edge.target_node
                    }
                    for edge in results.edges
                ]
                logger.info(f"Found {len(memories)} memories")
                return {
                    "status": "success",
                    "count": len(memories),
                    "memories": memories
                }
            else:
                logger.info("No memories found")
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

    def save_memory(self, content: str, source: str = "google_adk") -> Dict[str, Any]:
        """
        Auto-generated save function for persisting memories.

        This function is automatically registered as a tool with the agent.

        Args:
            content: Information to save to memory
            source: Source identifier for the memory

        Returns:
            Dict with status and episode_id
        """
        logger.info(f"Saving memory: {content[:50]}...")

        try:
            episode_id = self.ryumem.add_episode(
                content=content,
                group_id=self.group_id,
                user_id=self.user_id,
                source=source
            )
            logger.info(f"Saved memory with episode_id: {episode_id}")
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

    def get_entity_context(self, entity_name: str) -> Dict[str, Any]:
        """
        Auto-generated function to get full context about an entity.

        Args:
            entity_name: Name of the entity to look up

        Returns:
            Dict with entity information and related facts
        """
        logger.info(f"Getting context for entity: {entity_name}")

        try:
            context = self.ryumem.get_entity_context(
                entity_name=entity_name,
                group_id=self.group_id
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
    user_id: str,
    db_path: str = "./memory.db",
    ryumem_instance: Optional[Ryumem] = None,
    **ryumem_kwargs
) -> RyumemGoogleADK:
    """
    One-line function to enable memory for a Google ADK agent.

    This is the primary entry point for integrating Ryumem with Google ADK.
    It automatically creates and registers memory tools with your agent.

    Args:
        agent: Google ADK Agent instance to add memory to
        user_id: User identifier for memory isolation
        db_path: Path to SQLite database file (default: "./memory.db")
        ryumem_instance: Optional pre-configured Ryumem instance
        **ryumem_kwargs: Additional arguments to pass to Ryumem constructor

    Returns:
        RyumemGoogleADK instance for advanced usage (optional)

    Example:
        ```python
        from google import genai
        from ryumem.integrations import enable_memory

        agent = genai.Agent(
            name="assistant",
            model="gemini-2.0-flash",
            instruction="You are a helpful assistant."
        )

        # One line to enable memory!
        enable_memory(agent, user_id="user_123")
        ```
    """
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
        user_id=user_id
    )

    # Auto-inject tools into agent
    if not hasattr(agent, 'tools'):
        agent.tools = []
        logger.warning("Agent doesn't have 'tools' attribute, creating new list")

    # Add memory tools
    agent.tools.extend(memory.tools)
    logger.info(f"Added {len(memory.tools)} memory tools to agent: {agent.name if hasattr(agent, 'name') else 'unnamed'}")

    return memory
