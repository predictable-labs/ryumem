"""
Data models for session management.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    """Status of a session."""
    ACTIVE = "active"
    COMPLETED = "completed"
    ERROR = "error"
    IDLE = "idle"


class SessionRun(BaseModel):
    """
    Represents a session with workflow execution state.

    Sessions persist across multiple query runs and maintain shared variables.
    """
    session_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the session"
    )
    user_id: str = Field(description="User ID owning this session")
    status: SessionStatus = Field(
        default=SessionStatus.ACTIVE,
        description="Current status of the session"
    )
    workflow_id: Optional[str] = Field(
        default=None,
        description="ID of the workflow being executed (if any)"
    )
    session_variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Shared variables accessible to all tools in the workflow"
    )
    started_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the session was started"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last time the session was updated"
    )
    current_node: Optional[str] = Field(
        default=None,
        description="Currently executing node (for active sessions)"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if session failed"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123",
                "user_id": "user_456",
                "status": "active",
                "workflow_id": "wf_789",
                "session_variables": {
                    "user_location": "San Francisco",
                    "node_1_output": {"temperature": 72, "condition": "sunny"}
                },
                "current_node": "node_2"
            }
        }

    def update_variables(self, new_variables: Dict[str, Any]) -> None:
        """Update session variables with new values."""
        self.session_variables.update(new_variables)
        self.updated_at = datetime.utcnow()

    def set_status(self, status: SessionStatus, error: Optional[str] = None) -> None:
        """Update session status."""
        self.status = status
        self.updated_at = datetime.utcnow()
        if error:
            self.error = error

    def set_current_node(self, node_id: Optional[str]) -> None:
        """Update currently executing node."""
        self.current_node = node_id
        self.updated_at = datetime.utcnow()
