"""CLI interface for running benchmarks."""

import click

from benchmarks.adapters.base import SearchStrategy
from benchmarks.adapters.registry import AdapterRegistry, register_all_adapters
from benchmarks.config import BenchmarkConfig
from benchmarks.report import ReportGenerator
from benchmarks.runner import BenchmarkRunner


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Ryumem Benchmark CLI - Compare memory systems using LoCoMo-MC10."""
    pass


@cli.command()
@click.option(
    "--systems",
    "-s",
    multiple=True,
    default=["ryumem", "mem0"],
    help="Memory systems to benchmark (can specify multiple)",
)
@click.option(
    "--limit",
    "-l",
    type=int,
    default=None,
    help="Limit number of questions to process",
)
@click.option(
    "--question-types",
    "-t",
    multiple=True,
    default=None,
    help="Filter by question types (single_hop, multi_hop, temporal_reasoning, open_domain, adversarial)",
)
@click.option(
    "--strategy",
    type=click.Choice(["semantic", "bm25", "hybrid", "traversal"]),
    default="hybrid",
    help="Search strategy to use",
)
@click.option(
    "--output-dir",
    "-o",
    type=str,
    default="./benchmark_reports",
    help="Output directory for reports",
)
# LLM/Embedding provider options (Ollama by default)
@click.option(
    "--llm-provider",
    type=click.Choice(["ollama", "openai", "gemini", "litellm"]),
    default="ollama",
    help="LLM provider for memory extraction",
)
@click.option(
    "--llm-model",
    default="llama3.2",
    help="LLM model name",
)
@click.option(
    "--ollama-url",
    default="http://localhost:11434",
    help="Ollama server URL",
)
@click.option(
    "--embedding-provider",
    type=click.Choice(["ollama", "openai", "gemini"]),
    default="ollama",
    help="Embedding provider",
)
@click.option(
    "--embedding-model",
    default="nomic-embed-text",
    help="Embedding model name",
)
# Optional API keys
@click.option(
    "--openai-api-key",
    envvar="OPENAI_API_KEY",
    default=None,
    help="OpenAI API key (or set OPENAI_API_KEY env var)",
)
@click.option(
    "--gemini-api-key",
    envvar="GEMINI_API_KEY",
    default=None,
    help="Gemini API key (or set GEMINI_API_KEY env var)",
)
@click.option(
    "--zep-api-key",
    envvar="ZEP_API_KEY",
    default=None,
    help="Zep Cloud API key (or set ZEP_API_KEY env var)",
)
# Ryumem specific
@click.option(
    "--ryumem-url",
    default="http://localhost:8000",
    help="Ryumem server URL",
)
@click.option(
    "--ryumem-api-key",
    envvar="RYUMEM_API_KEY",
    default=None,
    help="Ryumem API key",
)
# Additional options
@click.option(
    "--search-limit",
    type=int,
    default=10,
    help="Number of results to retrieve per search",
)
@click.option(
    "--no-clear",
    is_flag=True,
    default=False,
    help="Don't clear data between questions (faster but less isolated)",
)
@click.option(
    "--include-details",
    is_flag=True,
    default=False,
    help="Include per-question details in JSON report",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable verbose output",
)
def run(
    systems,
    limit,
    question_types,
    strategy,
    output_dir,
    llm_provider,
    llm_model,
    ollama_url,
    embedding_provider,
    embedding_model,
    openai_api_key,
    gemini_api_key,
    zep_api_key,
    ryumem_url,
    ryumem_api_key,
    search_limit,
    no_clear,
    include_details,
    verbose,
):
    """Run benchmark comparison across memory systems."""
    click.echo("=" * 60)
    click.echo("Ryumem Benchmark - LoCoMo-MC10")
    click.echo("=" * 60)

    # Build configuration
    config = BenchmarkConfig(
        systems=list(systems),
        question_limit=limit,
        question_types=list(question_types) if question_types else None,
        search_strategy=strategy,
        search_limit=search_limit,
        output_dir=output_dir,
        llm_provider=llm_provider,
        llm_model=llm_model,
        ollama_url=ollama_url,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        openai_api_key=openai_api_key,
        gemini_api_key=gemini_api_key,
        ryumem_url=ryumem_url,
        ryumem_api_key=ryumem_api_key,
        clear_between_questions=not no_clear,
        verbose=verbose,
        system_configs={
            "zep": {"api_key": zep_api_key},
        },
    )

    # Print configuration
    click.echo(f"\nConfiguration:")
    click.echo(f"  Systems: {', '.join(config.systems)}")
    click.echo(f"  Question limit: {config.question_limit or 'all'}")
    click.echo(f"  Question types: {config.question_types or 'all'}")
    click.echo(f"  Search strategy: {config.search_strategy}")
    click.echo(f"  LLM provider: {config.llm_provider} ({config.llm_model})")
    click.echo(f"  Embedding provider: {config.embedding_provider} ({config.embedding_model})")
    click.echo(f"  Output dir: {config.output_dir}")
    click.echo()

    # Run benchmark
    runner = BenchmarkRunner(config)
    try:
        runner.setup()
        results = runner.run()

        # Generate reports
        click.echo("\nGenerating reports...")
        report_gen = ReportGenerator(results, output_dir)
        report_paths = report_gen.generate_all(include_question_results=include_details)

        click.echo(f"\nReports generated:")
        click.echo(f"  JSON: {report_paths['json']}")
        click.echo(f"  Markdown: {report_paths['markdown']}")

        # Print final summary
        click.echo("\n" + "=" * 60)
        click.echo("FINAL SUMMARY")
        click.echo("=" * 60)
        for result in results.values():
            click.echo(f"\n{result.system_name} v{result.system_version}:")
            click.echo(f"  Accuracy: {result.accuracy:.1%}")
            click.echo(f"  MRR: {result.mrr:.3f}")
            click.echo(f"  Recall@5: {result.recall_at_5:.1%}")
            click.echo(f"  Avg Search: {result.avg_search_time_ms:.1f}ms")
            click.echo(f"  P95 Search: {result.p95_search_time_ms:.1f}ms")
            click.echo(f"  Peak Memory: {result.peak_memory_mb:.1f}MB")

    except KeyboardInterrupt:
        click.echo("\n\nBenchmark interrupted by user.")
    except Exception as e:
        click.echo(f"\n\nBenchmark failed with error: {e}")
        raise
    finally:
        runner.teardown()


@cli.command("list-systems")
def list_systems():
    """List available memory system adapters."""
    register_all_adapters()

    click.echo("Available memory systems:")
    for name in AdapterRegistry.list_adapters():
        try:
            adapter = AdapterRegistry.get(name)
            strategies = [s.value for s in adapter.supported_strategies]
            click.echo(f"  - {name}: {adapter.name} (strategies: {', '.join(strategies)})")
        except Exception as e:
            click.echo(f"  - {name}: (error loading: {e})")


@cli.command("info")
@click.argument("system")
def system_info(system):
    """Show detailed information about a memory system adapter."""
    register_all_adapters()

    try:
        adapter = AdapterRegistry.get(system)
        click.echo(f"\n{adapter.name}")
        click.echo("=" * len(adapter.name))
        click.echo(f"Version: {adapter.version}")
        click.echo(f"Supported strategies: {', '.join(s.value for s in adapter.supported_strategies)}")
    except ValueError as e:
        click.echo(f"Error: {e}")


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
