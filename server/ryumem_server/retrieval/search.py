"""
Search and retrieval system.
Implements semantic search, graph traversal, BM25, and hybrid search strategies.
"""

import json
import logging
import math
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from ryumem_server.core.graph_db import RyugraphDB
from ryumem_server.core.models import EntityEdge, EntityNode, EpisodeNode, EpisodeType, SearchConfig, SearchResult
from ryumem_server.retrieval.bm25 import BM25Index
from ryumem_server.utils.embeddings import EmbeddingClient

logger = logging.getLogger(__name__)


def _sanitize_user_id(user_id: Any) -> Optional[str]:
    """
    Sanitize user_id value from database.
    Converts nan (float) to None, which can happen when SQLite returns NULL.

    Args:
        user_id: Raw user_id value from database

    Returns:
        None if user_id is None or nan, otherwise the string value
    """
    if user_id is None:
        return None
    # Check if it's a float nan
    if isinstance(user_id, float) and math.isnan(user_id):
        return None
    return user_id


class SearchEngine:
    """
    Unified search engine with multiple retrieval strategies.
    """

    def __init__(
        self,
        db: RyugraphDB,
        embedding_client: EmbeddingClient,
        bm25_index: Optional[BM25Index] = None,
        episode_config: Optional[Any] = None,
    ):
        """
        Initialize search engine.

        Args:
            db: Ryugraph database instance
            embedding_client: Embedding client for semantic search
            bm25_index: Optional BM25 index (created if not provided)
            episode_config: Episode configuration for embeddings settings
        """
        from ryumem.core.config import EpisodeConfig

        self.db = db
        self.embedding_client = embedding_client
        self.episode_config = episode_config if episode_config is not None else EpisodeConfig()
        self.bm25_index = bm25_index or BM25Index()

        logger.info("Initialized SearchEngine")

    def search(self, config: SearchConfig) -> SearchResult:
        """
        Perform search using the specified strategy.

        Args:
            config: Search configuration

        Returns:
            SearchResult with entities, edges, and scores
        """
        logger.info(
            f"Starting search: strategy={config.strategy}, "
            f"query='{config.query[:50]}...', limit={config.limit}"
        )

        # Auto-fallback to BM25 if semantic/hybrid requested but embeddings disabled
        strategy = config.strategy
        if strategy in ["semantic", "hybrid"] and not self.episode_config.enable_embeddings:
            logger.warning(
                f"Episode embeddings disabled, falling back to BM25 for query: {config.query[:50]}"
            )
            strategy = "bm25"

        # Auto-fallback to BM25 for tag-only search (empty query)
        if not config.query and strategy in ["semantic", "hybrid"]:
            logger.info("Tag-only search detected, using BM25 strategy")
            strategy = "bm25"

        # Run base search strategy
        if strategy == "semantic":
            results = self._semantic_search(config)
        elif strategy == "traversal":
            results = self._traversal_search(config)
        elif strategy == "bm25":
            results = self._bm25_search(config)
        elif strategy == "hybrid":
            results = self._hybrid_search(config)
        else:
            raise ValueError(f"Unknown search strategy: {config.strategy}")

        # Apply temporal decay if enabled
        if config.apply_temporal_decay:
            results = self._apply_temporal_decay(
                results,
                decay_factor=config.temporal_decay_factor,
            )

        # Apply update-awareness boost if enabled
        if config.apply_update_boost:
            results = self._apply_update_boost(
                results,
                boost_factor=config.update_boost_factor,
                recent_threshold_days=config.recent_threshold_days,
            )

        return results

    def _semantic_search(self, config: SearchConfig) -> SearchResult:
        """
        Semantic search using embedding similarity.

        New strategy: Episode-first search
        1. Search episodes by content similarity
        2. Get entities mentioned in those episodes
        3. Get relationships between those entities
        4. Also search entities and edges directly for additional context

        Args:
            config: Search configuration

        Returns:
            SearchResult
        """
        # Generate query embedding
        logger.debug(f"🔍 Generating embedding for query: '{config.query}'")
        query_embedding = self.embedding_client.embed(config.query)
        logger.debug(f"✅ Generated embedding: {len(query_embedding)} dimensions")
        logger.debug(f"🔍 Query embedding: {query_embedding}")

        # Step 1: Search similar episodes (NEW)
        logger.debug(f"🎬 Searching for similar episodes (threshold: {config.similarity_threshold}, limit: {config.limit}, kinds: {config.kinds})")
        episode_results = self.db.search_similar_episodes(
            embedding=query_embedding,
            user_id=config.user_id,
            threshold=config.similarity_threshold,
            limit=config.limit,
            kinds=config.kinds,
            tags=config.tags,
            tag_match_mode=config.tag_match_mode,
        )
        logger.debug(f"📊 Found {len(episode_results)} similar episodes")

        # Step 2: Get entities from matched episodes
        episode_entity_uuids = set()
        for episode in episode_results:
            # Get entities mentioned in this episode via MENTIONS edges
            mentioned_entities = self.db.get_episode_entities(episode["uuid"])
            episode_entity_uuids.update([e["uuid"] for e in mentioned_entities])

        logger.debug(f"📊 Found {len(episode_entity_uuids)} entities from episodes")

        # Step 3: Search similar entities (direct semantic search)
        logger.debug(f"🔎 Searching for similar entities (threshold: {config.similarity_threshold}, limit: {config.limit})")
        entity_results = self.db.search_similar_entities(
            embedding=query_embedding,
            user_id=config.user_id,
            threshold=config.similarity_threshold,
            limit=config.limit,
        )
        logger.debug(f"📊 Found {len(entity_results)} similar entities")

        # Step 4: Search similar edges
        logger.debug(f"🔎 Searching for similar edges (threshold: {config.similarity_threshold}, limit: {config.limit})")
        edge_results = self.db.search_similar_edges(
            embedding=query_embedding,
            user_id=config.user_id,
            threshold=config.similarity_threshold,
            limit=config.limit,
        )
        logger.debug(f"📊 Found {len(edge_results)} similar edges")

        # Convert to models
        entities: List[EntityNode] = []
        scores: Dict[str, float] = {}
        seen_entity_uuids = set()

        # Add entities from directly-searched entity results with their similarity scores
        for result in entity_results:
            entity = EntityNode(
                uuid=result["uuid"],
                name=result["name"],
                entity_type=result["entity_type"],
                summary=result.get("summary", ""),
                mentions=result["mentions"],
                user_id=_sanitize_user_id(result.get("user_id")),
            )
            entities.append(entity)
            scores[entity.uuid] = result["similarity"]
            seen_entity_uuids.add(entity.uuid)

        # Add entities from episodes (if not already included)
        for entity_uuid in episode_entity_uuids:
            if entity_uuid not in seen_entity_uuids:
                # Fetch full entity data
                entity_data = self.db.get_entity_by_uuid(entity_uuid)
                if entity_data:
                    entity = EntityNode(
                        uuid=entity_data["uuid"],
                        name=entity_data["name"],
                        entity_type=entity_data["entity_type"],
                        summary=entity_data.get("summary", ""),
                        mentions=entity_data["mentions"],
                        user_id=_sanitize_user_id(entity_data.get("user_id")),
                    )
                    entities.append(entity)
                    # Give these entities a slightly lower score since they came from episode association
                    scores[entity.uuid] = config.similarity_threshold * 0.9
                    seen_entity_uuids.add(entity_uuid)

        edges: List[EntityEdge] = []
        for result in edge_results:
            edge = EntityEdge(
                uuid=result["edge_uuid"],
                source_node_uuid=result["source_uuid"],
                target_node_uuid=result["target_uuid"],
                name=result["relation_type"],
                fact=result["fact"],
            )
            edges.append(edge)
            scores[edge.uuid] = result["similarity"]

        # Convert episode results to EpisodeNode objects
        episodes: List[EpisodeNode] = []
        for result in episode_results:
            try:
                # Handle nan values for optional string fields
                def safe_str_or_none(value):
                    if value is None or (isinstance(value, float) and math.isnan(value)):
                        return None
                    return value

                # Handle metadata deserialization
                metadata = result.get("metadata", {})
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except (json.JSONDecodeError, TypeError):
                        metadata = {}

                # Extract chunking data from metadata if present
                chunks = None
                chunk_offsets = None
                chunking_data = metadata.get("_chunking", {})
                if chunking_data:
                    chunks = chunking_data.get("chunks")
                    chunk_offsets = chunking_data.get("chunk_offsets")
                    # Convert chunk_offsets to tuples if stored as lists
                    if chunk_offsets:
                        chunk_offsets = [tuple(offset) if isinstance(offset, list) else offset for offset in chunk_offsets]

                from ryumem_server.core.models import EpisodeKind
                episode = EpisodeNode(
                    uuid=result["uuid"],
                    name=result.get("name", ""),
                    content=result["content"],
                    source=EpisodeType.from_str(result.get("source", "text")),
                    source_description=result.get("source_description", ""),
                    kind=EpisodeKind.from_str(result.get("kind", "query")),
                    user_id=safe_str_or_none(result.get("user_id")),
                    agent_id=safe_str_or_none(result.get("agent_id")),
                    metadata=metadata,
                    # Include chunk data
                    chunks=chunks,
                    chunk_offsets=chunk_offsets,
                )
                episodes.append(episode)
                scores[episode.uuid] = result["similarity"]
            except Exception as e:
                logger.warning(f"Failed to convert episode result to EpisodeNode: {e}, skipping episode {result.get('uuid', 'unknown')}")
                continue

        logger.info(
            f"Semantic search found {len(episode_results)} episodes, "
            f"{len(entities)} entities ({len(episode_entity_uuids)} from episodes), "
            f"{len(edges)} edges"
        )

        return SearchResult(
            entities=entities,
            edges=edges,
            episodes=episodes,  # Add episodes to the result!
            scores=scores,
            metadata={
                "strategy": "semantic",
                "query": config.query,
                "threshold": config.similarity_threshold,
                "episodes_found": len(episode_results),
                "entities_from_episodes": len(episode_entity_uuids),
            }
        )

    def _traversal_search(self, config: SearchConfig) -> SearchResult:
        """
        Graph traversal search starting from query-matched entities.

        Args:
            config: Search configuration

        Returns:
            SearchResult
        """
        # First, find starting entities using semantic search
        query_embedding = self.embedding_client.embed(config.query)

        starting_entities = self.db.search_similar_entities(
            embedding=query_embedding,
            user_id=config.user_id,
            threshold=config.similarity_threshold,
            limit=min(config.limit, 5),  # Limit starting points
        )

        if not starting_entities:
            logger.info("No starting entities found for traversal")
            return SearchResult(entities=[], edges=[], scores={})

        # Traverse graph from starting entities
        visited_entities: Set[str] = set()
        visited_edges: Set[str] = set()
        entities: List[EntityNode] = []
        edges: List[EntityEdge] = []
        scores: Dict[str, float] = {}

        # Add starting entities
        for result in starting_entities:
            entity_uuid = result["uuid"]
            visited_entities.add(entity_uuid)

            entity = EntityNode(
                uuid=entity_uuid,
                name=result["name"],
                entity_type=result["entity_type"],
                summary=result.get("summary", ""),
                mentions=result["mentions"],
                user_id=_sanitize_user_id(result.get("user_id")),
            )
            entities.append(entity)
            scores[entity_uuid] = result["similarity"]

        # BFS traversal
        current_depth = 0
        current_layer = [e["uuid"] for e in starting_entities]

        while current_depth < config.max_depth and current_layer:
            next_layer: List[str] = []

            for entity_uuid in current_layer:
                # Get relationships for this entity
                relationships = self.db.get_entity_relationships(
                    entity_uuid=entity_uuid,
                    include_expired=config.include_expired,
                )

                for rel in relationships:
                    # Add edge if not visited
                    edge_uuid = rel["edge_uuid"]
                    if edge_uuid not in visited_edges:
                        visited_edges.add(edge_uuid)

                        edge = EntityEdge(
                            uuid=edge_uuid,
                            source_node_uuid=rel["entity_uuid"],
                            target_node_uuid=rel["other_uuid"],
                            name=rel["relation_type"],
                            fact=rel["fact"],
                            valid_at=rel.get("valid_at"),
                            invalid_at=rel.get("invalid_at"),
                            expired_at=rel.get("expired_at"),
                        )
                        edges.append(edge)
                        # Decay score by depth
                        scores[edge_uuid] = 1.0 / (current_depth + 1)

                    # Add connected entity if not visited
                    other_uuid = rel["other_uuid"]
                    if other_uuid not in visited_entities:
                        visited_entities.add(other_uuid)

                        entity = EntityNode(
                            uuid=other_uuid,
                            name=rel["other_name"],
                            entity_type="ENTITY",  # Would need to fetch full details
                        )
                        entities.append(entity)
                        next_layer.append(other_uuid)
                        # Decay score by depth
                        scores[other_uuid] = 1.0 / (current_depth + 2)

                # Stop if we've reached the limit
                if len(entities) >= config.limit:
                    break

            current_layer = next_layer
            current_depth += 1

        logger.info(
            f"Traversal search found {len(entities)} entities, {len(edges)} edges "
            f"(depth: {current_depth})"
        )

        return SearchResult(
            entities=entities[:config.limit],
            edges=edges[:config.limit],
            scores=scores,
            metadata={
                "strategy": "traversal",
                "query": config.query,
                "max_depth": config.max_depth,
                "final_depth": current_depth,
            }
        )

    def _bm25_search(self, config: SearchConfig) -> SearchResult:
        """
        BM25 keyword-based search.

        Args:
            config: Search configuration

        Returns:
            SearchResult
        """
        # Search entities using BM25
        entity_results = self.bm25_index.search_entities(
            query=config.query,
            top_k=config.limit,
        )

        # Search edges using BM25
        edge_results = self.bm25_index.search_edges(
            query=config.query,
            top_k=config.limit,
        )

        # Search episodes using BM25
        episode_results = self.bm25_index.search_episodes(
            query=config.query,
            top_k=config.limit,
            tags=config.tags,
            tag_match_mode=config.tag_match_mode,
            kinds=config.kinds,
            user_id=config.user_id,
        )

        # Fetch full entity objects from database
        entities: List[EntityNode] = []
        scores: Dict[str, float] = {}

        for entity_uuid, score in entity_results:
            # Apply BM25 score threshold
            if score < config.min_bm25_score:
                continue

            # Get entity from DB
            entity_data = self.db.get_entity_by_uuid(entity_uuid)
            if entity_data:
                # Apply user_id filter if specified (None or empty string means all users)
                if not config.user_id or entity_data.get("user_id") == config.user_id:
                    entity = EntityNode(
                        uuid=entity_data["uuid"],
                        name=entity_data["name"],
                        entity_type=entity_data["entity_type"],
                        summary=entity_data.get("summary", ""),
                        mentions=entity_data["mentions"],
                        user_id=_sanitize_user_id(entity_data.get("user_id")),
                    )
                    entities.append(entity)
                    scores[entity.uuid] = score

        # Fetch full edge objects from database
        edges: List[EntityEdge] = []

        for edge_uuid, score in edge_results:
            # Apply BM25 score threshold
            if score < config.min_bm25_score:
                continue

            # Get edge from DB
            edge_data = self.db.get_edge_by_uuid(edge_uuid)
            if edge_data:
                edge = EntityEdge(
                    uuid=edge_data["uuid"],
                    source_node_uuid=edge_data["source_uuid"],
                    target_node_uuid=edge_data["target_uuid"],
                    name=edge_data["relation_type"],
                    fact=edge_data["fact"],
                    valid_at=edge_data.get("valid_at"),
                    invalid_at=edge_data.get("invalid_at"),
                    expired_at=edge_data.get("expired_at"),
                )
                edges.append(edge)
                scores[edge.uuid] = score

        # Fetch full episode objects from database
        episodes: List[EpisodeNode] = []

        for episode_uuid, score in episode_results:
            # Apply BM25 score threshold (skip for tag-only search)
            if config.query and score < config.min_bm25_score:
                continue

            # Get episode from DB
            episode_data = self.db.get_episode_by_uuid(episode_uuid)
            if episode_data:
                # Apply user_id filter if specified (None or empty string means all users)
                if not config.user_id or episode_data.get("user_id") == config.user_id:
                    try:
                        # Handle nan values for optional string fields
                        def safe_str_or_none(value):
                            if value is None or (isinstance(value, float) and math.isnan(value)):
                                return None
                            return value

                        # Handle metadata deserialization
                        metadata = episode_data.get("metadata", {})
                        if isinstance(metadata, str):
                            try:
                                metadata = json.loads(metadata)
                            except (json.JSONDecodeError, TypeError):
                                metadata = {}

                        # Extract chunking data from metadata if present
                        chunks = None
                        chunk_offsets = None
                        chunking_data = metadata.get("_chunking", {})
                        if chunking_data:
                            chunks = chunking_data.get("chunks")
                            chunk_offsets = chunking_data.get("chunk_offsets")
                            # Convert chunk_offsets to tuples if stored as lists
                            if chunk_offsets:
                                chunk_offsets = [tuple(offset) if isinstance(offset, list) else offset for offset in chunk_offsets]

                        from ryumem_server.core.models import EpisodeKind
                        episode = EpisodeNode(
                            uuid=episode_data["uuid"],
                            name=episode_data.get("name", ""),
                            content=episode_data["content"],
                            source=EpisodeType.from_str(episode_data.get("source", "text")),
                            source_description=episode_data.get("source_description", ""),
                            kind=EpisodeKind.from_str(episode_data.get("kind", "query")),
                            user_id=safe_str_or_none(episode_data.get("user_id")),
                            agent_id=safe_str_or_none(episode_data.get("agent_id")),
                            metadata=metadata,
                            # Include chunk data
                            chunks=chunks,
                            chunk_offsets=chunk_offsets,
                        )
                        episodes.append(episode)
                        scores[episode.uuid] = score
                    except Exception as e:
                        logger.warning(f"Failed to convert episode {episode_uuid} to EpisodeNode: {e}, skipping")
                        continue

        # BM25 index already returns results in the correct order (score + recency)
        # No need to re-sort here as it can disrupt the intended ranking
        logger.info(f"BM25 search found {len(entities)} entities, {len(edges)} edges, {len(episodes)} episodes (threshold: {config.min_bm25_score})")

        return SearchResult(
            entities=entities[:config.limit],
            edges=edges[:config.limit],
            episodes=episodes[:config.limit],
            scores=scores,
            metadata={
                "strategy": "bm25",
                "query": config.query,
            }
        )

    def _hybrid_search(self, config: SearchConfig) -> SearchResult:
        """
        Hybrid search combining semantic, BM25, and traversal approaches.
        Uses Reciprocal Rank Fusion (RRF) to merge results.

        Args:
            config: Search configuration

        Returns:
            SearchResult
        """
        # Run all three search strategies
        semantic_result = self._semantic_search(config)
        bm25_result = self._bm25_search(config)
        traversal_result = self._traversal_search(config)

        # Merge results using RRF (3-way fusion)
        merged_entities, merged_edges, merged_episodes, merged_scores = self._reciprocal_rank_fusion(
            results=[semantic_result, bm25_result, traversal_result],
            k=config.rrf_k,  # Use configurable RRF constant
        )

        # Filter by minimum RRF score threshold
        filtered_entities = [
            e for e in merged_entities
            if merged_scores.get(e.uuid, 0.0) >= config.min_rrf_score
        ]
        filtered_edges = [
            e for e in merged_edges
            if merged_scores.get(e.uuid, 0.0) >= config.min_rrf_score
        ]
        filtered_episodes = [
            e for e in merged_episodes
            if merged_scores.get(e.uuid, 0.0) >= config.min_rrf_score
        ]

        # Sort by score and limit
        sorted_entities = sorted(
            filtered_entities,
            key=lambda e: merged_scores.get(e.uuid, 0.0),
            reverse=True
        )[:config.limit]

        sorted_edges = sorted(
            filtered_edges,
            key=lambda e: merged_scores.get(e.uuid, 0.0),
            reverse=True
        )[:config.limit]

        sorted_episodes = sorted(
            filtered_episodes,
            key=lambda e: merged_scores.get(e.uuid, 0.0),
            reverse=True
        )[:config.limit]

        logger.info(
            f"Hybrid search found {len(sorted_entities)} entities, {len(sorted_edges)} edges, "
            f"{len(sorted_episodes)} episodes (RRF threshold: {config.min_rrf_score}, k={config.rrf_k})"
        )

        return SearchResult(
            entities=sorted_entities,
            edges=sorted_edges,
            episodes=sorted_episodes,  # Add episodes to the result!
            scores=merged_scores,
            metadata={
                "strategy": "hybrid",
                "query": config.query,
                "semantic_entities": len(semantic_result.entities),
                "bm25_entities": len(bm25_result.entities),
                "traversal_entities": len(traversal_result.entities),
                "episodes_found": semantic_result.metadata.get("episodes_found", 0),
                "entities_from_episodes": semantic_result.metadata.get("entities_from_episodes", 0),
            }
        )

    def _reciprocal_rank_fusion(
        self,
        results: List[SearchResult],
        k: int = 60,
    ) -> Tuple[List[EntityNode], List[EntityEdge], List[EpisodeNode], Dict[str, float]]:
        """
        Merge multiple search results using Reciprocal Rank Fusion.

        RRF formula: score(item) = sum(1 / (k + rank(item)))

        Args:
            results: List of SearchResult objects to merge
            k: RRF constant (typically 60)

        Returns:
            Tuple of (merged_entities, merged_edges, merged_episodes, merged_scores)
        """
        # Track entities, edges, and episodes by UUID
        entity_map: Dict[str, EntityNode] = {}
        edge_map: Dict[str, EntityEdge] = {}
        episode_map: Dict[str, EpisodeNode] = {}
        rrf_scores: Dict[str, float] = defaultdict(float)

        for result in results:
            # Process entities
            for rank, entity in enumerate(result.entities, start=1):
                entity_map[entity.uuid] = entity
                rrf_scores[entity.uuid] += 1.0 / (k + rank)

            # Process edges
            for rank, edge in enumerate(result.edges, start=1):
                edge_map[edge.uuid] = edge
                rrf_scores[edge.uuid] += 1.0 / (k + rank)

            # Process episodes
            for rank, episode in enumerate(result.episodes, start=1):
                episode_map[episode.uuid] = episode
                rrf_scores[episode.uuid] += 1.0 / (k + rank)

        merged_entities = list(entity_map.values())
        merged_edges = list(edge_map.values())
        merged_episodes = list(episode_map.values())

        return merged_entities, merged_edges, merged_episodes, dict(rrf_scores)

    def get_entity_context(
        self,
        entity_uuid: str,
        max_depth: int = 2,
        include_expired: bool = False,
    ) -> Dict:
        """
        Get comprehensive context for an entity including its relationships.

        Args:
            entity_uuid: UUID of the entity
            max_depth: Maximum traversal depth
            include_expired: Whether to include expired edges

        Returns:
            Dictionary with entity details and relationship graph
        """
        # Get entity details
        entity_data = self.db.get_entity_by_uuid(entity_uuid)
        if not entity_data:
            return {}

        # Get relationships
        relationships = self.db.get_entity_relationships(
            entity_uuid=entity_uuid,
            include_expired=include_expired,
        )

        # Build context
        context = {
            "entity": entity_data,
            "relationships": relationships,
            "relationship_count": len(relationships),
        }

        return context

    def _apply_temporal_decay(
        self,
        results: SearchResult,
        decay_factor: float = 0.95,
        reference_time: Optional[datetime] = None,
    ) -> SearchResult:
        """
        Apply temporal decay to search scores.

        More recent facts score higher than older facts using exponential decay.

        Formula: final_score = base_score * (decay_factor ^ days_old)

        Args:
            results: Original search results
            decay_factor: Decay rate per day (0-1, default 0.95 = 5% decay per day)
            reference_time: Reference time (default: now)

        Returns:
            SearchResult with updated scores
        """
        from datetime import datetime, timezone

        if reference_time is None:
            reference_time = datetime.now(timezone.utc)

        # Make timezone-aware if not already
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)

        new_scores = {}

        # Apply to entities
        for entity in results.entities:
            base_score = results.scores.get(entity.uuid, 0.0)

            # Make created_at timezone-aware if needed
            entity_time = entity.created_at
            if entity_time.tzinfo is None:
                entity_time = entity_time.replace(tzinfo=timezone.utc)

            # Calculate days since creation
            days_old = (reference_time - entity_time).days
            days_old = max(0, days_old)  # Ensure non-negative

            # Apply exponential decay
            decay_multiplier = decay_factor ** days_old

            new_scores[entity.uuid] = base_score * decay_multiplier

        # Apply to edges
        for edge in results.edges:
            base_score = results.scores.get(edge.uuid, 0.0)

            # Use valid_at if available, else created_at
            edge_time = edge.valid_at or edge.created_at
            if edge_time.tzinfo is None:
                edge_time = edge_time.replace(tzinfo=timezone.utc)

            # Calculate days since fact became valid
            days_old = (reference_time - edge_time).days
            days_old = max(0, days_old)

            # Apply exponential decay
            decay_multiplier = decay_factor ** days_old

            new_scores[edge.uuid] = base_score * decay_multiplier

        # Re-sort by new scores
        results.entities.sort(key=lambda e: new_scores.get(e.uuid, 0.0), reverse=True)
        results.edges.sort(key=lambda e: new_scores.get(e.uuid, 0.0), reverse=True)
        results.scores = new_scores

        return results

    def _apply_update_boost(
        self,
        results: SearchResult,
        boost_factor: float = 1.2,
        recent_threshold_days: int = 7,
        reference_time: Optional[datetime] = None,
    ) -> SearchResult:
        """
        Boost entities/edges that have been recently created or updated.

        This makes the system "update-aware" - recently modified facts
        are more likely to be relevant.

        Args:
            results: Search results
            boost_factor: Boost multiplier for recent facts (default: 1.2 = 20% boost)
            recent_threshold_days: Days to consider "recent" (default: 7)
            reference_time: Reference time (default: now)

        Returns:
            SearchResult with updated scores
        """
        from datetime import datetime, timedelta, timezone

        if reference_time is None:
            reference_time = datetime.now(timezone.utc)

        # Make timezone-aware if not already
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)

        cutoff = reference_time - timedelta(days=recent_threshold_days)

        # Boost recently created entities
        for entity in results.entities:
            entity_time = entity.created_at
            if entity_time.tzinfo is None:
                entity_time = entity_time.replace(tzinfo=timezone.utc)

            if entity_time >= cutoff:
                results.scores[entity.uuid] *= boost_factor

        # Boost recently created or modified edges
        for edge in results.edges:
            # Check creation time
            edge_time = edge.created_at
            if edge_time.tzinfo is None:
                edge_time = edge_time.replace(tzinfo=timezone.utc)

            if edge_time >= cutoff:
                results.scores[edge.uuid] *= boost_factor
            # Also check if recently invalidated (may still be contextually relevant)
            elif edge.invalid_at:
                invalid_time = edge.invalid_at
                if invalid_time.tzinfo is None:
                    invalid_time = invalid_time.replace(tzinfo=timezone.utc)
                if invalid_time >= cutoff:
                    # Smaller boost for recently invalidated facts
                    results.scores[edge.uuid] *= (boost_factor * 0.8)

        # Re-sort by new scores
        results.entities.sort(key=lambda e: results.scores.get(e.uuid, 0.0), reverse=True)
        results.edges.sort(key=lambda e: results.scores.get(e.uuid, 0.0), reverse=True)

        return results
