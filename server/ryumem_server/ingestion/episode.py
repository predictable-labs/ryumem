"""
Episode ingestion pipeline.
Orchestrates the entire ingestion process: episodes -> entities -> relationships -> invalidation.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, TYPE_CHECKING
from uuid import uuid4

from ryumem_server.core.graph_db import RyugraphDB
from ryumem_server.core.models import EpisodeNode, EpisodeType, EpisodeKind, EpisodicEdge
from ryumem_server.ingestion.entity_extractor import EntityExtractor
from ryumem_server.ingestion.relation_extractor import RelationExtractor
from ryumem_server.utils.embeddings import EmbeddingClient
from ryumem_server.utils.llm import LLMClient

if TYPE_CHECKING:
    from ryumem_server.retrieval.bm25 import BM25Index
    from ryumem.core.config import EpisodeConfig

logger = logging.getLogger(__name__)


class EpisodeIngestion:
    """
    Manages the complete episode ingestion pipeline.
    """

    def __init__(
        self,
        db: RyugraphDB,
        llm_client: LLMClient,
        embedding_client: EmbeddingClient,
        entity_similarity_threshold: float = 0.7,
        relationship_similarity_threshold: float = 0.8,
        max_context_episodes: int = 5,
        bm25_index: Optional["BM25Index"] = None,
        enable_entity_extraction: bool = False,
        episode_config: Optional["EpisodeConfig"] = None,
        worker_enabled: bool = False,
        redis_url: str = "redis://localhost:6379",
    ):
        """
        Initialize episode ingestion pipeline.

        Args:
            db: Ryugraph database instance
            llm_client: LLM client
            embedding_client: Embedding client
            entity_similarity_threshold: Threshold for entity deduplication
            relationship_similarity_threshold: Threshold for relationship deduplication
            max_context_episodes: Maximum number of previous episodes to use as context
            bm25_index: Optional BM25 index for keyword search
            enable_entity_extraction: Whether to enable entity extraction (default: False)
            episode_config: Episode configuration (default: creates new with defaults)
            worker_enabled: Whether to use background worker for entity extraction
            redis_url: Redis URL for worker queue (only used if worker_enabled=True)
        """
        from ryumem.core.config import EpisodeConfig

        self.db = db
        self.llm_client = llm_client
        self.embedding_client = embedding_client
        self.max_context_episodes = max_context_episodes
        self.bm25_index = bm25_index
        self.enable_entity_extraction = enable_entity_extraction
        self.episode_config = episode_config if episode_config is not None else EpisodeConfig()
        self.worker_enabled = worker_enabled
        self.redis_url = redis_url

        # Initialize extractors
        self.entity_extractor = EntityExtractor(
            db=db,
            llm_client=llm_client,
            embedding_client=embedding_client,
            similarity_threshold=entity_similarity_threshold,
        )

        self.relation_extractor = RelationExtractor(
            db=db,
            llm_client=llm_client,
            embedding_client=embedding_client,
            similarity_threshold=relationship_similarity_threshold,
        )

        logger.info(f"Initialized EpisodeIngestion pipeline (entity_extraction={'enabled' if enable_entity_extraction else 'disabled'})")

    def ingest(
        self,
        content: str,
        user_id: str,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        source: EpisodeType = EpisodeType.text,
        kind: 'EpisodeKind' = None,
        source_description: str = "",
        metadata: Optional[Dict] = None,
        name: Optional[str] = None,
        extract_entities: Optional[bool] = None,
        episode_config_override: Optional["EpisodeConfig"] = None,
        queue_extraction: Optional[bool] = None,
        customer_id: str = "",
        api_key: str = "",
    ) -> str:
        """
        Ingest a new episode and extract entities/relationships.

        This is the main entry point for the ingestion pipeline.

        Pipeline (sync mode):
        1. Create episode node
        2. Get context from previous episodes (if entity extraction enabled)
        3. Extract entities and resolve against existing (if enabled)
        4. Extract relationships and resolve against existing (if enabled)
        5. Create MENTIONS edges from episode to entities (if entities extracted)
        6. Detect and invalidate contradicting edges (if enabled)
        7. Update entity summaries (if enabled)

        Pipeline (async worker mode):
        1. Create episode node with content embedding
        2. Queue extraction job to Redis
        3. Return immediately (worker handles steps 2-7)

        Args:
            content: Episode content (text, message, or JSON)
            user_id: User ID (required)
            agent_id: Optional agent ID
            session_id: Optional session ID
            source: Type of episode (message, json, text)
            source_description: Description of the source
            metadata: Optional metadata dictionary
            name: Optional name for the episode
            extract_entities: Override instance setting for entity extraction (None uses instance default)
            queue_extraction: Override worker setting (None uses instance default)
            customer_id: Customer ID for worker authentication (used when queueing)
            api_key: API key for worker authentication (used when queueing)

        Returns:
            UUID of the created episode
        """
        # Determine whether to extract entities for this request
        # Per-request override takes precedence over instance setting
        should_extract_entities = extract_entities if extract_entities is not None else self.enable_entity_extraction

        # Determine whether to use worker queue
        # Per-request override takes precedence, then instance setting
        should_queue = queue_extraction if queue_extraction is not None else self.worker_enabled

        # Use override config if provided, otherwise use instance config
        config = episode_config_override if episode_config_override is not None else self.episode_config

        start_time = datetime.utcnow()

        # Generate embedding if enabled (for semantic duplicate detection)
        if config.enable_embeddings:
            content_embedding = self.embedding_client.embed(content)
        else:
            content_embedding = None

        # Check for duplicate episode if deduplication enabled
        existing_episode = None
        if config.deduplication_enabled:
            if config.enable_embeddings:
                # Use semantic similarity (embedding-based)
                existing_episode = self.db.find_similar_episode(
                    content=content,
                    content_embedding=content_embedding,
                    user_id=user_id,
                    time_window_hours=config.time_window_hours,
                    similarity_threshold=config.similarity_threshold,
                )
            else:
                # Use BM25 keyword similarity
                existing_episode = self.db.find_similar_episode_bm25(
                    content=content,
                    user_id=user_id,
                    bm25_index=self.bm25_index,
                    time_window_hours=config.time_window_hours,
                    similarity_threshold=config.bm25_similarity_threshold,
                )

        if existing_episode:
            logger.info(
                f"Duplicate episode detected! Skipping ingestion. "
                f"Existing episode: {existing_episode['uuid'][:8]}... "
                f"created at {existing_episode['created_at']}"
            )
            return existing_episode["uuid"]

        step_start = start_time

        # Generate episode UUID
        episode_uuid = str(uuid4())

        # Generate episode name if not provided
        if not name:
            name = f"Episode {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"

        logger.info(f"Starting ingestion for episode {episode_uuid}")

        # Ensure metadata includes session_id if provided
        episode_metadata = metadata.copy() if metadata else {}
        if session_id:
            # Initialize or update sessions structure so get_episode_by_session_id can find it
            if 'sessions' not in episode_metadata:
                episode_metadata['sessions'] = {}
            if session_id not in episode_metadata['sessions']:
                episode_metadata['sessions'][session_id] = []

        episode = EpisodeNode(
            uuid=episode_uuid,
            name=name,
            content=content,
            content_embedding=content_embedding,
            source=source,
            source_description=source_description,
            kind=kind if kind is not None else EpisodeKind.query,
            created_at=start_time,
            valid_at=start_time,
            user_id=user_id,
            agent_id=agent_id,
            metadata=episode_metadata,
        )

        # Save episode to database
        self.db.save_episode(episode)

        # Add episode to BM25 index for keyword search
        if self.bm25_index:
            self.bm25_index.add_episode(episode)
            logger.debug(f"Added episode to BM25 index")

        step_duration = (datetime.utcnow() - step_start).total_seconds()
        logger.info(f"⏱️  [TIMING] Step 1 - Create episode node with embedding: {step_duration:.2f}s")
        logger.debug(f"Created episode node: {episode_uuid}")

        # Check if we should queue extraction to background worker
        if should_extract_entities and should_queue:
            return self._queue_extraction_job(
                episode_uuid=episode_uuid,
                content=content,
                user_id=user_id,
                session_id=session_id,
                customer_id=customer_id,
                api_key=api_key,
                episode_metadata=episode_metadata,
            )

        # Step 2: Get context from previous episodes (only if entity extraction is enabled)
        if should_extract_entities:
            step_start = datetime.utcnow()
            context = self._get_episode_context(
                user_id=user_id,
                session_id=session_id,
            )
            step_duration = (datetime.utcnow() - step_start).total_seconds()
            logger.info(f"⏱️  [TIMING] Step 2 - Get episode context: {step_duration:.2f}s")
        else:
            context = []
            logger.info(f"Entity extraction disabled for episode {episode_uuid}, skipping context retrieval")

        # Step 3: Extract and resolve entities (OPTIONAL - controlled by flag)
        if should_extract_entities:
            step_start = datetime.utcnow()
            entities, entity_map = self.entity_extractor.extract_and_resolve(
                content=content,
                user_id=user_id,
                context=context,
            )
            step_duration = (datetime.utcnow() - step_start).total_seconds()
            logger.info(f"⏱️  [TIMING] Step 3 - Extract and resolve entities: {step_duration:.2f}s ({len(entities)} entities)")

            if not entities:
                logger.info(f"No entities extracted for episode {episode_uuid}")
                return episode_uuid
        else:
            entities = []
            entity_map = {}
            logger.info(f"Entity extraction disabled for episode {episode_uuid}, skipping Steps 3-7")
            return episode_uuid

        # Add entities to BM25 index
        step_start = datetime.utcnow()
        if self.bm25_index:
            for entity in entities:
                self.bm25_index.add_entity(entity)
            step_duration = (datetime.utcnow() - step_start).total_seconds()
            logger.info(f"⏱️  [TIMING] Step 3b - Add entities to BM25 index: {step_duration:.2f}s")
            logger.debug(f"Added {len(entities)} entities to BM25 index")

        # Step 4: Extract and resolve relationships
        step_start = datetime.utcnow()
        edges = self.relation_extractor.extract_and_resolve(
            content=content,
            entities=entities,
            entity_map=entity_map,
            episode_uuid=episode_uuid,
            user_id=user_id,
            context=context,
        )
        step_duration = (datetime.utcnow() - step_start).total_seconds()
        logger.info(f"⏱️  [TIMING] Step 4 - Extract and resolve relationships: {step_duration:.2f}s ({len(edges)} edges)")

        # Add edges to BM25 index
        step_start = datetime.utcnow()
        if self.bm25_index and edges:
            for edge in edges:
                self.bm25_index.add_edge(edge)
            step_duration = (datetime.utcnow() - step_start).total_seconds()
            logger.info(f"⏱️  [TIMING] Step 4b - Add edges to BM25 index: {step_duration:.2f}s")
            logger.debug(f"Added {len(edges)} edges to BM25 index")

        # Step 5: Create MENTIONS edges (episode -> entities)
        step_start = datetime.utcnow()
        self._create_mentions_edges(
            episode_uuid=episode_uuid,
            entity_uuids=[e.uuid for e in entities],
        )
        step_duration = (datetime.utcnow() - step_start).total_seconds()
        logger.info(f"⏱️  [TIMING] Step 5 - Create MENTIONS edges: {step_duration:.2f}s")

        # Step 6: Detect and invalidate contradicting edges
        step_start = datetime.utcnow()
        if edges:
            contradicting_edges = self.relation_extractor.detect_contradictions(
                new_edges=edges,
                user_id=user_id,
            )

            if contradicting_edges:
                self.relation_extractor.invalidate_edges(contradicting_edges)
                logger.info(f"Invalidated {len(contradicting_edges)} contradicting edges")
        step_duration = (datetime.utcnow() - step_start).total_seconds()
        logger.info(f"⏱️  [TIMING] Step 6 - Detect and invalidate contradictions: {step_duration:.2f}s")

        # Step 7: Update entity summaries with new context
        step_start = datetime.utcnow()
        for entity in entities:
            try:
                self.entity_extractor.update_entity_summary(
                    entity_uuid=entity.uuid,
                    new_context=content,
                )
            except Exception as e:
                logger.error(f"Error updating summary for entity {entity.uuid}: {e}")
        step_duration = (datetime.utcnow() - step_start).total_seconds()
        logger.info(f"⏱️  [TIMING] Step 7 - Update entity summaries: {step_duration:.2f}s")

        # Update episode with entity edge references
        episode.entity_edges = [e.uuid for e in edges]
        self.db.save_episode(episode)

        # Log completion
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"⏱️  [TIMING] ═══════════════════════════════════════════════════")
        logger.info(
            f"⏱️  [TIMING] TOTAL ingestion time for episode {episode_uuid[:8]}: {duration:.2f}s"
        )
        logger.info(f"⏱️  [TIMING] Results: {len(entities)} entities, {len(edges)} relationships")
        logger.info(f"⏱️  [TIMING] ═══════════════════════════════════════════════════")

        return episode_uuid

    def ingest_batch(
        self,
        episodes: List[Dict],
        user_id: str,
    ) -> List[str]:
        """
        Ingest multiple episodes in batch.

        Args:
            episodes: List of episode dictionaries with keys:
                - content: Episode content
                - agent_id: Optional agent ID
                - session_id: Optional session ID
                - source: Optional episode type
                - metadata: Optional metadata
            user_id: User ID (required)

        Returns:
            List of episode UUIDs
        """
        episode_uuids = []

        for i, episode_data in enumerate(episodes):
            try:
                uuid = self.ingest(
                    content=episode_data["content"],
                    user_id=user_id,
                    agent_id=episode_data.get("agent_id"),
                    session_id=episode_data.get("session_id"),
                    source=episode_data.get("source", EpisodeType.text),
                    metadata=episode_data.get("metadata"),
                )
                episode_uuids.append(uuid)
                logger.info(f"Batch ingestion: {i + 1}/{len(episodes)} completed")

            except Exception as e:
                logger.error(f"Error ingesting episode {i + 1}: {e}")
                continue

        logger.info(f"Batch ingestion completed: {len(episode_uuids)}/{len(episodes)} successful")
        return episode_uuids

    def _get_episode_context(
        self,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> str:
        """
        Get context from previous episodes.

        Args:
            user_id: User ID (required)
            session_id: Optional session ID filter

        Returns:
            Formatted context string
        """
        try:
            recent_episodes = self.db.get_episode_context(
                user_id=user_id,
                limit=self.max_context_episodes,
                session_id=session_id,
            )

            if not recent_episodes:
                return ""

            # Format episodes as context
            context_lines = ["Previous episodes:"]
            for ep in recent_episodes:
                context_lines.append(f"- {ep['name']}: {ep['content'][:100]}...")

            return "\n".join(context_lines)

        except Exception as e:
            logger.error(f"Error getting episode context: {e}")
            return ""

    def _create_mentions_edges(
        self,
        episode_uuid: str,
        entity_uuids: List[str],
    ) -> None:
        """
        Create MENTIONS edges from episode to entities.

        Args:
            episode_uuid: UUID of the episode
            entity_uuids: List of entity UUIDs mentioned in the episode
        """
        for entity_uuid in entity_uuids:
            try:
                edge = EpisodicEdge(
                    uuid=str(uuid4()),
                    source_node_uuid=episode_uuid,
                    target_node_uuid=entity_uuid,
                    created_at=datetime.utcnow(),
                )

                self.db.save_episodic_edge(edge)

            except Exception as e:
                logger.error(
                    f"Error creating MENTIONS edge from {episode_uuid} to {entity_uuid}: {e}"
                )

    def _queue_extraction_job(
        self,
        episode_uuid: str,
        content: str,
        user_id: str,
        session_id: Optional[str] = None,
        customer_id: str = "",
        api_key: str = "",
        episode_metadata: Optional[Dict] = None,
    ) -> str:
        """
        Queue an extraction job to the background worker.

        Args:
            episode_uuid: UUID of the episode to extract entities from
            content: Episode content
            user_id: User ID
            session_id: Optional session ID for context
            customer_id: Customer ID for authentication
            api_key: API key for authentication
            episode_metadata: Episode metadata dict to update with job info

        Returns:
            Episode UUID
        """
        import os
        try:
            from ryumem_server.worker.queue import ExtractionJob, enqueue_extraction_job

            # Get context for extraction
            context = self._get_episode_context(
                user_id=user_id,
                session_id=session_id,
            )

            # Create extraction job
            job_id = str(uuid4())
            job = ExtractionJob(
                job_id=job_id,
                episode_uuid=episode_uuid,
                content=content,
                user_id=user_id,
                customer_id=customer_id,
                api_key=api_key,
                context=context if context else None,
                created_at=datetime.utcnow(),
            )

            # Set Redis URL from environment or instance config
            redis_url = os.environ.get("REDIS_URL", self.redis_url)
            os.environ["REDIS_URL"] = redis_url

            # Enqueue the job
            enqueue_extraction_job(job)

            # Update episode metadata with extraction status
            if episode_metadata is None:
                episode_metadata = {}

            episode_metadata["extraction_status"] = "pending"
            episode_metadata["extraction_job_id"] = job_id
            episode_metadata["extraction_queued_at"] = datetime.utcnow().isoformat()

            # Update episode in database
            self.db.execute(
                "MATCH (e:Episode {uuid: $uuid}) SET e.metadata = $metadata",
                {"uuid": episode_uuid, "metadata": json.dumps(episode_metadata)}
            )

            logger.info(f"Queued extraction job {job_id} for episode {episode_uuid}")
            return episode_uuid

        except ImportError as e:
            logger.warning(f"Redis/worker not available, falling back to sync extraction: {e}")
            # Fallback to sync extraction if worker not available
            return self._sync_extraction(episode_uuid, content, user_id, session_id)
        except Exception as e:
            logger.error(f"Error queueing extraction job: {e}")
            # Fallback to sync extraction on error
            return self._sync_extraction(episode_uuid, content, user_id, session_id)

    def _sync_extraction(
        self,
        episode_uuid: str,
        content: str,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> str:
        """
        Fallback synchronous extraction when worker is not available.

        This runs the full extraction pipeline synchronously.
        """
        logger.info(f"Running synchronous extraction for episode {episode_uuid}")

        # Get context
        context = self._get_episode_context(
            user_id=user_id,
            session_id=session_id,
        )

        # Extract entities
        entities, entity_map = self.entity_extractor.extract_and_resolve(
            content=content,
            user_id=user_id,
            context=context,
        )

        if not entities:
            logger.info(f"No entities extracted for episode {episode_uuid}")
            return episode_uuid

        # Extract relationships
        edges = self.relation_extractor.extract_and_resolve(
            content=content,
            entities=entities,
            entity_map=entity_map,
            episode_uuid=episode_uuid,
            user_id=user_id,
            context=context,
        )

        # Create MENTIONS edges
        self._create_mentions_edges(
            episode_uuid=episode_uuid,
            entity_uuids=[e.uuid for e in entities],
        )

        # Detect contradictions
        if edges:
            contradicting_edges = self.relation_extractor.detect_contradictions(
                new_edges=edges,
                user_id=user_id,
            )
            if contradicting_edges:
                self.relation_extractor.invalidate_edges(contradicting_edges)

        # Update summaries
        for entity in entities:
            try:
                self.entity_extractor.update_entity_summary(
                    entity_uuid=entity.uuid,
                    new_context=content,
                )
            except Exception as e:
                logger.error(f"Error updating summary for entity {entity.uuid}: {e}")

        # Add to BM25 index
        if self.bm25_index:
            for entity in entities:
                self.bm25_index.add_entity(entity)
            for edge in edges:
                self.bm25_index.add_edge(edge)

        logger.info(f"Sync extraction complete: {len(entities)} entities, {len(edges)} relationships")
        return episode_uuid
