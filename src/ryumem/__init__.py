"""
Ryumem - Bi-temporal Knowledge Graph Memory System

A memory system using ryugraph as the graph database layer.

Example:
    from ryumem import Ryumem

    # Initialize
    ryumem = Ryumem(
        db_path="./data/memory.db",
        openai_api_key="sk-...",
    )

    # Add episodes
    ryumem.add_episode(
        content="Alice works at Google in Mountain View",
        user_id="user_123",
    )

    # Search
    results = ryumem.search(
        query="Where does Alice work?",
        user_id="user_123",
    )

    # Get entity context
    context = ryumem.get_entity_context(
        entity_name="Alice",
        user_id="user_123",
    )
"""

from ryumem.core.config import RyumemConfig
from ryumem.core.models import (
    EntityEdge,
    EntityNode,
    EpisodeNode,
    EpisodeType,
    EpisodeKind,
    EpisodicEdge,
    SearchConfig,
    SearchResult,
)
from ryumem.main import Ryumem

__version__ = "0.1.0"

__all__ = [
    "Ryumem",
    "RyumemConfig",
    "EpisodeNode",
    "EntityNode",
    "EntityEdge",
    "EpisodicEdge",
    "EpisodeType",
    "EpisodeKind",
    "SearchConfig",
    "SearchResult",
]
