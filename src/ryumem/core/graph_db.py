"""
Ryugraph database layer - adapted from mem0's kuzu implementation.
Ryugraph is a renamed version of kuzu, so the API should be identical.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import ryu as ryugraph

from ryumem.core.models import (
    CommunityEdge,
    CommunityNode,
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

    def __init__(self, db_path: str, embedding_dimensions: int = 3072, read_only: bool = False):
        """
        Initialize Ryugraph database connection.

        Args:
            db_path: Path to the ryugraph database directory
            embedding_dimensions: Dimension of embedding vectors (default: 3072 for text-embedding-3-large)
            read_only: If True, open database in READ_ONLY mode (allows concurrent access)
        """
        self.db_path = db_path
        self.embedding_dimensions = embedding_dimensions
        self.read_only = read_only

        # Create database and connection
        self.db = ryugraph.Database(db_path, read_only=read_only)
        self.conn = ryugraph.Connection(self.db)

        # Initialize schema only in read-write mode
        if not read_only:
            self.create_schema()

        mode = "READ_ONLY" if read_only else "READ_WRITE"
        logger.info(f"Initialized RyugraphDB at {db_path} with {embedding_dimensions}D embeddings in {mode} mode")

    def create_schema(self) -> None:
        """
        Create the graph schema for Ryumem.
        Includes Episode, Entity, and Community nodes with their relationships.
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
                created_at TIMESTAMP,
                valid_at TIMESTAMP,
                group_id STRING,
                user_id STRING,
                agent_id STRING,
                session_id STRING,
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
                instruction_type STRING,
                instruction_text STRING,
                original_user_request STRING,
                description STRING,
                version INT64,
                active BOOLEAN,
                created_at TIMESTAMP
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
                group_id STRING,
                user_id STRING,
                labels STRING[],
                attributes STRING
            );
            """
        )

        # Community nodes
        self.execute(
            f"""
            CREATE NODE TABLE IF NOT EXISTS Community(
                uuid STRING PRIMARY KEY,
                name STRING,
                summary STRING,
                name_embedding FLOAT[{self.embedding_dimensions}],
                created_at TIMESTAMP,
                group_id STRING,
                members STRING[],
                member_count INT64
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
                attributes STRING,
                group_id STRING
            );
            """
        )

        # MENTIONS edges (Episode -> Entity)
        self.execute(
            """
            CREATE REL TABLE IF NOT EXISTS MENTIONS(
                FROM Episode TO Entity,
                uuid STRING,
                created_at TIMESTAMP,
                group_id STRING
            );
            """
        )

        # HAS_MEMBER edges (Community -> Entity)
        self.execute(
            """
            CREATE REL TABLE IF NOT EXISTS HAS_MEMBER(
                FROM Community TO Entity,
                uuid STRING,
                created_at TIMESTAMP,
                group_id STRING
            );
            """
        )

        # TRIGGERED edges (Episode -> Episode) for query-to-tool-execution linking
        self.execute(
            """
            CREATE REL TABLE IF NOT EXISTS TRIGGERED(
                FROM Episode TO Episode,
                uuid STRING,
                created_at TIMESTAMP,
                group_id STRING
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
            e.created_at = $created_at,
            e.valid_at = $valid_at,
            e.group_id = $group_id,
            e.user_id = $user_id,
            e.agent_id = $agent_id,
            e.session_id = $session_id,
            e.metadata = $metadata,
            e.entity_edges = $entity_edges
        ON MATCH SET
            e.entity_edges = $entity_edges,
            e.content_embedding = $content_embedding
        RETURN e.uuid AS uuid
        """

        params = {
            "uuid": episode.uuid,
            "name": episode.name,
            "content": episode.content,
            "content_embedding": getattr(episode, 'content_embedding', None),
            "source": episode.source.value,
            "source_description": episode.source_description,
            "created_at": episode.created_at,
            "valid_at": episode.valid_at,
            "group_id": episode.group_id,
            "user_id": episode.user_id,
            "agent_id": episode.agent_id,
            "session_id": episode.session_id,
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
            "e.group_id = $group_id",
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
            "group_id": entity.group_id,
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
            r.attributes = $attributes,
            r.group_id = $group_id
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
            "group_id": edge.group_id,
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
            r.created_at = $created_at,
            r.group_id = $group_id
        RETURN r.uuid AS uuid
        """

        params = {
            "episode_uuid": edge.source_node_uuid,
            "entity_uuid": edge.target_node_uuid,
            "uuid": edge.uuid,
            "created_at": edge.created_at,
            "group_id": edge.group_id,
        }

        return self.execute(query, params)

    def find_similar_episode(
        self,
        content: str,
        group_id: str,
        user_id: Optional[str] = None,
        time_window_hours: int = 24,
    ) -> Optional[Dict[str, Any]]:
        """
        Find an episode with identical or very similar content.

        Uses exact content matching within a time window to detect duplicates.

        Args:
            content: Episode content to check
            group_id: Group ID
            user_id: Optional user ID
            time_window_hours: Look back this many hours for duplicates

        Returns:
            Existing episode dict if found, None otherwise
        """
        from datetime import datetime, timedelta, timezone

        # Check for exact content match first (fast)
        query = """
        MATCH (e:Episode)
        WHERE e.content = $content
          AND e.group_id = $group_id
          AND e.created_at > $time_cutoff
        """

        if user_id:
            query += " AND e.user_id = $user_id"

        query += """
        RETURN
            e.uuid AS uuid,
            e.content AS content,
            e.created_at AS created_at
        ORDER BY e.created_at DESC
        LIMIT 1
        """

        time_cutoff = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)

        params = {
            "content": content,
            "group_id": group_id,
            "time_cutoff": time_cutoff,
        }

        if user_id:
            params["user_id"] = user_id

        results = self.execute(query, params)
        return results[0] if results else None

    def search_similar_entities(
        self,
        embedding: List[float],
        group_id: str,
        threshold: float = 0.7,
        limit: int = 10,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for entities similar to the given embedding.

        Args:
            embedding: Query embedding vector
            group_id: Group ID to filter by
            threshold: Minimum similarity threshold (0.0-1.0)
            limit: Maximum number of results
            user_id: Optional user ID filter

        Returns:
            List of similar entities with similarity scores
        """
        # Build WHERE conditions
        conditions = [
            "e.name_embedding IS NOT NULL",
            "e.group_id = $group_id"
        ]
        params = {
            "embedding": embedding,
            "group_id": group_id,
            "threshold": threshold,
            "limit": limit,
        }

        if user_id:
            conditions.append("e.user_id = $user_id")
            params["user_id"] = user_id

        where_clause = " AND ".join(conditions)

        query = f"""
        MATCH (e:Entity)
        WHERE {where_clause}
        WITH e, array_cosine_similarity(e.name_embedding, CAST($embedding, 'FLOAT[{self.embedding_dimensions}]')) AS similarity
        WHERE similarity >= $threshold
        RETURN
            e.uuid AS uuid,
            e.name AS name,
            e.entity_type AS entity_type,
            e.summary AS summary,
            e.mentions AS mentions,
            e.group_id AS group_id,
            similarity
        ORDER BY similarity DESC
        LIMIT $limit
        """

        return self.execute(query, params)

    def search_similar_episodes(
        self,
        embedding: List[float],
        group_id: str,
        threshold: float = 0.7,
        limit: int = 10,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for episodes similar to the given embedding.

        Args:
            embedding: Query embedding vector
            group_id: Group ID to filter by
            threshold: Minimum similarity threshold (0.0-1.0)
            limit: Maximum number of results
            user_id: Optional user ID filter

        Returns:
            List of similar episodes with similarity scores
        """
        # Build WHERE conditions
        conditions = [
            "ep.content_embedding IS NOT NULL",
            "ep.group_id = $group_id"
        ]
        params = {
            "embedding": embedding,
            "group_id": group_id,
            "threshold": threshold,
            "limit": limit,
        }

        if user_id:
            conditions.append("ep.user_id = $user_id")
            params["user_id"] = user_id

        where_clause = " AND ".join(conditions)

        query = f"""
        MATCH (ep:Episode)
        WHERE {where_clause}
        WITH ep, array_cosine_similarity(ep.content_embedding, CAST($embedding, 'FLOAT[{self.embedding_dimensions}]')) AS similarity
        WHERE similarity >= $threshold
        RETURN
            ep.uuid AS uuid,
            ep.name AS name,
            ep.content AS content,
            ep.source AS source,
            ep.source_description AS source_description,
            ep.created_at AS created_at,
            ep.valid_at AS valid_at,
            ep.group_id AS group_id,
            ep.user_id AS user_id,
            ep.agent_id AS agent_id,
            ep.session_id AS session_id,
            ep.metadata AS metadata,
            similarity
        ORDER BY similarity DESC
        LIMIT $limit
        """

        return self.execute(query, params)

    def search_similar_edges(
        self,
        embedding: List[float],
        group_id: str,
        threshold: float = 0.8,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search for entity edges similar to the given embedding.

        Args:
            embedding: Query embedding vector
            group_id: Group ID to filter by
            threshold: Minimum similarity threshold (0.0-1.0)
            limit: Maximum number of results

        Returns:
            List of similar edges with similarity scores
        """
        query = f"""
        MATCH (source:Entity)-[r:RELATES_TO]->(target:Entity)
        WHERE r.fact_embedding IS NOT NULL
          AND r.group_id = $group_id
          AND (r.expired_at IS NULL OR r.expired_at > current_timestamp())
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
            "group_id": group_id,
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
            e.group_id AS group_id,
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
            r.episodes AS episodes,
            r.group_id AS group_id
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

    def delete_by_group_id(self, group_id: str) -> None:
        """
        Delete all data for a specific group_id.

        Args:
            group_id: Group ID to delete
        """
        # Delete in order: edges first, then nodes
        self.execute(
            """
            MATCH ()-[r:MENTIONS|RELATES_TO|HAS_MEMBER {group_id: $group_id}]->()
            DELETE r
            """,
            {"group_id": group_id}
        )

        for node_type in ["Episode", "Entity", "Community"]:
            self.execute(
                f"""
                MATCH (n:{node_type} {{group_id: $group_id}})
                DETACH DELETE n
                """,
                {"group_id": group_id}
            )

        logger.info(f"Deleted all data for group_id: {group_id}")

    def get_episode_context(
        self,
        group_id: str,
        limit: int = 5,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get recent episodes for context in extraction.

        Args:
            group_id: Group ID to filter by
            limit: Maximum number of episodes to return
            user_id: Optional user ID filter
            session_id: Optional session ID filter

        Returns:
            List of recent episodes
        """
        conditions = ["e.group_id = $group_id"]
        params = {"group_id": group_id, "limit": limit}

        if user_id:
            conditions.append("e.user_id = $user_id")
            params["user_id"] = user_id

        if session_id:
            conditions.append("e.session_id = $session_id")
            params["session_id"] = session_id

        where_clause = " AND ".join(conditions)

        query = f"""
        MATCH (e:Episode)
        WHERE {where_clause}
        RETURN
            e.uuid AS uuid,
            e.name AS name,
            e.content AS content,
            e.created_at AS created_at
        ORDER BY e.created_at DESC
        LIMIT $limit
        """

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
            e.group_id AS group_id
        """

        params = {"episode_uuid": episode_uuid}
        return self.execute(query, params)

    # ===== Community Methods =====

    def save_community(self, community: "CommunityNode") -> Dict[str, Any]:
        """
        Save a community node to the database.

        Args:
            community: CommunityNode to save

        Returns:
            Result dictionary
        """
        import json

        # Convert members list to JSON string array
        members_json = json.dumps(community.members)

        query = """
        MERGE (c:Community {uuid: $uuid})
        ON CREATE SET
            c.name = $name,
            c.summary = $summary,
            c.created_at = $created_at,
            c.group_id = $group_id,
            c.members = $members,
            c.member_count = $member_count
        ON MATCH SET
            c.summary = $summary,
            c.members = $members,
            c.member_count = $member_count
        RETURN c.uuid AS uuid
        """

        params = {
            "uuid": community.uuid,
            "name": community.name,
            "summary": community.summary,
            "created_at": community.created_at,
            "group_id": community.group_id,
            "members": members_json,
            "member_count": len(community.members),
        }

        result = self.execute(query, params)
        logger.debug(f"Saved community: {community.uuid}")
        return result

    def create_has_member_edge(
        self,
        community_uuid: str,
        entity_uuid: str,
    ) -> Dict[str, Any]:
        """
        Create a HAS_MEMBER edge from Community to Entity.

        Args:
            community_uuid: UUID of the community
            entity_uuid: UUID of the entity

        Returns:
            Result dictionary
        """
        from datetime import datetime, timezone
        from uuid import uuid4

        query = """
        MATCH (c:Community {uuid: $community_uuid})
        MATCH (e:Entity {uuid: $entity_uuid})
        CREATE (c)-[r:HAS_MEMBER {
            uuid: $uuid,
            created_at: $created_at,
            group_id: c.group_id
        }]->(e)
        RETURN r.uuid AS uuid
        """

        params = {
            "community_uuid": community_uuid,
            "entity_uuid": entity_uuid,
            "uuid": str(uuid4()),
            "created_at": datetime.now(timezone.utc),
        }

        result = self.execute(query, params)
        logger.debug(f"Created HAS_MEMBER edge: {community_uuid} -> {entity_uuid}")
        return result

    def get_all_entities(self, group_id: str) -> List[Dict[str, Any]]:
        """
        Get all entities for a group.

        Args:
            group_id: Group ID

        Returns:
            List of entity dictionaries
        """
        query = """
        MATCH (e:Entity)
        WHERE e.group_id = $group_id
        RETURN
            e.uuid AS uuid,
            e.name AS name,
            e.entity_type AS entity_type,
            e.summary AS summary,
            e.mentions AS mentions,
            e.group_id AS group_id
        """

        return self.execute(query, {"group_id": group_id})

    def get_all_edges(self, group_id: str) -> List[Dict[str, Any]]:
        """
        Get all relationship edges for a group.

        Args:
            group_id: Group ID

        Returns:
            List of edge dictionaries
        """
        query = """
        MATCH (source:Entity)-[r:RELATES_TO]->(target:Entity)
        WHERE r.group_id = $group_id
        RETURN
            r.uuid AS uuid,
            source.uuid AS source_uuid,
            target.uuid AS target_uuid,
            r.name AS relation_type,
            r.fact AS fact,
            r.valid_at AS valid_at,
            r.invalid_at AS invalid_at,
            r.expired_at AS expired_at,
            r.group_id AS group_id
        """

        return self.execute(query, {"group_id": group_id})

    def get_community_by_uuid(self, community_uuid: str) -> Optional[Dict[str, Any]]:
        """
        Get a community by UUID.

        Args:
            community_uuid: UUID of the community

        Returns:
            Community dictionary or None
        """
        import json

        query = """
        MATCH (c:Community {uuid: $uuid})
        RETURN
            c.uuid AS uuid,
            c.name AS name,
            c.summary AS summary,
            c.created_at AS created_at,
            c.group_id AS group_id,
            c.members AS members,
            c.member_count AS member_count
        """

        result = self.execute(query, {"uuid": community_uuid})

        if result:
            community = result[0]
            # Parse members JSON string back to list
            if community.get("members"):
                community["members"] = json.loads(community["members"])
            return community

        return None

    def delete_communities(self, group_id: str) -> None:
        """
        Delete all communities for a group.

        Args:
            group_id: Group ID
        """
        query = """
        MATCH (c:Community {group_id: $group_id})
        DETACH DELETE c
        """

        self.execute(query, {"group_id": group_id})
        logger.info(f"Deleted all communities for group: {group_id}")

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

    def close(self) -> None:
        """Close the database connection"""
        # Ryugraph/Kuzu connections don't need explicit closing
        logger.info("RyugraphDB connection closed")

    def reset(self) -> None:
        """
        Reset the entire database (delete all nodes and relationships).
        WARNING: This is irreversible!
        """
        logger.warning("Resetting entire graph database...")
        self.execute("MATCH (n) DETACH DELETE n")
        logger.info("Graph database reset complete")
