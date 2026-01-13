"""Abstract base class for memory system adapters."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SearchStrategy(Enum):
    """Available search strategies."""

    SEMANTIC = "semantic"
    BM25 = "bm25"
    HYBRID = "hybrid"
    TRAVERSAL = "traversal"


@dataclass
class IngestionResult:
    """Result from ingesting content into a memory system."""

    success: bool
    episode_id: Optional[str] = None
    error: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class SearchResult:
    """A single result from searching a memory system."""

    content: str
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResponse:
    """Full response from a search operation."""

    results: List[SearchResult] = field(default_factory=list)
    duration_ms: float = 0.0
    error: Optional[str] = None


class MemorySystemAdapter(ABC):
    """
    Abstract base class for memory system adapters.

    Each adapter wraps a memory system (ryumem, mem0, etc.) and provides
    a unified interface for benchmarking operations.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the memory system."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Version of the memory system."""
        pass

    @property
    def supported_strategies(self) -> List[SearchStrategy]:
        """List of search strategies supported by this system."""
        return [SearchStrategy.SEMANTIC]  # Default

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initialize the memory system with configuration.

        Args:
            config: Configuration dictionary with provider settings
        """
        pass

    @abstractmethod
    def ingest(
        self,
        content: str,
        user_id: str,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        """
        Ingest content into the memory system.

        Args:
            content: Text content to ingest
            user_id: User identifier for multi-tenancy
            session_id: Session identifier
            metadata: Optional metadata to attach

        Returns:
            IngestionResult with success status and timing
        """
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        user_id: str,
        limit: int = 10,
        strategy: SearchStrategy = SearchStrategy.SEMANTIC,
    ) -> SearchResponse:
        """
        Search the memory system.

        Args:
            query: Search query
            user_id: User identifier for multi-tenancy
            limit: Maximum number of results
            strategy: Search strategy to use

        Returns:
            SearchResponse with results and timing
        """
        pass

    @abstractmethod
    def clear(self, user_id: str) -> bool:
        """
        Clear all data for a user.

        Args:
            user_id: User identifier

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Clean up resources."""
        pass

    def get_memory_usage(self) -> Dict[str, Any]:
        """Get current memory usage statistics."""
        import tracemalloc

        if tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            return {
                "current_mb": current / 1024 / 1024,
                "peak_mb": peak / 1024 / 1024,
            }
        return {"current_mb": 0.0, "peak_mb": 0.0}
