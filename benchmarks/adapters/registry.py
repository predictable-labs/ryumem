"""Adapter registry for memory systems."""

from typing import Dict, List, Type
from benchmarks.adapters.base import MemorySystemAdapter


class AdapterRegistry:
    """Registry for memory system adapters."""

    _adapters: Dict[str, Type[MemorySystemAdapter]] = {}

    @classmethod
    def register(cls, name: str, adapter_class: Type[MemorySystemAdapter]) -> None:
        """
        Register an adapter class.

        Args:
            name: Unique name for the adapter
            adapter_class: Adapter class to register
        """
        cls._adapters[name.lower()] = adapter_class

    @classmethod
    def get(cls, name: str) -> MemorySystemAdapter:
        """
        Get an adapter instance by name.

        Args:
            name: Name of the adapter

        Returns:
            New instance of the adapter

        Raises:
            ValueError: If adapter not found
        """
        name_lower = name.lower()
        if name_lower not in cls._adapters:
            available = ", ".join(cls._adapters.keys())
            raise ValueError(
                f"Unknown adapter: {name}. Available adapters: {available}"
            )
        return cls._adapters[name_lower]()

    @classmethod
    def list_adapters(cls) -> List[str]:
        """Get list of registered adapter names."""
        return list(cls._adapters.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if an adapter is registered."""
        return name.lower() in cls._adapters


def register_all_adapters() -> None:
    """Register all built-in adapters."""
    from benchmarks.adapters.ryumem_adapter import RyumemAdapter
    from benchmarks.adapters.mem0_adapter import Mem0Adapter
    from benchmarks.adapters.langchain_adapter import LangChainAdapter
    from benchmarks.adapters.zep_adapter import ZepAdapter

    AdapterRegistry.register("ryumem", RyumemAdapter)
    AdapterRegistry.register("mem0", Mem0Adapter)
    AdapterRegistry.register("langchain", LangChainAdapter)
    AdapterRegistry.register("zep", ZepAdapter)
