"""
Configuration management for Ryumem
"""

import os
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator


class RyumemConfig(BaseModel):
    """
    Configuration for Ryumem instance.
    Can be initialized from environment variables or passed directly.
    """

    # Database settings
    db_path: str = Field(
        default="./data/ryumem.db",
        description="Path to ryugraph database directory"
    )

    # OpenAI settings
    openai_api_key: str = Field(description="OpenAI API key")
    llm_model: str = Field(default="gpt-4", description="LLM model to use for extraction")
    embedding_model: str = Field(
        default="text-embedding-3-large",
        description="Embedding model to use"
    )
    embedding_dimensions: int = Field(
        default=3072,
        description="Embedding vector dimensions (text-embedding-3-large uses 3072)"
    )

    # Extraction settings
    entity_similarity_threshold: float = Field(
        default=0.7,
        description="Cosine similarity threshold for entity deduplication (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    relationship_similarity_threshold: float = Field(
        default=0.8,
        description="Cosine similarity threshold for relationship deduplication (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    max_context_episodes: int = Field(
        default=5,
        description="Maximum number of previous episodes to use as context for extraction"
    )

    # Search settings
    default_search_limit: int = Field(
        default=10,
        description="Default number of search results to return"
    )
    default_search_strategy: str = Field(
        default="hybrid",
        description="Default search strategy: semantic, traversal, or hybrid"
    )
    max_traversal_depth: int = Field(
        default=2,
        description="Maximum depth for graph traversal in search"
    )

    # Community detection settings
    enable_community_detection: bool = Field(
        default=True,
        description="Whether to enable automatic community detection"
    )
    community_detection_threshold: int = Field(
        default=10,
        description="Minimum number of entities before running community detection"
    )

    # Performance settings
    batch_size: int = Field(
        default=10,
        description="Batch size for embedding operations"
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retries for API calls"
    )
    timeout_seconds: int = Field(
        default=30,
        description="Timeout for API calls in seconds"
    )

    @field_validator("llm_model")
    @classmethod
    def validate_llm_model(cls, v: str) -> str:
        """Validate LLM model name"""
        valid_models = ["gpt-4", "gpt-4-turbo", "gpt-4-turbo-preview", "gpt-3.5-turbo"]
        if v not in valid_models:
            raise ValueError(f"LLM model must be one of {valid_models}")
        return v

    @field_validator("embedding_model")
    @classmethod
    def validate_embedding_model(cls, v: str) -> str:
        """Validate embedding model name"""
        valid_models = [
            "text-embedding-3-large",
            "text-embedding-3-small",
            "text-embedding-ada-002"
        ]
        if v not in valid_models:
            raise ValueError(f"Embedding model must be one of {valid_models}")
        return v

    @field_validator("embedding_dimensions")
    @classmethod
    def validate_embedding_dimensions(cls, v: int, values) -> int:
        """Validate embedding dimensions match the model"""
        embedding_model = values.data.get("embedding_model", "text-embedding-3-large")
        expected_dims = {
            "text-embedding-3-large": 3072,
            "text-embedding-3-small": 1536,
            "text-embedding-ada-002": 1536
        }
        expected = expected_dims.get(embedding_model, 3072)
        if v != expected:
            raise ValueError(
                f"Embedding dimensions {v} don't match expected {expected} for {embedding_model}"
            )
        return v

    @field_validator("default_search_strategy")
    @classmethod
    def validate_search_strategy(cls, v: str) -> str:
        """Validate search strategy"""
        valid_strategies = ["semantic", "traversal", "hybrid"]
        if v not in valid_strategies:
            raise ValueError(f"Search strategy must be one of {valid_strategies}")
        return v

    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> "RyumemConfig":
        """
        Load configuration from environment variables.

        Args:
            env_file: Optional path to .env file

        Returns:
            RyumemConfig instance

        Environment variables:
            RYUMEM_DB_PATH: Database path
            OPENAI_API_KEY: OpenAI API key
            RYUMEM_LLM_MODEL: LLM model name
            RYUMEM_EMBEDDING_MODEL: Embedding model name
            RYUMEM_EMBEDDING_DIMENSIONS: Embedding dimensions
            ... (other settings with RYUMEM_ prefix)
        """
        # Load .env file if specified
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        # Get OpenAI API key (required)
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        # Build config from environment variables
        config_dict = {
            "openai_api_key": openai_api_key,
            "db_path": os.getenv("RYUMEM_DB_PATH", "./data/ryumem.db"),
            "llm_model": os.getenv("RYUMEM_LLM_MODEL", "gpt-4"),
            "embedding_model": os.getenv("RYUMEM_EMBEDDING_MODEL", "text-embedding-3-large"),
        }

        # Add optional integer settings
        for key in [
            "embedding_dimensions",
            "max_context_episodes",
            "default_search_limit",
            "max_traversal_depth",
            "community_detection_threshold",
            "batch_size",
            "max_retries",
            "timeout_seconds"
        ]:
            env_key = f"RYUMEM_{key.upper()}"
            env_value = os.getenv(env_key)
            if env_value:
                config_dict[key] = int(env_value)

        # Add optional float settings
        for key in ["entity_similarity_threshold", "relationship_similarity_threshold"]:
            env_key = f"RYUMEM_{key.upper()}"
            env_value = os.getenv(env_key)
            if env_value:
                config_dict[key] = float(env_value)

        # Add optional boolean settings
        for key in ["enable_community_detection"]:
            env_key = f"RYUMEM_{key.upper()}"
            env_value = os.getenv(env_key)
            if env_value:
                config_dict[key] = env_value.lower() in ("true", "1", "yes")

        # Add optional string settings
        for key in ["default_search_strategy"]:
            env_key = f"RYUMEM_{key.upper()}"
            env_value = os.getenv(env_key)
            if env_value:
                config_dict[key] = env_value

        return cls(**config_dict)

    def to_dict(self) -> dict:
        """Convert config to dictionary"""
        return self.model_dump()

    def __repr__(self) -> str:
        """String representation (masks API key)"""
        config_dict = self.model_dump()
        if "openai_api_key" in config_dict:
            config_dict["openai_api_key"] = "sk-..." + config_dict["openai_api_key"][-4:]
        return f"RyumemConfig({config_dict})"
