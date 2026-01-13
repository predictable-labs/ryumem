"""
Redis client for extraction job queue.
"""

import json
import os
import logging
from datetime import datetime
from typing import Optional

import redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
EXTRACTION_QUEUE = "ryumem:extraction:jobs"
EXTRACTION_STATUS_PREFIX = "ryumem:extraction:status:"
STATUS_TTL_SECONDS = 86400  # 24 hours


class RedisClient:
    """Client for managing extraction job queue and status in Redis."""

    def __init__(self, url: Optional[str] = None):
        """Initialize Redis client.

        Args:
            url: Redis connection URL. Defaults to REDIS_URL env var.
        """
        self.url = url or REDIS_URL
        self._client: Optional[redis.Redis] = None

    @property
    def client(self) -> redis.Redis:
        """Lazy connection to Redis."""
        if self._client is None:
            self._client = redis.from_url(self.url, decode_responses=True)
        return self._client

    def close(self):
        """Close Redis connection."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def enqueue_extraction(self, job: dict) -> str:
        """Push extraction job to queue.

        Args:
            job: Job data dict (ExtractionJob.model_dump())

        Returns:
            Job ID (episode_uuid)
        """
        job_id = job["episode_uuid"]

        # Serialize datetime objects
        serialized_job = self._serialize_job(job)

        self.client.lpush(EXTRACTION_QUEUE, json.dumps(serialized_job))
        self.set_status(job_id, "pending", {
            "queued_at": datetime.utcnow().isoformat()
        })

        logger.info(f"Enqueued extraction job for episode {job_id}")
        return job_id

    def dequeue_extraction(self, timeout: int = 0) -> Optional[dict]:
        """Blocking pop from queue.

        Args:
            timeout: Seconds to wait (0 = block forever)

        Returns:
            Job data dict or None if timeout
        """
        result = self.client.brpop(EXTRACTION_QUEUE, timeout=timeout)
        if result:
            _, job_json = result
            return json.loads(job_json)
        return None

    def set_status(self, job_id: str, status: str, metadata: Optional[dict] = None):
        """Set extraction status with optional metadata.

        Args:
            job_id: Episode UUID
            status: Status string (pending, in_progress, completed, failed)
            metadata: Additional status metadata
        """
        key = f"{EXTRACTION_STATUS_PREFIX}{job_id}"
        data = {"status": status, **(metadata or {})}

        # Serialize values
        serialized = {k: str(v) if not isinstance(v, str) else v for k, v in data.items()}

        self.client.hset(key, mapping=serialized)
        self.client.expire(key, STATUS_TTL_SECONDS)

    def get_status(self, job_id: str) -> dict:
        """Get extraction status.

        Args:
            job_id: Episode UUID

        Returns:
            Status dict with status and metadata fields
        """
        key = f"{EXTRACTION_STATUS_PREFIX}{job_id}"
        return self.client.hgetall(key)

    def get_queue_length(self) -> int:
        """Get number of pending jobs in queue."""
        return self.client.llen(EXTRACTION_QUEUE)

    def _serialize_job(self, job: dict) -> dict:
        """Serialize job dict for JSON encoding."""
        result = {}
        for key, value in job.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, dict):
                result[key] = self._serialize_job(value)
            else:
                result[key] = value
        return result


# Singleton instance for easy import
_default_client: Optional[RedisClient] = None


def get_redis_client() -> RedisClient:
    """Get or create default Redis client singleton."""
    global _default_client
    if _default_client is None:
        _default_client = RedisClient()
    return _default_client
