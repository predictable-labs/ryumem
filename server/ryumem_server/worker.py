"""
Extraction worker for async entity extraction via Redis queue.

Usage:
    ryumem-worker                    # Single worker
    ryumem-worker --workers 4        # Multiple concurrent workers
"""

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
from typing import Optional

import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from ryumem_server.queue.redis_client import RedisClient
from ryumem_server.queue.models import ExtractionJob, ExtractionResult

logger = logging.getLogger(__name__)


class ExtractionWorker:
    """Worker that processes entity extraction jobs from Redis queue."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        db_path: Optional[str] = None,
    ):
        """Initialize extraction worker.

        Args:
            redis_url: Redis connection URL. Defaults to REDIS_URL env var.
            db_path: Database path. Defaults to DB_PATH env var.
        """
        self.redis = RedisClient(redis_url) if redis_url else RedisClient()
        self.db_path = db_path or os.getenv("DB_PATH", "./data/ryumem.db")
        self.ryumem = None  # Lazy initialization
        self.running = False
        self._stop_event = asyncio.Event()

    def _init_ryumem(self):
        """Lazy initialization of Ryumem instance."""
        if self.ryumem is None:
            from ryumem_server.lib import Ryumem
            self.ryumem = Ryumem(db_path=self.db_path)
            logger.info(f"Initialized Ryumem with db_path={self.db_path}")

    async def process_job(self, job: ExtractionJob) -> ExtractionResult:
        """Process single extraction job.

        Args:
            job: ExtractionJob with episode details

        Returns:
            ExtractionResult with outcome
        """
        logger.info(f"Processing extraction for episode {job.episode_uuid}")

        # Update status to in_progress
        self.redis.set_status(job.episode_uuid, "in_progress", {
            "started_at": datetime.utcnow().isoformat()
        })

        try:
            # Initialize Ryumem if needed
            self._init_ryumem()

            # Run extraction
            result = self.ryumem.process_extraction(
                episode_uuid=job.episode_uuid,
                content=job.content,
                user_id=job.user_id,
                session_id=job.session_id,
            )

            extraction_result = ExtractionResult(
                episode_uuid=job.episode_uuid,
                status="completed",
                entities_count=result["entities_count"],
                edges_count=result["edges_count"],
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            )

            # Update Redis status
            self.redis.set_status(job.episode_uuid, "completed", {
                "entities_count": str(result["entities_count"]),
                "edges_count": str(result["edges_count"]),
                "completed_at": datetime.utcnow().isoformat()
            })

            logger.info(
                f"Extraction completed for episode {job.episode_uuid}: "
                f"{result['entities_count']} entities, {result['edges_count']} edges"
            )

        except Exception as e:
            logger.exception(f"Extraction failed for episode {job.episode_uuid}")

            extraction_result = ExtractionResult(
                episode_uuid=job.episode_uuid,
                status="failed",
                error=str(e),
                completed_at=datetime.utcnow(),
            )

            # Update Redis status
            self.redis.set_status(job.episode_uuid, "failed", {
                "error": str(e),
                "completed_at": datetime.utcnow().isoformat()
            })

        # Call webhook if provided
        if job.webhook_url:
            await self._call_webhook(job.webhook_url, extraction_result)

        return extraction_result

    async def _call_webhook(self, url: str, result: ExtractionResult):
        """Send webhook callback on extraction completion.

        Args:
            url: Webhook URL to POST to
            result: ExtractionResult to send
        """
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "event": f"extraction_{result.status}",
                    "episode_uuid": result.episode_uuid,
                    "entities_count": result.entities_count,
                    "edges_count": result.edges_count,
                    "error": result.error,
                    "completed_at": result.completed_at.isoformat() if result.completed_at else None,
                }

                response = await client.post(url, json=payload, timeout=30)
                logger.info(
                    f"Webhook sent to {url} for episode {result.episode_uuid}: "
                    f"status={response.status_code}"
                )

        except Exception as e:
            logger.warning(
                f"Webhook failed for episode {result.episode_uuid}: {e}"
            )

    async def run(self):
        """Main worker loop - process jobs from Redis queue."""
        self.running = True
        logger.info("Extraction worker started, waiting for jobs...")

        while self.running and not self._stop_event.is_set():
            try:
                # Blocking pop with 5 second timeout
                job_data = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.redis.dequeue_extraction(timeout=5)
                )

                if job_data:
                    job = ExtractionJob(**job_data)
                    await self.process_job(job)

            except Exception as e:
                logger.exception(f"Error in worker loop: {e}")
                await asyncio.sleep(1)  # Brief pause on error

        logger.info("Worker stopped")

    def stop(self):
        """Stop the worker gracefully."""
        logger.info("Stopping worker...")
        self.running = False
        self._stop_event.set()

    def close(self):
        """Clean up resources."""
        self.redis.close()
        if self.ryumem:
            self.ryumem.close()


async def run_workers(num_workers: int, redis_url: Optional[str], db_path: Optional[str]):
    """Run multiple workers concurrently.

    Args:
        num_workers: Number of concurrent workers
        redis_url: Redis connection URL
        db_path: Database path
    """
    workers = [
        ExtractionWorker(redis_url=redis_url, db_path=db_path)
        for _ in range(num_workers)
    ]

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("Received shutdown signal")
        for worker in workers:
            worker.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        # Run all workers
        await asyncio.gather(*[worker.run() for worker in workers])
    finally:
        # Clean up
        for worker in workers:
            worker.close()


def main():
    """CLI entry point for extraction worker."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Ryumem Entity Extraction Worker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    ryumem-worker                     # Single worker
    ryumem-worker --workers 4         # Multiple workers
    ryumem-worker --redis-url redis://localhost:6379
        """
    )
    parser.add_argument(
        "--redis-url",
        default=os.getenv("REDIS_URL"),
        help="Redis URL (default: REDIS_URL env var or redis://localhost:6379)"
    )
    parser.add_argument(
        "--db-path",
        default=os.getenv("DB_PATH"),
        help="Database path (default: DB_PATH env var or ./data/ryumem.db)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of concurrent workers (default: 1)"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    logger.info(f"Starting {args.workers} extraction worker(s)...")
    logger.info(f"Redis URL: {args.redis_url or 'redis://localhost:6379'}")
    logger.info(f"DB Path: {args.db_path or './data/ryumem.db'}")

    # Run workers
    asyncio.run(run_workers(
        num_workers=args.workers,
        redis_url=args.redis_url,
        db_path=args.db_path,
    ))


if __name__ == "__main__":
    main()
