"""
Configuration management for Ryumem using pydantic-settings
"""

import logging
from typing import Literal, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class DatabaseConfig(BaseSettings):
    """Database configuration"""

    db_path: str = Field(
        default="./data/ryumem.db",
        description="Path to ryugraph database directory"
    )


class EntityExtractionConfig(BaseSettings):
    """Entity extraction and episode deduplication configuration"""

    enabled: bool = Field(
        default=False,
        description="Whether to enable entity extraction during ingestion (disabled by default to reduce token usage)"
    )
    entity_similarity_threshold: float = Field(
        default=0.65,
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
        description="Maximum number of previous episodes to use as context for extraction",
        ge=0
    )


class EpisodeConfig(BaseSettings):
    """Episode ingestion and deduplication configuration"""

    enable_embeddings: bool = Field(
        default=True,
        description="Whether to generate embeddings for episodes (if False, uses BM25 for search/dedup)"
    )

    # Deduplication settings
    deduplication_enabled: bool = Field(
        default=True,
        description="Whether to enable episode deduplication"
    )
    similarity_threshold: float = Field(
        default=0.95,
        description="Cosine similarity threshold for semantic episode deduplication (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    bm25_similarity_threshold: float = Field(
        default=0.7,
        description="BM25 score threshold for keyword-based episode deduplication (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    time_window_hours: int = Field(
        default=24,
        description="Time window in hours to check for duplicate episodes",
        gt=0
    )


class AgentConfig(BaseSettings):
    """Agent configuration"""
    memory_enabled: bool = Field(
        default=True,
        description="Whether memory features are enabled for the agent"
    )
    enhance_agent_instruction: bool = Field(
        default=True,
        description="Whether to enhance agent instructions with memory guidance"
    )

    # Default instruction blocks
    default_memory_block: str = Field(
        default="""MEMORY USAGE:
Use search_memory to find relevant context before answering questions.
Use save_memory to store important information for future reference.
""",
        description="Default memory instruction block added to agent instructions"
    )
    default_tool_block: str = Field(
        default="""TOOL SELECTION:
Before selecting which tool to use, search_memory for past tool usage patterns and success rates.
Use queries like "tool execution for [task type]" to find which tools worked well for similar tasks.
""",
        description="Default tool selection instruction block added to agent instructions"
    )
    default_query_augmentation_template: str = Field(
        default="""[Previous Attempt Summary]

Your previous approach was:
{agent_response}

Tools previously used:
{simplified_tool_summary}

Last Session Details:
{last_session}

Using this memory, improve your next attempt.

***IMPORTANT — REQUIRED BEHAVIOR***
You MUST reuse any **concrete facts, results, conclusions, or discovered information** from the previous attempt if they are relevant.
Do NOT ignore previously known truths.
Treat the previous attempt as authoritative memory, not optional context.

In your response, briefly include:
1. What you learned last time (1-2 bullets).
2. How you're using that knowledge now.

This demonstrates to the user that memory is working and you're building on past progress.""",
        description="Default template for query augmentation with historical context"
    )


class ToolTrackingConfig(BaseSettings):
    """Tool tracking configuration for Google ADK integration"""

    track_tools: bool = Field(
        default=True,
        description="Enable tool call tracking"
    )
    track_mcp_toolsets: bool = Field(
        default=True,
        description="Enable tracking for MCP toolset executions"
    )
    track_queries: bool = Field(
        default=True,
        description="Enable query tracking"
    )
    augment_queries: bool = Field(
        default=True,
        description="Enable query augmentation with similar past queries"
    )
    similarity_threshold: float = Field(
        default=0.3,
        description="Similarity threshold for query augmentation",
        ge=0.0,
        le=1.0
    )
    similarity_strategy: str = Field(
        default="hybrid",
        description="Search strategy for finding similar queries (semantic, bm25, hybrid, traversal)"
    )
    top_k_similar: int = Field(
        default=5,
        description="Number of similar queries to include in augmentation",
        gt=0
    )
    sample_rate: float = Field(
        default=1.0,
        description="Sample rate for tool tracking (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    summarize_outputs: bool = Field(
        default=True,
        description="Whether to summarize tool outputs"
    )
    max_output_chars: int = Field(
        default=1000,
        description="Maximum characters for tool output before truncation/summarization",
        gt=0
    )
    sanitize_pii: bool = Field(
        default=True,
        description="Whether to sanitize PII from tool outputs"
    )
    enhance_descriptions: bool = Field(
        default=False,
        description="Whether to enhance tool descriptions using LLM"
    )
    ignore_errors: bool = Field(
        default=True,
        description="Whether to ignore errors during tracking"
    )
    min_rrf_score: float = Field(
        default=0.0,
        description="Minimum RRF score threshold for query augmentation (only applies when using hybrid search strategy)",
        ge=0.0,
        le=1.0
    )


class RyumemConfig(BaseSettings):
    """
    Main configuration for Ryumem client instance.
    Config is fetched from the server.
    """

    # Nested configuration sections
    entity_extraction: EntityExtractionConfig = Field(default_factory=EntityExtractionConfig)
    tool_tracking: ToolTrackingConfig = Field(default_factory=ToolTrackingConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    episode: EpisodeConfig = Field(default_factory=EpisodeConfig)

    def to_dict(self) -> dict:
        """Convert config to dictionary"""
        return self.model_dump()

    def __repr__(self) -> str:
        """String representation"""
        return f"RyumemConfig({self.model_dump()})"
