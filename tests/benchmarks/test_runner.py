"""Unit tests for benchmark runner."""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from typing import List, Any

from benchmarks.config import BenchmarkConfig
from benchmarks.runner import BenchmarkRunner, BenchmarkResult
from benchmarks.adapters.base import (
    IngestionResult,
    SearchResponse,
    SearchResult,
    SearchStrategy,
)


class TestBenchmarkConfig:
    """Test BenchmarkConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = BenchmarkConfig()
        assert config.systems == ["ryumem", "mem0"]
        assert config.dataset_split == "train"
        assert config.question_limit is None
        assert config.search_strategy == "hybrid"
        assert config.llm_provider == "ollama"
        assert config.embedding_provider == "ollama"

    def test_custom_config(self):
        """Test custom configuration."""
        config = BenchmarkConfig(
            systems=["ryumem"],
            question_limit=100,
            search_strategy="semantic",
            llm_provider="openai",
        )
        assert config.systems == ["ryumem"]
        assert config.question_limit == 100
        assert config.search_strategy == "semantic"
        assert config.llm_provider == "openai"

    def test_get_system_config(self):
        """Test getting system-specific configuration."""
        config = BenchmarkConfig(
            llm_provider="ollama",
            llm_model="llama3.2",
            ryumem_url="http://localhost:8000",
        )
        ryumem_config = config.get_system_config("ryumem")
        assert ryumem_config["llm_provider"] == "ollama"
        assert ryumem_config["llm_model"] == "llama3.2"
        assert ryumem_config["server_url"] == "http://localhost:8000"

    def test_to_dict(self):
        """Test config serialization."""
        config = BenchmarkConfig(systems=["ryumem"], question_limit=50)
        config_dict = config.to_dict()
        assert config_dict["systems"] == ["ryumem"]
        assert config_dict["question_limit"] == 50


class TestBenchmarkResult:
    """Test BenchmarkResult dataclass."""

    def test_result_creation(self):
        """Test creating a benchmark result."""
        result = BenchmarkResult(
            system_name="Ryumem",
            system_version="0.6.1",
            accuracy=0.785,
            accuracy_by_type={"single_hop": 0.82, "multi_hop": 0.75},
            mrr=0.82,
            recall_at_1=0.785,
            recall_at_3=0.85,
            recall_at_5=0.90,
            recall_at_10=0.95,
            avg_ingestion_time_ms=120.5,
            avg_search_time_ms=45.2,
            p50_search_time_ms=42.0,
            p95_search_time_ms=125.8,
            p99_search_time_ms=200.0,
            total_ingestion_time_s=60.0,
            total_search_time_s=22.6,
            peak_memory_mb=512.3,
            avg_memory_mb=400.0,
            total_questions=500,
            total_sessions_ingested=2500,
        )

        assert result.system_name == "Ryumem"
        assert result.accuracy == 0.785
        assert result.mrr == 0.82
        assert result.avg_search_time_ms == 45.2


class TestBenchmarkRunner:
    """Test BenchmarkRunner."""

    @patch("benchmarks.runner.register_all_adapters")
    def test_runner_initialization(self, mock_register):
        """Test runner initialization."""
        config = BenchmarkConfig(systems=["ryumem"])
        runner = BenchmarkRunner(config)
        assert runner.config == config
        mock_register.assert_called_once()

    @patch("benchmarks.runner.LoCoMoDataset")
    @patch("benchmarks.runner.AdapterRegistry")
    @patch("benchmarks.runner.register_all_adapters")
    def test_setup(self, mock_register, mock_registry, mock_dataset):
        """Test runner setup."""
        mock_adapter = MagicMock()
        mock_adapter.name = "Ryumem"
        mock_adapter.version = "0.6.1"
        mock_registry.get.return_value = mock_adapter

        config = BenchmarkConfig(systems=["ryumem"], question_limit=10)
        runner = BenchmarkRunner(config)
        runner.setup()

        mock_dataset.assert_called_once_with(
            split="train",
            question_types=None,
            limit=10,
        )
        mock_registry.get.assert_called_with("ryumem")

    @patch("benchmarks.runner.register_all_adapters")
    def test_teardown(self, mock_register):
        """Test runner teardown."""
        mock_adapter = MagicMock()
        config = BenchmarkConfig(systems=["ryumem"])
        runner = BenchmarkRunner(config)
        runner.adapters = {"ryumem": mock_adapter}

        runner.teardown()

        mock_adapter.shutdown.assert_called_once()


class TestProcessQuestion:
    """Test question processing logic."""

    def test_evaluate_correct_answer_at_rank_1(self):
        """Test that correct answer at rank 1 is detected."""
        search_results = [
            SearchResult(content="The answer is Paris, France.", score=0.95),
            SearchResult(content="London is in England.", score=0.8),
        ]

        # Simulating evaluation logic
        correct_answer = "paris"
        correct_rank = None
        for rank, result in enumerate(search_results, 1):
            if correct_answer in result.content.lower():
                correct_rank = rank
                break

        assert correct_rank == 1

    def test_evaluate_correct_answer_at_rank_2(self):
        """Test that correct answer at rank 2 is detected."""
        search_results = [
            SearchResult(content="London is in England.", score=0.95),
            SearchResult(content="The answer is Paris, France.", score=0.8),
        ]

        correct_answer = "paris"
        correct_rank = None
        for rank, result in enumerate(search_results, 1):
            if correct_answer in result.content.lower():
                correct_rank = rank
                break

        assert correct_rank == 2

    def test_evaluate_answer_not_found(self):
        """Test when correct answer is not in results."""
        search_results = [
            SearchResult(content="London is in England.", score=0.95),
            SearchResult(content="Berlin is in Germany.", score=0.8),
        ]

        correct_answer = "paris"
        correct_rank = None
        for rank, result in enumerate(search_results, 1):
            if correct_answer in result.content.lower():
                correct_rank = rank
                break

        assert correct_rank is None
