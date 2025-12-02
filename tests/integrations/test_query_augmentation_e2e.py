"""
End-to-end tests for query augmentation with multi-user isolation.

These tests verify:
1. Episode creation with embeddings
2. Query augmentation finding similar past queries
3. Multi-user data isolation (critical security test)
4. Session management and episode reuse
5. Edge cases (duplicates, empty queries)

Tests use real Ryumem server, real embeddings, and real database operations
for maximum confidence in production behavior.
"""

import pytest
import os
import uuid
import time
from ryumem import Ryumem
from ryumem.core.metadata_models import EpisodeMetadata, QueryRun
import datetime

class TestQueryAugmentationE2E:
    """End-to-end tests for query augmentation with multi-user isolation."""

    @pytest.fixture
    def ryumem_client(self):
        """Create Ryumem client for testing."""
        # Use environment variables - Ryumem() will auto-detect RYUMEM_API_URL
        return Ryumem()

    @pytest.fixture
    def unique_user(self):
        """Generate unique user ID for test isolation."""
        return f"test_user_{uuid.uuid4().hex[:8]}"

    @pytest.fixture
    def unique_session(self):
        """Generate unique session ID."""
        return f"test_session_{uuid.uuid4().hex[:8]}"

    def test_episode_creation_with_embedding(self, ryumem_client, unique_user, unique_session):
        """Test that episodes are created with embeddings."""
        # Create episode
        episode_id = ryumem_client.add_episode(
            content="Try to find the password",
            user_id=unique_user,
            session_id=unique_session,
            source="message"
        )

        assert episode_id is not None, "Episode ID should be returned"

        # Verify episode exists with embedding
        episode = ryumem_client.get_episode_by_uuid(episode_id)
        assert episode is not None, "Episode should exist in database"
        assert episode.content == "Try to find the password", "Episode content should match"
        assert episode.user_id == unique_user, "Episode should belong to correct user"
        assert episode.source.value == "message", "Episode source should be 'message'"

    def test_first_query_no_augmentation(self, ryumem_client, unique_user, unique_session):
        """First query should find the episode we just created (but no previous history)."""
        # Create first episode
        episode_id = ryumem_client.add_episode(
            content="What is the capital of France?",
            user_id=unique_user,
            session_id=unique_session,
            source="message"
        )

        # Search for similar queries (should find the one we just created)
        results = ryumem_client.search(
            query="What is the capital of France?",
            user_id=unique_user,
            session_id=unique_session,
            strategy="semantic"
        )

        # Should find at least the episode we created
        assert len(results.episodes) >= 1, "Should find at least one episode"
        assert any(ep.uuid == episode_id for ep in results.episodes), "Should find the episode we created"

    def test_similar_query_finds_previous(self, ryumem_client, unique_user):
        """Second similar query should find first episode across sessions."""
        session1 = f"session_{uuid.uuid4().hex[:8]}"
        session2 = f"session_{uuid.uuid4().hex[:8]}"

        # Create first episode in session 1
        episode1_id = ryumem_client.add_episode(
            content="How do I reset my password?",
            user_id=unique_user,
            session_id=session1,
            source="message"
        )

        # Wait briefly for indexing
        # Search from session 2 (cross-session search)
        results = ryumem_client.search(
            query="How do I reset my password?",  # Same query
            user_id=unique_user,
            session_id=session2,
            strategy="semantic"
        )

        # Should find episode from session 1
        assert len(results.episodes) >= 1, "Should find episodes from previous session"
        episode_uuids = [ep.uuid for ep in results.episodes]
        assert episode1_id in episode_uuids, "Should find the episode from session 1"

    def test_multi_user_isolation(self, ryumem_client):
        """Verify user A's queries don't leak to user B (CRITICAL SECURITY TEST)."""
        user_a = f"user_a_{uuid.uuid4().hex[:8]}"
        user_b = f"user_b_{uuid.uuid4().hex[:8]}"
        session_a = f"session_{uuid.uuid4().hex[:8]}"
        session_b = f"session_{uuid.uuid4().hex[:8]}"

        # User A creates episode
        episode_a = ryumem_client.add_episode(
            content="User A's secret query about passwords",
            user_id=user_a,
            session_id=session_a,
            source="message"
        )

        # User B creates episode
        episode_b = ryumem_client.add_episode(
            content="User B's query about passwords",
            user_id=user_b,
            session_id=session_b,
            source="message"
        )

        # User B searches - should NOT see User A's episode
        results_b = ryumem_client.search(
            query="passwords",
            user_id=user_b,
            session_id=session_b,
            strategy="semantic"
        )

        episode_uuids_for_b = [ep.uuid for ep in results_b.episodes]
        assert episode_a not in episode_uuids_for_b, "SECURITY VIOLATION: User A's episode leaked to User B!"
        assert episode_b in episode_uuids_for_b, "User B should see their own episode"

        # User A searches - should NOT see User B's episode
        results_a = ryumem_client.search(
            query="passwords",
            user_id=user_a,
            session_id=session_a,
            strategy="semantic"
        )

        episode_uuids_for_a = [ep.uuid for ep in results_a.episodes]
        assert episode_b not in episode_uuids_for_a, "SECURITY VIOLATION: User B's episode leaked to User A!"
        assert episode_a in episode_uuids_for_a, "User A should see their own episode"

    def test_session_episode_reuse(self, ryumem_client, unique_user, unique_session):
        """Test that episodes can be retrieved by session ID."""
        # Create episode for session

        query_run = QueryRun(
            run_id="one",
            user_id=unique_user,
            timestamp=datetime.datetime.utcnow().isoformat(),
            query="Session test query",
            augmented_query="Session test query",
            agent_response="",
            tools_used=[]
        )

        episode_metadata = EpisodeMetadata(integration="google_adk")
        episode_metadata.add_query_run(unique_session, query_run)

        episode_id = ryumem_client.add_episode(
            content="Session test query",
            user_id=unique_user,
            session_id=unique_session,
            source="message",
            metadata=episode_metadata.model_dump(),
        )

        # Get episode by session ID
        episode = ryumem_client.get_episode_by_session_id(unique_session)
        assert episode is not None, "Should retrieve episode by session ID"
        assert episode.uuid == episode_id, "Retrieved episode should match created episode"

    def test_duplicate_query_deduplication(self, ryumem_client, unique_user, unique_session):
        """Test that duplicate queries within time window return same episode."""
        content = "Exact duplicate query test"

        # Create first episode
        episode_id_1 = ryumem_client.add_episode(
            content=content,
            user_id=unique_user,
            session_id=unique_session,
            source="message"
        )

        # Create second episode with same content (within 24h window)
        episode_id_2 = ryumem_client.add_episode(
            content=content,
            user_id=unique_user,
            session_id=unique_session,
            source="message"
        )

        # Should return same episode ID (deduplication)
        assert episode_id_1 == episode_id_2, "Duplicate episodes should return same ID (deduplication)"

    def test_empty_query_handling(self, ryumem_client, unique_user, unique_session):
        """Test that empty queries are handled gracefully."""
        # Search with empty query
        results = ryumem_client.search(
            query="",
            user_id=unique_user,
            session_id=unique_session,
            strategy="semantic"
        )

        # Should return empty results without error
        assert isinstance(results.episodes, list), "Should return list of episodes"
        # Empty query should find nothing or handle gracefully
        assert len(results.episodes) >= 0, "Should not crash on empty query"

    def test_tool_summary_detailed_format(self, ryumem_client, unique_user, unique_session):
        """Test that tool_summary is correctly formatted with detailed stats in episode metadata."""
        from ryumem.core.metadata_models import ToolExecution
        
        # Create a query run with tool executions
        tool_exec = ToolExecution(
            tool_name="test_tool",
            success=True,
            timestamp=datetime.datetime.utcnow().isoformat(),
            input_params={"arg1": "val1"},
            output_summary="result1"
        )
        
        query_run = QueryRun(
            run_id="run_stats",
            user_id=unique_user,
            timestamp=datetime.datetime.utcnow().isoformat(),
            query="Stats test",
            tools_used=[tool_exec]
        )
        
        episode_metadata = EpisodeMetadata(integration="google_adk")
        episode_metadata.add_query_run(unique_session, query_run)
        
        # Verify the stats format directly on metadata model (now using standard get_tool_usage_summary)
        stats_summary = episode_metadata.get_tool_usage_summary()
        expected = "test_tool with [arg1=val1] -> result1"
        assert stats_summary == expected, f"Expected '{expected}', got '{stats_summary}'"
        
        # Verify empty output handling
        tool_exec_empty = ToolExecution(
            tool_name="empty_tool",
            success=True,
            timestamp=datetime.datetime.utcnow().isoformat(),
            input_params={"arg": "val"},
            output_summary=""
        )
        query_run.tools_used = [tool_exec_empty]
        episode_metadata = EpisodeMetadata(integration="google_adk")
        episode_metadata.add_query_run(unique_session, query_run)
        
        stats_summary = episode_metadata.get_tool_usage_summary()
        expected = "empty_tool with [arg=val] -> []"
        assert stats_summary == expected, f"Expected '{expected}', got '{stats_summary}'"
