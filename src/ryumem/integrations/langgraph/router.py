import logging
from typing import Dict, Any, Optional, List, Callable
from ryumem import Ryumem
from .history import RyumemStore
from .strategies import Strategy, DeterministicStrategy, HybridStrategy, LLMStrategy
from .utils.context import set_current_router, reset_current_router

logger = logging.getLogger(__name__)

class LangGraphRouter:
    """
    Central router for LangGraph integrations using Ryumem.
    
    Acts as a LangGraph node that decides the next step based on history
    and the configured strategy.
    """
    
    def __init__(
        self,
        ryumem: Ryumem,
        strategy: str = "deterministic",
        planner_llm: Optional[Any] = None, # Optional LLM instance if needed for custom strategies
        max_depth: int = 10,
        sequence: Optional[List[str]] = None, # For deterministic sequence
    ):
        self.ryumem = ryumem
        self.history_store = RyumemStore(ryumem)
        self.max_depth = max_depth
        self.tools: Dict[str, Callable] = {}
        
        # Load strategy
        if strategy == "deterministic":
            self.strategy = DeterministicStrategy(sequence)
        elif strategy == "llm":
            self.strategy = LLMStrategy(ryumem)
        elif strategy == "hybrid":
            self.strategy = HybridStrategy(ryumem, sequence)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")
            
    def register_tool(self, tool: Callable) -> None:
        """Register a tool with the router."""
        tool_name = getattr(tool, "_tool_name", tool.__name__)
        self.tools[tool_name] = tool
        
    def record_step(
        self,
        tool_name: str,
        input_data: Any,
        output_data: Any,
        success: bool,
        error: Optional[str],
        duration_ms: int
    ) -> None:
        """
        Record a step execution to history.
        Called by @track_usage decorator.
        """
        # We need session_id and user_id. 
        # In a real LangGraph node, these should be in the state passed to the tool.
        # But the decorator captures input_data which is the state.
        
        if isinstance(input_data, dict):
            session_id = input_data.get("session_id")
            user_id = input_data.get("user_id", "default_user")
        else:
            # Fallback if input is not a dict (unlikely for LangGraph)
            logger.warning("Input data is not a dict, cannot extract session_id")
            return
            
        if not session_id:
            logger.warning("No session_id found in input data, cannot record step")
            return
            
        step = {
            "tool_name": tool_name,
            "input_data": input_data,
            "output_data": output_data,
            "success": success,
            "error": error,
            "duration_ms": duration_ms
        }
        
        self.history_store.save_step(session_id, step, user_id)
        
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph node entry point.
        
        Decides the next node to execute.
        """
        # Set context for decorators
        token = set_current_router(self)
        
        try:
            session_id = state.get("session_id")
            if not session_id:
                raise ValueError("State must contain 'session_id'")
                
            current_node = state.get("current_node")
            
            # Load history
            history = self.history_store.load_session(session_id)
            
            # Check max depth
            if len(history) >= self.max_depth:
                logger.warning(f"Max depth {self.max_depth} reached, ending session")
                state["next_node"] = "__end__"
                return state
            
            # Decide next node
            next_node = self.strategy.decide_next(current_node, history, self.tools)
            
            state["next_node"] = next_node
            
            # Update current node for next iteration (though LangGraph usually handles this)
            # We set it here so the next router call knows what just happened if it wasn't updated
            # But actually, 'current_node' in state usually means "where we are now".
            # If router is a node, 'current_node' might be 'router'.
            # The strategy needs to know what *tool* was just executed.
            # If the router is called *after* a tool, 'current_node' should be that tool.
            
            return state
            
        finally:
            reset_current_router(token)

    def __enter__(self):
        """Set this router as the current active router in context."""
        self._token = set_current_router(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Reset the context."""
        reset_current_router(self._token)
