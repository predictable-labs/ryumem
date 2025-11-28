"""
Data models for Ryumem
Simplified for ryugraph with full multi-tenancy support
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EpisodeType(Enum):
    """
    Enumeration of different types of episodes that can be processed.

    Attributes:
        message: Message-type episode formatted as "actor: content"
        json: Episode containing JSON structured data
        text: Plain text episode
    """
    message = 'message'
    json = 'json'
    text = 'text'

    @staticmethod
    def from_str(episode_type: str) -> 'EpisodeType':
        if episode_type == 'message':
            return EpisodeType.message
        if episode_type == 'json':
            return EpisodeType.json
        if episode_type == 'text':
            return EpisodeType.text
        raise ValueError(f'Episode type: {episode_type} not implemented')


class EpisodeKind(Enum):
    """
    Enumeration of episode kinds - distinguishes query episodes from memory episodes.

    Attributes:
        query: Regular user query/interaction episode
        memory: LLM-saved memory episode
    """
    query = 'query'
    memory = 'memory'

    @staticmethod
    def from_str(kind: str) -> 'EpisodeKind':
        if kind == 'query':
            return EpisodeKind.query
        if kind == 'memory':
            return EpisodeKind.memory
        raise ValueError(f'Episode kind: {kind} not implemented')


class EpisodeNode(BaseModel):
    """
    Represents an episode (a discrete unit of ingestion).
    Each episode captures a message, JSON, or text at a point in time.
    """
    uuid: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(default='', description='Name/title of the episode')
    content: str = Field(default='', description='Raw episode data/content')
    content_embedding: list[float] | None = Field(
        default=None,
        description='Embedding vector for the episode content'
    )
    source: EpisodeType = Field(default=EpisodeType.text, description='Source type of episode')
    source_description: str = Field(default='', description='Description of the data source')
    kind: EpisodeKind = Field(default=EpisodeKind.query, description='Episode kind: query or memory')
    created_at: datetime = Field(default_factory=datetime.utcnow)
    valid_at: datetime = Field(
        default_factory=datetime.utcnow,
        description='Datetime when the original document was created'
    )

    # Multi-tenancy fields
    user_id: str | None = Field(default=None, description='User ID for multi-tenancy')
    agent_id: str | None = Field(default=None, description='Agent ID for multi-tenancy')

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict, description='Additional metadata')
    entity_edges: list[str] = Field(
        default_factory=list,
        description='List of entity edge UUIDs referenced in this episode'
    )

    class Config:
        json_schema_extra = {
            "example": {
                "uuid": "123e4567-e89b-12d3-a456-426614174000",
                "name": "User message",
                "content": "user: I love Python programming",
                "source": "message",
                "user_id": "user_123",
            }
        }

    def get(self, key: str, default: Any = None) -> Any:
        """Support dictionary-style .get() access."""
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        """Support dictionary-style [] access."""
        return getattr(self, key)


class EntityNode(BaseModel):
    """
    Represents an entity extracted from episodes.
    Entities are people, places, organizations, concepts, etc.
    """
    uuid: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(description='Name of the entity')
    entity_type: str = Field(default='ENTITY', description='Type of entity (e.g., PERSON, ORG, CONCEPT)')
    summary: str = Field(default='', description='Summary of the entity and its context')
    name_embedding: list[float] | None = Field(
        default=None,
        description='Embedding of the entity name (3072 dimensions for text-embedding-3-large)'
    )
    mentions: int = Field(default=1, description='Number of times entity has been mentioned')
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Multi-tenancy fields
    user_id: str | None = Field(default=None, description='User ID for multi-tenancy')

    # Additional attributes
    labels: list[str] = Field(default_factory=list, description='Additional labels for the entity')
    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description='Additional custom attributes'
    )

    class Config:
        json_schema_extra = {
            "example": {
                "uuid": "123e4567-e89b-12d3-a456-426614174001",
                "name": "Python",
                "entity_type": "PROGRAMMING_LANGUAGE",
                "summary": "A high-level programming language",
                "mentions": 5
            }
        }


class EntityEdge(BaseModel):
    """
    Represents a relationship between two entities.
    Includes bi-temporal information (valid_at, invalid_at, expired_at).
    """
    uuid: str = Field(default_factory=lambda: str(uuid4()))
    source_node_uuid: str = Field(description='UUID of source entity')
    target_node_uuid: str = Field(description='UUID of target entity')
    name: str = Field(description='Relationship type/name (e.g., WORKS_AT, KNOWS)')
    fact: str = Field(description='Natural language description of the relationship')
    fact_embedding: list[float] | None = Field(
        default=None,
        description='Embedding of the fact (3072 dimensions)'
    )

    # Temporal fields (bi-temporal model)
    created_at: datetime = Field(default_factory=datetime.utcnow, description='When edge was created in system')
    valid_at: datetime | None = Field(default=None, description='When the fact became true in real world')
    invalid_at: datetime | None = Field(default=None, description='When the fact stopped being true')
    expired_at: datetime | None = Field(default=None, description='When the edge was invalidated/superseded')

    # Metadata
    episodes: list[str] = Field(
        default_factory=list,
        description='List of episode UUIDs that reference this edge'
    )
    mentions: int = Field(default=1, description='Number of times relationship has been mentioned')
    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description='Additional custom attributes'
    )

    class Config:
        json_schema_extra = {
            "example": {
                "uuid": "123e4567-e89b-12d3-a456-426614174002",
                "source_node_uuid": "entity_1_uuid",
                "target_node_uuid": "entity_2_uuid",
                "name": "WORKS_AT",
                "fact": "Alice works at Google",
                "valid_at": "2024-01-01T00:00:00Z"
            }
        }


class EpisodicEdge(BaseModel):
    """
    Represents a MENTIONS relationship between an episode and an entity.
    Links episodes to the entities they mention.
    """
    uuid: str = Field(default_factory=lambda: str(uuid4()))
    source_node_uuid: str = Field(description='UUID of episode (source)')
    target_node_uuid: str = Field(description='UUID of entity (target)')
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Search and retrieval models

class SearchConfig(BaseModel):
    """Configuration for search operations"""
    query: str = Field(description='Search query text')
    user_id: str | None = Field(default=None, description='Optional user ID filter')
    agent_id: str | None = Field(default=None, description='Optional agent ID filter')
    session_id: str | None = Field(default=None, description='Optional session ID filter')
    limit: int = Field(default=10, description='Maximum number of results')
    strategy: str = Field(
        default='hybrid',
        description='Search strategy: semantic, traversal, or hybrid'
    )
    similarity_threshold: float = Field(
        default=0.5,
        description='Minimum similarity score for results (lowered to 0.5 for better recall)',
        ge=0.0,
        le=1.0
    )
    include_expired: bool = Field(
        default=False,
        description='Whether to include expired edges in results'
    )
    max_depth: int = Field(
        default=2,
        description='Maximum depth for graph traversal'
    )
    # Temporal decay settings
    apply_temporal_decay: bool = Field(
        default=True,
        description='Whether to apply temporal decay to scores (recent facts score higher)'
    )
    temporal_decay_factor: float = Field(
        default=0.95,
        description='Decay factor per day (0-1). Default 0.95 = 5% decay per day',
        ge=0.0,
        le=1.0
    )
    apply_update_boost: bool = Field(
        default=True,
        description='Whether to boost recently updated/created facts'
    )
    update_boost_factor: float = Field(
        default=1.2,
        description='Boost multiplier for recently updated facts',
        ge=1.0,
        le=2.0
    )
    recent_threshold_days: int = Field(
        default=7,
        description='Days to consider a fact "recent" for update boost'
    )
    # Hybrid search settings
    rrf_k: int = Field(
        default=60,
        description='RRF constant for hybrid search (default: 60)',
        ge=1,
        le=100
    )
    min_rrf_score: float = Field(
        default=0.025,
        description='Minimum RRF score threshold for hybrid search results (filters weak matches)',
        ge=0.0,
        le=1.0
    )
    # BM25 settings
    min_bm25_score: float = Field(
        default=0.1,
        description='Minimum BM25 score threshold for keyword search results (higher = stricter)',
        ge=0.0,
        le=20.0
    )


class SearchResult(BaseModel):
    """Results from a search operation"""
    entities: list[EntityNode] = Field(default_factory=list)
    edges: list[EntityEdge] = Field(default_factory=list)
    episodes: list[EpisodeNode] = Field(default_factory=list)
    scores: dict[str, float] = Field(
        default_factory=dict,
        description='Mapping of node/edge UUID to relevance score'
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description='Additional metadata about the search'
    )

    class Config:
        json_schema_extra = {
            "example": {
                "entities": [],
                "edges": [],
                "scores": {"entity_uuid_1": 0.95, "entity_uuid_2": 0.87},
                "metadata": {"search_time_ms": 150, "strategy": "hybrid"}
            }
        }


class RyumemConfig(BaseModel):
    """Configuration for Ryumem instance"""
    db_path: str = Field(description='Path to ryugraph database')
    openai_api_key: str = Field(description='OpenAI API key')
    llm_model: str = Field(default='gpt-4', description='LLM model to use')
    embedding_model: str = Field(
        default='text-embedding-3-large',
        description='Embedding model to use'
    )
    embedding_dimensions: int = Field(
        default=3072,
        description='Embedding vector dimensions'
    )
    entity_similarity_threshold: float = Field(
        default=0.7,
        description='Threshold for entity deduplication',
        ge=0.0,
        le=1.0
    )
    relationship_similarity_threshold: float = Field(
        default=0.8,
        description='Threshold for relationship deduplication',
        ge=0.0,
        le=1.0
    )
    max_context_episodes: int = Field(
        default=5,
        description='Maximum number of previous episodes to use as context'
    )

    class Config:
        json_schema_extra = {
            "example": {
                "db_path": "./data/ryumem.db",
                "openai_api_key": "sk-...",
                "llm_model": "gpt-4",
                "embedding_model": "text-embedding-3-large"
            }
        }


# Client SDK response models

class ToolNode(BaseModel):
    """Represents a tool in the system."""
    tool_name: str = Field(description='Name of the tool')
    description: str = Field(description='Description of what the tool does')
    name_embedding: list[float] | None = Field(
        default=None,
        description='Embedding vector for the tool name'
    )
    created_at: datetime | None = Field(default=None, description='When the tool was registered')

    class Config:
        json_schema_extra = {
            "example": {
                "tool_name": "search_memory",
                "description": "Search through memory for relevant information",
                "name_embedding": [0.1, 0.2, 0.3]
            }
        }


class CypherResult(BaseModel):
    """Generic container for Cypher query results."""
    data: dict[str, Any] = Field(default_factory=dict, description='Result data from query')

    class Config:
        json_schema_extra = {
            "example": {
                "data": {"uuid": "123", "name": "John", "count": 5}
            }
        }


class EmbeddingResponse(BaseModel):
    """Response from embedding generation."""
    embedding: list[float] = Field(description='The embedding vector')
    model: str | None = Field(default=None, description='Model used for embedding')

    class Config:
        json_schema_extra = {
            "example": {
                "embedding": [0.1, 0.2, 0.3],
                "model": "text-embedding-3-large"
            }
        }


class LLMResponse(BaseModel):
    """Response from LLM generation."""
    content: str = Field(description='Generated text content')
    model: str | None = Field(default=None, description='Model used for generation')
    tokens_used: int | None = Field(default=None, description='Number of tokens used')

    class Config:
        json_schema_extra = {
            "example": {
                "content": "This is the generated response",
                "model": "gpt-4",
                "tokens_used": 150
            }
        }
