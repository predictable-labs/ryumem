from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel

class LangGraphState(BaseModel):
    """Base state for LangGraph workflows using Ryumem."""
    session_id: str
    user_id: str
    current_node: Optional[str] = None
    next_node: Optional[str] = None
    history: List[Dict[str, Any]] = []
    # Allow extra fields
    class Config:
        extra = "allow"

# Define other types as needed
