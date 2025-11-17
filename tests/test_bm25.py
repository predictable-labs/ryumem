"""
Tests for BM25 keyword search index.
"""

import pytest
from ryumem.core.models import EntityNode, EntityEdge
from ryumem.retrieval.bm25 import BM25Index
from datetime import datetime, timezone
from uuid import uuid4


class TestBM25Index:
    """Test BM25 keyword search functionality."""

    @pytest.fixture
    def bm25_index(self):
        """Create a fresh BM25 index for testing."""
        return BM25Index()

    @pytest.fixture
    def sample_entities(self):
        """Create sample entities for testing."""
        return [
            EntityNode(
                uuid=str(uuid4()),
                name="Alice",
                entity_type="person",
                summary="Software engineer at Google specializing in machine learning",
                mentions=5,
                created_at=datetime.now(timezone.utc),
                embedding=[0.1] * 3072,
                group_id="test_group",
            ),
            EntityNode(
                uuid=str(uuid4()),
                name="Bob",
                entity_type="person",
                summary="Data scientist working on natural language processing",
                mentions=3,
                created_at=datetime.now(timezone.utc),
                embedding=[0.2] * 3072,
                group_id="test_group",
            ),
            EntityNode(
                uuid=str(uuid4()),
                name="Google",
                entity_type="organization",
                summary="Technology company based in Mountain View California",
                mentions=10,
                created_at=datetime.now(timezone.utc),
                embedding=[0.3] * 3072,
                group_id="test_group",
            ),
        ]

    @pytest.fixture
    def sample_edges(self):
        """Create sample edges for testing."""
        return [
            EntityEdge(
                uuid=str(uuid4()),
                source_uuid="alice_uuid",
                target_uuid="google_uuid",
                fact="Alice works at Google as a software engineer",
                relation_type="WORKS_AT",
                valid_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                mentions=3,
                fact_embedding=[0.4] * 3072,
            ),
            EntityEdge(
                uuid=str(uuid4()),
                source_uuid="bob_uuid",
                target_uuid="google_uuid",
                fact="Bob previously worked at Google before joining Meta",
                relation_type="WORKED_AT",
                valid_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                mentions=2,
                fact_embedding=[0.5] * 3072,
            ),
        ]

    def test_initialization(self, bm25_index):
        """Test BM25 index initialization."""
        assert bm25_index.entity_uuids == []
        assert bm25_index.entity_corpus == []
        assert bm25_index.edge_uuids == []
        assert bm25_index.edge_corpus == []
        assert bm25_index.entity_bm25 is None
        assert bm25_index.edge_bm25 is None

    def test_add_entity(self, bm25_index, sample_entities):
        """Test adding entities to BM25 index."""
        entity = sample_entities[0]
        bm25_index.add_entity(entity)

        assert len(bm25_index.entity_uuids) == 1
        assert entity.uuid in bm25_index.entity_uuids
        assert len(bm25_index.entity_corpus) == 1
        assert bm25_index.entity_bm25 is not None

    def test_add_edge(self, bm25_index, sample_edges):
        """Test adding edges to BM25 index."""
        edge = sample_edges[0]
        bm25_index.add_edge(edge)

        assert len(bm25_index.edge_uuids) == 1
        assert edge.uuid in bm25_index.edge_uuids
        assert len(bm25_index.edge_corpus) == 1
        assert bm25_index.edge_bm25 is not None

    def test_search_entities_keyword_match(self, bm25_index, sample_entities):
        """Test entity search with keyword matching."""
        # Add all entities
        for entity in sample_entities:
            bm25_index.add_entity(entity)

        # Search for "machine learning"
        results = bm25_index.search_entities("machine learning", top_k=5)

        assert len(results) > 0
        # Alice should rank high because her summary contains "machine learning"
        top_uuid = results[0][0]
        assert top_uuid == sample_entities[0].uuid

    def test_search_entities_no_results(self, bm25_index, sample_entities):
        """Test entity search with no matching keywords."""
        for entity in sample_entities:
            bm25_index.add_entity(entity)

        # Search for something not in the corpus
        results = bm25_index.search_entities("quantum physics", top_k=5)

        # Should return results but with low scores
        # or potentially empty if min_score is set
        assert isinstance(results, list)

    def test_search_edges_keyword_match(self, bm25_index, sample_edges):
        """Test edge search with keyword matching."""
        for edge in sample_edges:
            bm25_index.add_edge(edge)

        # Search for "software engineer"
        results = bm25_index.search_edges("software engineer", top_k=5)

        assert len(results) > 0
        # First edge should rank higher
        top_uuid = results[0][0]
        assert top_uuid == sample_edges[0].uuid

    def test_search_empty_index(self, bm25_index):
        """Test searching an empty index."""
        results = bm25_index.search_entities("test query", top_k=5)
        assert results == []

        results = bm25_index.search_edges("test query", top_k=5)
        assert results == []

    def test_remove_entity(self, bm25_index, sample_entities):
        """Test removing an entity from the index."""
        entity = sample_entities[0]
        bm25_index.add_entity(entity)

        assert len(bm25_index.entity_uuids) == 1

        # Remove the entity
        success = bm25_index.remove_entity(entity.uuid)
        assert success is True
        assert len(bm25_index.entity_uuids) == 0

    def test_remove_nonexistent_entity(self, bm25_index):
        """Test removing an entity that doesn't exist."""
        success = bm25_index.remove_entity("nonexistent_uuid")
        assert success is False

    def test_remove_edge(self, bm25_index, sample_edges):
        """Test removing an edge from the index."""
        edge = sample_edges[0]
        bm25_index.add_edge(edge)

        assert len(bm25_index.edge_uuids) == 1

        # Remove the edge
        success = bm25_index.remove_edge(edge.uuid)
        assert success is True
        assert len(bm25_index.edge_uuids) == 0

    def test_clear(self, bm25_index, sample_entities, sample_edges):
        """Test clearing the entire index."""
        for entity in sample_entities:
            bm25_index.add_entity(entity)
        for edge in sample_edges:
            bm25_index.add_edge(edge)

        assert len(bm25_index.entity_uuids) > 0
        assert len(bm25_index.edge_uuids) > 0

        bm25_index.clear()

        assert len(bm25_index.entity_uuids) == 0
        assert len(bm25_index.edge_uuids) == 0
        assert bm25_index.entity_bm25 is None
        assert bm25_index.edge_bm25 is None

    def test_stats(self, bm25_index, sample_entities, sample_edges):
        """Test getting index statistics."""
        stats = bm25_index.stats()
        assert stats["entity_count"] == 0
        assert stats["edge_count"] == 0

        for entity in sample_entities:
            bm25_index.add_entity(entity)
        for edge in sample_edges:
            bm25_index.add_edge(edge)

        stats = bm25_index.stats()
        assert stats["entity_count"] == len(sample_entities)
        assert stats["edge_count"] == len(sample_edges)

    def test_save_and_load(self, bm25_index, sample_entities, tmp_path):
        """Test saving and loading the BM25 index."""
        # Add entities
        for entity in sample_entities:
            bm25_index.add_entity(entity)

        # Save the index
        save_path = tmp_path / "test_bm25.pkl"
        bm25_index.save(str(save_path))

        assert save_path.exists()

        # Create a new index and load
        new_index = BM25Index()
        success = new_index.load(str(save_path))

        assert success is True
        assert len(new_index.entity_uuids) == len(sample_entities)
        assert new_index.stats() == bm25_index.stats()

    def test_load_nonexistent_file(self, bm25_index):
        """Test loading from a file that doesn't exist."""
        success = bm25_index.load("/nonexistent/path/file.pkl")
        assert success is False

    def test_top_k_limit(self, bm25_index, sample_entities):
        """Test that top_k parameter limits results."""
        for entity in sample_entities:
            bm25_index.add_entity(entity)

        # Search with top_k=1
        results = bm25_index.search_entities("engineer scientist", top_k=1)
        assert len(results) <= 1

        # Search with top_k=2
        results = bm25_index.search_entities("engineer scientist", top_k=2)
        assert len(results) <= 2

    def test_min_score_threshold(self, bm25_index, sample_entities):
        """Test minimum score threshold filtering."""
        for entity in sample_entities:
            bm25_index.add_entity(entity)

        # Search with no min_score
        results_no_filter = bm25_index.search_entities("test", top_k=10, min_score=0.0)

        # Search with high min_score (should filter out low matches)
        results_filtered = bm25_index.search_entities("test", top_k=10, min_score=5.0)

        # Filtered results should have fewer or equal items
        assert len(results_filtered) <= len(results_no_filter)

    def test_repr(self, bm25_index, sample_entities):
        """Test string representation."""
        repr_str = repr(bm25_index)
        assert "BM25Index" in repr_str
        assert "entities=0" in repr_str

        for entity in sample_entities:
            bm25_index.add_entity(entity)

        repr_str = repr(bm25_index)
        assert f"entities={len(sample_entities)}" in repr_str
