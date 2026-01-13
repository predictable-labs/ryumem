"""LangChain memory system adapter using FAISS vector store."""

import time
from typing import Any, Dict, List, Optional

from benchmarks.adapters.base import (
    MemorySystemAdapter,
    IngestionResult,
    SearchResponse,
    SearchResult,
    SearchStrategy,
)


class LangChainAdapter(MemorySystemAdapter):
    """Adapter for LangChain memory with FAISS vector store."""

    def __init__(self):
        self._vectorstore = None
        self._embeddings = None
        self._config: Dict[str, Any] = {}
        self._documents: Dict[str, List] = {}  # user_id -> documents

    @property
    def name(self) -> str:
        return "LangChain"

    @property
    def version(self) -> str:
        try:
            from importlib.metadata import version
            return version("langchain")
        except Exception:
            return "unknown"

    @property
    def supported_strategies(self) -> List[SearchStrategy]:
        return [SearchStrategy.SEMANTIC]

    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize LangChain with embeddings."""
        self._config = config
        embedding_provider = config.get("embedding_provider", "ollama")

        # Configure embeddings based on provider
        if embedding_provider == "ollama":
            from langchain_ollama import OllamaEmbeddings
            self._embeddings = OllamaEmbeddings(
                model=config.get("embedding_model", "nomic-embed-text"),
                base_url=config.get("ollama_url", "http://localhost:11434"),
            )
        elif embedding_provider == "openai":
            from langchain_openai import OpenAIEmbeddings
            self._embeddings = OpenAIEmbeddings(
                model=config.get("embedding_model", "text-embedding-3-small"),
                openai_api_key=config.get("openai_api_key"),
            )
        elif embedding_provider == "gemini":
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            self._embeddings = GoogleGenerativeAIEmbeddings(
                model=config.get("embedding_model", "models/text-embedding-004"),
                google_api_key=config.get("gemini_api_key"),
            )
        else:
            # Fallback to Ollama
            from langchain_ollama import OllamaEmbeddings
            self._embeddings = OllamaEmbeddings(
                model="nomic-embed-text",
                base_url="http://localhost:11434",
            )

        # Initialize empty vectorstores dict
        self._vectorstores: Dict[str, Any] = {}

    def _get_or_create_vectorstore(self, user_id: str):
        """Get or create a vectorstore for a user."""
        if user_id not in self._vectorstores:
            from langchain_community.vectorstores import FAISS
            from langchain_core.documents import Document

            # Create with a placeholder document
            placeholder = Document(page_content="placeholder", metadata={"user_id": user_id})
            self._vectorstores[user_id] = FAISS.from_documents([placeholder], self._embeddings)
            self._documents[user_id] = []
        return self._vectorstores[user_id]

    def ingest(
        self,
        content: str,
        user_id: str,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        """Ingest content into LangChain FAISS."""
        from langchain_core.documents import Document

        start = time.perf_counter()
        try:
            doc_metadata = {
                "user_id": user_id,
                "session_id": session_id,
                **(metadata or {}),
            }
            doc = Document(page_content=content, metadata=doc_metadata)

            vectorstore = self._get_or_create_vectorstore(user_id)
            vectorstore.add_documents([doc])

            # Track for clearing
            if user_id not in self._documents:
                self._documents[user_id] = []
            self._documents[user_id].append(doc)

            duration_ms = (time.perf_counter() - start) * 1000
            return IngestionResult(
                success=True,
                episode_id=f"doc_{len(self._documents[user_id])}",
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
        """Search LangChain FAISS."""
        start = time.perf_counter()
        try:
            if user_id not in self._vectorstores:
                duration_ms = (time.perf_counter() - start) * 1000
                return SearchResponse(results=[], duration_ms=duration_ms)

            vectorstore = self._vectorstores[user_id]
            results = vectorstore.similarity_search_with_score(query, k=limit)

            search_results = []
            for doc, score in results:
                # Skip placeholder documents
                if doc.page_content == "placeholder":
                    continue
                search_results.append(
                    SearchResult(
                        content=doc.page_content,
                        score=1.0 - score,  # Convert distance to similarity
                        metadata=doc.metadata,
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
            if user_id in self._vectorstores:
                del self._vectorstores[user_id]
            if user_id in self._documents:
                del self._documents[user_id]
            return True
        except Exception:
            return False

    def shutdown(self) -> None:
        """Clean up resources."""
        self._vectorstores = {}
        self._documents = {}
        self._embeddings = None
