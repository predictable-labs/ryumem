from typing import List, Dict, Any, Optional
from .base import Strategy
from .deterministic import DeterministicStrategy
from .llm_based import LLMStrategy
from ryumem import Ryumem

class HybridStrategy(Strategy):
    """
    Hybrid strategy that tries Deterministic first, then falls back to LLM.
    """
    
    def __init__(self, ryumem: Ryumem, sequence: Optional[List[str]] = None):
        self.deterministic = DeterministicStrategy(sequence)
        self.llm = LLMStrategy(ryumem)

    def decide_next(
        self, 
        current_node: Optional[str], 
        history: List[Dict[str, Any]], 
        tools: Dict[str, Any]
    ) -> str:
        # Try deterministic first
        next_node = self.deterministic.decide_next(current_node, history, tools)
        
        # If deterministic returns __end__ but we haven't really done much (heuristic),
        # or if we want LLM to override, we could change logic.
        # For now, let's say if deterministic has a clear path (sequence), use it.
        # If deterministic is just "visit once" and we want more intelligence, maybe LLM is better.
        
        # Actually, "Hybrid" usually means "Rule based if rule exists, else LLM".
        # If we provided a sequence, we probably want to follow it.
        if self.deterministic.sequence:
            return next_node
            
        # If no sequence, use LLM
        return self.llm.decide_next(current_node, history, tools)
