from typing import Callable, Any

def register_tool(tool_name: str) -> Callable:
    """
    Decorator to register a function as a tool for LangGraph.
    
    Attaches metadata to the function that LangGraphRouter can discover.
    
    Args:
        tool_name: The name of the tool to register.
        
    Returns:
        The decorated function with attached metadata.
    """
    def decorator(fn: Callable) -> Callable:
        fn._is_tool = True
        fn._tool_name = tool_name
        return fn
    return decorator
