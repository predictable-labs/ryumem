"""Benchmark configuration using Pydantic."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class BenchmarkConfig(BaseSettings):
    """Configuration for benchmark runs."""

    # Systems to benchmark
    systems: List[str] = Field(
        default=["ryumem", "mem0"],
        description="Memory systems to benchmark",
    )

    # Dataset configuration
    dataset_split: str = Field(default="train", description="Dataset split to use")
    question_limit: Optional[int] = Field(
        default=None, description="Limit number of questions (None = all)"
    )
    question_types: Optional[List[str]] = Field(
        default=None,
        description="Filter by question types (single_hop, multi_hop, temporal_reasoning, open_domain, adversarial)",
    )

    # Search configuration
    search_strategy: str = Field(
        default="hybrid",
        description="Search strategy (semantic, bm25, hybrid, traversal)",
    )
    search_limit: int = Field(default=10, description="Number of results to retrieve")

    # LLM provider configuration (Google ADK by default)
    llm_provider: Literal["google_adk", "ollama", "openai", "gemini", "litellm"] = Field(
        default="google_adk", description="LLM provider"
    )
    llm_model: str = Field(default="gemini-flash-lite-latest", description="LLM model name")
    ollama_url: str = Field(
        default="http://localhost:11434", description="Ollama server URL"
    )

    # Embedding provider configuration
    embedding_provider: Literal["ollama", "openai", "gemini"] = Field(
        default="ollama", description="Embedding provider"
    )
    embedding_model: str = Field(
        default="nomic-embed-text", description="Embedding model name"
    )

    # Optional API keys (can use env vars)
    openai_api_key: Optional[str] = Field(
        default=None, description="OpenAI API key (or use OPENAI_API_KEY env var)"
    )
    gemini_api_key: Optional[str] = Field(
        default=None, description="Gemini API key (or use GEMINI_API_KEY env var)"
    )

    # Ryumem specific configuration
    ryumem_url: str = Field(
        default="http://localhost:8000", description="Ryumem server URL"
    )
    ryumem_api_key: Optional[str] = Field(
        default=None, description="Ryumem API key"
    )

    # Zep configuration
    zep_api_key: Optional[str] = Field(
        default=None, description="Zep Cloud API key (or use ZEP_API_KEY env var)"
    )

    # Output configuration
    output_dir: str = Field(
        default="./benchmark_reports", description="Output directory for reports"
    )

    # Benchmark behavior
    clear_between_questions: bool = Field(
        default=True, description="Clear memory between questions for isolation"
    )
    verbose: bool = Field(default=False, description="Enable verbose output")
    rate_limit_delay: float = Field(
        default=1.0, description="Delay in seconds between LLM API calls"
    )

    # Per-system configuration overrides
    system_configs: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Per-system configuration overrides"
    )

    class Config:
        env_prefix = "BENCHMARK_"
        env_file = ".env"
        extra = "ignore"

    def get_system_config(self, system_name: str) -> Dict[str, Any]:
        """Get configuration for a specific system, merging with defaults."""
        base_config = {
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "ollama_url": self.ollama_url,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
            "openai_api_key": self.openai_api_key,
            "gemini_api_key": self.gemini_api_key,
        }

        # Add system-specific defaults
        if system_name == "ryumem":
            base_config["server_url"] = self.ryumem_url
            base_config["api_key"] = self.ryumem_api_key
        elif system_name == "zep":
            base_config["api_key"] = self.zep_api_key

        # Merge with system-specific overrides
        if system_name in self.system_configs:
            base_config.update(self.system_configs[system_name])

        return base_config

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for serialization."""
        return {
            "systems": self.systems,
            "dataset_split": self.dataset_split,
            "question_limit": self.question_limit,
            "question_types": self.question_types,
            "search_strategy": self.search_strategy,
            "search_limit": self.search_limit,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
            "clear_between_questions": self.clear_between_questions,
        }
