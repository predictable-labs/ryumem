import contextvars
from typing import Optional, Any

# Context variable to store the current LangGraphRouter instance
_current_router = contextvars.ContextVar("current_router", default=None)

def get_current_router() -> Optional[Any]:
    """Get the active LangGraphRouter instance from context."""
    return _current_router.get()

def set_current_router(router: Any) -> Any:
    """Set the active LangGraphRouter instance in context."""
    return _current_router.set(router)

def reset_current_router(token: Any) -> None:
    """Reset the active LangGraphRouter instance in context."""
    _current_router.reset(token)
