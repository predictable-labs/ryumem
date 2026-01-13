"""Abstract base class for benchmark datasets."""

from abc import ABC, abstractmethod
from typing import Iterator, Any


class BenchmarkDataset(ABC):
    """Abstract base class for benchmark datasets."""

    @abstractmethod
    def load(self) -> None:
        """Load the dataset."""
        pass

    @abstractmethod
    def __len__(self) -> int:
        """Return the number of items in the dataset."""
        pass

    @abstractmethod
    def __iter__(self) -> Iterator[Any]:
        """Iterate over dataset items."""
        pass
