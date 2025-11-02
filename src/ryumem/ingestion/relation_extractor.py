"""
Relationship extraction and resolution module.
Extracts relationships between entities and resolves them against existing relationships.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from ryumem.core.graph_db import RyugraphDB
from ryumem.core.models import EntityEdge, EntityNode
from ryumem.utils.embeddings import EmbeddingClient
from ryumem.utils.llm import LLMClient

logger = logging.getLogger(__name__)


class RelationExtractor:
    """
    Handles relationship extraction and resolution.
    """

    def __init__(
        self,
        db: RyugraphDB,
        llm_client: LLMClient,
        embedding_client: EmbeddingClient,
        similarity_threshold: float = 0.8,
    ):
        """
        Initialize relation extractor.

        Args:
            db: Ryugraph database instance
            llm_client: LLM client for extraction
            embedding_client: Embedding client for similarity search
            similarity_threshold: Threshold for relationship deduplication (0.0-1.0)
        """
        self.db = db
        self.llm_client = llm_client
        self.embedding_client = embedding_client
        self.similarity_threshold = similarity_threshold

        logger.info(f"Initialized RelationExtractor with threshold: {similarity_threshold}")

    def extract_and_resolve(
        self,
        content: str,
        entities: List[EntityNode],
        entity_map: Dict[str, str],
        episode_uuid: str,
        group_id: str,
        context: Optional[str] = None,
    ) -> List[EntityEdge]:
        """
        Extract relationships from content and resolve them against existing relationships.

        Args:
            content: Text content to extract relationships from
            entities: List of resolved entities
            entity_map: Mapping of entity names to UUIDs
            episode_uuid: UUID of the current episode
            group_id: Group ID for multi-tenancy
            context: Optional context from previous episodes

        Returns:
            List of resolved entity edges
        """
        if not entities:
            logger.info("No entities provided for relationship extraction")
            return []

        # Step 1: Extract relationships using LLM
        entity_names = [e.name for e in entities]
        extracted = self._extract_relationships_with_llm(
            content=content,
            entities=entity_names,
            user_id=group_id,
            context=context,
        )

        if not extracted:
            logger.info("No relationships extracted from content")
            return []

        logger.info(f"Extracted {len(extracted)} raw relationships")

        # Step 2: Generate embeddings for all facts
        facts = [r["fact"] for r in extracted]
        embeddings = self.embedding_client.embed_batch(facts)

        # Step 3: Resolve each relationship
        resolved_edges: List[EntityEdge] = []

        for rel_data, embedding in zip(extracted, embeddings):
            source_name = rel_data["source"].lower().replace(" ", "_")
            dest_name = rel_data["destination"].lower().replace(" ", "_")
            relation_type = rel_data["relationship"].upper().replace(" ", "_")
            fact = rel_data["fact"]

            # Get UUIDs for source and destination
            source_uuid = entity_map.get(source_name)
            dest_uuid = entity_map.get(dest_name)

            if not source_uuid or not dest_uuid:
                logger.warning(
                    f"Skipping relationship - entity not found: "
                    f"{source_name} -> {dest_name}"
                )
                continue

            # Search for similar existing relationships
            similar = self.db.search_similar_edges(
                embedding=embedding,
                group_id=group_id,
                threshold=self.similarity_threshold,
                limit=1,
            )

            if similar:
                # Found similar edge - update it
                existing = similar[0]
                edge_uuid = existing["edge_uuid"]

                logger.debug(
                    f"Resolved relationship to existing edge "
                    f"(similarity: {existing['similarity']:.3f})"
                )

                # Get existing edge data
                existing_episodes = []  # Would need to fetch from DB

                edge = EntityEdge(
                    uuid=edge_uuid,
                    source_node_uuid=source_uuid,
                    target_node_uuid=dest_uuid,
                    name=relation_type,
                    fact=fact,
                    fact_embedding=embedding,
                    episodes=[episode_uuid],  # Add current episode
                    mentions=1,  # Will be incremented in DB
                    group_id=group_id,
                )

            else:
                # No similar edge found - create new one
                edge_uuid = str(uuid4())

                edge = EntityEdge(
                    uuid=edge_uuid,
                    source_node_uuid=source_uuid,
                    target_node_uuid=dest_uuid,
                    name=relation_type,
                    fact=fact,
                    fact_embedding=embedding,
                    created_at=datetime.utcnow(),
                    valid_at=datetime.utcnow(),  # Assume valid from now
                    episodes=[episode_uuid],
                    mentions=1,
                    group_id=group_id,
                )

                logger.debug(
                    f"Created new relationship: {source_name} --[{relation_type}]--> {dest_name}"
                )

            # Save edge to database
            self.db.save_entity_edge(edge, source_uuid, dest_uuid)
            resolved_edges.append(edge)

        logger.info(
            f"Resolved {len(resolved_edges)} relationships "
            f"({len([e for e in resolved_edges if e.mentions == 1])} new, "
            f"{len([e for e in resolved_edges if e.mentions > 1])} updated)"
        )

        return resolved_edges

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
            entities: List of entity names to find relationships for
            user_id: User ID for context
            context: Optional context

        Returns:
            List of dicts with 'source', 'relationship', 'destination', 'fact' keys
        """
        try:
            relationships = self.llm_client.extract_relationships(
                text=content,
                entities=entities,
                user_id=user_id,
                context=context,
            )

            # Normalize relationship data
            normalized = []
            for rel in relationships:
                normalized.append({
                    "source": rel["source"].lower().replace(" ", "_"),
                    "relationship": rel["relationship"].upper().replace(" ", "_"),
                    "destination": rel["destination"].lower().replace(" ", "_"),
                    "fact": rel["fact"],
                })

            return normalized

        except Exception as e:
            logger.error(f"Error extracting relationships with LLM: {e}")
            return []

    def detect_contradictions(
        self,
        new_edges: List[EntityEdge],
        group_id: str,
    ) -> List[str]:
        """
        Detect contradicting edges that should be invalidated.

        Args:
            new_edges: List of newly extracted edges
            group_id: Group ID

        Returns:
            List of edge UUIDs to invalidate
        """
        if not new_edges:
            return []

        to_invalidate: List[str] = []

        # For each new edge, check if it contradicts existing edges
        for new_edge in new_edges:
            # Get existing relationships for the source entity
            existing_rels = self.db.get_entity_relationships(
                entity_uuid=new_edge.source_node_uuid,
                include_expired=False,
            )

            # Filter to same relation type
            same_type_rels = [
                r for r in existing_rels
                if r["relation_type"] == new_edge.name
            ]

            if not same_type_rels:
                continue

            # Build fact lists for comparison
            new_facts = [new_edge.fact]
            existing_facts = [r["fact"] for r in same_type_rels]

            try:
                # Use LLM to detect contradictions
                contradictions = self.llm_client.detect_contradictions(
                    new_facts=new_facts,
                    existing_facts=existing_facts,
                )

                # Mark contradicting edges for invalidation
                for contradiction in contradictions:
                    existing_idx = contradiction["existing_fact_index"]
                    if 0 <= existing_idx < len(same_type_rels):
                        edge_uuid = same_type_rels[existing_idx]["edge_uuid"]
                        to_invalidate.append(edge_uuid)
                        logger.info(
                            f"Detected contradiction - will invalidate edge {edge_uuid}: "
                            f"{contradiction['reason']}"
                        )

            except Exception as e:
                logger.error(f"Error detecting contradictions: {e}")
                continue

        return to_invalidate

    def invalidate_edges(self, edge_uuids: List[str]) -> None:
        """
        Invalidate (expire) a list of edges.

        Args:
            edge_uuids: List of edge UUIDs to invalidate
        """
        for uuid in edge_uuids:
            try:
                self.db.invalidate_edge(uuid)
                logger.info(f"Invalidated edge {uuid}")
            except Exception as e:
                logger.error(f"Error invalidating edge {uuid}: {e}")
