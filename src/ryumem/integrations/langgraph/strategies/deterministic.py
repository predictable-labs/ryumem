from typing import List, Dict, Any, Optional
from .base import Strategy

class DeterministicStrategy(Strategy):
    """
    Simple deterministic strategy.
    
    Rules:
    - If current_node is None (start), pick the first available tool.
    - If history shows we just visited a node, try to move to the next logical one 
      (in a simple linear flow or based on simple rules).
    - Avoid immediate loops (don't repeat the same node twice in a row unless specified).
    
    For a generic router without a defined graph structure, "deterministic" is hard 
    unless we have a predefined sequence. 
    
    Assumption: The user might provide a 'sequence' or we just cycle through tools once.
    
    Better approach for "generic" deterministic:
    - If we haven't visited a tool, visit it.
    - If we visited all tools, end.
    """
    
    def __init__(self, sequence: Optional[List[str]] = None):
        self.sequence = sequence

    def decide_next(
        self, 
        current_node: Optional[str], 
        history: List[Dict[str, Any]], 
        tools: Dict[str, Any]
    ) -> str:
        if not tools:
            return "__end__"
            
        tool_names = list(tools.keys())
        
        if self.sequence:
            # Follow defined sequence
            if not current_node:
                return self.sequence[0] if self.sequence else "__end__"
            
            try:
                idx = self.sequence.index(current_node)
                if idx + 1 < len(self.sequence):
                    return self.sequence[idx + 1]
            except ValueError:
                pass
            return "__end__"
            
        # Default: Visit each tool once
        visited_tools = {step['tool_name'] for step in history}
        
        for tool in tool_names:
            if tool not in visited_tools:
                return tool
                
        return "__end__"
