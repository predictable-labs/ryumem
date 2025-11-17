"""
Tests for memory pruning and compaction.
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta, timezone

from ryumem.maintenance.pruner import MemoryPruner


class TestMemoryPruner:
    """Test memory pruning and compaction functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database."""
        db = Mock()
        db.execute = Mock()
        return db

    @pytest.fixture
    def pruner(self, mock_db):
        """Create a memory pruner instance."""
        return MemoryPruner(mock_db)

    def test_initialization(self, pruner, mock_db):
        """Test pruner initialization."""
        assert pruner.db == mock_db

    def test_prune_expired_edges(self, pruner, mock_db):
        """Test pruning expired edges."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        mock_db.execute.return_value = [{"deleted_count": 5}]

        deleted = pruner.prune_expired_edges("test_group", cutoff)

        assert deleted == 5
        mock_db.execute.assert_called_once()

        # Check the query was called with correct parameters
        call_args = mock_db.execute.call_args
        assert call_args[0][1]["user_id"] == "test_group"
        assert call_args[0][1]["cutoff_date"] == cutoff

    def test_prune_expired_edges_none_found(self, pruner, mock_db):
        """Test pruning when no expired edges exist."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        mock_db.execute.return_value = [{"deleted_count": 0}]

        deleted = pruner.prune_expired_edges("test_group", cutoff)

        assert deleted == 0

    def test_prune_low_mention_entities(self, pruner, mock_db):
        """Test pruning entities with low mentions."""
        mock_db.execute.return_value = [{"deleted_count": 3}]

        deleted = pruner.prune_low_mention_entities(
            "test_group",
            min_mentions=2,
            min_age_days=30
        )

        assert deleted == 3
        mock_db.execute.assert_called_once()

        # Verify query parameters
        call_args = mock_db.execute.call_args
        assert call_args[0][1]["user_id"] == "test_group"
        assert call_args[0][1]["min_mentions"] == 2

    def test_prune_low_mention_entities_custom_params(self, pruner, mock_db):
        """Test pruning with custom parameters."""
        mock_db.execute.return_value = [{"deleted_count": 1}]

        deleted = pruner.prune_low_mention_entities(
            "test_group",
            min_mentions=5,
            min_age_days=60
        )

        assert deleted == 1

        # Check that cutoff date is calculated correctly
        call_args = mock_db.execute.call_args
        cutoff_date = call_args[0][1]["cutoff_date"]
        expected_cutoff = datetime.now(timezone.utc) - timedelta(days=60)

        # Allow 1 second tolerance for test execution time
        assert abs((cutoff_date - expected_cutoff).total_seconds()) < 1

    def test_cosine_similarity(self, pruner):
        """Test cosine similarity calculation."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]

        similarity = pruner._cosine_similarity(vec1, vec2)
        assert abs(similarity - 1.0) < 0.001  # Should be 1.0 (identical)

        vec3 = [1.0, 0.0, 0.0]
        vec4 = [0.0, 1.0, 0.0]

        similarity = pruner._cosine_similarity(vec3, vec4)
        assert abs(similarity - 0.0) < 0.001  # Should be 0.0 (orthogonal)

        vec5 = [1.0, 1.0, 0.0]
        vec6 = [1.0, 1.0, 0.0]

        similarity = pruner._cosine_similarity(vec5, vec6)
        assert abs(similarity - 1.0) < 0.001

    def test_cosine_similarity_zero_vectors(self, pruner):
        """Test cosine similarity with zero vectors."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 1.0, 1.0]

        similarity = pruner._cosine_similarity(vec1, vec2)
        assert similarity == 0.0  # Undefined, returns 0

    def test_compact_redundant_edges_no_edges(self, pruner, mock_db):
        """Test compaction when no edges exist."""
        mock_db.get_all_edges.return_value = []

        merged = pruner.compact_redundant_edges("test_group")

        assert merged == 0

    def test_compact_redundant_edges_no_duplicates(self, pruner, mock_db):
        """Test compaction when edges are not similar enough."""
        edges = [
            {
                "uuid": "edge1",
                "source_uuid": "a",
                "target_uuid": "b",
                "fact_embedding": [1.0, 0.0, 0.0],
            },
            {
                "uuid": "edge2",
                "source_uuid": "a",
                "target_uuid": "b",
                "fact_embedding": [0.0, 1.0, 0.0],  # Orthogonal - not similar
            },
        ]
        mock_db.get_all_edges.return_value = edges

        merged = pruner.compact_redundant_edges("test_group", similarity_threshold=0.95)

        assert merged == 0  # No merging should occur

    def test_compact_redundant_edges_merges_similar(self, pruner, mock_db):
        """Test that highly similar edges are merged."""
        edges = [
            {
                "uuid": "edge1",
                "source_uuid": "a",
                "target_uuid": "b",
                "fact_embedding": [1.0, 0.0, 0.0],
                "mentions": 2,
                "episodes": '["ep1"]',
            },
            {
                "uuid": "edge2",
                "source_uuid": "a",
                "target_uuid": "b",
                "fact_embedding": [0.99, 0.01, 0.0],  # Very similar
                "mentions": 1,
                "episodes": '["ep2"]',
            },
        ]
        mock_db.get_all_edges.return_value = edges
        mock_db.execute.return_value = None

        merged = pruner.compact_redundant_edges("test_group", similarity_threshold=0.9)

        assert merged == 1
        # Should call execute twice: once to update edge1, once to delete edge2
        assert mock_db.execute.call_count == 2

    def test_merge_edges(self, pruner, mock_db):
        """Test merging two edges."""
        edge1 = {
            "uuid": "edge1",
            "mentions": 2,
            "episodes": '["ep1", "ep2"]',
        }
        edge2 = {
            "uuid": "edge2",
            "mentions": 3,
            "episodes": '["ep3", "ep4"]',
        }

        mock_db.execute.return_value = None

        pruner._merge_edges(edge1, edge2)

        # Should have called execute twice
        assert mock_db.execute.call_count == 2

        # First call should update edge1
        first_call = mock_db.execute.call_args_list[0]
        assert first_call[0][1]["uuid"] == "edge1"
        assert first_call[0][1]["mentions"] == 5  # 2 + 3

        # Second call should delete edge2
        second_call = mock_db.execute.call_args_list[1]
        assert second_call[0][1]["uuid"] == "edge2"

    def test_prune_all_comprehensive(self, pruner, mock_db):
        """Test running all pruning operations together."""
        mock_db.execute.return_value = [{"deleted_count": 10}]
        mock_db.get_all_edges.return_value = []

        stats = pruner.prune_all(
            "test_group",
            expired_cutoff_days=90,
            min_mentions=2,
            min_age_days=30,
            compact_redundant=True,
            similarity_threshold=0.95,
        )

        assert "expired_edges_deleted" in stats
        assert "entities_deleted" in stats
        assert "edges_merged" in stats

        # All operations should have been called
        assert mock_db.execute.call_count >= 2  # At least expired edges and entity pruning

    def test_prune_all_without_compaction(self, pruner, mock_db):
        """Test prune_all with compaction disabled."""
        mock_db.execute.return_value = [{"deleted_count": 5}]
        mock_db.get_all_edges.return_value = []

        stats = pruner.prune_all(
            "test_group",
            compact_redundant=False
        )

        assert stats["edges_merged"] == 0
        # get_all_edges should not be called when compaction is disabled
        mock_db.get_all_edges.assert_not_called()

    def test_compact_edges_different_pairs(self, pruner, mock_db):
        """Test that only edges with same (source, target) are compared."""
        edges = [
            {
                "uuid": "edge1",
                "source_uuid": "a",
                "target_uuid": "b",
                "fact_embedding": [1.0, 0.0, 0.0],
            },
            {
                "uuid": "edge2",
                "source_uuid": "c",
                "target_uuid": "d",  # Different pair
                "fact_embedding": [1.0, 0.0, 0.0],  # Identical embedding
            },
        ]
        mock_db.get_all_edges.return_value = edges

        merged = pruner.compact_redundant_edges("test_group")

        # Should not merge because they connect different entities
        assert merged == 0

    def test_compact_edges_missing_embeddings(self, pruner, mock_db):
        """Test that edges without embeddings are skipped."""
        edges = [
            {
                "uuid": "edge1",
                "source_uuid": "a",
                "target_uuid": "b",
                "fact_embedding": None,  # Missing
            },
            {
                "uuid": "edge2",
                "source_uuid": "a",
                "target_uuid": "b",
                "fact_embedding": [1.0, 0.0, 0.0],
            },
        ]
        mock_db.get_all_edges.return_value = edges

        merged = pruner.compact_redundant_edges("test_group")

        # Should not merge because edge1 has no embedding
        assert merged == 0

    def test_compact_edges_handles_list_episodes(self, pruner, mock_db):
        """Test merging edges when episodes is already a list (not JSON string)."""
        edges = [
            {
                "uuid": "edge1",
                "source_uuid": "a",
                "target_uuid": "b",
                "fact_embedding": [1.0, 0.0, 0.0],
                "mentions": 1,
                "episodes": ["ep1"],  # Already a list
            },
            {
                "uuid": "edge2",
                "source_uuid": "a",
                "target_uuid": "b",
                "fact_embedding": [0.99, 0.01, 0.0],
                "mentions": 1,
                "episodes": ["ep2"],  # Already a list
            },
        ]
        mock_db.get_all_edges.return_value = edges
        mock_db.execute.return_value = None

        merged = pruner.compact_redundant_edges("test_group", similarity_threshold=0.9)

        assert merged == 1

    def test_prune_all_returns_statistics(self, pruner, mock_db):
        """Test that prune_all returns detailed statistics."""
        mock_db.execute.return_value = [{"deleted_count": 7}]
        mock_db.get_all_edges.return_value = []

        stats = pruner.prune_all("test_group")

        assert isinstance(stats, dict)
        assert all(key in stats for key in ["expired_edges_deleted", "entities_deleted", "edges_merged"])
        assert all(isinstance(val, int) for val in stats.values())
