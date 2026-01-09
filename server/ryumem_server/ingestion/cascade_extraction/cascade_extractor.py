"""
CascadeExtractor - Main orchestrator for multi-round cascade extraction.

Coordinates the three-stage extraction pipeline:
1. Node extraction
2. Relationship extraction
3. Triplet extraction

And converts the result to Ryumem's EntityNode/EntityEdge models.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Union

from .models import KnowledgeGraph, ExtractedNode, ExtractedEdge
from .extract_nodes import extract_nodes, extract_nodes_sync
from .extract_relationships import extract_relationships, extract_relationships_sync
from .extract_triplets import extract_triplets, extract_triplets_sync

logger = logging.getLogger(__name__)


class CascadeExtractor:
    """
    Multi-round cascade extraction orchestrator.

    Performs three-stage extraction:
    1. Extract potential nodes from text
    2. Extract relationship types and refine nodes
    3. Extract complete triplets as a knowledge graph

    Each stage runs multiple rounds for better extraction quality.
    """

    def __init__(
        self,
        llm_client,
        n_rounds: int = 2,
    ):
        """
        Initialize CascadeExtractor.

        Args:
            llm_client: LLM client with create_structured_output method
            n_rounds: Number of extraction rounds per stage (default: 2)
        """
        self.llm_client = llm_client
        self.n_rounds = n_rounds

        logger.info(f"Initialized CascadeExtractor with {n_rounds} rounds per stage")

    async def aextract(
        self,
        text: str,
        user_id: str,
        context: Optional[str] = None,
    ) -> KnowledgeGraph:
        """
        Async cascade extraction pipeline.

        Args:
            text: Input text to extract knowledge from
            user_id: User ID for self-reference resolution
            context: Optional conversation context

        Returns:
            KnowledgeGraph with extracted nodes and edges
        """
        logger.info(f"Starting cascade extraction for user {user_id}")

        # Stage 1: Extract nodes
        logger.debug("Stage 1: Extracting nodes...")
        nodes = await extract_nodes(
            text=text,
            user_id=user_id,
            llm_client=self.llm_client,
            n_rounds=self.n_rounds,
            context=context,
        )

        if not nodes:
            logger.warning("No nodes extracted, returning empty graph")
            return KnowledgeGraph(nodes=[], edges=[])

        # Stage 2: Extract relationships and refine nodes
        logger.debug("Stage 2: Extracting relationships...")
        refined_nodes, relationships = await extract_relationships(
            text=text,
            nodes=nodes,
            user_id=user_id,
            llm_client=self.llm_client,
            n_rounds=self.n_rounds,
            context=context,
        )

        if not refined_nodes:
            logger.warning("No refined nodes, returning empty graph")
            return KnowledgeGraph(nodes=[], edges=[])

        # Stage 3: Extract triplets
        logger.debug("Stage 3: Extracting triplets...")
        graph = await extract_triplets(
            text=text,
            nodes=refined_nodes,
            relationships=relationships,
            user_id=user_id,
            llm_client=self.llm_client,
            n_rounds=self.n_rounds,
            context=context,
        )

        logger.info(
            f"Cascade extraction complete: {len(graph.nodes)} nodes, "
            f"{len(graph.edges)} edges"
        )
        return graph

    def extract(
        self,
        text: str,
        user_id: str,
        context: Optional[str] = None,
    ) -> KnowledgeGraph:
        """
        Synchronous cascade extraction pipeline.

        Args:
            text: Input text to extract knowledge from
            user_id: User ID for self-reference resolution
            context: Optional conversation context

        Returns:
            KnowledgeGraph with extracted nodes and edges
        """
        logger.info(f"Starting cascade extraction for user {user_id}")

        # Stage 1: Extract nodes
        logger.debug("Stage 1: Extracting nodes...")
        nodes = extract_nodes_sync(
            text=text,
            user_id=user_id,
            llm_client=self.llm_client,
            n_rounds=self.n_rounds,
            context=context,
        )

        if not nodes:
            logger.warning("No nodes extracted, returning empty graph")
            return KnowledgeGraph(nodes=[], edges=[])

        # Stage 2: Extract relationships and refine nodes
        logger.debug("Stage 2: Extracting relationships...")
        refined_nodes, relationships = extract_relationships_sync(
            text=text,
            nodes=nodes,
            user_id=user_id,
            llm_client=self.llm_client,
            n_rounds=self.n_rounds,
            context=context,
        )

        if not refined_nodes:
            logger.warning("No refined nodes, returning empty graph")
            return KnowledgeGraph(nodes=[], edges=[])

        # Stage 3: Extract triplets
        logger.debug("Stage 3: Extracting triplets...")
        graph = extract_triplets_sync(
            text=text,
            nodes=refined_nodes,
            relationships=relationships,
            user_id=user_id,
            llm_client=self.llm_client,
            n_rounds=self.n_rounds,
            context=context,
        )

        logger.info(
            f"Cascade extraction complete: {len(graph.nodes)} nodes, "
            f"{len(graph.edges)} edges"
        )
        return graph

    def to_ryumem_models(
        self,
        graph: KnowledgeGraph,
        user_id: str,
        episode_uuid: str,
    ) -> Tuple[List, List]:
        """
        Convert KnowledgeGraph to Ryumem's EntityNode and EntityEdge models.

        Args:
            graph: KnowledgeGraph from cascade extraction
            user_id: User ID for the entities
            episode_uuid: Episode UUID to associate with edges

        Returns:
            Tuple of (List[EntityNode], List[EntityEdge])
        """
        # Import here to avoid circular imports
        from ryumem_server.core.models import EntityNode, EntityEdge

        now = datetime.now(timezone.utc)

        # Convert nodes to EntityNode
        entity_nodes: List[EntityNode] = []
        node_uuid_map: dict = {}  # Map extracted node ID to EntityNode UUID

        for extracted_node in graph.nodes:
            entity_uuid = str(uuid.uuid4())
            node_uuid_map[extracted_node.id] = entity_uuid

            # Normalize name: lowercase with underscores
            name = extracted_node.name.lower().replace(" ", "_")

            entity_node = EntityNode(
                uuid=entity_uuid,
                name=name,
                entity_type=extracted_node.type.upper(),
                summary=extracted_node.description or "",
                name_embedding=None,  # Will be generated during resolution
                mentions=1,
                created_at=now,
                user_id=user_id,
            )
            entity_nodes.append(entity_node)

        # Convert edges to EntityEdge
        entity_edges: List[EntityEdge] = []

        for extracted_edge in graph.edges:
            # Get mapped UUIDs
            source_uuid = node_uuid_map.get(extracted_edge.source_node_id)
            target_uuid = node_uuid_map.get(extracted_edge.target_node_id)

            if not source_uuid or not target_uuid:
                logger.warning(
                    f"Skipping edge with missing node: "
                    f"{extracted_edge.source_node_id} -> {extracted_edge.target_node_id}"
                )
                continue

            # Generate fact if not provided
            fact = extracted_edge.fact
            if not fact:
                source_name = extracted_edge.source_node_id.replace("_", " ")
                target_name = extracted_edge.target_node_id.replace("_", " ")
                rel_name = extracted_edge.relationship_name.replace("_", " ").lower()
                fact = f"{source_name} {rel_name} {target_name}"

            entity_edge = EntityEdge(
                uuid=str(uuid.uuid4()),
                source_node_uuid=source_uuid,
                target_node_uuid=target_uuid,
                name=extracted_edge.relationship_name.upper(),
                fact=fact,
                fact_embedding=None,  # Will be generated during resolution
                created_at=now,
                valid_at=now,
                invalid_at=None,
                expired_at=None,
                episodes=[episode_uuid],
                mentions=1,
            )
            entity_edges.append(entity_edge)

        logger.info(
            f"Converted to Ryumem models: {len(entity_nodes)} EntityNodes, "
            f"{len(entity_edges)} EntityEdges"
        )
        return entity_nodes, entity_edges
