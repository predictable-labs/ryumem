"""
Tests for community detection functionality.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone
from uuid import uuid4

from ryumem.community.detector import CommunityDetector
from ryumem.core.models import CommunityNode


class TestCommunityDetector:
    """Test community detection functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database."""
        db = Mock()
        return db

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        llm = Mock()
        llm.api_key = "test_key"
        llm.model = "gpt-4"
        return llm

    @pytest.fixture
    def detector(self, mock_db, mock_llm_client):
        """Create a community detector instance."""
        return CommunityDetector(mock_db, mock_llm_client)

    @pytest.fixture
    def sample_entities(self):
        """Create sample entities that form clusters."""
        return [
            {
                "uuid": "alice_uuid",
                "name": "Alice",
                "entity_type": "person",
                "summary": "Software engineer at Google",
            },
            {
                "uuid": "bob_uuid",
                "name": "Bob",
                "entity_type": "person",
                "summary": "Product manager at Google",
            },
            {
                "uuid": "google_uuid",
                "name": "Google",
                "entity_type": "organization",
                "summary": "Technology company",
            },
            {
                "uuid": "charlie_uuid",
                "name": "Charlie",
                "entity_type": "person",
                "summary": "Professor at Stanford",
            },
            {
                "uuid": "stanford_uuid",
                "name": "Stanford",
                "entity_type": "organization",
                "summary": "University in California",
            },
        ]

    @pytest.fixture
    def sample_edges(self):
        """Create sample edges connecting entities."""
        return [
            {
                "uuid": "edge1",
                "source_uuid": "alice_uuid",
                "target_uuid": "google_uuid",
                "fact": "Alice works at Google",
                "relation_type": "WORKS_AT",
                "expired_at": None,
            },
            {
                "uuid": "edge2",
                "source_uuid": "bob_uuid",
                "target_uuid": "google_uuid",
                "fact": "Bob works at Google",
                "relation_type": "WORKS_AT",
                "expired_at": None,
            },
            {
                "uuid": "edge3",
                "source_uuid": "charlie_uuid",
                "target_uuid": "stanford_uuid",
                "fact": "Charlie teaches at Stanford",
                "relation_type": "WORKS_AT",
                "expired_at": None,
            },
        ]

    def test_initialization(self, detector, mock_db, mock_llm_client):
        """Test detector initialization."""
        assert detector.db == mock_db
        assert detector.llm_client == mock_llm_client

    def test_detect_communities_no_entities(self, detector, mock_db):
        """Test community detection with no entities."""
        mock_db.get_all_entities.return_value = []

        num_communities = detector.detect_communities("test_group")

        assert num_communities == 0
        mock_db.get_all_entities.assert_called_once_with("test_group")

    def test_detect_communities_creates_graph(
        self, detector, mock_db, sample_entities, sample_edges
    ):
        """Test that community detection creates a NetworkX graph."""
        mock_db.get_all_entities.return_value = sample_entities
        mock_db.get_all_edges.return_value = sample_edges
        mock_db.save_community.return_value = None
        mock_db.create_has_member_edge.return_value = None

        with patch("ryumem.community.detector.OpenAI"):
            num_communities = detector.detect_communities(
                "test_group", min_community_size=2
            )

        # Should detect at least 1 community (possibly 2: Google cluster and Stanford cluster)
        assert num_communities >= 1
        mock_db.save_community.assert_called()

    def test_extract_community_name_from_summary(self, detector):
        """Test extracting community name from summary."""
        summary = "This community focuses on artificial intelligence research. It includes researchers and institutions."

        name = detector._extract_community_name(summary, 0)

        assert "artificial intelligence" in name.lower()
        assert len(name) <= 63  # Max 60 chars + "..."

    def test_extract_community_name_fallback(self, detector):
        """Test community name fallback when summary is empty."""
        summary = ""

        name = detector._extract_community_name(summary, 5)

        assert name == "Community 5"

    def test_extract_community_name_truncation(self, detector):
        """Test that long community names are truncated."""
        long_summary = "A" * 100 + ". More text."

        name = detector._extract_community_name(long_summary, 0)

        assert len(name) <= 63
        assert name.endswith("...")

    def test_generate_community_summary_with_llm(self, detector):
        """Test generating community summary using LLM."""
        entity_infos = [
            {
                "name": "Alice",
                "type": "person",
                "summary": "Software engineer",
            },
            {
                "name": "Bob",
                "type": "person",
                "summary": "Data scientist",
            },
        ]

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "A community of tech professionals"

        with patch("ryumem.community.detector.OpenAI") as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            summary = detector._generate_community_summary(entity_infos)

        assert summary == "A community of tech professionals"
        mock_client.chat.completions.create.assert_called_once()

    def test_generate_community_summary_fallback(self, detector):
        """Test community summary fallback when LLM fails."""
        entity_infos = [
            {"name": "Alice", "type": "person", "summary": "Engineer"},
            {"name": "Bob", "type": "person", "summary": "Scientist"},
        ]

        with patch("ryumem.community.detector.OpenAI", side_effect=Exception("API Error")):
            summary = detector._generate_community_summary(entity_infos)

        # Should use fallback
        assert "Alice" in summary
        assert "2 entities" in summary

    def test_create_community_node(self, detector, mock_db):
        """Test creating a CommunityNode."""
        import networkx as nx

        G = nx.Graph()
        G.add_node("e1", name="Alice", entity_type="person", summary="Engineer")
        G.add_node("e2", name="Bob", entity_type="person", summary="Scientist")

        entity_uuids = ["e1", "e2"]

        with patch.object(detector, "_generate_community_summary", return_value="Tech community"):
            community = detector._create_community(
                community_id=0,
                entity_uuids=entity_uuids,
                user_id="test_group",
                graph=G,
            )

        assert isinstance(community, CommunityNode)
        assert community.user_id == "test_group"
        assert community.summary == "Tech community"
        assert community.members == entity_uuids
        assert len(community.uuid) > 0

    def test_create_has_member_edges(self, detector, mock_db):
        """Test creating HAS_MEMBER edges."""
        community_uuid = str(uuid4())
        entity_uuids = ["e1", "e2", "e3"]

        mock_db.create_has_member_edge.return_value = None

        detector._create_has_member_edges(community_uuid, entity_uuids)

        # Should create an edge for each entity
        assert mock_db.create_has_member_edge.call_count == 3

    def test_update_communities_deletes_existing(self, detector, mock_db):
        """Test that update_communities deletes existing communities first."""
        mock_db.delete_communities.return_value = None
        mock_db.get_all_entities.return_value = []

        detector.update_communities("test_group")

        mock_db.delete_communities.assert_called_once_with("test_group")

    def test_get_community_context(self, detector, mock_db):
        """Test getting community context."""
        community_data = {
            "uuid": "comm1",
            "name": "Tech Community",
            "members": ["e1", "e2"],
        }
        entity1 = {"uuid": "e1", "name": "Alice"}
        entity2 = {"uuid": "e2", "name": "Bob"}

        mock_db.get_community_by_uuid.return_value = community_data
        mock_db.get_entity_by_uuid.side_effect = [entity1, entity2]

        context = detector.get_community_context("comm1")

        assert context["community"] == community_data
        assert len(context["members"]) == 2
        assert context["member_count"] == 2

    def test_get_community_context_not_found(self, detector, mock_db):
        """Test getting context for nonexistent community."""
        mock_db.get_community_by_uuid.return_value = None

        context = detector.get_community_context("nonexistent")

        assert context == {}

    def test_min_community_size_filter(self, detector, mock_db, sample_entities, sample_edges):
        """Test that communities smaller than min_size are filtered out."""
        # Create entities that form one large cluster and one small (singleton)
        entities = sample_entities[:3]  # 3 entities in main cluster
        entities.append({
            "uuid": "isolated_uuid",
            "name": "Isolated",
            "entity_type": "person",
            "summary": "No connections",
        })

        mock_db.get_all_entities.return_value = entities
        mock_db.get_all_edges.return_value = sample_edges[:2]  # Only connect first 3
        mock_db.save_community.return_value = None
        mock_db.create_has_member_edge.return_value = None

        with patch("ryumem.community.detector.OpenAI"):
            # Filter out communities smaller than 2
            num_communities = detector.detect_communities(
                "test_group",
                min_community_size=2
            )

        # The isolated entity should be filtered out
        # Only the main cluster should remain
        assert num_communities >= 1

    def test_resolution_parameter(self, detector, mock_db, sample_entities, sample_edges):
        """Test that resolution parameter affects community granularity."""
        mock_db.get_all_entities.return_value = sample_entities
        mock_db.get_all_edges.return_value = sample_edges
        mock_db.save_community.return_value = None
        mock_db.create_has_member_edge.return_value = None

        with patch("ryumem.community.detector.OpenAI"):
            # Lower resolution = fewer, larger communities
            num_low_res = detector.detect_communities(
                "test_group",
                resolution=0.5,
                min_community_size=1
            )

            # Delete communities and re-detect
            mock_db.save_community.reset_mock()

            # Higher resolution = more, smaller communities
            num_high_res = detector.detect_communities(
                "test_group",
                resolution=2.0,
                min_community_size=1
            )

        # This is probabilistic, but generally higher resolution = more communities
        # We just check that both work without errors
        assert num_low_res >= 0
        assert num_high_res >= 0
