"""
Memory pruning and compaction for Ryumem.

Keeps the knowledge graph compact and efficient by:
- Removing expired/obsolete facts
- Pruning low-value entities
- Merging redundant relationships
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import numpy as np

from ryumem.core.graph_db import RyugraphDB

logger = logging.getLogger(__name__)


class MemoryPruner:
    """
    Prune obsolete memories to keep the graph compact and token-efficient.

    Pruning strategies:
    - Remove facts that were invalidated long ago
    - Delete entities with very few mentions (likely noise)
    - Merge near-duplicate relationship facts
    """

    def __init__(self, db: RyugraphDB):
        """
        Initialize memory pruner.

        Args:
            db: Ryugraph database instance
        """
        self.db = db
        logger.info("Initialized MemoryPruner")

    def prune_expired_edges(
        self,
        group_id: str,
        cutoff_date: datetime,
    ) -> int:
        """
        Delete edges that have been expired/invalidated before cutoff_date.

        These are facts that were contradicted or superseded long ago
        and are no longer contextually relevant.

        Args:
            group_id: Group ID to prune
            cutoff_date: Delete edges expired before this date

        Returns:
            Number of edges deleted

        Example:
            from datetime import datetime, timedelta, timezone

            # Delete facts expired more than 90 days ago
            cutoff = datetime.now(timezone.utc) - timedelta(days=90)
            deleted = pruner.prune_expired_edges("user_123", cutoff)
            print(f"Deleted {deleted} expired edges")
        """
        query = """
        MATCH ()-[e:RELATES_TO]->()
        WHERE e.group_id = $group_id
          AND e.expired_at IS NOT NULL
          AND e.expired_at < $cutoff_date
        DELETE e
        RETURN COUNT(e) AS deleted_count
        """

        result = self.db.execute(query, {
            "group_id": group_id,
            "cutoff_date": cutoff_date,
        })

        deleted_count = result[0]["deleted_count"] if result else 0
        logger.info(f"Deleted {deleted_count} expired edges for group {group_id}")
        return deleted_count

    def prune_low_mention_entities(
        self,
        group_id: str,
        min_mentions: int = 2,
        min_age_days: int = 30,
    ) -> int:
        """
        Delete entities that have very few mentions and are old enough.

        Entities with low mentions are likely:
        - Extraction errors
        - Typos or misidentified names
        - Tangential/irrelevant entities

        Args:
            group_id: Group ID to prune
            min_mentions: Minimum mentions required to keep (default: 2)
            min_age_days: Minimum age in days before pruning (default: 30)

        Returns:
            Number of entities deleted

        Example:
            # Delete entities with < 2 mentions that are > 30 days old
            deleted = pruner.prune_low_mention_entities("user_123")
            print(f"Deleted {deleted} low-value entities")
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=min_age_days)

        query = """
        MATCH (e:Entity)
        WHERE e.group_id = $group_id
          AND e.mentions < $min_mentions
          AND e.created_at < $cutoff_date
        DETACH DELETE e
        RETURN COUNT(e) AS deleted_count
        """

        result = self.db.execute(query, {
            "group_id": group_id,
            "min_mentions": min_mentions,
            "cutoff_date": cutoff_date,
        })

        deleted_count = result[0]["deleted_count"] if result else 0
        logger.info(
            f"Deleted {deleted_count} low-mention entities for group {group_id} "
            f"(min_mentions={min_mentions}, min_age_days={min_age_days})"
        )
        return deleted_count

    def compact_redundant_edges(
        self,
        group_id: str,
        similarity_threshold: float = 0.95,
    ) -> int:
        """
        Find and merge near-duplicate relationship facts.

        Redundant facts occur when:
        - Multiple episodes describe the same relationship differently
        - Entity resolution creates duplicate edges
        - Slight variations in phrasing

        This method uses fact_embedding similarity to detect redundancy.

        Args:
            group_id: Group ID to compact
            similarity_threshold: Minimum cosine similarity to consider duplicate (default: 0.95)

        Returns:
            Number of edges merged

        Example:
            # Merge facts that are > 95% similar
            merged = pruner.compact_redundant_edges("user_123")
            print(f"Merged {merged} redundant edges")
        """
        # Fetch all edges for this group
        edges = self.db.get_all_edges(group_id)

        if not edges:
            logger.info(f"No edges found for group {group_id}")
            return 0

        # Group edges by (source, target) pair
        edge_groups = defaultdict(list)
        for edge in edges:
            key = tuple(sorted([edge["source_uuid"], edge["target_uuid"]]))
            edge_groups[key].append(edge)

        merged_count = 0

        # Check each group for redundancy
        for (source, target), group_edges in edge_groups.items():
            if len(group_edges) < 2:
                continue

            # Find similar pairs within this group
            for i in range(len(group_edges)):
                edge1 = group_edges[i]

                # Skip if already deleted
                if edge1.get("_deleted"):
                    continue

                for j in range(i + 1, len(group_edges)):
                    edge2 = group_edges[j]

                    # Skip if already deleted
                    if edge2.get("_deleted"):
                        continue

                    # Check if both edges have embeddings
                    emb1 = edge1.get("fact_embedding")
                    emb2 = edge2.get("fact_embedding")

                    if not emb1 or not emb2:
                        continue

                    # Compute cosine similarity
                    try:
                        similarity = self._cosine_similarity(emb1, emb2)
                    except Exception as e:
                        logger.warning(f"Error computing similarity: {e}")
                        continue

                    # If highly similar, merge
                    if similarity >= similarity_threshold:
                        self._merge_edges(edge1, edge2)
                        edge2["_deleted"] = True
                        merged_count += 1

                        logger.debug(
                            f"Merged edges {edge1['uuid']} and {edge2['uuid']} "
                            f"(similarity: {similarity:.3f})"
                        )

        logger.info(f"Merged {merged_count} redundant edges for group {group_id}")
        return merged_count

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Compute cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity (0-1)
        """
        v1 = np.array(vec1)
        v2 = np.array(vec2)

        dot_product = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def _merge_edges(self, edge1: Dict, edge2: Dict) -> None:
        """
        Merge edge2 into edge1.

        Args:
            edge1: Edge to keep (will be updated)
            edge2: Edge to delete (will be merged into edge1)
        """
        # Merge mentions
        new_mentions = edge1.get("mentions", 1) + edge2.get("mentions", 1)

        # Merge episode lists
        episodes1 = edge1.get("episodes", [])
        episodes2 = edge2.get("episodes", [])

        if isinstance(episodes1, str):
            import json
            episodes1 = json.loads(episodes1)
        if isinstance(episodes2, str):
            import json
            episodes2 = json.loads(episodes2)

        merged_episodes = list(set(episodes1 + episodes2))

        # Update edge1 in database
        import json

        query = """
        MATCH ()-[e:RELATES_TO]->()
        WHERE e.uuid = $uuid
        SET
            e.mentions = $mentions,
            e.episodes = $episodes
        RETURN e.uuid AS uuid
        """

        self.db.execute(query, {
            "uuid": edge1["uuid"],
            "mentions": new_mentions,
            "episodes": json.dumps(merged_episodes),
        })

        # Delete edge2
        query = """
        MATCH ()-[e:RELATES_TO]->()
        WHERE e.uuid = $uuid
        DELETE e
        """

        self.db.execute(query, {"uuid": edge2["uuid"]})

        logger.debug(f"Merged edge {edge2['uuid']} into {edge1['uuid']}")

    def prune_all(
        self,
        group_id: str,
        expired_cutoff_days: int = 90,
        min_mentions: int = 2,
        min_age_days: int = 30,
        compact_redundant: bool = True,
        similarity_threshold: float = 0.95,
    ) -> Dict[str, int]:
        """
        Run all pruning operations for a group.

        This is a convenience method that executes all pruning strategies.

        Args:
            group_id: Group ID to prune
            expired_cutoff_days: Delete expired edges older than N days
            min_mentions: Minimum mentions for entities
            min_age_days: Minimum age before pruning entities
            compact_redundant: Whether to merge redundant edges
            similarity_threshold: Threshold for edge similarity

        Returns:
            Dictionary with pruning statistics

        Example:
            stats = pruner.prune_all("user_123")
            print(f"Pruning results: {stats}")
            # Output: {'expired_edges_deleted': 15, 'entities_deleted': 3, 'edges_merged': 8}
        """
        logger.info(f"Starting comprehensive pruning for group {group_id}")

        cutoff = datetime.now(timezone.utc) - timedelta(days=expired_cutoff_days)

        stats = {
            "expired_edges_deleted": self.prune_expired_edges(group_id, cutoff),
            "entities_deleted": self.prune_low_mention_entities(
                group_id,
                min_mentions=min_mentions,
                min_age_days=min_age_days,
            ),
            "edges_merged": 0,
        }

        if compact_redundant:
            stats["edges_merged"] = self.compact_redundant_edges(
                group_id,
                similarity_threshold=similarity_threshold,
            )

        logger.info(f"Pruning complete for group {group_id}: {stats}")
        return stats
