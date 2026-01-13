"""Mem0 memory system adapter."""

import time
from typing import Any, Dict, List, Optional

from benchmarks.adapters.base import (
    MemorySystemAdapter,
    IngestionResult,
    SearchResponse,
    SearchResult,
    SearchStrategy,
)


class Mem0Adapter(MemorySystemAdapter):
    """Adapter for Mem0 memory system."""

    def __init__(self):
        self._client = None
        self._config: Dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "Mem0"

    @property
    def version(self) -> str:
        try:
            from importlib.metadata import version
            return version("mem0ai")
        except Exception:
            return "unknown"

    @property
    def supported_strategies(self) -> List[SearchStrategy]:
        return [SearchStrategy.SEMANTIC]

    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize Mem0 client with Ollama by default."""
        from mem0 import Memory

        self._config = config

        # Build mem0 configuration
        llm_provider = config.get("llm_provider", "ollama")
        embedding_provider = config.get("embedding_provider", "ollama")

        mem0_config = {}

        # Configure LLM
        if llm_provider == "ollama":
            mem0_config["llm"] = {
                "provider": "ollama",
                "config": {
                    "model": config.get("llm_model", "llama3.2"),
                    "ollama_base_url": config.get("ollama_url", "http://localhost:11434"),
                },
            }
        elif llm_provider == "openai":
            mem0_config["llm"] = {
                "provider": "openai",
                "config": {
                    "model": config.get("llm_model", "gpt-4o-mini"),
                    "api_key": config.get("openai_api_key"),
                },
            }
        elif llm_provider == "gemini":
            mem0_config["llm"] = {
                "provider": "google",
                "config": {
                    "model": config.get("llm_model", "gemini-2.0-flash"),
                    "api_key": config.get("gemini_api_key"),
                },
            }

        # Configure embeddings
        if embedding_provider == "ollama":
            mem0_config["embedder"] = {
                "provider": "ollama",
                "config": {
                    "model": config.get("embedding_model", "nomic-embed-text"),
                    "ollama_base_url": config.get("ollama_url", "http://localhost:11434"),
                },
            }
        elif embedding_provider == "openai":
            mem0_config["embedder"] = {
                "provider": "openai",
                "config": {
                    "model": config.get("embedding_model", "text-embedding-3-small"),
                    "api_key": config.get("openai_api_key"),
                },
            }
        elif embedding_provider == "gemini":
            mem0_config["embedder"] = {
                "provider": "google",
                "config": {
                    "model": config.get("embedding_model", "models/text-embedding-004"),
                    "api_key": config.get("gemini_api_key"),
                },
            }

        # Use in-memory vector store for benchmarking
        mem0_config["vector_store"] = {
            "provider": "qdrant",
            "config": {
                "collection_name": "benchmark_mem0",
                "embedding_model_dims": 768 if embedding_provider == "ollama" else 1536,
                "on_disk": False,
            },
        }

        self._client = Memory.from_config(mem0_config)

    def ingest(
        self,
        content: str,
        user_id: str,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        """Ingest content into Mem0."""
        start = time.perf_counter()
        try:
            # Mem0 expects messages format
            messages = [{"role": "user", "content": content}]
            result = self._client.add(messages, user_id=user_id, metadata=metadata)

            memory_id = None
            if result and len(result) > 0:
                memory_id = result[0].get("id") if isinstance(result[0], dict) else None

            duration_ms = (time.perf_counter() - start) * 1000
            return IngestionResult(
                success=True,
                episode_id=memory_id,
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
        strategy: SearchStrategy = SearchStrategy.SEMANTIC,
    ) -> SearchResponse:
        """Search Mem0."""
        start = time.perf_counter()
        try:
            results = self._client.search(
                query=query,
                user_id=user_id,
                limit=limit,
            )

            search_results = []
            for mem in results:
                if isinstance(mem, dict):
                    search_results.append(
                        SearchResult(
                            content=mem.get("memory", mem.get("text", "")),
                            score=mem.get("score", 0.0),
                            metadata={"id": mem.get("id")},
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
        try:
            self._client.delete_all(user_id=user_id)
            return True
        except Exception:
            return False

    def shutdown(self) -> None:
        """Clean up resources."""
        self._client = None
