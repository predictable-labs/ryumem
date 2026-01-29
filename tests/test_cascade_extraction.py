"""
Comprehensive tests for refactored cascade extraction and LLM clients.

Tests verify the actual refactored code works correctly, not just interface contracts.
Mocks only actual API calls, tests all internal logic.
"""

import json
from unittest.mock import AsyncMock, Mock, MagicMock

import pytest
from pydantic import BaseModel

from ryumem_server.ingestion.cascade_extraction.extract_nodes import (
    extract_nodes,
    extract_nodes_sync,
)
from ryumem_server.ingestion.cascade_extraction.extract_relationships import (
    extract_relationships,
    extract_relationships_sync,
)
from ryumem_server.ingestion.cascade_extraction.extract_triplets import (
    extract_triplets,
    extract_triplets_sync,
)
from ryumem_server.ingestion.cascade_extraction.models import (
    ExtractedEdge,
    ExtractedNode,
    KnowledgeGraph,
    NodesAndRelationships,
    PotentialNodes,
)


def create_mock_litellm_client():
    """Helper to create a mock client that acts like LiteLLMClient."""
    # Create a mock that has the methods we need
    mock_client = Mock()
    mock_client.model = "gpt-4o-mini"
    mock_client.max_retries = 3
    mock_client.timeout = 30

    # Add the litellm attribute that would be set in __init__
    mock_client.litellm = MagicMock()

    return mock_client


# ============================================================================
# Test Cascade Extraction - Node Stage
# ============================================================================


class TestNodeExtraction:
    """Test node extraction with actual template rendering and deduplication logic."""

    @pytest.mark.asyncio
    async def test_extract_nodes_two_rounds_with_deduplication(self):
        """Test that nodes are deduplicated across rounds."""
        mock_response_1 = Mock()
        mock_response_1.choices = [Mock(message=Mock(content='{"nodes": ["Alice", "Google", "Bob"]}'))]

        mock_response_2 = Mock()
        mock_response_2.choices = [Mock(message=Mock(content='{"nodes": ["Bob", "San Francisco", "Alice"]}'))]

        # Create mock client and set up the async method
        mock_client = create_mock_litellm_client()
        mock_client.acreate_structured_output = AsyncMock(side_effect=[
            PotentialNodes(nodes=["Alice", "Google", "Bob"]),
            PotentialNodes(nodes=["Bob", "San Francisco", "Alice"])
        ])

        result = await extract_nodes(
            text="Alice and Bob work at Google in San Francisco",
            user_id="test_user",
            llm_client=mock_client,
            n_rounds=2,
            context=None,
        )

        # Verify deduplication - should have 4 unique nodes
        assert len(result) == 4
        assert "Alice" in result
        assert "Bob" in result
        assert "Google" in result
        assert "San Francisco" in result
        # Verify no duplicates
        assert len(result) == len(set(result))
        # Verify method was called twice
        assert mock_client.acreate_structured_output.call_count == 2


    def test_extract_nodes_sync(self):
        """Test sync version."""
        mock_client = create_mock_litellm_client()
        mock_client.create_structured_output = Mock(return_value=PotentialNodes(nodes=["Python", "FastAPI"]))

        result = extract_nodes_sync(
            text="test",
            user_id="test_user",
            llm_client=mock_client,
            n_rounds=1,
            context=None,
        )

        assert result == ["Python", "FastAPI"]
        assert mock_client.create_structured_output.call_count == 1


# ============================================================================
# Test Cascade Extraction - Relationship Stage
# ============================================================================


class TestRelationshipExtraction:
    """Test relationship extraction with node refinement."""

    @pytest.mark.asyncio
    async def test_extract_relationships_case_normalization(self):
        """Test that relationships are normalized to uppercase."""
        mock_client = create_mock_litellm_client()
        mock_client.acreate_structured_output = AsyncMock(
            return_value=NodesAndRelationships(
                nodes=["Alice", "Bob"],
                relationships=["knows", "WORKS_WITH", "Mentors"]
            )
        )

        nodes, relationships = await extract_relationships(
            text="test",
            nodes=["Alice", "Bob"],
            user_id="test_user",
            llm_client=mock_client,
            n_rounds=1,
            context=None,
        )

        # All should be uppercase
        assert relationships == ["KNOWS", "WORKS_WITH", "MENTORS"]


    def test_extract_relationships_sync(self):
        """Test sync version."""
        mock_client = create_mock_litellm_client()
        mock_client.create_structured_output = Mock(
            return_value=NodesAndRelationships(
                nodes=["Python", "Django"],
                relationships=["uses"]
            )
        )

        nodes, relationships = extract_relationships_sync(
            text="test",
            nodes=["Python", "Django"],
            user_id="test_user",
            llm_client=mock_client,
            n_rounds=1,
            context=None,
        )

        assert nodes == ["Python", "Django"]
        assert relationships == ["USES"]


# ============================================================================
# Test Cascade Extraction - Triplet Stage
# ============================================================================


class TestTripletExtraction:
    """Test triplet extraction with graph merging."""

    @pytest.mark.asyncio
    async def test_extract_triplets_merges_graphs(self):
        """Test that graphs are properly merged across rounds."""
        graph_1 = KnowledgeGraph(
            nodes=[
                ExtractedNode(id="alice", name="Alice", type="PERSON"),
                ExtractedNode(id="google", name="Google", type="ORGANIZATION")
            ],
            edges=[
                ExtractedEdge(source_node_id="alice", target_node_id="google", relationship_name="WORKS_AT")
            ]
        )

        graph_2 = KnowledgeGraph(
            nodes=[
                ExtractedNode(id="alice", name="Alice", type="PERSON"),  # Duplicate
                ExtractedNode(id="bob", name="Bob", type="PERSON")
            ],
            edges=[
                ExtractedEdge(source_node_id="alice", target_node_id="bob", relationship_name="KNOWS")
            ]
        )

        mock_client = create_mock_litellm_client()
        mock_client.acreate_structured_output = AsyncMock(side_effect=[graph_1, graph_2])

        result = await extract_triplets(
            text="test",
            nodes=["Alice", "Google", "Bob"],
            relationships=["WORKS_AT", "KNOWS"],
            user_id="test_user",
            llm_client=mock_client,
            n_rounds=2,
            context=None,
        )

        # Should have 3 unique nodes (Alice not duplicated)
        assert len(result.nodes) == 3
        node_ids = [n.id for n in result.nodes]
        assert "alice" in node_ids
        assert "google" in node_ids
        assert "bob" in node_ids
        # Should have 2 edges
        assert len(result.edges) == 2


    @pytest.mark.asyncio
    async def test_extract_triplets_validates_graph(self):
        """Test that invalid edges are removed."""
        graph = KnowledgeGraph(
            nodes=[ExtractedNode(id="alice", name="Alice", type="PERSON")],
            edges=[
                ExtractedEdge(source_node_id="alice", target_node_id="nonexistent", relationship_name="KNOWS"),
                ExtractedEdge(source_node_id="alice", target_node_id="alice", relationship_name="SELF")
            ]
        )

        mock_client = create_mock_litellm_client()
        mock_client.acreate_structured_output = AsyncMock(return_value=graph)

        result = await extract_triplets(
            text="test",
            nodes=["Alice"],
            relationships=["KNOWS", "SELF"],
            user_id="test_user",
            llm_client=mock_client,
            n_rounds=1,
            context=None,
        )

        # Should only have the valid edge (self-reference is valid)
        assert len(result.edges) == 1
        assert result.edges[0].source_node_id == "alice"
        assert result.edges[0].target_node_id == "alice"


print("All tests defined successfully")
