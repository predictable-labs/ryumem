"""Zep memory system adapter."""

import time
import uuid
from typing import Any, Dict, List, Optional

from benchmarks.adapters.base import (
    MemorySystemAdapter,
    IngestionResult,
    SearchResponse,
    SearchResult,
    SearchStrategy,
)


class ZepAdapter(MemorySystemAdapter):
    """Adapter for Zep memory system (Cloud or self-hosted)."""

    def __init__(self):
        self._client = None
        self._config: Dict[str, Any] = {}
        self._sessions: Dict[str, str] = {}  # user_id -> session_id

    @property
    def name(self) -> str:
        return "Zep"

    @property
    def version(self) -> str:
        try:
            from importlib.metadata import version
            return version("zep-cloud")
        except Exception:
            try:
                from importlib.metadata import version
                return version("zep-python")
            except Exception:
                return "unknown"

    @property
    def supported_strategies(self) -> List[SearchStrategy]:
        return [SearchStrategy.SEMANTIC]

    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize Zep client."""
        self._config = config

        api_key = config.get("api_key") or config.get("zep_api_key")

        if api_key:
            # Use Zep Cloud
            try:
                from zep_cloud.client import Zep
                self._client = Zep(api_key=api_key)
                self._use_cloud = True
            except ImportError:
                raise ImportError(
                    "zep-cloud package not installed. Install with: pip install zep-cloud"
                )
        else:
            # Fall back to self-hosted (requires zep-python)
            try:
                from zep_python import ZepClient
                base_url = config.get("zep_url", "http://localhost:8000")
                self._client = ZepClient(base_url=base_url)
                self._use_cloud = False
            except ImportError:
                raise ImportError(
                    "Zep requires an API key for Cloud or zep-python for self-hosted. "
                    "Set ZEP_API_KEY env var or install zep-python."
                )

    def _get_or_create_session(self, user_id: str) -> str:
        """Get or create a session for a user."""
        if user_id not in self._sessions:
            session_id = f"bench_{user_id}_{uuid.uuid4().hex[:8]}"
            self._sessions[user_id] = session_id

            if self._use_cloud:
                try:
                    from zep_cloud.types import Session
                    self._client.memory.add_session(
                        session_id=session_id,
                        user_id=user_id,
                    )
                except Exception:
                    pass  # Session may already exist
            else:
                try:
                    from zep_python.memory import Session
                    self._client.memory.add_session(
                        Session(session_id=session_id, user_id=user_id)
                    )
                except Exception:
                    pass

        return self._sessions[user_id]

    def ingest(
        self,
        content: str,
        user_id: str,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        """Ingest content into Zep."""
        start = time.perf_counter()
        try:
            zep_session_id = self._get_or_create_session(user_id)

            if self._use_cloud:
                from zep_cloud.types import Message
                message = Message(
                    role="user",
                    role_type="user",
                    content=content,
                    metadata=metadata,
                )
                self._client.memory.add(session_id=zep_session_id, messages=[message])
            else:
                from zep_python.memory import Memory, Message
                message = Message(
                    role="user",
                    content=content,
                    metadata=metadata,
                )
                self._client.memory.add_memory(
                    session_id=zep_session_id,
                    memory=Memory(messages=[message]),
                )

            duration_ms = (time.perf_counter() - start) * 1000
            return IngestionResult(
                success=True,
                episode_id=zep_session_id,
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
        """Search Zep."""
        start = time.perf_counter()
        try:
            if user_id not in self._sessions:
                duration_ms = (time.perf_counter() - start) * 1000
                return SearchResponse(results=[], duration_ms=duration_ms)

            zep_session_id = self._sessions[user_id]

            if self._use_cloud:
                results = self._client.memory.search(
                    session_id=zep_session_id,
                    text=query,
                    limit=limit,
                )
            else:
                from zep_python.memory import MemorySearchPayload
                results = self._client.memory.search_memory(
                    session_id=zep_session_id,
                    search_payload=MemorySearchPayload(text=query),
                    limit=limit,
                )

            search_results = []
            for result in results:
                content = ""
                score = 0.0

                if hasattr(result, "message"):
                    content = result.message.content if result.message else ""
                elif hasattr(result, "content"):
                    content = result.content

                if hasattr(result, "score"):
                    score = result.score or 0.0
                elif hasattr(result, "dist"):
                    score = 1.0 - (result.dist or 0.0)

                if content:
                    search_results.append(
                        SearchResult(
                            content=content,
                            score=score,
                            metadata={},
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
            if user_id in self._sessions:
                session_id = self._sessions[user_id]
                if self._use_cloud:
                    self._client.memory.delete(session_id=session_id)
                else:
                    self._client.memory.delete_memory(session_id=session_id)
                del self._sessions[user_id]
            return True
        except Exception:
            return False

    def shutdown(self) -> None:
        """Clean up resources."""
        self._client = None
        self._sessions = {}
