"""
Ryugraph database layer.
Ryugraph is a renamed version of kuzu, so the API should be identical.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import ryugraph

from ryumem_server.core.models import (
    EntityEdge,
    EntityNode,
    EpisodeNode,
    EpisodicEdge,
)

logger = logging.getLogger(__name__)


class RyugraphDB:
    """
    Ryugraph database interface for Ryumem.
    Handles all graph database operations including schema creation,
    node/edge CRUD operations, and embedding-based similarity search.
    """

    def __init__(self, db_path: str, embedding_dimensions: int = 3072):
        """
        Initialize Ryugraph database connection.

        Args:
            db_path: Path to the ryugraph database directory
            embedding_dimensions: Dimension of embedding vectors (default: 3072 for text-embedding-3-large)
        """
        self.db_path = db_path
        self.embedding_dimensions = embedding_dimensions

        # Create database and connection with WAL corruption recovery
        try:
            self.db = ryugraph.Database(db_path, read_only=False)
            self.conn = ryugraph.Connection(self.db)
        except RuntimeError as e:
            if "Corrupted wal file" in str(e) or "invalid WAL record type" in str(e):
                logger.warning(f"Detected corrupted WAL file: {e}")
                logger.warning("Attempting to delete WAL file and retry...")

                # Delete WAL file for this specific database
                # WAL file is named {db_path}.wal (e.g., admin.db.wal for admin.db)
                import os

                wal_file = f"{db_path}.wal"

                if os.path.exists(wal_file):
                    try:
                        os.remove(wal_file)
                        logger.info(f"Deleted corrupted WAL file: {wal_file}")
                    except Exception as del_err:
                        logger.error(f"Failed to delete {wal_file}: {del_err}")
                        raise
                else:
                    logger.warning(f"WAL file not found at expected location: {wal_file}")

                # Retry opening database
                self.db = ryugraph.Database(db_path, read_only=False)
                self.conn = ryugraph.Connection(self.db)
                logger.info("Successfully opened database after WAL recovery")
            else:
                raise

        # Initialize schema
        self.create_schema()

        logger.info(f"Initialized RyugraphDB at {db_path} with {embedding_dimensions}D embeddings")

    def create_schema(self) -> None:
        """
        Create the graph schema for Ryumem.
        Includes Episode, Entity nodes with their relationships.
        """
        # Episode nodes
        self.execute(
            f"""
            CREATE NODE TABLE IF NOT EXISTS Episode(
                uuid STRING PRIMARY KEY,
                name STRING,
                content STRING,
                content_embedding FLOAT[{self.embedding_dimensions}],
                source STRING,
                source_description STRING,
                kind STRING DEFAULT 'query',
                created_at TIMESTAMP,
                valid_at TIMESTAMP,
                user_id STRING,
                agent_id STRING,
                metadata STRING,
                entity_edges STRING[]
            );
            """
        )

        # Agent Instruction nodes (separate from Episodes)
        self.execute(
            """
            CREATE NODE TABLE IF NOT EXISTS AgentInstruction(
                uuid STRING PRIMARY KEY,
                agent_type STRING,
                base_instruction STRING,
                enhanced_instruction STRING,
                query_augmentation_template STRING,
                memory_enabled BOOLEAN,
                tool_tracking_enabled BOOLEAN,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            );
            """
        )

        # Tool nodes (separate from Entities)
        self.execute(
            f"""
            CREATE NODE TABLE IF NOT EXISTS Tool(
                uuid STRING PRIMARY KEY,
                tool_name STRING,
                description STRING,
                name_embedding FLOAT[{self.embedding_dimensions}],
                mentions INT64,
                created_at TIMESTAMP
            );
            """
        )

        # SystemConfig nodes for storing application configuration
        self.execute(
            """
            CREATE NODE TABLE IF NOT EXISTS SystemConfig(
                key STRING PRIMARY KEY,
                value STRING,
                category STRING,
                data_type STRING,
                is_sensitive BOOLEAN,
                updated_at TIMESTAMP,
                description STRING
            );
            """
        )

        # Entity nodes
        self.execute(
            f"""
            CREATE NODE TABLE IF NOT EXISTS Entity(
                uuid STRING PRIMARY KEY,
                name STRING,
                entity_type STRING,
                summary STRING,
                name_embedding FLOAT[{self.embedding_dimensions}],
                mentions INT64,
                created_at TIMESTAMP,
                user_id STRING,
                labels STRING[],
                attributes STRING
            );
            """
        )


        # RELATES_TO edges (Entity -> Entity)
        self.execute(
            f"""
            CREATE REL TABLE IF NOT EXISTS RELATES_TO(
                FROM Entity TO Entity,
                uuid STRING,
                name STRING,
                fact STRING,
                fact_embedding FLOAT[{self.embedding_dimensions}],
                created_at TIMESTAMP,
                valid_at TIMESTAMP,
                invalid_at TIMESTAMP,
                expired_at TIMESTAMP,
                episodes STRING[],
                mentions INT64,
                attributes STRING
            );
            """
        )

        # MENTIONS edges (Episode -> Entity)
        self.execute(
            """
            CREATE REL TABLE IF NOT EXISTS MENTIONS(
                FROM Episode TO Entity,
                uuid STRING,
                created_at TIMESTAMP
            );
            """
        )


        # TRIGGERED edges (Episode -> Episode) for query-to-tool-execution linking
        self.execute(
            """
            CREATE REL TABLE IF NOT EXISTS TRIGGERED(
                FROM Episode TO Episode,
                uuid STRING,
                created_at TIMESTAMP
            );
            """
        )

        logger.info("Graph schema created successfully")

    def execute(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a Cypher query and return results as dictionaries.

        Args:
            query: Cypher query string
            parameters: Optional query parameters

        Returns:
            List of result dictionaries
        """
        try:
            results = self.conn.execute(query, parameters or {})
            return [dict(row) for row in results.get_as_df().to_dict('records')]
        except Exception as e:
            logger.error(f"Error executing query: {e}\nQuery: {query}\nParameters: {parameters}")
            raise

    def save_episode(self, episode: EpisodeNode) -> Dict[str, Any]:
        """
        Save an episode node to the database.

        Args:
            episode: EpisodeNode to save

        Returns:
            Result dictionary
        """
        import json

        query = """
        MERGE (e:Episode {uuid: $uuid})
        ON CREATE SET
            e.name = $name,
            e.content = $content,
            e.content_embedding = $content_embedding,
            e.source = $source,
            e.source_description = $source_description,
            e.kind = $kind,
            e.created_at = $created_at,
            e.valid_at = $valid_at,
            e.user_id = $user_id,
            e.agent_id = $agent_id,
            e.metadata = $metadata,
            e.entity_edges = $entity_edges
        ON MATCH SET
            e.entity_edges = $entity_edges,
            e.content_embedding = $content_embedding,
            e.kind = $kind
        RETURN e.uuid AS uuid
        """

        params = {
            "uuid": episode.uuid,
            "name": episode.name,
            "content": episode.content,
            "content_embedding": getattr(episode, 'content_embedding', None),
            "source": episode.source.value,
            "source_description": episode.source_description,
            "kind": episode.kind.value if hasattr(episode.kind, 'value') else str(episode.kind),
            "created_at": episode.created_at,
            "valid_at": episode.valid_at,
            "user_id": episode.user_id,
            "agent_id": episode.agent_id,
            "metadata": json.dumps(episode.metadata),
            "entity_edges": episode.entity_edges,
        }

        return self.execute(query, params)

    def save_entity(self, entity: EntityNode) -> Dict[str, Any]:
        """
        Save an entity node to the database using MERGE logic.
        Updates mentions and embedding if the entity already exists.

        Args:
            entity: EntityNode to save

        Returns:
            Result dictionary
        """
        import json

        # Build dynamic query based on whether name_embedding is provided
        # Only update embedding if explicitly provided (not None)
        # This preserves existing embeddings when updating entity properties like summary
        if entity.name_embedding is not None:
            embedding_clause = f"e.name_embedding = CAST($name_embedding, 'FLOAT[{self.embedding_dimensions}]')"
        else:
            embedding_clause = None
            # Log warning if creating a new entity without embedding
            # (Note: MERGE will handle both create and update, but we can't distinguish here)
            logger.debug(f"Saving entity '{entity.name}' without name_embedding - will preserve existing or leave NULL")

        # Build CREATE clause
        create_fields = [
            "e.name = $name",
            "e.entity_type = $entity_type",
            "e.summary = $summary",
        ]
        if embedding_clause:
            create_fields.append(embedding_clause)
        create_fields.extend([
            "e.mentions = $mentions",
            "e.created_at = $created_at",
            "e.user_id = $user_id",
            "e.labels = $labels",
            "e.attributes = $attributes"
        ])

        # Build UPDATE clause (on match)
        update_fields = [
            "e.mentions = coalesce(e.mentions, 0) + 1",
            "e.summary = $summary",
        ]
        if embedding_clause:
            update_fields.append(embedding_clause)
        update_fields.append("e.attributes = $attributes")

        # Build query with proper string formatting (can't use \n in f-string expressions)
        create_clause = ',\n            '.join(create_fields)
        update_clause = ',\n            '.join(update_fields)

        query = f"""
        MERGE (e:Entity {{uuid: $uuid}})
        ON CREATE SET
            {create_clause}
        ON MATCH SET
            {update_clause}
        RETURN e.uuid AS uuid
        """

        params = {
            "uuid": entity.uuid,
            "name": entity.name,
            "entity_type": entity.entity_type,
            "summary": entity.summary,
            "name_embedding": entity.name_embedding,
            "mentions": entity.mentions,
            "created_at": entity.created_at,
            "user_id": entity.user_id,
            "labels": entity.labels,
            "attributes": json.dumps(entity.attributes),
        }

        return self.execute(query, params)

    def save_entity_edge(self, edge: EntityEdge, source_uuid: str, target_uuid: str) -> Dict[str, Any]:
        """
        Save an entity edge (relationship) to the database.

        Args:
            edge: EntityEdge to save
            source_uuid: UUID of source entity
            target_uuid: UUID of target entity

        Returns:
            Result dictionary
        """
        import json

        query = f"""
        MATCH (source:Entity {{uuid: $source_uuid}})
        MATCH (target:Entity {{uuid: $target_uuid}})
        MERGE (source)-[r:RELATES_TO {{uuid: $uuid}}]->(target)
        ON CREATE SET
            r.name = $name,
            r.fact = $fact,
            r.fact_embedding = CAST($fact_embedding, 'FLOAT[{self.embedding_dimensions}]'),
            r.created_at = $created_at,
            r.valid_at = $valid_at,
            r.invalid_at = $invalid_at,
            r.expired_at = $expired_at,
            r.episodes = $episodes,
            r.mentions = $mentions,
            r.attributes = $attributes
        ON MATCH SET
            r.mentions = coalesce(r.mentions, 0) + 1,
            r.fact = $fact,
            r.fact_embedding = CAST($fact_embedding, 'FLOAT[{self.embedding_dimensions}]'),
            r.episodes = $episodes,
            r.attributes = $attributes
        RETURN r.uuid AS uuid
        """

        params = {
            "source_uuid": source_uuid,
            "target_uuid": target_uuid,
            "uuid": edge.uuid,
            "name": edge.name,
            "fact": edge.fact,
            "fact_embedding": edge.fact_embedding,
            "created_at": edge.created_at,
            "valid_at": edge.valid_at,
            "invalid_at": edge.invalid_at,
            "expired_at": edge.expired_at,
            "episodes": edge.episodes,
            "mentions": edge.mentions,
            "attributes": json.dumps(edge.attributes),
        }

        return self.execute(query, params)

    def save_episodic_edge(self, edge: EpisodicEdge) -> Dict[str, Any]:
        """
        Save an episodic edge (MENTIONS relationship).

        Args:
            edge: EpisodicEdge to save

        Returns:
            Result dictionary
        """
        query = """
        MATCH (episode:Episode {uuid: $episode_uuid})
        MATCH (entity:Entity {uuid: $entity_uuid})
        MERGE (episode)-[r:MENTIONS {uuid: $uuid}]->(entity)
        ON CREATE SET
            r.created_at = $created_at
        RETURN r.uuid AS uuid
        """

        params = {
            "episode_uuid": edge.source_node_uuid,
            "entity_uuid": edge.target_node_uuid,
            "uuid": edge.uuid,
            "created_at": edge.created_at,
        }

        return self.execute(query, params)

    def _find_exact_episode_match(
        self,
        content: str,
        user_id: str,
        time_cutoff: Any,
    ) -> Optional[Dict[str, Any]]:
        """Helper to check for exact content match."""
        exact_results = self.execute(
            """
            MATCH (e:Episode)
            WHERE e.content = $content AND e.user_id = $user_id AND e.created_at > $time_cutoff
            RETURN e.uuid AS uuid, e.content AS content, e.created_at AS created_at, e.user_id AS user_id
            ORDER BY e.created_at DESC LIMIT 1
            """,
            {"content": content, "user_id": user_id, "time_cutoff": time_cutoff}
        )
        return exact_results[0] if exact_results else None

    def _filter_episodes_by_time_cutoff(
        self,
        episode_uuids: List[str],
        time_cutoff: Any,
    ) -> Optional[Dict[str, Any]]:
        """Helper to filter episode UUIDs by time cutoff, returns most recent."""
        if not episode_uuids:
            return None

        results = self.execute(
            """
            MATCH (e:Episode)
            WHERE e.uuid IN $uuids AND e.created_at > $time_cutoff
            RETURN e.uuid AS uuid, e.content AS content, e.created_at AS created_at, e.user_id AS user_id
            ORDER BY e.created_at DESC LIMIT 1
            """,
            {"uuids": episode_uuids, "time_cutoff": time_cutoff}
        )
        return results[0] if results else None

    def find_similar_episode(
        self,
        content: str,
        content_embedding: List[float],
        user_id: str,
        time_window_hours: int = 24,
        similarity_threshold: float = 0.95,
    ) -> Optional[Dict[str, Any]]:
        """
        Find an episode with identical or very similar content using semantic similarity.

        Uses embedding-based cosine similarity within a time window to detect duplicates.
        This catches semantic duplicates that differ in minor wording, punctuation, or phrasing.

        Args:
            content: Episode content to check
            content_embedding: Embedding vector for the content
            user_id: User ID (required)
            time_window_hours: Look back this many hours for duplicates
            similarity_threshold: Minimum cosine similarity to consider a duplicate (default: 0.95)

        Returns:
            Existing episode dict if found, None otherwise
        """
        from datetime import datetime, timedelta, timezone

        time_cutoff = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)

        # Check exact match first
        exact_match = self._find_exact_episode_match(content, user_id, time_cutoff)
        if exact_match:
            return exact_match

        # Use existing search_similar_episodes method with time filter
        similar_episodes = self.search_similar_episodes(
            embedding=content_embedding,
            user_id=user_id,
            threshold=similarity_threshold,
            limit=1,
            time_cutoff=time_cutoff,
        )

        return similar_episodes[0] if similar_episodes else None

    def find_similar_episode_bm25(
        self,
        content: str,
        user_id: str,
        bm25_index: Optional[Any],
        time_window_hours: int = 24,
        similarity_threshold: float = 0.7,
    ) -> Optional[Dict[str, Any]]:
        """Find similar episode using BM25 keyword search (for when embeddings are disabled)."""
        from datetime import datetime, timedelta, timezone

        time_cutoff = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)

        # Check exact match first (reuse helper)
        exact_match = self._find_exact_episode_match(content, user_id, time_cutoff)
        if exact_match:
            return exact_match

        # BM25 fuzzy search
        if not bm25_index:
            return None

        results = bm25_index.search_episodes(
            query=content, top_k=10, min_score=similarity_threshold
        )

        if not results:
            return None

        # Get candidate UUIDs from BM25 results
        candidate_uuids = [uuid for uuid, score in results]

        # TODO: BM25 search doesn't filter by user_id - need to add user_id filtering to BM25Index
        # Use helper to filter by time_cutoff (handles datetime comparison in DB)
        return self._filter_episodes_by_time_cutoff(candidate_uuids, time_cutoff)

    def get_episode_by_session_id(self, session_id: str) -> Optional[EpisodeNode]:
        """
        Find an episode that contains the given session_id in its metadata.sessions.

        Args:
            session_id: Session ID to search for

        Returns:
            EpisodeNode if found, None otherwise
        """
        import json

        query = """
        MATCH (e:Episode)
        WHERE e.metadata IS NOT NULL
        RETURN
            e.uuid AS uuid,
            e.name AS name,
            e.content AS content,
            e.content_embedding AS content_embedding,
            e.source AS source,
            e.source_description AS source_description,
            e.created_at AS created_at,
            e.valid_at AS valid_at,
            e.user_id AS user_id,
            e.agent_id AS agent_id,
            e.metadata AS metadata,
            e.entity_edges AS entity_edges
        """

        results = self.execute(query)

        # Filter in Python since Kùzu may not support JSON path queries
        for row in results:
            try:
                metadata = json.loads(row['metadata']) if row['metadata'] else {}
                sessions = metadata.get('sessions', {})
                if session_id in sessions:
                    # Convert to EpisodeNode
                    from ryumem_server.core.models import EpisodeNode, EpisodeType
                    import math

                    # Helper to clean nan/None values
                    def clean_value(val):
                        if val is None:
                            return None
                        if isinstance(val, float) and math.isnan(val):
                            return None
                        return val

                    return EpisodeNode(
                        uuid=row['uuid'],
                        name=row['name'],
                        content=row['content'],
                        content_embedding=clean_value(row.get('content_embedding')),
                        source=EpisodeType(row['source']),
                        source_description=row['source_description'],
                        created_at=row['created_at'],
                        valid_at=row['valid_at'],
                        user_id=clean_value(row['user_id']),
                        agent_id=clean_value(row['agent_id']),
                        metadata=metadata,
                        entity_edges=row['entity_edges'] or [],
                    )
            except (json.JSONDecodeError, KeyError):
                continue

        return None

    def get_triggered_episodes(
        self,
        source_uuid: str,
        source_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[EpisodeNode]:
        """
        Get episodes linked from a source episode via TRIGGERED relationships.

        Args:
            source_uuid: UUID of the source episode
            source_type: Optional filter by episode source type (e.g., 'json', 'message')
            limit: Maximum number of episodes to return

        Returns:
            List of triggered episode nodes
        """
        query = """
        MATCH (source:Episode {uuid: $source_uuid})-[r:TRIGGERED]->(target:Episode)
        WHERE target.metadata IS NOT NULL
        """

        if source_type:
            query += " AND target.source = $source_type"

        query += """
        RETURN target.uuid AS uuid,
               target.name AS name,
               target.content AS content,
               target.content_embedding AS content_embedding,
               target.source AS source,
               target.source_description AS source_description,
               target.created_at AS created_at,
               target.valid_at AS valid_at,
               target.user_id AS user_id,
               target.agent_id AS agent_id,
               target.metadata AS metadata,
               target.entity_edges AS entity_edges
        ORDER BY target.created_at DESC
        LIMIT $limit
        """

        params = {"source_uuid": source_uuid, "limit": limit}
        if source_type:
            params["source_type"] = source_type

        results = self.execute(query, params)
        episodes = []

        for row in results:
            try:
                from ryumem_server.core.models import EpisodeType
                import math

                # Helper to clean nan/None values
                def clean_value(val):
                    if val is None:
                        return None
                    if isinstance(val, float) and math.isnan(val):
                        return None
                    return val

                metadata = None
                if row.get('metadata'):
                    metadata_str = row['metadata']
                    metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str

                episode = EpisodeNode(
                    uuid=row['uuid'],
                    name=row['name'],
                    content=row['content'],
                    content_embedding=clean_value(row.get('content_embedding')),
                    source=EpisodeType(row['source']),
                    source_description=row.get('source_description', ''),
                    created_at=row['created_at'],
                    valid_at=row.get('valid_at'),
                    user_id=clean_value(row.get('user_id')),
                    agent_id=clean_value(row.get('agent_id')),
                    metadata=metadata or {},
                    entity_edges=row.get('entity_edges', []),
                )
                episodes.append(episode)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse episode: {e}")
                continue

        return episodes

    def search_similar_entities(
        self,
        embedding: List[float],
        user_id: str,
        threshold: float = 0.7,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search for entities similar to the given embedding.

        Args:
            embedding: Query embedding vector
            user_id: User ID (required)
            threshold: Minimum similarity threshold (0.0-1.0)
            limit: Maximum number of results

        Returns:
            List of similar entities with similarity scores
        """
        query = f"""
        MATCH (e:Entity)
        WHERE e.name_embedding IS NOT NULL
          AND e.user_id = $user_id
        WITH e, array_cosine_similarity(e.name_embedding, CAST($embedding, 'FLOAT[{self.embedding_dimensions}]')) AS similarity
        WHERE similarity >= $threshold
        RETURN
            e.uuid AS uuid,
            e.name AS name,
            e.entity_type AS entity_type,
            e.summary AS summary,
            e.mentions AS mentions,
            similarity
        ORDER BY similarity DESC
        LIMIT $limit
        """

        params = {
            "embedding": embedding,
            "user_id": user_id,
            "threshold": threshold,
            "limit": limit,
        }

        return self.execute(query, params)

    def search_similar_episodes(
        self,
        embedding: List[float],
        user_id: str,
        threshold: float = 0.7,
        limit: int = 10,
        kinds: Optional[List[str]] = None,
        time_cutoff: Optional[Any] = None,
        tags: Optional[List[str]] = None,
        tag_match_mode: str = 'any',
    ) -> List[Dict[str, Any]]:
        """
        Search for episodes similar to the given embedding.

        Args:
            embedding: Query embedding vector
            user_id: User ID (required)
            threshold: Minimum similarity threshold (0.0-1.0)
            limit: Maximum number of results
            kinds: Filter by episode kinds (e.g., ['query'], ['memory'], or None for all)
            time_cutoff: Optional datetime cutoff - only return episodes created after this time
            tags: Optional list of tags to filter by
            tag_match_mode: Tag matching mode - 'any' (at least one tag) or 'all' (all tags)

        Returns:
            List of similar episodes with similarity scores
        """
        # Build kind filter
        kind_filter = ""
        if kinds:
            kind_list = "', '".join(kinds)
            kind_filter = f"AND ep.kind IN ['{kind_list}']"

        # Build time filter
        time_filter = ""
        if time_cutoff is not None:
            time_filter = "AND ep.created_at > $time_cutoff"

        query = f"""
        MATCH (ep:Episode)
        WHERE ep.content_embedding IS NOT NULL
          AND ep.user_id = $user_id
          {kind_filter}
          {time_filter}
        WITH ep, array_cosine_similarity(ep.content_embedding, CAST($embedding, 'FLOAT[{self.embedding_dimensions}]')) AS similarity
        WHERE similarity >= $threshold
        RETURN
            ep.uuid AS uuid,
            ep.name AS name,
            ep.content AS content,
            ep.source AS source,
            ep.source_description AS source_description,
            ep.kind AS kind,
            ep.created_at AS created_at,
            ep.valid_at AS valid_at,
            ep.user_id AS user_id,
            ep.agent_id AS agent_id,
            ep.metadata AS metadata,
            similarity
        ORDER BY similarity DESC, ep.created_at DESC
        LIMIT $limit
        """

        params = {
            "embedding": embedding,
            "user_id": user_id,
            "threshold": threshold,
            "limit": limit,
        }

        if time_cutoff is not None:
            params["time_cutoff"] = time_cutoff

        # Execute query
        raw_results = self.execute(query, params)

        # Application-level tag filtering
        if tags:
            import json
            query_tags = {tag.lower() for tag in tags}
            filtered_results = []

            for result in raw_results:
                metadata = result.get("metadata")
                if metadata:
                    try:
                        # Handle both dict and JSON string metadata
                        metadata_dict = metadata if isinstance(metadata, dict) else json.loads(metadata)
                        episode_tags = {str(tag).lower() for tag in metadata_dict.get("tags", []) if tag}

                        # Apply tag matching
                        if tag_match_mode == 'all':
                            # All query tags must be present
                            if query_tags.issubset(episode_tags):
                                filtered_results.append(result)
                        else:  # 'any' mode
                            # At least one query tag must match
                            if query_tags & episode_tags:
                                filtered_results.append(result)
                    except (json.JSONDecodeError, TypeError, AttributeError):
                        # Skip episodes with malformed metadata
                        continue

            return filtered_results

        return raw_results

    def search_similar_edges(
        self,
        embedding: List[float],
        user_id: str,
        threshold: float = 0.8,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search for entity edges similar to the given embedding.

        Args:
            embedding: Query embedding vector
            user_id: User ID (required)
            threshold: Minimum similarity threshold (0.0-1.0)
            limit: Maximum number of results

        Returns:
            List of similar edges with similarity scores
        """
        query = f"""
        MATCH (source:Entity)-[r:RELATES_TO]->(target:Entity)
        WHERE r.fact_embedding IS NOT NULL
          AND (r.expired_at IS NULL OR r.expired_at > current_timestamp())
          AND source.user_id = $user_id
          AND target.user_id = $user_id
        WITH source, r, target,
             array_cosine_similarity(r.fact_embedding, CAST($embedding, 'FLOAT[{self.embedding_dimensions}]')) AS similarity
        WHERE similarity >= $threshold
        RETURN
            source.uuid AS source_uuid,
            source.name AS source_name,
            r.uuid AS edge_uuid,
            r.name AS relation_type,
            r.fact AS fact,
            target.uuid AS target_uuid,
            target.name AS target_name,
            similarity
        ORDER BY similarity DESC
        LIMIT $limit
        """

        params = {
            "embedding": embedding,
            "user_id": user_id,
            "threshold": threshold,
            "limit": limit,
        }

        return self.execute(query, params)

    def get_entity_by_uuid(self, uuid: str) -> Optional[Dict[str, Any]]:
        """Get an entity by its UUID"""
        query = """
        MATCH (e:Entity {uuid: $uuid})
        RETURN
            e.uuid AS uuid,
            e.name AS name,
            e.entity_type AS entity_type,
            e.summary AS summary,
            e.mentions AS mentions,
            e.created_at AS created_at,
            e.user_id AS user_id
        """
        results = self.execute(query, {"uuid": uuid})
        return results[0] if results else None

    def get_edge_by_uuid(self, uuid: str) -> Optional[Dict[str, Any]]:
        """Get a relationship edge by its UUID"""
        query = """
        MATCH (s:Entity)-[r:RELATES_TO]->(t:Entity)
        WHERE r.uuid = $uuid
        RETURN
            r.uuid AS uuid,
            s.uuid AS source_uuid,
            t.uuid AS target_uuid,
            r.fact AS fact,
            r.name AS relation_type,
            r.valid_at AS valid_at,
            r.invalid_at AS invalid_at,
            r.expired_at AS expired_at,
            r.created_at AS created_at,
            r.mentions AS mentions,
            r.episodes AS episodes
        """
        results = self.execute(query, {"uuid": uuid})
        return results[0] if results else None

    def get_entity_relationships(
        self,
        entity_uuid: str,
        include_expired: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all relationships for an entity.

        Args:
            entity_uuid: UUID of the entity
            include_expired: Whether to include expired edges

        Returns:
            List of relationships
        """
        expired_filter = "" if include_expired else "AND (r.expired_at IS NULL OR r.expired_at > current_timestamp())"

        query = f"""
        MATCH (e:Entity {{uuid: $uuid}})-[r:RELATES_TO]-(other:Entity)
        WHERE 1=1 {expired_filter}
        RETURN
            e.uuid AS entity_uuid,
            e.name AS entity_name,
            r.uuid AS edge_uuid,
            r.name AS relation_type,
            r.fact AS fact,
            r.valid_at AS valid_at,
            r.invalid_at AS invalid_at,
            r.expired_at AS expired_at,
            other.uuid AS other_uuid,
            other.name AS other_name
        """

        return self.execute(query, {"uuid": entity_uuid})

    def invalidate_edge(self, edge_uuid: str) -> Dict[str, Any]:
        """
        Mark an edge as expired (invalidated).

        Args:
            edge_uuid: UUID of the edge to invalidate

        Returns:
            Result dictionary
        """
        query = """
        MATCH ()-[r:RELATES_TO {uuid: $uuid}]->()
        SET r.expired_at = current_timestamp()
        RETURN r.uuid AS uuid, r.expired_at AS expired_at
        """

        return self.execute(query, {"uuid": edge_uuid})

    def delete_by_user_id(self, user_id: str) -> None:
        """
        Delete all data for a specific user_id.

        Args:
            user_id: User ID to delete
        """
        # Delete episodes for user
        self.execute(
            """
            MATCH (n:Episode {user_id: $user_id})
            DETACH DELETE n
            """,
            {"user_id": user_id}
        )

        # Delete entities for user
        self.execute(
            """
            MATCH (n:Entity {user_id: $user_id})
            DETACH DELETE n
            """,
            {"user_id": user_id}
        )

        logger.info(f"Deleted all data for user_id: {user_id}")

    def get_episode_context(
        self,
        user_id: str,
        limit: int = 5,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get recent episodes for context in extraction.

        Args:
            user_id: User ID to filter by (required)
            limit: Maximum number of episodes to return
            session_id: Optional session ID filter (searches in metadata.sessions)

        Returns:
            List of recent episodes
        """
        if session_id:
            # Use new method to find episode by session_id in metadata
            episode = self.get_episode_by_session_id(session_id)
            if episode and episode.user_id == user_id:
                return [{
                    "uuid": episode.uuid,
                    "name": episode.name,
                    "content": episode.content,
                    "created_at": episode.created_at,
                }]
            return []

        # No session filter - get recent episodes by user_id
        query = """
        MATCH (e:Episode)
        WHERE e.user_id = $user_id
        RETURN
            e.uuid AS uuid,
            e.name AS name,
            e.content AS content,
            e.created_at AS created_at
        ORDER BY e.created_at DESC
        LIMIT $limit
        """

        params = {"user_id": user_id, "limit": limit}
        return self.execute(query, params)

    def get_episode_entities(
        self,
        episode_uuid: str,
    ) -> List[Dict[str, Any]]:
        """
        Get all entities mentioned in an episode.

        Args:
            episode_uuid: UUID of the episode

        Returns:
            List of entities with their properties
        """
        query = """
        MATCH (ep:Episode {uuid: $episode_uuid})-[:MENTIONS]->(e:Entity)
        RETURN
            e.uuid AS uuid,
            e.name AS name,
            e.entity_type AS entity_type,
            e.summary AS summary,
            e.mentions AS mentions,
            e.user_id AS user_id
        """

        params = {"episode_uuid": episode_uuid}
        return self.execute(query, params)

    def get_episodes(
        self,
        user_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search: Optional[str] = None,
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        """
        Get episodes with pagination and filtering.

        Args:
            user_id: Optional user ID filter
            limit: Maximum number of episodes to return
            offset: Number of episodes to skip
            start_date: Optional start date filter
            end_date: Optional end date filter
            search: Optional content search filter
            sort_order: Sort order - "desc" (newest first) or "asc" (oldest first)

        Returns:
            Dictionary with 'episodes' list and 'total' count
        """
        conditions = []
        params = {
            "limit": limit,
            "offset": offset,
        }

        if user_id:
            conditions.append("e.user_id = $user_id")
            params["user_id"] = user_id

        if start_date:
            conditions.append("e.created_at >= $start_date")
            params["start_date"] = start_date

        if end_date:
            conditions.append("e.created_at <= $end_date")
            params["end_date"] = end_date

        if search:
            conditions.append("e.content CONTAINS $search")
            params["search"] = search

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        order_clause = "DESC" if sort_order.lower() == "desc" else "ASC"

        # Get total count
        count_query = f"""
        MATCH (e:Episode)
        WHERE {where_clause}
        RETURN COUNT(e) AS total
        """
        count_result = self.execute(count_query, params)
        total = count_result[0]["total"] if count_result else 0

        # Get episodes
        episodes_query = f"""
        MATCH (e:Episode)
        WHERE {where_clause}
        RETURN
            e.uuid AS uuid,
            e.name AS name,
            e.content AS content,
            e.source AS source,
            e.source_description AS source_description,
            e.kind AS kind,
            e.created_at AS created_at,
            e.valid_at AS valid_at,
            e.user_id AS user_id,
            e.metadata AS metadata
        ORDER BY e.created_at {order_clause}
        SKIP $offset
        LIMIT $limit
        """

        episodes = self.execute(episodes_query, params)

        return {
            "episodes": episodes,
            "total": total,
        }

    def get_episode_by_uuid(self, episode_uuid: str) -> Optional[Dict[str, Any]]:
        """
        Get a single episode by its UUID.

        Args:
            episode_uuid: UUID of the episode

        Returns:
            Episode dictionary or None if not found
        """
        query = """
        MATCH (e:Episode {uuid: $uuid})
        RETURN
            e.uuid AS uuid,
            e.name AS name,
            e.content AS content,
            e.source AS source,
            e.source_description AS source_description,
            e.kind AS kind,
            e.created_at AS created_at,
            e.valid_at AS valid_at,
            e.user_id AS user_id,
            e.agent_id AS agent_id,
            e.metadata AS metadata,
            e.entity_edges AS entity_edges
        """

        result = self.execute(query, {"uuid": episode_uuid})
        return result[0] if result else None

    def update_episode_metadata(self, episode_uuid: str, metadata: Dict) -> Dict[str, Any]:
        """
        Update metadata for an existing episode.

        Args:
            episode_uuid: UUID of the episode
            metadata: New metadata dictionary to set

        Returns:
            Result dictionary
        """
        import json

        query = """
        MATCH (e:Episode {uuid: $uuid})
        SET e.metadata = $metadata
        RETURN e.uuid AS uuid
        """

        params = {
            "uuid": episode_uuid,
            "metadata": json.dumps(metadata),
        }

        return self.execute(query, params)

    def delete_episode(self, episode_uuid: str) -> Dict[str, Any]:
        """
        Delete an episode and all its relationships.

        Args:
            episode_uuid: UUID of the episode to delete

        Returns:
            Result dictionary with deletion confirmation
        """
        query = """
        MATCH (e:Episode {uuid: $uuid})
        DETACH DELETE e
        RETURN $uuid AS deleted_uuid
        """

        params = {"uuid": episode_uuid}
        result = self.execute(query, params)

        return {"success": True, "deleted_uuid": episode_uuid}

    def get_all_entities(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all entities, optionally filtered by user.

        Args:
            user_id: User ID for filtering (optional - returns all users if None)

        Returns:
            List of entity dictionaries
        """
        if user_id:
            query = """
            MATCH (e:Entity)
            WHERE e.user_id = $user_id
            RETURN
                e.uuid AS uuid,
                e.name AS name,
                e.entity_type AS entity_type,
                e.summary AS summary,
                e.mentions AS mentions,
                e.user_id AS user_id
            """
            return self.execute(query, {"user_id": user_id})
        else:
            query = """
            MATCH (e:Entity)
            RETURN
                e.uuid AS uuid,
                e.name AS name,
                e.entity_type AS entity_type,
                e.summary AS summary,
                e.mentions AS mentions,
                e.user_id AS user_id
            """
            return self.execute(query, {})

    def get_all_edges(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all relationship edges, optionally filtered by user.

        Args:
            user_id: User ID for filtering (optional - returns all users if None)

        Returns:
            List of edge dictionaries
        """
        if user_id:
            query = """
            MATCH (source:Entity)-[r:RELATES_TO]->(target:Entity)
            WHERE source.user_id = $user_id
              AND target.user_id = $user_id
            RETURN
                r.uuid AS uuid,
                source.uuid AS source_uuid,
                target.uuid AS target_uuid,
                r.name AS relation_type,
                r.fact AS fact,
                r.valid_at AS valid_at,
                r.invalid_at AS invalid_at,
                r.expired_at AS expired_at
            """
            return self.execute(query, {"user_id": user_id})
        else:
            query = """
            MATCH (source:Entity)-[r:RELATES_TO]->(target:Entity)
            RETURN
                r.uuid AS uuid,
                source.uuid AS source_uuid,
                target.uuid AS target_uuid,
                r.name AS relation_type,
                r.fact AS fact,
                r.valid_at AS valid_at,
                r.invalid_at AS invalid_at,
                r.expired_at AS expired_at
            """
            return self.execute(query, {})

    def get_all_users(self) -> List[str]:
        """
        Get all distinct user IDs in the database.
        Queries both Entity and Episode nodes to ensure complete user coverage.

        Returns:
            List of user_id strings
        """
        user_ids = set()

        # Get users from entities
        entity_query = """
        MATCH (e:Entity)
        WHERE e.user_id IS NOT NULL
        RETURN DISTINCT e.user_id AS user_id
        """
        entity_results = self.execute(entity_query, {})
        user_ids.update([r["user_id"] for r in entity_results if r.get("user_id")])

        # Get users from episodes (captures users with queries but no entities yet)
        episode_query = """
        MATCH (ep:Episode)
        WHERE ep.user_id IS NOT NULL
        RETURN DISTINCT ep.user_id AS user_id
        """
        episode_results = self.execute(episode_query, {})
        user_ids.update([r["user_id"] for r in episode_results if r.get("user_id")])

        return sorted(list(user_ids))


    # ===== Tool Methods =====

    def save_tool(self, tool_name: str, description: str, name_embedding: Optional[List[float]] = None) -> Dict[str, Any]:
        """
        Save a tool node to the database.

        Args:
            tool_name: Name of the tool
            description: Description of the tool
            name_embedding: Optional embedding vector for the tool name

        Returns:
            Result dictionary
        """
        from datetime import datetime, timezone
        from uuid import uuid4
        import hashlib

        # Generate deterministic UUID from tool_name for consistency
        tool_uuid = str(uuid4())  # Will be used only if creating

        # Check if tool exists first
        existing = self.get_tool_by_name(tool_name)

        if existing:
            # Tool exists - just update mentions and description
            update_query = f"""
            MATCH (t:Tool {{tool_name: $tool_name}})
            SET t.mentions = coalesce(t.mentions, 0) + 1,
                t.description = $description
            """
            if name_embedding is not None:
                update_query += f""",
                t.name_embedding = CAST($name_embedding, 'FLOAT[{self.embedding_dimensions}]')
            """
            update_query += """
            RETURN t.uuid AS uuid
            """

            params = {
                "tool_name": tool_name,
                "description": description,
                "name_embedding": name_embedding,
            }

            result = self.execute(update_query, params)
            logger.debug(f"Updated existing tool: {tool_name}")
            return result
        else:
            # Create new tool
            if name_embedding is not None:
                create_query = f"""
                CREATE (t:Tool {{
                    uuid: $uuid,
                    tool_name: $tool_name,
                    description: $description,
                    name_embedding: CAST($name_embedding, 'FLOAT[{self.embedding_dimensions}]'),
                    mentions: $mentions,
                    created_at: $created_at
                }})
                RETURN t.uuid AS uuid
                """
            else:
                create_query = """
                CREATE (t:Tool {
                    uuid: $uuid,
                    tool_name: $tool_name,
                    description: $description,
                    mentions: $mentions,
                    created_at: $created_at
                })
                RETURN t.uuid AS uuid
                """

            params = {
                "uuid": tool_uuid,
                "tool_name": tool_name,
                "description": description,
                "name_embedding": name_embedding,
                "mentions": 1,
                "created_at": datetime.now(timezone.utc),
            }

            result = self.execute(create_query, params)
            logger.debug(f"Created new tool: {tool_name}")
            return result

    def get_tool_by_name(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a tool by its name.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool dictionary or None
        """
        query = """
        MATCH (t:Tool {tool_name: $tool_name})
        RETURN
            t.uuid AS uuid,
            t.tool_name AS tool_name,
            t.description AS description,
            t.mentions AS mentions,
            t.created_at AS created_at
        """

        result = self.execute(query, {"tool_name": tool_name})
        return result[0] if result else None

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """
        Get all tools.

        Returns:
            List of tool dictionaries
        """
        query = """
        MATCH (t:Tool)
        RETURN
            t.uuid AS uuid,
            t.tool_name AS tool_name,
            t.description AS description,
            t.mentions AS mentions,
            t.created_at AS created_at
        ORDER BY t.tool_name
        """

        return self.execute(query)

    # ===== SystemConfig Methods =====

    def save_config(
        self,
        key: str,
        value: str,
        category: str,
        data_type: str,
        is_sensitive: bool = False,
        description: str = ""
    ) -> Dict[str, Any]:
        """
        Save or update a system configuration value.

        Args:
            key: Configuration key (e.g., 'llm.provider')
            value: Configuration value (stored as string, JSON for complex types)
            category: Configuration category (e.g., 'llm', 'embedding', 'api_keys')
            data_type: Data type ('string', 'int', 'float', 'bool', 'list')
            is_sensitive: Whether this is sensitive data (for UI masking)
            description: Human-readable description

        Returns:
            Result dictionary
        """
        from datetime import datetime, timezone

        query = """
        MERGE (c:SystemConfig {key: $key})
        SET
            c.value = $value,
            c.category = $category,
            c.data_type = $data_type,
            c.is_sensitive = $is_sensitive,
            c.updated_at = $updated_at,
            c.description = $description
        RETURN c.key AS key
        """

        params = {
            "key": key,
            "value": value,
            "category": category,
            "data_type": data_type,
            "is_sensitive": is_sensitive,
            "updated_at": datetime.now(timezone.utc),
            "description": description,
        }

        return self.execute(query, params)

    def get_config(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get a system configuration value by key.

        Args:
            key: Configuration key

        Returns:
            Config dictionary or None
        """
        query = """
        MATCH (c:SystemConfig {key: $key})
        RETURN
            c.key AS key,
            c.value AS value,
            c.category AS category,
            c.data_type AS data_type,
            c.is_sensitive AS is_sensitive,
            c.updated_at AS updated_at,
            c.description AS description
        """

        result = self.execute(query, {"key": key})
        return result[0] if result else None

    def get_all_configs(self) -> List[Dict[str, Any]]:
        """
        Get all system configuration values.

        Returns:
            List of config dictionaries
        """
        query = """
        MATCH (c:SystemConfig)
        RETURN
            c.key AS key,
            c.value AS value,
            c.category AS category,
            c.data_type AS data_type,
            c.is_sensitive AS is_sensitive,
            c.updated_at AS updated_at,
            c.description AS description
        ORDER BY c.category, c.key
        """

        return self.execute(query)

    def get_configs_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get all configuration values for a specific category.

        Args:
            category: Configuration category

        Returns:
            List of config dictionaries
        """
        query = """
        MATCH (c:SystemConfig {category: $category})
        RETURN
            c.key AS key,
            c.value AS value,
            c.category AS category,
            c.data_type AS data_type,
            c.is_sensitive AS is_sensitive,
            c.updated_at AS updated_at,
            c.description AS description
        ORDER BY c.key
        """

        return self.execute(query, {"category": category})

    def delete_config(self, key: str) -> Dict[str, Any]:
        """
        Delete a system configuration value.

        Args:
            key: Configuration key

        Returns:
            Result dictionary
        """
        query = """
        MATCH (c:SystemConfig {key: $key})
        DELETE c
        RETURN $key AS deleted_key
        """

        return self.execute(query, {"key": key})

    def close(self) -> None:
        """Close the database connection"""
        try:
            # Close connection first
            if hasattr(self, 'conn') and not self.conn.is_closed:
                self.conn.close()

            # Then close database
            if hasattr(self, 'db') and not self.db.is_closed:
                self.db.close()

            logger.info("RyugraphDB connection closed")
        except Exception as e:
            logger.error(f"Error closing RyugraphDB: {e}", exc_info=True)

    def reset(self) -> None:
        """
        Reset the entire database (delete all nodes and relationships).
        WARNING: This is irreversible!
        """
        logger.warning("Resetting entire graph database...")
        self.execute("MATCH (n) DETACH DELETE n")
        logger.info("Graph database reset complete")
