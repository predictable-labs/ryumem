"""
Tests for temporal decay scoring in search.
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from ryumem.core.models import EntityNode, EntityEdge, SearchResult, SearchConfig
from ryumem.retrieval.search import SearchEngine


class TestTemporalDecay:
    """Test temporal decay scoring functionality."""

    @pytest.fixture
    def entities_different_ages(self):
        """Create entities with different creation dates."""
        now = datetime.now(timezone.utc)

        return [
            EntityNode(
                uuid="recent_entity",
                name="Recent Entity",
                entity_type="test",
                summary="Created recently",
                mentions=1,
                created_at=now - timedelta(days=1),  # 1 day old
                embedding=[0.1] * 3072,
                group_id="test",
            ),
            EntityNode(
                uuid="old_entity",
                name="Old Entity",
                entity_type="test",
                summary="Created long ago",
                mentions=1,
                created_at=now - timedelta(days=100),  # 100 days old
                embedding=[0.2] * 3072,
                group_id="test",
            ),
            EntityNode(
                uuid="medium_entity",
                name="Medium Entity",
                entity_type="test",
                summary="Created some time ago",
                mentions=1,
                created_at=now - timedelta(days=30),  # 30 days old
                embedding=[0.3] * 3072,
                group_id="test",
            ),
        ]

    @pytest.fixture
    def edges_different_ages(self):
        """Create edges with different valid_at dates."""
        now = datetime.now(timezone.utc)

        return [
            EntityEdge(
                uuid="recent_edge",
                source_uuid="e1",
                target_uuid="e2",
                fact="Recent fact",
                relation_type="TEST",
                valid_at=now - timedelta(days=2),
                created_at=now - timedelta(days=2),
                mentions=1,
                fact_embedding=[0.4] * 3072,
            ),
            EntityEdge(
                uuid="old_edge",
                source_uuid="e3",
                target_uuid="e4",
                fact="Old fact",
                relation_type="TEST",
                valid_at=now - timedelta(days=200),
                created_at=now - timedelta(days=200),
                mentions=1,
                fact_embedding=[0.5] * 3072,
            ),
        ]

    @pytest.fixture
    def search_engine(self):
        """Create a mock search engine for testing."""
        from unittest.mock import Mock

        mock_db = Mock()
        mock_embedding_client = Mock()
        mock_bm25_index = Mock()

        engine = SearchEngine(mock_db, mock_embedding_client, mock_bm25_index)
        return engine

    def test_apply_temporal_decay_entities(self, search_engine, entities_different_ages):
        """Test temporal decay on entity search results."""
        # Create search result with equal base scores
        result = SearchResult(
            entities=entities_different_ages,
            edges=[],
            scores={
                "recent_entity": 1.0,
                "medium_entity": 1.0,
                "old_entity": 1.0,
            }
        )

        # Apply temporal decay
        decayed_result = search_engine._apply_temporal_decay(
            result,
            decay_factor=0.95,  # 5% decay per day
        )

        # Recent entity should have highest score
        recent_score = decayed_result.scores["recent_entity"]
        medium_score = decayed_result.scores["medium_entity"]
        old_score = decayed_result.scores["old_entity"]

        assert recent_score > medium_score > old_score
        assert recent_score >= 0.95  # Should be close to original (only 1 day old)
        assert old_score < 0.1  # Should be much lower (100 days old with 5% daily decay)

    def test_apply_temporal_decay_edges(self, search_engine, edges_different_ages):
        """Test temporal decay on edge search results."""
        result = SearchResult(
            entities=[],
            edges=edges_different_ages,
            scores={
                "recent_edge": 1.0,
                "old_edge": 1.0,
            }
        )

        decayed_result = search_engine._apply_temporal_decay(
            result,
            decay_factor=0.99,  # 1% decay per day
        )

        recent_score = decayed_result.scores["recent_edge"]
        old_score = decayed_result.scores["old_edge"]

        assert recent_score > old_score
        # With 1% decay over 2 days: 0.99^2 ≈ 0.98
        assert recent_score >= 0.98
        # With 1% decay over 200 days: 0.99^200 ≈ 0.134
        assert old_score < 0.2

    def test_temporal_decay_no_decay(self, search_engine, entities_different_ages):
        """Test with decay_factor=1.0 (no decay)."""
        result = SearchResult(
            entities=entities_different_ages,
            edges=[],
            scores={
                "recent_entity": 1.0,
                "medium_entity": 1.0,
                "old_entity": 1.0,
            }
        )

        decayed_result = search_engine._apply_temporal_decay(
            result,
            decay_factor=1.0,  # No decay
        )

        # All scores should remain 1.0
        assert decayed_result.scores["recent_entity"] == 1.0
        assert decayed_result.scores["medium_entity"] == 1.0
        assert decayed_result.scores["old_entity"] == 1.0

    def test_temporal_decay_custom_reference_time(self, search_engine, entities_different_ages):
        """Test temporal decay with custom reference time."""
        now = datetime.now(timezone.utc)
        past_reference = now - timedelta(days=50)  # Reference point 50 days ago

        result = SearchResult(
            entities=entities_different_ages,
            edges=[],
            scores={"recent_entity": 1.0, "medium_entity": 1.0, "old_entity": 1.0}
        )

        decayed_result = search_engine._apply_temporal_decay(
            result,
            decay_factor=0.95,
            reference_time=past_reference,
        )

        # With reference time 50 days ago:
        # - recent_entity (1 day old) would have been created 49 days AFTER reference (future!)
        # - This should still work (might result in days_old = 0 or negative handled properly)

        # At minimum, this shouldn't crash
        assert "recent_entity" in decayed_result.scores

    def test_temporal_decay_reorders_results(self, search_engine):
        """Test that temporal decay reorders results correctly."""
        now = datetime.now(timezone.utc)

        # Create entities where the old one has higher base score
        entities = [
            EntityNode(
                uuid="high_score_old",
                name="Old but relevant",
                entity_type="test",
                summary="High relevance but old",
                mentions=1,
                created_at=now - timedelta(days=100),
                embedding=[0.1] * 3072,
                group_id="test",
            ),
            EntityNode(
                uuid="low_score_recent",
                name="Recent but less relevant",
                entity_type="test",
                summary="Lower relevance but recent",
                mentions=1,
                created_at=now - timedelta(days=1),
                embedding=[0.2] * 3072,
                group_id="test",
            ),
        ]

        result = SearchResult(
            entities=entities,
            edges=[],
            scores={
                "high_score_old": 0.9,  # High base score
                "low_score_recent": 0.6,  # Lower base score
            }
        )

        decayed_result = search_engine._apply_temporal_decay(
            result,
            decay_factor=0.95,
        )

        # After decay, recent entity might score higher
        # 0.95^1 * 0.6 = 0.57 vs 0.95^100 * 0.9 ≈ 0.005
        # So recent should win

        # Check that entities are reordered
        assert decayed_result.entities[0].uuid == "low_score_recent"
        assert decayed_result.entities[1].uuid == "high_score_old"

    def test_search_config_temporal_decay_settings(self):
        """Test SearchConfig with temporal decay parameters."""
        config = SearchConfig(
            query="test",
            group_id="test",
            apply_temporal_decay=True,
            temporal_decay_factor=0.98,
        )

        assert config.apply_temporal_decay is True
        assert config.temporal_decay_factor == 0.98

    def test_search_config_default_temporal_decay(self):
        """Test SearchConfig default temporal decay settings."""
        config = SearchConfig(
            query="test",
            group_id="test",
        )

        # Check defaults
        assert config.apply_temporal_decay is True  # Should be enabled by default
        assert config.temporal_decay_factor == 0.95  # Default 5% decay per day

    def test_search_config_disable_temporal_decay(self):
        """Test disabling temporal decay in SearchConfig."""
        config = SearchConfig(
            query="test",
            group_id="test",
            apply_temporal_decay=False,
        )

        assert config.apply_temporal_decay is False

    def test_temporal_decay_extreme_ages(self, search_engine):
        """Test temporal decay with extreme entity ages."""
        now = datetime.now(timezone.utc)

        entities = [
            EntityNode(
                uuid="just_created",
                name="Just created",
                entity_type="test",
                summary="Brand new",
                mentions=1,
                created_at=now,  # 0 days old
                embedding=[0.1] * 3072,
                group_id="test",
            ),
            EntityNode(
                uuid="very_old",
                name="Very old",
                entity_type="test",
                summary="Ancient",
                mentions=1,
                created_at=now - timedelta(days=365),  # 1 year old
                embedding=[0.2] * 3072,
                group_id="test",
            ),
        ]

        result = SearchResult(
            entities=entities,
            edges=[],
            scores={"just_created": 1.0, "very_old": 1.0}
        )

        decayed_result = search_engine._apply_temporal_decay(
            result,
            decay_factor=0.99,
        )

        just_created_score = decayed_result.scores["just_created"]
        very_old_score = decayed_result.scores["very_old"]

        # 0 days old should have full score
        assert just_created_score == 1.0

        # 365 days old with 1% daily decay: 0.99^365 ≈ 0.026
        assert very_old_score < 0.05

    def test_temporal_decay_preserves_relative_order_when_similar_age(self, search_engine):
        """Test that entities of similar age preserve base score ordering."""
        now = datetime.now(timezone.utc)

        entities = [
            EntityNode(
                uuid="high_score",
                name="High score",
                entity_type="test",
                summary="More relevant",
                mentions=1,
                created_at=now - timedelta(days=10),
                embedding=[0.1] * 3072,
                group_id="test",
            ),
            EntityNode(
                uuid="low_score",
                name="Low score",
                entity_type="test",
                summary="Less relevant",
                mentions=1,
                created_at=now - timedelta(days=11),  # Only 1 day older
                embedding=[0.2] * 3072,
                group_id="test",
            ),
        ]

        result = SearchResult(
            entities=entities,
            edges=[],
            scores={
                "high_score": 0.8,
                "low_score": 0.4,
            }
        )

        decayed_result = search_engine._apply_temporal_decay(
            result,
            decay_factor=0.99,
        )

        # Both are ~10 days old, so decay is similar
        # Base score difference should be preserved
        assert decayed_result.scores["high_score"] > decayed_result.scores["low_score"]
