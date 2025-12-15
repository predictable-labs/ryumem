"""
Redis queue client for entity extraction jobs.

Provides functions to enqueue, dequeue, and manage extraction jobs.
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Queue names
EXTRACTION_QUEUE = "ryumem:extraction_jobs"
EXTRACTION_PROCESSING = "ryumem:extraction_processing"
EXTRACTION_RESULTS = "ryumem:extraction_results"

# Default Redis URL
DEFAULT_REDIS_URL = "redis://localhost:6379"


class ExtractionJob(BaseModel):
    """Model for an extraction job in the queue."""
    job_id: str
    episode_uuid: str
    content: str
    user_id: str
    customer_id: str = ""
    api_key: str = ""
    context: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "pending"  # pending, processing, completed, failed
    retry_count: int = 0
    max_retries: int = 3

    def to_json(self) -> str:
        """Serialize job to JSON string."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str: str) -> "ExtractionJob":
        """Deserialize job from JSON string."""
        return cls.model_validate_json(json_str)


_redis_client = None


def get_redis_client():
    """Get or create Redis client singleton."""
    global _redis_client
    if _redis_client is None:
        import redis
        redis_url = os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)
        _redis_client = redis.from_url(redis_url, decode_responses=True)
        logger.info(f"Connected to Redis at {redis_url}")
    return _redis_client


def enqueue_extraction_job(job: ExtractionJob) -> str:
    """
    Add an extraction job to the queue.

    Args:
        job: ExtractionJob to enqueue

    Returns:
        Job ID
    """
    client = get_redis_client()

    # Store job data
    job_key = f"ryumem:job:{job.job_id}"
    client.set(job_key, job.to_json(), ex=86400)  # 24 hour TTL

    # Add to queue
    client.lpush(EXTRACTION_QUEUE, job.job_id)

    logger.info(f"Enqueued extraction job {job.job_id} for episode {job.episode_uuid}")
    return job.job_id


def dequeue_extraction_job(timeout: int = 5) -> Optional[ExtractionJob]:
    """
    Dequeue an extraction job from the queue.

    Uses BRPOPLPUSH for reliable queue processing - moves job to processing
    list atomically.

    Args:
        timeout: Blocking timeout in seconds

    Returns:
        ExtractionJob if available, None otherwise
    """
    client = get_redis_client()

    # Blocking pop from queue, push to processing list
    result = client.brpoplpush(EXTRACTION_QUEUE, EXTRACTION_PROCESSING, timeout)

    if result is None:
        return None

    job_id = result
    job_key = f"ryumem:job:{job_id}"

    # Get job data
    job_json = client.get(job_key)
    if job_json is None:
        logger.warning(f"Job {job_id} not found in storage, removing from processing")
        client.lrem(EXTRACTION_PROCESSING, 1, job_id)
        return None

    job = ExtractionJob.from_json(job_json)
    job.status = "processing"

    # Update job status in storage
    client.set(job_key, job.to_json(), ex=86400)

    logger.info(f"Dequeued extraction job {job_id}")
    return job


def complete_job(job_id: str) -> None:
    """
    Mark a job as completed and remove from processing list.

    Args:
        job_id: Job ID to complete
    """
    client = get_redis_client()

    # Remove from processing list
    client.lrem(EXTRACTION_PROCESSING, 1, job_id)

    # Update job status
    job_key = f"ryumem:job:{job_id}"
    job_json = client.get(job_key)
    if job_json:
        job = ExtractionJob.from_json(job_json)
        job.status = "completed"
        client.set(job_key, job.to_json(), ex=3600)  # Keep for 1 hour after completion

    logger.info(f"Completed extraction job {job_id}")


def fail_job(job_id: str, error: str, requeue: bool = True) -> bool:
    """
    Mark a job as failed and optionally requeue for retry.

    Args:
        job_id: Job ID that failed
        error: Error message
        requeue: Whether to requeue for retry

    Returns:
        True if requeued, False if max retries exceeded
    """
    client = get_redis_client()

    # Remove from processing list
    client.lrem(EXTRACTION_PROCESSING, 1, job_id)

    # Get current job state
    job_key = f"ryumem:job:{job_id}"
    job_json = client.get(job_key)
    if not job_json:
        logger.warning(f"Failed job {job_id} not found in storage")
        return False

    job = ExtractionJob.from_json(job_json)
    job.retry_count += 1

    if requeue and job.retry_count < job.max_retries:
        # Requeue for retry
        job.status = "pending"
        client.set(job_key, job.to_json(), ex=86400)
        client.lpush(EXTRACTION_QUEUE, job_id)
        logger.info(f"Requeued job {job_id} for retry ({job.retry_count}/{job.max_retries})")
        return True
    else:
        # Max retries exceeded or no requeue
        job.status = "failed"
        client.set(job_key, job.to_json(), ex=3600)  # Keep failed jobs for 1 hour
        logger.error(f"Job {job_id} failed permanently after {job.retry_count} retries: {error}")
        return False


def update_job_status(job_id: str, status: str, result: Optional[dict] = None) -> None:
    """
    Update the status of a job.

    Args:
        job_id: Job ID to update
        status: New status
        result: Optional result data to store
    """
    client = get_redis_client()

    job_key = f"ryumem:job:{job_id}"
    job_json = client.get(job_key)
    if not job_json:
        logger.warning(f"Job {job_id} not found when updating status")
        return

    job = ExtractionJob.from_json(job_json)
    job.status = status
    client.set(job_key, job.to_json(), ex=86400)

    if result:
        result_key = f"ryumem:result:{job_id}"
        client.set(result_key, json.dumps(result), ex=86400)

    logger.debug(f"Updated job {job_id} status to {status}")


def get_job_status(job_id: str) -> Optional[dict]:
    """
    Get the current status of a job.

    Args:
        job_id: Job ID to query

    Returns:
        Dict with job status and result, or None if not found
    """
    client = get_redis_client()

    job_key = f"ryumem:job:{job_id}"
    job_json = client.get(job_key)
    if not job_json:
        return None

    job = ExtractionJob.from_json(job_json)

    # Get result if available
    result_key = f"ryumem:result:{job_id}"
    result_json = client.get(result_key)
    result = json.loads(result_json) if result_json else None

    return {
        "job_id": job.job_id,
        "episode_uuid": job.episode_uuid,
        "status": job.status,
        "retry_count": job.retry_count,
        "created_at": job.created_at.isoformat(),
        "result": result,
    }


def get_queue_stats() -> dict:
    """
    Get statistics about the extraction queue.

    Returns:
        Dict with queue statistics
    """
    client = get_redis_client()

    return {
        "pending": client.llen(EXTRACTION_QUEUE),
        "processing": client.llen(EXTRACTION_PROCESSING),
    }
