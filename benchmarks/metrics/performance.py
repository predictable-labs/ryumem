"""Performance metrics for benchmarking."""

from typing import Dict, List
import numpy as np


class PerformanceMetrics:
    """Collects and computes performance metrics."""

    def __init__(self):
        self.ingestion_times: List[float] = []
        self.search_times: List[float] = []
        self.total_ingestion_time: float = 0.0
        self.total_search_time: float = 0.0

    def add_ingestion_time(self, time_ms: float) -> None:
        """
        Add an ingestion time measurement.

        Args:
            time_ms: Time in milliseconds
        """
        self.ingestion_times.append(time_ms)
        self.total_ingestion_time += time_ms

    def add_search_time(self, time_ms: float) -> None:
        """
        Add a search time measurement.

        Args:
            time_ms: Time in milliseconds
        """
        self.search_times.append(time_ms)
        self.total_search_time += time_ms

    def get_avg_ingestion_time(self) -> float:
        """Get average ingestion time in milliseconds."""
        if not self.ingestion_times:
            return 0.0
        return float(np.mean(self.ingestion_times))

    def get_avg_search_time(self) -> float:
        """Get average search time in milliseconds."""
        if not self.search_times:
            return 0.0
        return float(np.mean(self.search_times))

    def get_percentile_ingestion(self, percentile: int) -> float:
        """
        Get percentile of ingestion times.

        Args:
            percentile: Percentile to calculate (e.g., 50, 95, 99)

        Returns:
            Time in milliseconds
        """
        if not self.ingestion_times:
            return 0.0
        return float(np.percentile(self.ingestion_times, percentile))

    def get_percentile_search(self, percentile: int) -> float:
        """
        Get percentile of search times.

        Args:
            percentile: Percentile to calculate (e.g., 50, 95, 99)

        Returns:
            Time in milliseconds
        """
        if not self.search_times:
            return 0.0
        return float(np.percentile(self.search_times, percentile))

    def get_min_search_time(self) -> float:
        """Get minimum search time in milliseconds."""
        if not self.search_times:
            return 0.0
        return float(np.min(self.search_times))

    def get_max_search_time(self) -> float:
        """Get maximum search time in milliseconds."""
        if not self.search_times:
            return 0.0
        return float(np.max(self.search_times))

    def get_std_search_time(self) -> float:
        """Get standard deviation of search times in milliseconds."""
        if not self.search_times:
            return 0.0
        return float(np.std(self.search_times))

    def get_summary(self) -> Dict[str, any]:
        """Get a summary of all performance metrics."""
        return {
            "ingestion": {
                "count": len(self.ingestion_times),
                "total_ms": self.total_ingestion_time,
                "total_s": self.total_ingestion_time / 1000,
                "avg_ms": self.get_avg_ingestion_time(),
                "p50_ms": self.get_percentile_ingestion(50),
                "p95_ms": self.get_percentile_ingestion(95),
                "p99_ms": self.get_percentile_ingestion(99),
            },
            "search": {
                "count": len(self.search_times),
                "total_ms": self.total_search_time,
                "total_s": self.total_search_time / 1000,
                "avg_ms": self.get_avg_search_time(),
                "min_ms": self.get_min_search_time(),
                "max_ms": self.get_max_search_time(),
                "std_ms": self.get_std_search_time(),
                "p50_ms": self.get_percentile_search(50),
                "p95_ms": self.get_percentile_search(95),
                "p99_ms": self.get_percentile_search(99),
            },
        }
