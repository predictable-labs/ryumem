import time
import functools
from typing import Callable, Any, Dict
import logging

logger = logging.getLogger(__name__)

def track_usage(fn: Callable) -> Callable:
    """
    Decorator to track tool usage in LangGraph.
    
    Logs input/output to the global LangGraphRouter instance if available.
    Expects the first argument to be 'state' dict or the function to be a method 
    where 'self' has access to the router, but primarily designed for LangGraph nodes
    where the router is managing the execution flow.
    
    However, since LangGraph nodes are often standalone functions, this decorator
    needs a way to access the router. 
    
    Strategy:
    The LangGraphRouter will set a context variable or we assume the router is 
    passed in the state or available globally. 
    
    For now, we will implement a simple version that looks for a 'router' key in the state
    or relies on a global context if we implement one.
    
    Actually, the user request showed:
    
    ```python
    @track_usage
    def search_node(state): ...
    ```
    
    And:
    ```python
    brain.record_step(...)
    ```
    
    So we need a way to get the brain/router instance. 
    We will use a context variable in `src/ryumem/integrations/langgraph/utils/context.py` (to be created)
    to store the current router instance during execution.
    """
    from ryumem.integrations.langgraph.utils.context import get_current_router
    
    @functools.wraps(fn)
    def wrapper(state: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
        start_time = time.time()
        tool_name = getattr(fn, "_tool_name", fn.__name__)
        
        # Capture input (deep copy might be expensive, so we'll be careful)
        # For now, just shallow copy or assume state is the input
        input_data = state.copy() if isinstance(state, dict) else str(state)
        
        try:
            output_state = fn(state, *args, **kwargs)
            success = True
            error = None
        except Exception as e:
            success = False
            error = str(e)
            output_state = None
            raise e
        finally:
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Get the router from context
            router = get_current_router()
            
            if router:
                try:
                    router.record_step(
                        tool_name=tool_name,
                        input_data=input_data,
                        output_data=output_state,
                        success=success,
                        error=error,
                        duration_ms=duration_ms
                    )
                except Exception as e:
                    logger.error(f"Failed to record step for {tool_name}: {e}")
            else:
                logger.warning(f"No active LangGraphRouter found to track {tool_name}")
                
        return output_state
    return wrapper
