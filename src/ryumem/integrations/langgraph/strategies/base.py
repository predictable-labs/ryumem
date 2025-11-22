from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class Strategy(ABC):
    """Abstract base class for routing strategies."""

    @abstractmethod
    def decide_next(
        self, 
        current_node: Optional[str], 
        history: List[Dict[str, Any]], 
        tools: Dict[str, Any]
    ) -> str:
        """
        Decide the next node to execute.
        
        Args:
            current_node: The name of the node just executed.
            history: List of previous steps (ToolExecutions).
            tools: Dictionary of available tools/nodes.
            
        Returns:
            The name of the next node to execute, or "__end__" to finish.
        """
        pass
