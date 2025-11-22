from typing import List, Dict, Any, Optional
from .base import Strategy
from ryumem import Ryumem

class LLMStrategy(Strategy):
    """
    LLM-based strategy for routing.
    
    Uses the Ryumem LLM client to decide the next step based on history and available tools.
    """
    
    def __init__(self, ryumem: Ryumem, model: str = "gemini-2.0-flash-exp"):
        self.ryumem = ryumem
        self.model = model

    def decide_next(
        self, 
        current_node: Optional[str], 
        history: List[Dict[str, Any]], 
        tools: Dict[str, Any]
    ) -> str:
        tool_names = list(tools.keys())
        if not tool_names:
            return "__end__"
            
        # Construct prompt
        history_str = "\n".join([
            f"- Step {i+1}: {step['tool_name']} (Success: {step['success']})" 
            for i, step in enumerate(history)
        ])
        
        prompt = f"""
        You are an intelligent router for a workflow.
        
        Available Tools: {', '.join(tool_names)}
        
        History:
        {history_str}
        
        Current Node: {current_node}
        
        Decide the next tool to execute to complete the task.
        If the task is complete or no further tools are needed, respond with "__end__".
        Only respond with the exact tool name or "__end__".
        """
        
        try:
            response = self.ryumem.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10
            )
            next_node = response.content.strip()
            
            if next_node in tool_names or next_node == "__end__":
                return next_node
            
            # Fallback if LLM hallucinates
            return "__end__"
            
        except Exception:
            # Fallback on error
            return "__end__"
