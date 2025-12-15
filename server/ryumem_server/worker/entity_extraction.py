"""
Entity Extraction Background Worker

Pulls jobs from Redis queue, runs LLM-based entity/relationship extraction,
and calls back to server endpoints to persist results.

Usage:
    python -m ryumem_server.worker

Environment variables:
    REDIS_URL - Redis connection URL (default: redis://localhost:6379)
    SERVER_URL - Ryumem server URL (default: http://localhost:8000)
    WORKER_INTERNAL_KEY - Shared secret for internal endpoints
    OPENAI_API_KEY - API key for LLM and embeddings
    LLM_MODEL - Model name for extraction (default: gpt-4)
    EMBEDDING_MODEL - Model name for embeddings (default: text-embedding-3-large)
"""

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import uuid4

import httpx

from ryumem_server.worker.queue import (
    ExtractionJob,
    dequeue_extraction_job,
    complete_job,
    fail_job,
    get_queue_stats,
)
# Import all LLM/Embedding clients for provider selection
from ryumem_server.utils.llm import LLMClient
from ryumem_server.utils.llm_gemini import GeminiClient
from ryumem_server.utils.llm_ollama import OllamaClient
from ryumem_server.utils.llm_litellm import LiteLLMClient
from ryumem_server.utils.embeddings import EmbeddingClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration defaults
DEFAULT_SERVER_URL = "http://localhost:8000"
DEFAULT_LLM_MODEL = "gpt-4"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-large"
DEFAULT_EMBEDDING_DIMENSIONS = 3072


class EntityExtractionWorker:
    """
    Background worker for entity/relationship extraction.

    Processes extraction jobs from Redis queue and persists results
    via HTTP callbacks to the Ryumem server.
    """

    def __init__(
        self,
        server_url: str,
        internal_key: str,
        llm_client: LLMClient,
        embedding_client: EmbeddingClient,
        entity_similarity_threshold: float = 0.65,
        relationship_similarity_threshold: float = 0.8,
    ):
        """
        Initialize extraction worker.

        Args:
            server_url: Base URL of Ryumem server
            internal_key: Shared secret for internal endpoints
            llm_client: LLM client for extraction
            embedding_client: Embedding client for vectors
            entity_similarity_threshold: Threshold for entity deduplication
            relationship_similarity_threshold: Threshold for relationship deduplication
        """
        self.server_url = server_url.rstrip("/")
        self.internal_key = internal_key
        self.llm_client = llm_client
        self.embedding_client = embedding_client
        self.entity_similarity_threshold = entity_similarity_threshold
        self.relationship_similarity_threshold = relationship_similarity_threshold

        self._running = False
        self._http_client: Optional[httpx.AsyncClient] = None

        logger.info(f"Initialized EntityExtractionWorker (server: {server_url})")

    async def start(self):
        """Start the worker loop."""
        self._running = True
        self._http_client = httpx.AsyncClient(timeout=60.0)

        logger.info("Starting entity extraction worker...")

        while self._running:
            try:
                # Check queue stats periodically
                stats = get_queue_stats()
                if stats["pending"] > 0 or stats["processing"] > 0:
                    logger.debug(f"Queue stats: {stats['pending']} pending, {stats['processing']} processing")

                # Dequeue next job
                job = dequeue_extraction_job(timeout=5)
                if job is None:
                    continue

                logger.info(f"Processing job {job.job_id} for episode {job.episode_uuid}")

                # Process the job
                await self._process_job(job)

            except Exception as e:
                logger.error(f"Error in worker loop: {e}", exc_info=True)
                await asyncio.sleep(1)

        if self._http_client:
            await self._http_client.aclose()

        logger.info("Entity extraction worker stopped")

    def stop(self):
        """Stop the worker loop."""
        logger.info("Stopping entity extraction worker...")
        self._running = False

    async def _process_job(self, job: ExtractionJob):
        """
        Process a single extraction job.

        Steps:
        1. Extract entities using LLM
        2. Generate entity embeddings
        3. Upsert entities via server
        4. Extract relationships using LLM
        5. Generate relationship embeddings
        6. Upsert relationships via server
        7. Mark extraction complete
        """
        try:
            start_time = datetime.utcnow()
            entities_count = 0
            relationships_count = 0

            # Step 1: Extract entities using LLM
            logger.info(f"[{job.job_id}] Step 1: Extracting entities...")
            extracted_entities = self._extract_entities_with_llm(
                content=job.content,
                user_id=job.user_id,
                context=job.context,
            )

            if not extracted_entities:
                logger.info(f"[{job.job_id}] No entities extracted, marking complete")
                await self._mark_extraction_complete(
                    job=job,
                    entities_count=0,
                    relationships_count=0,
                )
                complete_job(job.job_id)
                return

            logger.info(f"[{job.job_id}] Extracted {len(extracted_entities)} raw entities")

            # Step 2: Generate entity embeddings
            logger.info(f"[{job.job_id}] Step 2: Generating entity embeddings...")
            entity_texts = [
                f"{e['entity']} ({e['entity_type']})"
                for e in extracted_entities
            ]
            entity_embeddings = self.embedding_client.embed_batch(entity_texts)

            # Step 3: Upsert entities via server
            logger.info(f"[{job.job_id}] Step 3: Upserting entities...")
            entity_map: Dict[str, str] = {}  # name -> uuid mapping

            for entity_data, embedding in zip(extracted_entities, entity_embeddings):
                entity_name = entity_data["entity"]
                entity_type = entity_data["entity_type"]

                result = await self._upsert_entity(
                    job=job,
                    name=entity_name,
                    entity_type=entity_type,
                    name_embedding=embedding,
                )

                if result:
                    entity_map[entity_name] = result["uuid"]
                    entities_count += 1

            logger.info(f"[{job.job_id}] Upserted {entities_count} entities")

            if not entity_map:
                logger.info(f"[{job.job_id}] No entities to link, marking complete")
                await self._mark_extraction_complete(
                    job=job,
                    entities_count=entities_count,
                    relationships_count=0,
                )
                complete_job(job.job_id)
                return

            # Step 4: Extract relationships using LLM
            logger.info(f"[{job.job_id}] Step 4: Extracting relationships...")
            entity_names = list(entity_map.keys())
            extracted_rels = self._extract_relationships_with_llm(
                content=job.content,
                entities=entity_names,
                user_id=job.user_id,
                context=job.context,
            )

            if not extracted_rels:
                logger.info(f"[{job.job_id}] No relationships extracted")
            else:
                logger.info(f"[{job.job_id}] Extracted {len(extracted_rels)} raw relationships")

                # Step 5: Generate relationship embeddings
                logger.info(f"[{job.job_id}] Step 5: Generating relationship embeddings...")
                facts = [r["fact"] for r in extracted_rels]
                fact_embeddings = self.embedding_client.embed_batch(facts)

                # Step 6: Upsert relationships via server
                logger.info(f"[{job.job_id}] Step 6: Upserting relationships...")
                for rel_data, embedding in zip(extracted_rels, fact_embeddings):
                    source_name = rel_data["source"].lower().replace(" ", "_")
                    dest_name = rel_data["destination"].lower().replace(" ", "_")
                    relation_type = rel_data["relationship"].upper().replace(" ", "_")
                    fact = rel_data["fact"]

                    source_uuid = entity_map.get(source_name)
                    dest_uuid = entity_map.get(dest_name)

                    if not source_uuid or not dest_uuid:
                        logger.warning(f"[{job.job_id}] Skipping relationship - entity not found: {source_name} -> {dest_name}")
                        continue

                    result = await self._upsert_relationship(
                        job=job,
                        source_entity_uuid=source_uuid,
                        target_entity_uuid=dest_uuid,
                        relation_type=relation_type,
                        fact=fact,
                        fact_embedding=embedding,
                    )

                    if result:
                        relationships_count += 1

                logger.info(f"[{job.job_id}] Upserted {relationships_count} relationships")

            # Step 7: Mark extraction complete
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"[{job.job_id}] Step 7: Marking extraction complete (took {duration:.2f}s)")

            await self._mark_extraction_complete(
                job=job,
                entities_count=entities_count,
                relationships_count=relationships_count,
            )

            complete_job(job.job_id)
            logger.info(f"[{job.job_id}] Job completed successfully: {entities_count} entities, {relationships_count} relationships")

        except Exception as e:
            logger.error(f"[{job.job_id}] Error processing job: {e}", exc_info=True)
            requeued = fail_job(job.job_id, str(e), requeue=True)
            if not requeued:
                # Mark as failed on server too
                await self._mark_extraction_complete(
                    job=job,
                    entities_count=0,
                    relationships_count=0,
                    error=str(e),
                )

    def _extract_entities_with_llm(
        self,
        content: str,
        user_id: str,
        context: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        Extract entities from content using LLM.

        Args:
            content: Text content
            user_id: User ID for self-reference resolution
            context: Optional context

        Returns:
            List of dicts with 'entity' and 'entity_type' keys
        """
        try:
            entities = self.llm_client.extract_entities(
                text=content,
                user_id=user_id,
                context=context,
            )

            # Normalize entity names
            normalized = []
            seen = set()

            for entity in entities:
                name = entity["entity"].lower().replace(" ", "_")
                if name not in seen:
                    normalized.append({
                        "entity": name,
                        "entity_type": entity["entity_type"].upper().replace(" ", "_")
                    })
                    seen.add(name)

            return normalized

        except Exception as e:
            logger.error(f"Error extracting entities with LLM: {e}")
            return []

    def _extract_relationships_with_llm(
        self,
        content: str,
        entities: List[str],
        user_id: str,
        context: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        Extract relationships from content using LLM.

        Args:
            content: Text content
            entities: List of entity names
            user_id: User ID
            context: Optional context

        Returns:
            List of dicts with 'source', 'destination', 'relationship', 'fact' keys
        """
        try:
            relationships = self.llm_client.extract_relationships(
                text=content,
                entities=entities,
                user_id=user_id,
                context=context,
            )
            return relationships

        except Exception as e:
            logger.error(f"Error extracting relationships with LLM: {e}")
            return []

    async def _upsert_entity(
        self,
        job: ExtractionJob,
        name: str,
        entity_type: str,
        name_embedding: List[float],
    ) -> Optional[Dict[str, Any]]:
        """
        Upsert an entity via server endpoint.

        Args:
            job: Current extraction job (for auth)
            name: Entity name
            entity_type: Entity type
            name_embedding: Entity name embedding

        Returns:
            Dict with entity info if successful, None otherwise
        """
        try:
            response = await self._http_client.post(
                f"{self.server_url}/internal/entities/upsert",
                json={
                    "name": name,
                    "entity_type": entity_type,
                    "name_embedding": name_embedding,
                    "user_id": job.user_id,
                    "customer_id": job.customer_id,
                    "similarity_threshold": self.entity_similarity_threshold,
                },
                headers=self._get_internal_headers(job),
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Error upserting entity '{name}': {e}")
            return None

    async def _upsert_relationship(
        self,
        job: ExtractionJob,
        source_entity_uuid: str,
        target_entity_uuid: str,
        relation_type: str,
        fact: str,
        fact_embedding: List[float],
    ) -> Optional[Dict[str, Any]]:
        """
        Upsert a relationship via server endpoint.

        Args:
            job: Current extraction job (for auth)
            source_entity_uuid: Source entity UUID
            target_entity_uuid: Target entity UUID
            relation_type: Relationship type
            fact: Fact description
            fact_embedding: Fact embedding

        Returns:
            Dict with relationship info if successful, None otherwise
        """
        try:
            response = await self._http_client.post(
                f"{self.server_url}/internal/relationships/upsert",
                json={
                    "source_entity_uuid": source_entity_uuid,
                    "target_entity_uuid": target_entity_uuid,
                    "relation_type": relation_type,
                    "fact": fact,
                    "fact_embedding": fact_embedding,
                    "episode_uuid": job.episode_uuid,
                    "user_id": job.user_id,
                    "customer_id": job.customer_id,
                    "similarity_threshold": self.relationship_similarity_threshold,
                },
                headers=self._get_internal_headers(job),
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Error upserting relationship: {e}")
            return None

    async def _mark_extraction_complete(
        self,
        job: ExtractionJob,
        entities_count: int,
        relationships_count: int,
        error: Optional[str] = None,
    ):
        """
        Mark extraction complete via server endpoint.

        Args:
            job: Current extraction job
            entities_count: Number of entities extracted
            relationships_count: Number of relationships extracted
            error: Optional error message if failed
        """
        try:
            response = await self._http_client.post(
                f"{self.server_url}/internal/episodes/{job.episode_uuid}/extraction-complete",
                json={
                    "job_id": job.job_id,
                    "entities_count": entities_count,
                    "relationships_count": relationships_count,
                    "customer_id": job.customer_id,
                    "error": error,
                },
                headers=self._get_internal_headers(job),
            )
            response.raise_for_status()

        except Exception as e:
            logger.error(f"Error marking extraction complete: {e}")

    def _get_internal_headers(self, job: ExtractionJob) -> Dict[str, str]:
        """Get headers for internal API calls."""
        headers = {
            "Content-Type": "application/json",
        }
        if self.internal_key:
            headers["X-Internal-Key"] = self.internal_key
        if job.api_key:
            headers["X-API-Key"] = job.api_key
        return headers


def create_worker() -> EntityExtractionWorker:
    """
    Create an EntityExtractionWorker from environment variables.

    Supported LLM providers:
        - gemini (default): Uses Google Gemini models
        - openai: Uses OpenAI GPT models
        - ollama: Uses local Ollama models
        - litellm: Uses LiteLLM for multi-provider support

    Supported Embedding providers:
        - gemini (default): Uses Gemini text-embedding-004
        - openai: Uses OpenAI text-embedding-3-large
        - ollama: Uses local Ollama embedding models
        - litellm: Uses LiteLLM for multi-provider support

    Environment variables:
        LLM_PROVIDER: LLM provider (gemini, openai, ollama, litellm)
        EMBEDDING_PROVIDER: Embedding provider (gemini, openai, ollama, litellm)
        GOOGLE_API_KEY: Required for gemini provider
        OPENAI_API_KEY: Required for openai provider
        OLLAMA_BASE_URL: Base URL for Ollama (default: http://localhost:11434)
        LLM_MODEL: Model name for LLM
        EMBEDDING_MODEL: Model name for embeddings
        EMBEDDING_DIMENSIONS: Embedding vector dimensions

    Returns:
        Configured EntityExtractionWorker instance
    """
    # Get configuration from environment
    server_url = os.environ.get("SERVER_URL", DEFAULT_SERVER_URL)
    internal_key = os.environ.get("WORKER_INTERNAL_KEY", "")

    # Provider configuration (default to Gemini)
    llm_provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    embedding_provider = os.environ.get("EMBEDDING_PROVIDER", "gemini").lower()

    # API keys
    google_api_key = os.environ.get("GOOGLE_API_KEY", "")
    openai_api_key = os.environ.get("OPENAI_API_KEY", "")
    ollama_base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    # Model configuration with provider-specific defaults
    if llm_provider == "gemini":
        default_llm_model = "gemini-2.0-flash-exp"
    elif llm_provider == "openai":
        default_llm_model = "gpt-4"
    elif llm_provider == "ollama":
        default_llm_model = "qwen2.5:7b"
    else:
        default_llm_model = "gpt-4"

    if embedding_provider == "gemini":
        default_embedding_model = "text-embedding-004"
        default_embedding_dimensions = 768
    elif embedding_provider == "openai":
        default_embedding_model = "text-embedding-3-large"
        default_embedding_dimensions = 3072
    elif embedding_provider == "ollama":
        default_embedding_model = "nomic-embed-text"
        default_embedding_dimensions = 768
    else:
        default_embedding_model = "text-embedding-3-large"
        default_embedding_dimensions = 3072

    llm_model = os.environ.get("LLM_MODEL", default_llm_model)
    embedding_model = os.environ.get("EMBEDDING_MODEL", default_embedding_model)
    embedding_dimensions = int(os.environ.get("EMBEDDING_DIMENSIONS", default_embedding_dimensions))

    # Initialize LLM client based on provider
    if llm_provider == "gemini":
        if not google_api_key:
            logger.error("GOOGLE_API_KEY environment variable is required for Gemini LLM provider")
            sys.exit(1)
        logger.info(f"Using Gemini for LLM: {llm_model}")
        llm_client = GeminiClient(
            api_key=google_api_key,
            model=llm_model,
        )
    elif llm_provider == "openai":
        if not openai_api_key:
            logger.error("OPENAI_API_KEY environment variable is required for OpenAI LLM provider")
            sys.exit(1)
        logger.info(f"Using OpenAI for LLM: {llm_model}")
        llm_client = LLMClient(
            api_key=openai_api_key,
            model=llm_model,
        )
    elif llm_provider == "ollama":
        logger.info(f"Using Ollama for LLM: {llm_model} at {ollama_base_url}")
        llm_client = OllamaClient(
            model=llm_model,
            base_url=ollama_base_url,
        )
    elif llm_provider == "litellm":
        logger.info(f"Using LiteLLM for LLM: {llm_model}")
        llm_client = LiteLLMClient(
            model=llm_model,
        )
    else:
        logger.error(f"Unknown LLM provider: {llm_provider}. Supported: gemini, openai, ollama, litellm")
        sys.exit(1)

    # Initialize embedding client based on provider
    if embedding_provider == "gemini":
        if not google_api_key:
            logger.error("GOOGLE_API_KEY environment variable is required for Gemini embedding provider")
            sys.exit(1)
        logger.info(f"Using Gemini for embeddings: {embedding_model}")
        embedding_client = GeminiClient(
            api_key=google_api_key,
            model=embedding_model,
        )
    elif embedding_provider == "openai":
        if not openai_api_key:
            logger.error("OPENAI_API_KEY environment variable is required for OpenAI embedding provider")
            sys.exit(1)
        logger.info(f"Using OpenAI for embeddings: {embedding_model}")
        embedding_client = EmbeddingClient(
            api_key=openai_api_key,
            model=embedding_model,
            dimensions=embedding_dimensions,
        )
    elif embedding_provider == "ollama":
        logger.info(f"Using Ollama for embeddings: {embedding_model} at {ollama_base_url}")
        embedding_client = OllamaClient(
            model=embedding_model,
            base_url=ollama_base_url,
        )
    elif embedding_provider == "litellm":
        logger.info(f"Using LiteLLM for embeddings: {embedding_model}")
        embedding_client = LiteLLMClient(
            model=embedding_model,
        )
    else:
        logger.error(f"Unknown embedding provider: {embedding_provider}. Supported: gemini, openai, ollama, litellm")
        sys.exit(1)

    # Create worker
    return EntityExtractionWorker(
        server_url=server_url,
        internal_key=internal_key,
        llm_client=llm_client,
        embedding_client=embedding_client,
    )


async def main():
    """Main entry point for the worker."""
    worker = create_worker()

    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        worker.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
