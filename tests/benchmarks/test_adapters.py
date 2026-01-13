"""Unit tests for benchmark adapters."""

import pytest
from unittest.mock import MagicMock, patch

from benchmarks.adapters.base import (
    MemorySystemAdapter,
    SearchStrategy,
    IngestionResult,
    SearchResult,
    SearchResponse,
)
from benchmarks.adapters.registry import AdapterRegistry, register_all_adapters


class TestSearchStrategy:
    """Test SearchStrategy enum."""

    def test_strategy_values(self):
        """Test all strategy values are defined."""
        assert SearchStrategy.SEMANTIC.value == "semantic"
        assert SearchStrategy.BM25.value == "bm25"
        assert SearchStrategy.HYBRID.value == "hybrid"
        assert SearchStrategy.TRAVERSAL.value == "traversal"


class TestDataclasses:
    """Test result dataclasses."""

    def test_ingestion_result(self):
        """Test IngestionResult dataclass."""
        result = IngestionResult(success=True, episode_id="ep_123", duration_ms=50.5)
        assert result.success is True
        assert result.episode_id == "ep_123"
        assert result.duration_ms == 50.5
        assert result.error is None

    def test_ingestion_result_with_error(self):
        """Test IngestionResult with error."""
        result = IngestionResult(success=False, error="Connection failed", duration_ms=10.0)
        assert result.success is False
        assert result.error == "Connection failed"

    def test_search_result(self):
        """Test SearchResult dataclass."""
        result = SearchResult(content="test content", score=0.95, metadata={"key": "value"})
        assert result.content == "test content"
        assert result.score == 0.95
        assert result.metadata == {"key": "value"}

    def test_search_response(self):
        """Test SearchResponse dataclass."""
        results = [SearchResult(content="result 1", score=0.9)]
        response = SearchResponse(results=results, duration_ms=25.0)
        assert len(response.results) == 1
        assert response.duration_ms == 25.0
        assert response.error is None


class TestAdapterRegistry:
    """Test adapter registry."""

    def test_register_all_adapters(self):
        """Test that all adapters are registered."""
        register_all_adapters()
        adapters = AdapterRegistry.list_adapters()
        assert "ryumem" in adapters
        assert "mem0" in adapters
        assert "langchain" in adapters
        assert "zep" in adapters

    def test_get_adapter(self):
        """Test getting an adapter by name."""
        register_all_adapters()
        adapter = AdapterRegistry.get("ryumem")
        assert adapter.name == "Ryumem"

    def test_get_adapter_case_insensitive(self):
        """Test adapter lookup is case insensitive."""
        register_all_adapters()
        adapter = AdapterRegistry.get("RYUMEM")
        assert adapter.name == "Ryumem"

    def test_get_unknown_adapter(self):
        """Test getting unknown adapter raises error."""
        register_all_adapters()
        with pytest.raises(ValueError, match="Unknown adapter"):
            AdapterRegistry.get("unknown_system")

    def test_is_registered(self):
        """Test checking if adapter is registered."""
        register_all_adapters()
        assert AdapterRegistry.is_registered("ryumem") is True
        assert AdapterRegistry.is_registered("unknown") is False


class TestRyumemAdapter:
    """Test Ryumem adapter."""

    def test_adapter_properties(self):
        """Test adapter name and supported strategies."""
        register_all_adapters()
        adapter = AdapterRegistry.get("ryumem")
        assert adapter.name == "Ryumem"
        assert SearchStrategy.SEMANTIC in adapter.supported_strategies
        assert SearchStrategy.BM25 in adapter.supported_strategies
        assert SearchStrategy.HYBRID in adapter.supported_strategies
        assert SearchStrategy.TRAVERSAL in adapter.supported_strategies

    @patch("ryumem.Ryumem")
    def test_initialize(self, mock_ryumem_class):
        """Test adapter initialization."""
        register_all_adapters()
        adapter = AdapterRegistry.get("ryumem")
        config = {"server_url": "http://test:8000", "api_key": "test-key"}
        adapter.initialize(config)
        mock_ryumem_class.assert_called_once_with(
            server_url="http://test:8000",
            api_key="test-key",
        )

    @patch("ryumem.Ryumem")
    def test_ingest(self, mock_ryumem_class):
        """Test content ingestion."""
        mock_client = MagicMock()
        mock_client.add_episode.return_value = "ep_123"
        mock_ryumem_class.return_value = mock_client

        register_all_adapters()
        adapter = AdapterRegistry.get("ryumem")
        adapter.initialize({})

        result = adapter.ingest(
            content="test content",
            user_id="user_1",
            session_id="session_1",
            metadata={"key": "value"},
        )

        assert result.success is True
        assert result.episode_id == "ep_123"
        assert result.duration_ms > 0

    @patch("ryumem.Ryumem")
    def test_search(self, mock_ryumem_class):
        """Test search functionality."""
        mock_episode = MagicMock()
        mock_episode.content = "found content"
        mock_episode.uuid = "ep_123"

        mock_result = MagicMock()
        mock_result.episodes = [mock_episode]
        mock_result.scores = {"ep_123": 0.95}

        mock_client = MagicMock()
        mock_client.search.return_value = mock_result
        mock_ryumem_class.return_value = mock_client

        register_all_adapters()
        adapter = AdapterRegistry.get("ryumem")
        adapter.initialize({})

        response = adapter.search(
            query="test query",
            user_id="user_1",
            limit=10,
            strategy=SearchStrategy.HYBRID,
        )

        assert len(response.results) == 1
        assert response.results[0].content == "found content"
        assert response.duration_ms > 0


class TestMem0Adapter:
    """Test Mem0 adapter."""

    def test_adapter_properties(self):
        """Test adapter name and supported strategies."""
        register_all_adapters()
        adapter = AdapterRegistry.get("mem0")
        assert adapter.name == "Mem0"
        assert SearchStrategy.SEMANTIC in adapter.supported_strategies
        assert len(adapter.supported_strategies) == 1  # Only semantic

    def test_initialize_with_ollama(self):
        """Test initialization with Ollama provider."""
        mem0 = pytest.importorskip("mem0")
        with patch.object(mem0, "Memory") as mock_memory_class:
            register_all_adapters()
            adapter = AdapterRegistry.get("mem0")
            config = {
                "llm_provider": "ollama",
                "llm_model": "llama3.2",
                "ollama_url": "http://localhost:11434",
                "embedding_provider": "ollama",
                "embedding_model": "nomic-embed-text",
            }
            adapter.initialize(config)
            mock_memory_class.from_config.assert_called_once()


class TestLangChainAdapter:
    """Test LangChain adapter."""

    def test_adapter_properties(self):
        """Test adapter name and supported strategies."""
        register_all_adapters()
        adapter = AdapterRegistry.get("langchain")
        assert adapter.name == "LangChain"
        assert SearchStrategy.SEMANTIC in adapter.supported_strategies
        assert len(adapter.supported_strategies) == 1


class TestZepAdapter:
    """Test Zep adapter."""

    def test_adapter_properties(self):
        """Test adapter name and supported strategies."""
        register_all_adapters()
        adapter = AdapterRegistry.get("zep")
        assert adapter.name == "Zep"
        assert SearchStrategy.SEMANTIC in adapter.supported_strategies
        assert len(adapter.supported_strategies) == 1
