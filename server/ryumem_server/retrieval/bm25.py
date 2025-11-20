"""
BM25 keyword search index for Ryumem.

Provides keyword-based search complementing vector search.
Uses rank_bm25 for efficient BM25 scoring.
"""

import logging
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rank_bm25 import BM25Okapi

from ryumem_server.core.models import EntityEdge, EntityNode

logger = logging.getLogger(__name__)


def tokenize(text: str) -> List[str]:
    """
    Simple tokenization for BM25.

    Converts to lowercase and splits on whitespace.
    Could be enhanced with proper NLP tokenization.

    Args:
        text: Text to tokenize

    Returns:
        List of tokens
    """
    return text.lower().split()


class BM25Index:
    """
    BM25 keyword search index for entities and relationship facts.

    Maintains separate BM25 indices for:
    - Entity documents (name + summary)
    - Edge documents (fact descriptions)

    Features:
    - Efficient keyword matching
    - Complement to vector similarity search
    - Persistent storage (pickle)
    """

    def __init__(self):
        """Initialize empty BM25 indices."""
        # Entity index
        self.entity_uuids: List[str] = []
        self.entity_corpus: List[List[str]] = []
        self.entity_bm25: Optional[BM25Okapi] = None

        # Edge index
        self.edge_uuids: List[str] = []
        self.edge_corpus: List[List[str]] = []
        self.edge_bm25: Optional[BM25Okapi] = None

        logger.info("BM25Index initialized")

    def add_entity(self, entity: EntityNode) -> None:
        """
        Add an entity to the BM25 index.

        Args:
            entity: Entity node to index

        Example:
            index.add_entity(EntityNode(
                uuid="123",
                name="Alice",
                entity_type="person",
                summary="Software engineer at Google",
            ))
        """
        # Create document from entity name + summary
        doc_text = f"{entity.name} {entity.summary}"
        tokens = tokenize(doc_text)

        self.entity_uuids.append(entity.uuid)
        self.entity_corpus.append(tokens)

        # Rebuild BM25 index
        self._rebuild_entity_index()

        logger.debug(f"Added entity to BM25: {entity.name}")

    def add_edge(self, edge: EntityEdge) -> None:
        """
        Add a relationship edge to the BM25 index.

        Args:
            edge: Entity edge to index

        Example:
            index.add_edge(EntityEdge(
                uuid="456",
                fact="Alice works at Google",
                ...
            ))
        """
        # Use the fact description as the document
        tokens = tokenize(edge.fact)

        self.edge_uuids.append(edge.uuid)
        self.edge_corpus.append(tokens)

        # Rebuild BM25 index
        self._rebuild_edge_index()

        logger.debug(f"Added edge to BM25: {edge.fact[:50]}...")

    def search_entities(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> List[Tuple[str, float]]:
        """
        Search entities using BM25 keyword matching.

        Args:
            query: Search query
            top_k: Maximum number of results
            min_score: Minimum BM25 score threshold

        Returns:
            List of (entity_uuid, score) tuples, sorted by score descending

        Example:
            results = index.search_entities("software engineer", top_k=5)
            for entity_uuid, score in results:
                print(f"{entity_uuid}: {score:.3f}")
        """
        if not self.entity_bm25 or not self.entity_corpus:
            logger.warning("Entity BM25 index is empty")
            return []

        # Tokenize query
        query_tokens = tokenize(query)

        # Get BM25 scores
        scores = self.entity_bm25.get_scores(query_tokens)

        # Create (uuid, score) pairs
        results = [
            (uuid, score)
            for uuid, score in zip(self.entity_uuids, scores)
            if score >= min_score
        ]

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)

        # Return top_k
        return results[:top_k]

    def search_edges(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> List[Tuple[str, float]]:
        """
        Search relationship edges using BM25 keyword matching.

        Args:
            query: Search query
            top_k: Maximum number of results
            min_score: Minimum BM25 score threshold

        Returns:
            List of (edge_uuid, score) tuples, sorted by score descending

        Example:
            results = index.search_edges("works at Google", top_k=5)
            for edge_uuid, score in results:
                print(f"{edge_uuid}: {score:.3f}")
        """
        if not self.edge_bm25 or not self.edge_corpus:
            logger.warning("Edge BM25 index is empty")
            return []

        # Tokenize query
        query_tokens = tokenize(query)

        # Get BM25 scores
        scores = self.edge_bm25.get_scores(query_tokens)

        # Create (uuid, score) pairs
        results = [
            (uuid, score)
            for uuid, score in zip(self.edge_uuids, scores)
            if score >= min_score
        ]

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)

        # Return top_k
        return results[:top_k]

    def remove_entity(self, entity_uuid: str) -> bool:
        """
        Remove an entity from the BM25 index.

        Args:
            entity_uuid: UUID of entity to remove

        Returns:
            True if entity was found and removed, False otherwise
        """
        try:
            idx = self.entity_uuids.index(entity_uuid)
            del self.entity_uuids[idx]
            del self.entity_corpus[idx]
            self._rebuild_entity_index()
            logger.debug(f"Removed entity from BM25: {entity_uuid}")
            return True
        except ValueError:
            logger.warning(f"Entity not found in BM25: {entity_uuid}")
            return False

    def remove_edge(self, edge_uuid: str) -> bool:
        """
        Remove an edge from the BM25 index.

        Args:
            edge_uuid: UUID of edge to remove

        Returns:
            True if edge was found and removed, False otherwise
        """
        try:
            idx = self.edge_uuids.index(edge_uuid)
            del self.edge_uuids[idx]
            del self.edge_corpus[idx]
            self._rebuild_edge_index()
            logger.debug(f"Removed edge from BM25: {edge_uuid}")
            return True
        except ValueError:
            logger.warning(f"Edge not found in BM25: {edge_uuid}")
            return False

    def _rebuild_entity_index(self) -> None:
        """Rebuild the entity BM25 index."""
        if self.entity_corpus:
            self.entity_bm25 = BM25Okapi(self.entity_corpus)
        else:
            self.entity_bm25 = None

    def _rebuild_edge_index(self) -> None:
        """Rebuild the edge BM25 index."""
        if self.edge_corpus:
            self.edge_bm25 = BM25Okapi(self.edge_corpus)
        else:
            self.edge_bm25 = None

    def save(self, path: str) -> None:
        """
        Save the BM25 index to disk.

        Args:
            path: File path to save to

        Example:
            index.save("./data/bm25_index.pkl")
        """
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "entity_uuids": self.entity_uuids,
            "entity_corpus": self.entity_corpus,
            "edge_uuids": self.edge_uuids,
            "edge_corpus": self.edge_corpus,
        }

        with open(path, "wb") as f:
            pickle.dump(data, f)

        logger.info(f"BM25 index saved to {path}")

    def load(self, path: str) -> bool:
        """
        Load the BM25 index from disk.

        Args:
            path: File path to load from

        Returns:
            True if loaded successfully, False otherwise

        Example:
            if index.load("./data/bm25_index.pkl"):
                print("Index loaded successfully")
        """
        path_obj = Path(path)
        if not path_obj.exists():
            logger.warning(f"BM25 index file not found: {path}")
            return False

        try:
            with open(path, "rb") as f:
                data = pickle.load(f)

            self.entity_uuids = data["entity_uuids"]
            self.entity_corpus = data["entity_corpus"]
            self.edge_uuids = data["edge_uuids"]
            self.edge_corpus = data["edge_corpus"]

            # Rebuild BM25 indices
            self._rebuild_entity_index()
            self._rebuild_edge_index()

            logger.info(
                f"BM25 index loaded from {path} "
                f"({len(self.entity_uuids)} entities, {len(self.edge_uuids)} edges)"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to load BM25 index: {e}")
            return False

    def clear(self) -> None:
        """Clear all data from the BM25 index."""
        self.entity_uuids = []
        self.entity_corpus = []
        self.entity_bm25 = None

        self.edge_uuids = []
        self.edge_corpus = []
        self.edge_bm25 = None

        logger.info("BM25 index cleared")

    def stats(self) -> Dict[str, int]:
        """
        Get index statistics.

        Returns:
            Dictionary with entity_count and edge_count
        """
        return {
            "entity_count": len(self.entity_uuids),
            "edge_count": len(self.edge_uuids),
        }

    def __repr__(self) -> str:
        """String representation."""
        stats = self.stats()
        return f"BM25Index(entities={stats['entity_count']}, edges={stats['edge_count']})"
