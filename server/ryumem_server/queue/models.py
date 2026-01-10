"""
Pydantic models for extraction job queue.
"""

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field


class ExtractionJob(BaseModel):
    """Job payload for entity extraction worker."""
    episode_uuid: str = Field(description='UUID of the episode to extract entities from')
    content: str = Field(description='Episode content for extraction')
    user_id: str = Field(description='User ID for multi-tenancy')
    session_id: Optional[str] = Field(default=None, description='Session ID')
    webhook_url: Optional[str] = Field(default=None, description='URL to call on completion')
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Database path - worker connects to same DB as server
    db_path: str = Field(description='Path to database (from server config)')

    # Additional metadata
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractionResult(BaseModel):
    """Result of entity extraction, used for webhook callback."""
    episode_uuid: str
    status: str  # completed, failed
    entities_count: int = 0
    edges_count: int = 0
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
