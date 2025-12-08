"""
Configuration management for Ryumem Server using pydantic-settings

Server config extends client config with server-specific settings (LLM, Embedding, System).
"""

import logging
from typing import Literal, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Import shared configs from client (configs that client uses locally)
from ryumem.core.config import (
    EntityExtractionConfig,
    ToolTrackingConfig,
    AgentConfig,
)

logger = logging.getLogger(__name__)


class DatabaseConfig(BaseSettings):
    """Database configuration"""

    db_path: str = Field(
        default="./data/ryumem.db",
        description="Path to ryugraph database directory"
    )

    model_config = SettingsConfigDict(env_prefix="RYUMEM_")


class LLMConfig(BaseSettings):
    """LLM provider configuration"""

    provider: Literal["openai", "ollama", "gemini", "litellm"] = Field(
        default="ollama",
        description="LLM provider: 'openai', 'ollama', 'gemini', or 'litellm'"
    )
    model: str = Field(
        default="qwen2.5:7b",
        description="LLM model to use (e.g., 'gpt-4o-mini' for OpenAI, 'qwen2.5:7b' for Ollama, 'gemini-2.0-flash-exp' for Gemini)"
    )

    # API Keys
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key (required if provider='openai')",
        validation_alias="OPENAI_API_KEY"
    )
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Google API key (required if provider='gemini')",
        validation_alias="GOOGLE_API_KEY"
    )

    # Ollama settings
    ollama_base_url: str = Field(
        default="http://100.108.18.43:11434",
        description="Ollama server URL"
    )

    # Temperature settings for different operations
    entity_extraction_temperature: float = Field(
        default=0.3,
        description="Temperature for entity extraction LLM calls",
        ge=0.0,
        le=2.0
    )
    relation_extraction_temperature: float = Field(
        default=0.3,
        description="Temperature for relationship extraction LLM calls",
        ge=0.0,
        le=2.0
    )
    tool_summarization_temperature: float = Field(
        default=0.3,
        description="Temperature for tool output summarization",
        ge=0.0,
        le=2.0
    )

    # Max tokens settings
    entity_extraction_max_tokens: int = Field(
        default=2000,
        description="Maximum tokens for entity extraction responses",
        gt=0
    )
    relation_extraction_max_tokens: int = Field(
        default=2000,
        description="Maximum tokens for relationship extraction responses",
        gt=0
    )
    tool_summarization_max_tokens: int = Field(
        default=100,
        description="Maximum tokens for tool output summaries",
        gt=0
    )

    # Timeouts and retries
    timeout_seconds: int = Field(
        default=180,
        description="Timeout for LLM API calls in seconds (increased for remote Ollama servers)",
        gt=0
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retries for LLM API calls",
        ge=0
    )

    model_config = SettingsConfigDict(
        env_prefix="RYUMEM_LLM_",
        env_nested_delimiter="__"
    )


class EmbeddingConfig(BaseSettings):
    """Embedding configuration"""

    provider: Literal["openai", "gemini", "ollama", "litellm"] = Field(
        default="ollama",
        description="Embedding provider: 'openai', 'gemini', 'ollama', or 'litellm'"
    )
    model: str = Field(
        default="nomic-embed-text",
        description="Embedding model to use (e.g., 'nomic-embed-text' for Ollama)"
    )

    # Ollama settings
    ollama_base_url: str = Field(
        default="http://100.108.18.43:11434",
        description="Ollama server URL for embeddings"
    )

    dimensions: int = Field(
        default=768,
        description="Embedding vector dimensions (text-embedding-3-large=3072, text-embedding-004=768, nomic-embed-text=768)"
    )
    batch_size: int = Field(
        default=100,
        description="Batch size for embedding operations",
        gt=0
    )
    timeout_seconds: int = Field(
        default=180,
        description="Timeout for embedding API calls in seconds",
        gt=0
    )

    model_config = SettingsConfigDict(
        env_prefix="RYUMEM_EMBEDDING_",
        env_nested_delimiter="__"
    )

    @field_validator("model")
    @classmethod
    def validate_embedding_model(cls, v: str) -> str:
        """Validate embedding model name based on provider"""
        # LiteLLM supports many models, so we allow any model name
        # Will be validated at runtime by the provider
        return v

    @model_validator(mode='after')
    def validate_dimensions(self) -> 'EmbeddingConfig':
        """Validate embedding dimensions match the model"""
        # Skip validation for LiteLLM - it supports many models with different dimensions
        if self.provider == "litellm":
            return self

        expected_dims = {
            "text-embedding-3-large": 3072,
            "text-embedding-3-small": 1536,
            "text-embedding-ada-002": 1536,
            "text-embedding-004": 768,
        }
        expected = expected_dims.get(self.model)
        if expected and self.dimensions != expected:
            raise ValueError(
                f"Embedding dimensions {self.dimensions} don't match expected {expected} for {self.model}"
            )
        return self


# EntityExtractionConfig, AgentConfig, ToolTrackingConfig are imported from client

class SearchConfig(BaseSettings):
    """Search and retrieval configuration"""

    default_limit: int = Field(
        default=10,
        description="Default number of search results to return",
        gt=0
    )
    default_strategy: Literal["semantic", "traversal", "hybrid"] = Field(
        default="hybrid",
        description="Default search strategy"
    )
    max_traversal_depth: int = Field(
        default=2,
        description="Maximum depth for graph traversal in search",
        ge=1
    )

    # RRF (Reciprocal Rank Fusion) parameters for hybrid search
    rrf_k: int = Field(
        default=60,
        description="RRF constant for hybrid search ranking",
        gt=0
    )
    min_rrf_score: float = Field(
        default=0.025,
        description="Minimum RRF score threshold for results",
        ge=0.0
    )

    # BM25 keyword search parameters
    min_bm25_score: float = Field(
        default=0.1,
        description="Minimum BM25 score threshold for keyword search",
        ge=0.0
    )

    model_config = SettingsConfigDict(
        env_prefix="RYUMEM_SEARCH_",
        env_nested_delimiter="__"
    )


class SystemConfig(BaseSettings):
    """System configuration"""

    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:3001",
        description="Comma-separated CORS origins"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR"
    )

    model_config = SettingsConfigDict(
        env_prefix="RYUMEM_SYSTEM_",
        env_nested_delimiter="__"
    )


class RyumemConfig(BaseSettings):
    """
    Main configuration for Ryumem instance.
    Uses pydantic-settings for automatic environment variable loading.

    Environment variables use the RYUMEM_ prefix. Each nested config has its own prefix.
    Examples:
        RYUMEM_DB_PATH=./data/memory.db
        RYUMEM_LLM_PROVIDER=openai
        RYUMEM_LLM_MODEL=gpt-4o-mini
        RYUMEM_EMBEDDING_PROVIDER=openai
        OPENAI_API_KEY=sk-...
        GOOGLE_API_KEY=...

    Note: Use single underscore between prefix and field name (e.g., RYUMEM_LLM_PROVIDER).
    Double underscores (__) are only for further nesting within a config section.
    """

    # Nested configuration sections
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    entity_extraction: EntityExtractionConfig = Field(default_factory=EntityExtractionConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    tool_tracking: ToolTrackingConfig = Field(default_factory=ToolTrackingConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    system: SystemConfig = Field(default_factory=SystemConfig)

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore"
    )

    def validate_api_keys(self) -> None:
        """
        Validate API key requirements based on provider.
        Call this explicitly before using the config to ensure all required keys are present.

        Raises:
            ValueError: If required API keys are missing for the configured providers
        """
        # Check LLM provider API key
        if self.llm.provider == "litellm":
            # LiteLLM auto-detects keys - just log info
            logger.info(f"Using LiteLLM with model: {self.llm.model}")
            logger.info("Ensure appropriate API key is set (e.g., OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY)")
            return
        elif self.llm.provider == "openai" and not self.llm.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required when using llm provider='openai'. "
                "Set it with: export OPENAI_API_KEY=your-key"
            )
        elif self.llm.provider == "gemini" and not self.llm.gemini_api_key:
            raise ValueError(
                "GOOGLE_API_KEY is required when using llm provider='gemini'. "
                "Set it with: export GOOGLE_API_KEY=your-key"
            )

        # Check embedding provider API key
        if self.embedding.provider == "openai" and not self.llm.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required when using embedding provider='openai'. "
                "Set it with: export OPENAI_API_KEY=your-key"
            )
        if self.embedding.provider == "gemini" and not self.llm.gemini_api_key:
            raise ValueError(
                "GOOGLE_API_KEY is required when using embedding provider='gemini'. "
                "Set it with: export GOOGLE_API_KEY=your-key"
            )
    
    def auto_configure_google_adk_settings(self) -> None:
        # AUTO-DETECTION LOGIC for Google ADK integration
        # Check for GOOGLE_API_KEY in environment
        google_api_key = self.llm.gemini_api_key

        if not google_api_key:
            raise ValueError(
                "Google ADK integration requires GOOGLE_API_KEY environment variable. "
                "Set it with: export GOOGLE_API_KEY='your-key'"
            )

        # Auto-configure for Gemini if not explicitly set
        if self.llm.gemini_api_key is None:
            self.llm.gemini_api_key = google_api_key

        # Use Gemini for LLM by default
        if self.llm.provider == "openai":  # Default from env
            self.llm.provider = "gemini"
            self.llm.model = "gemini-2.0-flash-exp"

        # Set embedding provider based on key availability
        openai_api_key = self.llm.openai_api_key

        if openai_api_key:
            # Prefer OpenAI for embeddings if available
            self.embedding.provider = 'openai'
            self.embedding.model = 'text-embedding-3-large'
            self.embedding.dimensions = 3072
            self.llm.openai_api_key = openai_api_key
            self.info("📊 Using OpenAI for embeddings (better quality)")
        else:
            # Fallback to Gemini for embeddings
            self.embedding.provider = 'gemini'
            self.embedding.model = 'text-embedding-004'
            self.embedding.dimensions = 768

    @model_validator(mode='after')
    def validate_provider_compatibility(self) -> 'RyumemConfig':
        """Validate provider and model compatibility"""
        # Auto-configure embedding provider based on LLM provider if not explicitly set
        # This is determined by checking if embedding provider is still at default value (ollama)
        # if self.llm.provider == "gemini" and self.embedding.provider == "ollama":
        #     # User likely only set LLM provider to gemini, auto-switch embedding too
        #     self.embedding.provider = "gemini"
        #     self.embedding.model = "text-embedding-004"
        #     self.embedding.dimensions = 768
        # elif self.llm.provider == "openai" and self.embedding.provider == "ollama":
        #     # User set LLM to openai, auto-switch embedding too
        #     self.embedding.provider = "openai"
        #     self.embedding.model = "text-embedding-3-large"
        #     self.embedding.dimensions = 3072

        # # Validate embedding model matches provider
        # openai_models = ["text-embedding-3-large", "text-embedding-3-small", "text-embedding-ada-002"]
        # gemini_models = ["text-embedding-004"]

        # if self.embedding.provider == "openai" and self.embedding.model not in openai_models:
        #     raise ValueError(f"Embedding model '{self.embedding.model}' is not compatible with provider 'openai'")
        # if self.embedding.provider == "gemini" and self.embedding.model not in gemini_models:
        #     raise ValueError(f"Embedding model '{self.embedding.model}' is not compatible with provider 'gemini'")

        return self

    @classmethod
    def from_database(cls, db: 'RyugraphDB') -> 'RyumemConfig':
        """
        Load configuration from database using ConfigService.

        Args:
            db: Database connection

        Returns:
            RyumemConfig instance populated from database
        """
        from ryumem_server.core.config_service import ConfigService

        service = ConfigService(db)
        return service.load_config_from_database()

    def to_dict(self) -> dict:
        """Convert config to dictionary"""
        return self.model_dump()

    def __repr__(self) -> str:
        """String representation (masks API keys)"""
        config_dict = self.model_dump()
        if config_dict.get("llm", {}).get("openai_api_key"):
            key = config_dict["llm"]["openai_api_key"]
            config_dict["llm"]["openai_api_key"] = "sk-..." + (key[-4:] if len(key) >= 4 else "***")
        if config_dict.get("llm", {}).get("gemini_api_key"):
            key = config_dict["llm"]["gemini_api_key"]
            config_dict["llm"]["gemini_api_key"] = "..." + (key[-4:] if len(key) >= 4 else "***")
        return f"RyumemConfig({config_dict})"
