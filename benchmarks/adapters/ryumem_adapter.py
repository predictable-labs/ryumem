"""Ryumem memory system adapter."""

import time
from typing import Any, Dict, List, Optional

from benchmarks.adapters.base import (
    MemorySystemAdapter,
    IngestionResult,
    SearchResponse,
    SearchResult,
    SearchStrategy,
)


class RyumemAdapter(MemorySystemAdapter):
    """Adapter for Ryumem memory system."""

    def __init__(self):
        self._client = None
        self._config: Dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "Ryumem"

    @property
    def version(self) -> str:
        try:
            from importlib.metadata import version
            return version("ryumem")
        except Exception:
            return "unknown"

    @property
    def supported_strategies(self) -> List[SearchStrategy]:
        return [
            SearchStrategy.SEMANTIC,
            SearchStrategy.BM25,
            SearchStrategy.HYBRID,
            SearchStrategy.TRAVERSAL,
        ]

    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize Ryumem client."""
        from ryumem import Ryumem

        self._config = config
        self._client = Ryumem(
            server_url=config.get("server_url", "http://localhost:8000"),
            api_key=config.get("api_key"),
        )

    def ingest(
        self,
        content: str,
        user_id: str,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        """Ingest content into Ryumem."""
        start = time.perf_counter()
        try:
            episode_id = self._client.add_episode(
                content=content,
                user_id=user_id,
                session_id=session_id,
                source="text",
                kind="memory",
                metadata=metadata or {},
            )
            duration_ms = (time.perf_counter() - start) * 1000
            return IngestionResult(
                success=True,
                episode_id=episode_id,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            return IngestionResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )

    def search(
        self,
        query: str,
        user_id: str,
        limit: int = 10,
        strategy: SearchStrategy = SearchStrategy.HYBRID,
    ) -> SearchResponse:
        """Search Ryumem."""
        start = time.perf_counter()
        try:
            strategy_map = {
                SearchStrategy.SEMANTIC: "semantic",
                SearchStrategy.BM25: "bm25",
                SearchStrategy.HYBRID: "hybrid",
                SearchStrategy.TRAVERSAL: "traversal",
            }
            result = self._client.search(
                query=query,
                user_id=user_id,
                session_id="benchmark",
                limit=limit,
                strategy=strategy_map.get(strategy, "hybrid"),
            )

            search_results = []
            for ep in result.episodes:
                score = result.scores.get(ep.uuid, 0.0) if hasattr(result, 'scores') and result.scores else 0.0
                search_results.append(
                    SearchResult(
                        content=ep.content,
                        score=score,
                        metadata={"uuid": ep.uuid},
                    )
                )

            duration_ms = (time.perf_counter() - start) * 1000
            return SearchResponse(
                results=search_results,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            return SearchResponse(
                results=[],
                error=str(e),
                duration_ms=duration_ms,
            )

    def clear(self, user_id: str) -> bool:
        """Clear data for a user."""
        # Ryumem doesn't have a per-user clear method yet
        # For benchmarking, we use unique user_ids per question
        return True

    def shutdown(self) -> None:
        """Clean up resources."""
        self._client = None
