"""Benchmark runner that orchestrates benchmarking across memory systems."""

import tracemalloc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from tqdm import tqdm

from benchmarks.adapters.base import MemorySystemAdapter, SearchStrategy
from benchmarks.adapters.registry import AdapterRegistry, register_all_adapters
from benchmarks.config import BenchmarkConfig
from benchmarks.datasets.locomo import LoCoMoDataset, LoCoMoQuestion
from benchmarks.llm_client import LLMClient
from benchmarks.metrics.accuracy import AccuracyMetrics
from benchmarks.metrics.memory import MemoryMetrics
from benchmarks.metrics.performance import PerformanceMetrics


@dataclass
class BenchmarkResult:
    """Results from running a benchmark on a single system."""

    system_name: str
    system_version: str

    # Accuracy metrics
    accuracy: float
    accuracy_by_type: Dict[str, float]
    mrr: float
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    recall_at_10: float

    # Performance metrics
    avg_ingestion_time_ms: float
    avg_search_time_ms: float
    p50_search_time_ms: float
    p95_search_time_ms: float
    p99_search_time_ms: float
    total_ingestion_time_s: float
    total_search_time_s: float

    # Memory metrics
    peak_memory_mb: float
    avg_memory_mb: float

    # Details
    total_questions: int
    total_sessions_ingested: int
    question_results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""


class BenchmarkRunner:
    """Orchestrates benchmarking across memory systems."""

    def __init__(self, config: BenchmarkConfig):
        """
        Initialize the benchmark runner.

        Args:
            config: Benchmark configuration
        """
        self.config = config
        self.dataset: Optional[LoCoMoDataset] = None
        self.adapters: Dict[str, MemorySystemAdapter] = {}
        self.results: Dict[str, BenchmarkResult] = {}

        # Initialize LLM client for answering questions
        # Supports "google_adk" (reads GOOGLE_API_KEY from env) or "ollama"
        self.llm_client = LLMClient(
            provider=config.llm_provider if config.llm_provider in ["google_adk", "ollama"] else "google_adk",
            model=config.llm_model,
            ollama_url=config.ollama_url,
            rate_limit_delay=config.rate_limit_delay,
        )

        # Register all adapters
        register_all_adapters()

    def setup(self) -> None:
        """Load dataset and initialize adapters."""
        # Load dataset
        print("Setting up benchmark...")
        self.dataset = LoCoMoDataset(
            split=self.config.dataset_split,
            question_types=self.config.question_types,
            limit=self.config.question_limit,
        )
        self.dataset.load()

        # Initialize adapters
        for system_name in self.config.systems:
            print(f"Initializing {system_name}...")
            try:
                adapter = AdapterRegistry.get(system_name)
                adapter.initialize(self.config.get_system_config(system_name))
                self.adapters[system_name] = adapter
                print(f"  {adapter.name} v{adapter.version} initialized")
            except Exception as e:
                print(f"  Failed to initialize {system_name}: {e}")

    def run(self) -> Dict[str, BenchmarkResult]:
        """
        Run benchmarks for all configured systems.

        Returns:
            Dictionary mapping system names to their benchmark results
        """
        for system_name, adapter in self.adapters.items():
            print(f"\n{'='*60}")
            print(f"Benchmarking: {adapter.name} v{adapter.version}")
            print(f"{'='*60}")

            result = self._benchmark_system(system_name, adapter)
            self.results[system_name] = result

            # Print summary
            print(f"\nResults for {adapter.name}:")
            print(f"  Accuracy: {result.accuracy:.2%}")
            print(f"  MRR: {result.mrr:.3f}")
            print(f"  Avg Search Time: {result.avg_search_time_ms:.1f}ms")
            print(f"  P95 Search Time: {result.p95_search_time_ms:.1f}ms")
            print(f"  Peak Memory: {result.peak_memory_mb:.1f}MB")

        return self.results

    def _benchmark_system(
        self, system_name: str, adapter: MemorySystemAdapter
    ) -> BenchmarkResult:
        """
        Run benchmark for a single system.

        Args:
            system_name: Name of the system
            adapter: Adapter instance

        Returns:
            BenchmarkResult with all metrics
        """
        # Initialize metrics collectors
        accuracy_metrics = AccuracyMetrics()
        performance_metrics = PerformanceMetrics()
        memory_metrics = MemoryMetrics()
        errors: List[str] = []
        question_results: List[Dict[str, Any]] = []
        total_sessions_ingested = 0

        # Start memory tracing
        memory_metrics.start_tracing()

        # Determine search strategy
        strategy_str = self.config.search_strategy.upper()
        try:
            search_strategy = SearchStrategy[strategy_str]
        except KeyError:
            search_strategy = SearchStrategy.HYBRID

        # Check if adapter supports the strategy
        if search_strategy not in adapter.supported_strategies:
            print(f"  Warning: {adapter.name} doesn't support {strategy_str}, using SEMANTIC")
            search_strategy = SearchStrategy.SEMANTIC

        # Process each question
        for question in tqdm(self.dataset, desc=f"Processing {system_name}"):
            try:
                result = self._process_question(
                    adapter, question, performance_metrics, search_strategy
                )

                # Check for critical failures and exit early
                if result.get("search_error"):
                    raise RuntimeError(
                        f"Search failed for question {question.question_id}: {result['search_error']}"
                    )

                if result.get("llm_error"):
                    raise RuntimeError(
                        f"LLM call failed for question {question.question_id}: {result['llm_error']}"
                    )

                question_results.append(result)

                # Update accuracy metrics
                accuracy_metrics.add_result(
                    correct=result["correct"],
                    question_type=question.question_type,
                    rank=result.get("correct_rank"),
                )

                total_sessions_ingested += result.get("sessions_ingested", 0)

                # Sample memory periodically
                memory_metrics.sample()

            except Exception as e:
                errors.append(f"Question {question.question_id}: {str(e)}")
                # Re-raise to fail fast
                raise

            finally:
                # Clear data between questions if configured
                if self.config.clear_between_questions:
                    adapter.clear(user_id=question.question_id)

        # Stop memory tracing
        memory_metrics.stop_tracing()

        # Build result
        accuracy_summary = accuracy_metrics.get_summary()
        performance_summary = performance_metrics.get_summary()
        memory_summary = memory_metrics.get_summary()

        return BenchmarkResult(
            system_name=adapter.name,
            system_version=adapter.version,
            accuracy=accuracy_summary["accuracy"],
            accuracy_by_type=accuracy_summary["accuracy_by_type"],
            mrr=accuracy_summary["mrr"],
            recall_at_1=accuracy_summary["recall_at_1"],
            recall_at_3=accuracy_summary["recall_at_3"],
            recall_at_5=accuracy_summary["recall_at_5"],
            recall_at_10=accuracy_summary["recall_at_10"],
            avg_ingestion_time_ms=performance_summary["ingestion"]["avg_ms"],
            avg_search_time_ms=performance_summary["search"]["avg_ms"],
            p50_search_time_ms=performance_summary["search"]["p50_ms"],
            p95_search_time_ms=performance_summary["search"]["p95_ms"],
            p99_search_time_ms=performance_summary["search"]["p99_ms"],
            total_ingestion_time_s=performance_summary["ingestion"]["total_s"],
            total_search_time_s=performance_summary["search"]["total_s"],
            peak_memory_mb=memory_summary["peak_mb"],
            avg_memory_mb=memory_summary["avg_mb"],
            total_questions=accuracy_summary["total_questions"],
            total_sessions_ingested=total_sessions_ingested,
            question_results=question_results,
            errors=errors,
            config=self.config.to_dict(),
            timestamp=datetime.utcnow().isoformat(),
        )

    def _process_question(
        self,
        adapter: MemorySystemAdapter,
        question: LoCoMoQuestion,
        performance_metrics: PerformanceMetrics,
        search_strategy: SearchStrategy,
    ) -> Dict[str, Any]:
        """
        Process a single question: ingest sessions, search, evaluate.

        Args:
            adapter: Memory system adapter
            question: Question to process
            performance_metrics: Metrics collector
            search_strategy: Strategy to use for search

        Returns:
            Dictionary with question results
        """
        user_id = question.question_id

        # Ingest conversation sessions
        conversations = self.dataset.format_sessions_as_conversations(question)
        sessions_ingested = 0

        for idx, conversation in enumerate(conversations):
            if conversation.strip():  # Skip empty conversations
                result = adapter.ingest(
                    content=conversation,
                    user_id=user_id,
                    session_id=f"session_{idx}",
                    metadata={"question_id": question.question_id},
                )
                performance_metrics.add_ingestion_time(result.duration_ms)
                if result.success:
                    sessions_ingested += 1

        # Search for answer
        search_response = adapter.search(
            query=question.question,
            user_id=user_id,
            limit=self.config.search_limit,
            strategy=search_strategy,
        )
        performance_metrics.add_search_time(search_response.duration_ms)

        # Use LLM to answer the question based on retrieved context
        context_episodes = [result.content for result in search_response.results]
        llm_answer = ""
        llm_error = None

        if context_episodes:
            try:
                llm_answer = self.llm_client.answer_question(
                    question=question.question,
                    context_episodes=context_episodes,
                    choices=question.choices,
                    user_id=user_id,
                    session_id="benchmark",
                )
            except Exception as e:
                llm_error = str(e)
                llm_answer = ""

        # Evaluate LLM's answer
        correct_answer = question.answer.lower().strip()
        correct_choice_text = question.choices[question.correct_choice_index].lower().strip()
        llm_answer_lower = llm_answer.lower().strip()

        # Check if LLM's answer matches the correct answer
        is_correct = (
            correct_answer in llm_answer_lower or
            correct_choice_text in llm_answer_lower or
            llm_answer_lower in correct_choice_text
        )

        # Also check which rank contains the correct answer (for recall metrics)
        correct_rank = None
        for rank, result in enumerate(search_response.results, 1):
            content_lower = result.content.lower()
            if correct_answer in content_lower or correct_choice_text in content_lower:
                correct_rank = rank
                break

        return {
            "question_id": question.question_id,
            "question": question.question,
            "question_type": question.question_type,
            "correct_answer": question.answer,
            "correct_choice": question.choices[question.correct_choice_index],
            "all_choices": question.choices,
            "llm_answer": llm_answer,
            "correct": is_correct,
            "correct_rank": correct_rank,
            "search_time_ms": search_response.duration_ms,
            "sessions_ingested": sessions_ingested,
            "num_results": len(search_response.results),
            "search_results": [
                {"content": r.content, "score": r.score}
                for r in search_response.results
            ],
            "search_error": search_response.error,
            "llm_error": llm_error,
        }

    def teardown(self) -> None:
        """Clean up adapters."""
        print("\nCleaning up...")
        for system_name, adapter in self.adapters.items():
            try:
                adapter.shutdown()
                print(f"  {system_name} shutdown complete")
            except Exception as e:
                print(f"  {system_name} shutdown error: {e}")
