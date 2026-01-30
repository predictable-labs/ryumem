"""Report generation for benchmark results."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict

from benchmarks.runner import BenchmarkResult


class ReportGenerator:
    """Generates benchmark reports in JSON and Markdown formats."""

    def __init__(
        self,
        results: Dict[str, BenchmarkResult],
        output_dir: str = "./benchmark_reports",
    ):
        """
        Initialize the report generator.

        Args:
            results: Dictionary mapping system names to benchmark results
            output_dir: Directory to save reports
        """
        self.results = results
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    def generate_json(self, include_question_results: bool = False) -> str:
        """
        Generate a JSON report.

        Args:
            include_question_results: Include per-question details (can be large)

        Returns:
            Path to the generated report
        """
        report = {
            "timestamp": self.timestamp,
            "generated_at": datetime.utcnow().isoformat(),
            "systems": {},
        }

        for system_name, result in self.results.items():
            system_report = {
                "name": result.system_name,
                "version": result.system_version,
                "accuracy": {
                    "overall": result.accuracy,
                    "by_type": result.accuracy_by_type,
                    "mrr": result.mrr,
                    "recall_at_1": result.recall_at_1,
                    "recall_at_3": result.recall_at_3,
                    "recall_at_5": result.recall_at_5,
                    "recall_at_10": result.recall_at_10,
                },
                "performance": {
                    "ingestion": {
                        "avg_ms": result.avg_ingestion_time_ms,
                        "total_s": result.total_ingestion_time_s,
                    },
                    "search": {
                        "avg_ms": result.avg_search_time_ms,
                        "p50_ms": result.p50_search_time_ms,
                        "p95_ms": result.p95_search_time_ms,
                        "p99_ms": result.p99_search_time_ms,
                        "total_s": result.total_search_time_s,
                    },
                },
                "memory": {
                    "peak_mb": result.peak_memory_mb,
                    "avg_mb": result.avg_memory_mb,
                },
                "stats": {
                    "total_questions": result.total_questions,
                    "total_sessions_ingested": result.total_sessions_ingested,
                    "error_count": len(result.errors),
                },
                "config": result.config,
            }

            if include_question_results:
                system_report["question_results"] = result.question_results
                system_report["errors"] = result.errors

            report["systems"][system_name] = system_report

        output_path = self.output_dir / f"benchmark_{self.timestamp}.json"
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

        return str(output_path)

    def generate_markdown(self) -> str:
        """
        Generate a Markdown report with summary tables.

        Returns:
            Path to the generated report
        """
        lines = [
            "# Memory System Benchmark Report",
            "",
            f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
        ]

        # Get config from first result
        first_result = next(iter(self.results.values()), None)
        if first_result and first_result.config:
            lines.extend([
                "## Configuration",
                "",
                f"- **Dataset Split:** {first_result.config.get('dataset_split', 'train')}",
                f"- **Question Limit:** {first_result.config.get('question_limit', 'all')}",
                f"- **Question Types:** {first_result.config.get('question_types', 'all')}",
                f"- **Search Strategy:** {first_result.config.get('search_strategy', 'hybrid')}",
                f"- **LLM Provider:** {first_result.config.get('llm_provider', 'ollama')}",
                f"- **Embedding Provider:** {first_result.config.get('embedding_provider', 'ollama')}",
                "",
            ])

        # Summary table
        lines.extend([
            "## Summary",
            "",
            "| System | Version | Accuracy | MRR | Recall@5 | Avg Search (ms) | P95 Search (ms) | Peak Memory (MB) |",
            "|--------|---------|----------|-----|----------|-----------------|-----------------|------------------|",
        ])

        for result in self.results.values():
            lines.append(
                f"| {result.system_name} | {result.system_version} | "
                f"{result.accuracy:.1%} | {result.mrr:.3f} | {result.recall_at_5:.1%} | "
                f"{result.avg_search_time_ms:.1f} | {result.p95_search_time_ms:.1f} | "
                f"{result.peak_memory_mb:.1f} |"
            )

        lines.append("")

        # Accuracy by question type
        lines.extend([
            "## Accuracy by Question Type",
            "",
        ])

        # Get all question types
        all_types = set()
        for result in self.results.values():
            all_types.update(result.accuracy_by_type.keys())
        all_types = sorted(all_types)

        if all_types:
            header = "| System | " + " | ".join(all_types) + " |"
            separator = "|--------|" + "|".join(["------"] * len(all_types)) + "|"
            lines.append(header)
            lines.append(separator)

            for result in self.results.values():
                values = [
                    f"{result.accuracy_by_type.get(t, 0):.1%}" for t in all_types
                ]
                lines.append(f"| {result.system_name} | " + " | ".join(values) + " |")

            lines.append("")

        # Performance details
        lines.extend([
            "## Performance Details",
            "",
            "| System | Avg Ingest (ms) | Total Ingest (s) | Avg Search (ms) | P50 (ms) | P95 (ms) | P99 (ms) |",
            "|--------|-----------------|------------------|-----------------|----------|----------|----------|",
        ])

        for result in self.results.values():
            lines.append(
                f"| {result.system_name} | "
                f"{result.avg_ingestion_time_ms:.1f} | {result.total_ingestion_time_s:.1f} | "
                f"{result.avg_search_time_ms:.1f} | {result.p50_search_time_ms:.1f} | "
                f"{result.p95_search_time_ms:.1f} | {result.p99_search_time_ms:.1f} |"
            )

        lines.append("")

        # Stats
        lines.extend([
            "## Statistics",
            "",
            "| System | Questions | Sessions Ingested | Errors |",
            "|--------|-----------|-------------------|--------|",
        ])

        for result in self.results.values():
            lines.append(
                f"| {result.system_name} | {result.total_questions} | "
                f"{result.total_sessions_ingested} | {len(result.errors)} |"
            )

        lines.append("")

        # Errors summary
        has_errors = any(len(r.errors) > 0 for r in self.results.values())
        if has_errors:
            lines.extend([
                "## Errors",
                "",
            ])
            for result in self.results.values():
                if result.errors:
                    lines.append(f"### {result.system_name}")
                    lines.append("")
                    for error in result.errors[:10]:  # Show first 10 errors
                        lines.append(f"- {error}")
                    if len(result.errors) > 10:
                        lines.append(f"- ... and {len(result.errors) - 10} more errors")
                    lines.append("")

        output_path = self.output_dir / f"benchmark_{self.timestamp}.md"
        with open(output_path, "w") as f:
            f.write("\n".join(lines))

        return str(output_path)

    def generate_detailed_results(self) -> str:
        """
        Generate a detailed markdown report showing per-question results.

        Returns:
            Path to the generated detailed report
        """
        lines = [
            "# Detailed Benchmark Results",
            "",
            f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
        ]

        for system_name, result in self.results.items():
            lines.extend([
                f"# System: {result.system_name} v{result.system_version}",
                "",
                f"**Overall Accuracy:** {result.accuracy:.1%}",
                "",
                "---",
                "",
            ])

            for idx, qr in enumerate(result.question_results, 1):
                status = "✅ CORRECT" if qr.get("correct") else "❌ INCORRECT"
                lines.extend([
                    f"## Question {idx} ({qr.get('question_id')})",
                    "",
                    f"**Status:** {status}",
                    f"**Type:** {qr.get('question_type')}",
                    "",
                    "### Question",
                    f"{qr.get('question')}",
                    "",
                ])

                # Show choices if available
                if qr.get('all_choices'):
                    lines.append("### Choices")
                    for i, choice in enumerate(qr.get('all_choices')):
                        marker = "✓" if choice == qr.get('correct_choice') else " "
                        lines.append(f"{i}. [{marker}] {choice}")
                    lines.append("")

                lines.extend([
                    "### Correct Answer",
                    f"**Answer:** {qr.get('correct_answer')}",
                    f"**Choice:** {qr.get('correct_choice')}",
                    "",
                    "### LLM's Answer",
                    f"**Generated Answer:** {qr.get('llm_answer', 'N/A')}",
                    "",
                ])

                if qr.get('llm_error'):
                    lines.extend([
                        f"**⚠️ LLM Error:** {qr.get('llm_error')}",
                        "",
                    ])

                # Show search results
                lines.extend([
                    "### Retrieved Results",
                    f"**Sessions Ingested:** {qr.get('sessions_ingested', 0)}",
                    f"**Search Time:** {qr.get('search_time_ms', 0):.2f}ms",
                    f"**Results Found:** {qr.get('num_results', 0)}",
                    "",
                ])

                if qr.get('search_error'):
                    lines.extend([
                        f"**⚠️ Search Error:** {qr.get('search_error')}",
                        "",
                    ])

                search_results = qr.get('search_results', [])
                if search_results:
                    correct_answer_lower = qr.get('correct_answer', '').lower().strip()
                    correct_choice_lower = qr.get('correct_choice', '').lower().strip()

                    for rank, sr in enumerate(search_results, 1):
                        content = sr.get('content', '')
                        content_lower = content.lower()

                        # Check if this result contains the answer
                        contains_answer = (
                            correct_answer_lower in content_lower or
                            correct_choice_lower in content_lower
                        )

                        rank_marker = "🎯" if contains_answer else "  "
                        lines.extend([
                            f"#### {rank_marker} Result #{rank} (score: {sr.get('score', 0):.4f})",
                            "```",
                            content[:500] + ("..." if len(content) > 500 else ""),
                            "```",
                            "",
                        ])

                        if contains_answer and rank == qr.get('correct_rank'):
                            lines.append(f"**✓ Answer found at rank {rank}**")
                            lines.append("")
                else:
                    lines.append("*No results returned*")
                    lines.append("")

                lines.extend([
                    "---",
                    "",
                ])

        output_path = self.output_dir / f"benchmark_{self.timestamp}_detailed.md"
        with open(output_path, "w") as f:
            f.write("\n".join(lines))

        return str(output_path)

    def generate_all(self, include_question_results: bool = False) -> Dict[str, str]:
        """
        Generate all report formats.

        Args:
            include_question_results: Include per-question details in JSON

        Returns:
            Dictionary with paths to generated reports
        """
        return {
            "json": self.generate_json(include_question_results),
            "markdown": self.generate_markdown(),
            "detailed": self.generate_detailed_results(),
        }
