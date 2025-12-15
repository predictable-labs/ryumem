"""
Background worker module for async entity extraction.

This module provides:
- Redis queue client for job distribution
- Entity extraction worker that processes jobs asynchronously
- HTTP callbacks to persist results via server endpoints

Usage:
    python -m ryumem_server.worker
"""

from ryumem_server.worker.queue import (
    ExtractionJob,
    enqueue_extraction_job,
    dequeue_extraction_job,
    update_job_status,
    get_job_status,
    get_redis_client,
)
from ryumem_server.worker.entity_extraction import (
    EntityExtractionWorker,
    create_worker,
)

__all__ = [
    "ExtractionJob",
    "enqueue_extraction_job",
    "dequeue_extraction_job",
    "update_job_status",
    "get_job_status",
    "get_redis_client",
    "EntityExtractionWorker",
    "create_worker",
]
