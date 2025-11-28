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

from ryumem_server.core.models import EntityEdge, EntityNode, EpisodeNode

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

        # Episode index
        self.episode_uuids: List[str] = []
        self.episode_corpus: List[List[str]] = []
        self.episode_bm25: Optional[BM25Okapi] = None

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

    def add_episode(self, episode: EpisodeNode) -> None:
        """
        Add an episode to the BM25 index.

        Indexes both episode content and memories from metadata.

        Args:
            episode: Episode node to index

        Example:
            index.add_episode(EpisodeNode(
                uuid="789",
                content="Python is a programming language",
                ...
            ))
        """
        # Collect text to index: episode content + memories from metadata
        texts_to_index = [episode.content]

        # Extract memories from episode metadata if present
        if episode.metadata:
            import json
            metadata_dict = episode.metadata if isinstance(episode.metadata, dict) else json.loads(episode.metadata)

            # Check if metadata has sessions with query runs
            if 'sessions' in metadata_dict:
                for session_id, runs in metadata_dict['sessions'].items():
                    if isinstance(runs, list):
                        for run in runs:
                            # Add LLM saved memory if present
                            if isinstance(run, dict) and 'llm_saved_memory' in run and run['llm_saved_memory']:
                                texts_to_index.append(run['llm_saved_memory'])

        # Combine all texts and tokenize
        combined_text = " ".join(texts_to_index)
        tokens = tokenize(combined_text)

        self.episode_uuids.append(episode.uuid)
        self.episode_corpus.append(tokens)

        # Rebuild BM25 index
        self._rebuild_episode_index()

        logger.debug(f"Added episode to BM25: {episode.content[:50]}... (with {len(texts_to_index)-1} memories)")

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

    def search_episodes(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> List[Tuple[str, float]]:
        """
        Search episodes using BM25 keyword matching.

        Args:
            query: Search query
            top_k: Maximum number of results
            min_score: Minimum BM25 score threshold

        Returns:
            List of (episode_uuid, score) tuples, sorted by score descending

        Example:
            results = index.search_episodes("programming language", top_k=5)
            for episode_uuid, score in results:
                print(f"{episode_uuid}: {score:.3f}")
        """
        if not self.episode_bm25 or not self.episode_corpus:
            logger.warning("Episode BM25 index is empty")
            return []

        # Tokenize query
        query_tokens = tokenize(query)

        # Get BM25 scores
        scores = self.episode_bm25.get_scores(query_tokens)

        # Create (uuid, score) pairs
        results = [
            (uuid, score)
            for uuid, score in zip(self.episode_uuids, scores)
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

    def _rebuild_episode_index(self) -> None:
        """Rebuild the episode BM25 index."""
        if self.episode_corpus:
            self.episode_bm25 = BM25Okapi(self.episode_corpus)
        else:
            self.episode_bm25 = None

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

        self.episode_uuids = []
        self.episode_corpus = []
        self.episode_bm25 = None

        logger.info("BM25 index cleared")

    def stats(self) -> Dict[str, int]:
        """
        Get index statistics.

        Returns:
            Dictionary with entity_count, edge_count, and episode_count
        """
        return {
            "entity_count": len(self.entity_uuids),
            "edge_count": len(self.edge_uuids),
            "episode_count": len(self.episode_uuids),
        }

    def __repr__(self) -> str:
        """String representation."""
        stats = self.stats()
        return f"BM25Index(entities={stats['entity_count']}, edges={stats['edge_count']}, episodes={stats['episode_count']})"

    def build_from_data(
        self,
        episodes: List[EpisodeNode] = None,
        entities: List[EntityNode] = None,
        edges: List[EntityEdge] = None,
    ) -> None:
        """
        Framework method to build BM25 index from episodes, entities, and edges.

        This is a convenience method that allows you to build the entire index
        from lists of data in one call.

        Args:
            episodes: List of episode nodes to index
            entities: List of entity nodes to index
            edges: List of entity edges to index

        Example:
            index = BM25Index()
            index.build_from_data(
                episodes=[episode1, episode2],
                entities=[entity1, entity2],
                edges=[edge1, edge2]
            )
        """
        logger.info("Building BM25 index from data...")

        # Add episodes
        if episodes:
            for episode in episodes:
                self.add_episode(episode)
            logger.info(f"Added {len(episodes)} episodes to BM25 index")

        # Add entities
        if entities:
            for entity in entities:
                self.add_entity(entity)
            logger.info(f"Added {len(entities)} entities to BM25 index")

        # Add edges
        if edges:
            for edge in edges:
                self.add_edge(edge)
            logger.info(f"Added {len(edges)} edges to BM25 index")

        logger.info(f"BM25 index built: {self}")
