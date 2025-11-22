from abc import ABC, abstractmethod
from typing import List, Dict, Any

class HistoryStore(ABC):
    """Abstract base class for history storage backends."""

    @abstractmethod
    def save_step(self, session_id: str, step: Dict[str, Any], user_id: str) -> None:
        """Save a single execution step to history."""
        pass
    
    @abstractmethod
    def load_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Load full session history."""
        pass
