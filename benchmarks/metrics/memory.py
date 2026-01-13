"""Memory usage metrics for benchmarking."""

import tracemalloc
from typing import Dict, List


class MemoryMetrics:
    """Collects and computes memory usage metrics."""

    def __init__(self):
        self.samples: List[float] = []  # Memory samples in MB
        self.peak_mb: float = 0.0
        self._tracing_started: bool = False

    def start_tracing(self) -> None:
        """Start memory tracing."""
        if not tracemalloc.is_tracing():
            tracemalloc.start()
            self._tracing_started = True

    def stop_tracing(self) -> None:
        """Stop memory tracing and record peak."""
        if tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            self.peak_mb = max(self.peak_mb, peak / 1024 / 1024)
            if self._tracing_started:
                tracemalloc.stop()
                self._tracing_started = False

    def sample(self) -> float:
        """
        Take a memory sample.

        Returns:
            Current memory usage in MB
        """
        if tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            current_mb = current / 1024 / 1024
            self.samples.append(current_mb)
            self.peak_mb = max(self.peak_mb, peak / 1024 / 1024)
            return current_mb
        return 0.0

    def set_peak(self, peak_mb: float) -> None:
        """
        Set peak memory usage.

        Args:
            peak_mb: Peak memory in megabytes
        """
        self.peak_mb = max(self.peak_mb, peak_mb)

    def get_avg_memory(self) -> float:
        """Get average memory usage in MB."""
        if not self.samples:
            return 0.0
        return sum(self.samples) / len(self.samples)

    def get_min_memory(self) -> float:
        """Get minimum memory usage in MB."""
        if not self.samples:
            return 0.0
        return min(self.samples)

    def get_max_memory(self) -> float:
        """Get maximum sampled memory usage in MB."""
        if not self.samples:
            return 0.0
        return max(self.samples)

    def get_summary(self) -> Dict[str, float]:
        """Get a summary of memory metrics."""
        return {
            "samples_count": len(self.samples),
            "avg_mb": self.get_avg_memory(),
            "min_mb": self.get_min_memory(),
            "max_mb": self.get_max_memory(),
            "peak_mb": self.peak_mb,
        }
