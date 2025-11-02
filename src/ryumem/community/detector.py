"""
Community detection for Ryumem.

Uses Louvain algorithm to cluster related entities into communities.
Generates LLM-powered summaries for each community.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List
from uuid import uuid4

import networkx as nx
from networkx.algorithms import community as nx_community

from ryumem.core.graph_db import RyugraphDB
from ryumem.core.models import CommunityNode
from ryumem.utils.llm import LLMClient

logger = logging.getLogger(__name__)


class CommunityDetector:
    """
    Detect communities (clusters) of related entities.

    Communities help with:
    - Organizing large knowledge graphs
    - Efficient retrieval (search within relevant communities first)
    - Higher-level summaries and reasoning
    - Token optimization (compress subgraphs into summaries)

    Uses:
    - Louvain algorithm for community detection
    - LLM-generated summaries for each community
    """

    def __init__(
        self,
        db: RyugraphDB,
        llm_client: LLMClient,
    ):
        """
        Initialize community detector.

        Args:
            db: Ryugraph database instance
            llm_client: LLM client for generating summaries
        """
        self.db = db
        self.llm_client = llm_client

        logger.info("Initialized CommunityDetector")

    def detect_communities(
        self,
        group_id: str,
        resolution: float = 1.0,
        min_community_size: int = 2,
    ) -> int:
        """
        Detect communities for a given group using Louvain algorithm.

        Creates CommunityNode objects for each detected community.

        Args:
            group_id: Group ID to detect communities for
            resolution: Resolution parameter for Louvain (higher = more communities)
            min_community_size: Minimum number of entities in a community

        Returns:
            Number of communities created

        Example:
            detector = CommunityDetector(db, llm_client)
            num_communities = detector.detect_communities("user_123")
            print(f"Created {num_communities} communities")
        """
        logger.info(f"Detecting communities for group: {group_id}")

        # Step 1: Fetch all entities and edges for this group
        entities = self.db.get_all_entities(group_id)
        edges = self.db.get_all_edges(group_id)

        if not entities:
            logger.warning(f"No entities found for group {group_id}")
            return 0

        logger.info(f"Building graph from {len(entities)} entities and {len(edges)} edges")

        # Step 2: Build NetworkX graph
        G = nx.Graph()

        # Add nodes
        for entity in entities:
            G.add_node(
                entity["uuid"],
                name=entity["name"],
                entity_type=entity["entity_type"],
                summary=entity.get("summary", ""),
            )

        # Add edges
        for edge in edges:
            # Only include active (non-expired) edges
            if edge.get("expired_at") is None:
                G.add_edge(
                    edge["source_uuid"],
                    edge["target_uuid"],
                    fact=edge["fact"],
                    relation_type=edge["relation_type"],
                )

        logger.info(f"Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

        # Step 3: Run Louvain community detection
        try:
            communities = nx_community.louvain_communities(
                G,
                resolution=resolution,
                seed=42,  # For reproducibility
            )
        except Exception as e:
            logger.error(f"Error running Louvain algorithm: {e}")
            return 0

        logger.info(f"Louvain detected {len(communities)} raw communities")

        # Step 4: Filter communities by size
        filtered_communities = [
            comm for comm in communities
            if len(comm) >= min_community_size
        ]

        logger.info(
            f"After filtering (min_size={min_community_size}): "
            f"{len(filtered_communities)} communities"
        )

        # Step 5: Create CommunityNode for each community
        created_count = 0
        for i, community_entities in enumerate(filtered_communities):
            try:
                community = self._create_community(
                    community_id=i,
                    entity_uuids=list(community_entities),
                    group_id=group_id,
                    graph=G,
                )

                # Save to database
                self.db.save_community(community)

                # Create HAS_MEMBER edges
                self._create_has_member_edges(community.uuid, list(community_entities))

                created_count += 1
                logger.debug(f"Created community {i}: {community.name} ({len(community_entities)} entities)")

            except Exception as e:
                logger.error(f"Error creating community {i}: {e}")
                continue

        logger.info(f"Successfully created {created_count} communities for group {group_id}")
        return created_count

    def _create_community(
        self,
        community_id: int,
        entity_uuids: List[str],
        group_id: str,
        graph: nx.Graph,
    ) -> CommunityNode:
        """
        Create a CommunityNode with LLM-generated summary.

        Args:
            community_id: Community identifier
            entity_uuids: List of entity UUIDs in this community
            group_id: Group ID
            graph: NetworkX graph (for accessing entity data)

        Returns:
            CommunityNode object
        """
        # Gather entity information
        entity_infos = []
        for entity_uuid in entity_uuids:
            node_data = graph.nodes.get(entity_uuid, {})
            entity_infos.append({
                "name": node_data.get("name", "Unknown"),
                "type": node_data.get("entity_type", "ENTITY"),
                "summary": node_data.get("summary", ""),
            })

        # Generate community summary using LLM
        summary = self._generate_community_summary(entity_infos)

        # Generate community name from summary (first sentence or fallback)
        name = self._extract_community_name(summary, community_id)

        return CommunityNode(
            uuid=str(uuid4()),
            name=name,
            summary=summary,
            members=entity_uuids,
            created_at=datetime.now(timezone.utc),
            group_id=group_id,
        )

    def _generate_community_summary(self, entity_infos: List[Dict]) -> str:
        """
        Generate an LLM-powered summary for a community of entities.

        Args:
            entity_infos: List of entity information dictionaries

        Returns:
            Summary text
        """
        # Build context from entity information
        context_lines = [
            f"- {entity['name']} ({entity['type']}): {entity.get('summary', 'No summary available')}"
            for entity in entity_infos
        ]
        context = "\n".join(context_lines)

        # Prompt for LLM
        prompt = f"""You are analyzing a cluster of related entities in a knowledge graph.

Entities in this cluster:
{context}

Generate a concise summary (2-3 sentences) that:
1. Identifies the common theme or topic connecting these entities
2. Describes the relationships between them
3. Provides useful context for understanding this cluster

Summary:"""

        try:
            # Use LLM to generate summary
            from openai import OpenAI
            client = OpenAI(api_key=self.llm_client.api_key)

            response = client.chat.completions.create(
                model=self.llm_client.model,
                messages=[
                    {"role": "system", "content": "You are a knowledge graph analyst."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=200,
            )

            summary = response.choices[0].message.content.strip()
            logger.debug(f"Generated community summary: {summary[:100]}...")
            return summary

        except Exception as e:
            logger.error(f"Error generating community summary: {e}")
            # Fallback to simple description
            entity_names = [e["name"] for e in entity_infos[:5]]
            return f"Community of {len(entity_infos)} entities including {', '.join(entity_names)}."

    def _extract_community_name(self, summary: str, community_id: int) -> str:
        """
        Extract a short name for the community from its summary.

        Args:
            summary: Community summary text
            community_id: Numeric community identifier

        Returns:
            Community name
        """
        # Try to use first sentence as name
        sentences = summary.split(".")
        if sentences:
            first_sentence = sentences[0].strip()
            # Truncate if too long
            if len(first_sentence) > 60:
                first_sentence = first_sentence[:57] + "..."
            return first_sentence

        # Fallback
        return f"Community {community_id}"

    def _create_has_member_edges(
        self,
        community_uuid: str,
        entity_uuids: List[str],
    ) -> None:
        """
        Create HAS_MEMBER edges from community to entities.

        Args:
            community_uuid: UUID of the community
            entity_uuids: List of entity UUIDs in the community
        """
        for entity_uuid in entity_uuids:
            try:
                self.db.create_has_member_edge(
                    community_uuid=community_uuid,
                    entity_uuid=entity_uuid,
                )
            except Exception as e:
                logger.error(
                    f"Error creating HAS_MEMBER edge from {community_uuid} "
                    f"to {entity_uuid}: {e}"
                )

    def update_communities(
        self,
        group_id: str,
        resolution: float = 1.0,
        min_community_size: int = 2,
    ) -> int:
        """
        Update communities by deleting existing ones and re-detecting.

        Should be called periodically as the knowledge graph evolves.

        Args:
            group_id: Group ID to update communities for
            resolution: Resolution parameter for Louvain
            min_community_size: Minimum community size

        Returns:
            Number of communities created

        Example:
            # Re-detect communities after adding many new entities
            num_communities = detector.update_communities("user_123")
        """
        logger.info(f"Updating communities for group: {group_id}")

        # Delete existing communities for this group
        try:
            self.db.delete_communities(group_id)
            logger.info(f"Deleted existing communities for group {group_id}")
        except Exception as e:
            logger.error(f"Error deleting existing communities: {e}")

        # Re-detect communities
        return self.detect_communities(
            group_id=group_id,
            resolution=resolution,
            min_community_size=min_community_size,
        )

    def get_community_context(
        self,
        community_uuid: str,
    ) -> Dict:
        """
        Get comprehensive context for a community.

        Args:
            community_uuid: UUID of the community

        Returns:
            Dictionary with community details and member entities
        """
        # Get community data
        community_data = self.db.get_community_by_uuid(community_uuid)
        if not community_data:
            return {}

        # Get member entities
        member_entities = []
        for entity_uuid in community_data.get("members", []):
            entity_data = self.db.get_entity_by_uuid(entity_uuid)
            if entity_data:
                member_entities.append(entity_data)

        return {
            "community": community_data,
            "members": member_entities,
            "member_count": len(member_entities),
        }
