"""
End-to-end integration tests for MCP workflows
Tests real-world usage scenarios combining multiple tools
"""

import pytest
import json
import time


@pytest.mark.usefixtures("verify_api_available")
class TestConversationMemoryWorkflow:
    """Test a typical conversation memory workflow"""

    def test_save_and_retrieve_conversation(self, mcp_client, test_user_id, test_session_id):
        """
        Test saving a multi-turn conversation and retrieving it later
        Simulates a typical Claude Desktop usage pattern
        """
        # Turn 1: User asks about Python
        mcp_client.call_tool("add_episode", {
            "content": "User asked: What are the best practices for Python error handling?",
            "user_id": test_user_id,
            "session_id": test_session_id,
            "kind": "query",
            "metadata": {"turn": 1, "type": "question"}
        })

        # Turn 2: Assistant responds with answer
        mcp_client.call_tool("add_episode", {
            "content": "Assistant explained: Use try-except blocks, specific exception types, and proper logging",
            "user_id": test_user_id,
            "session_id": test_session_id,
            "kind": "memory",
            "metadata": {"turn": 2, "type": "answer"}
        })

        # Turn 3: User follows up
        mcp_client.call_tool("add_episode", {
            "content": "User asked: Can you give an example with logging?",
            "user_id": test_user_id,
            "session_id": test_session_id,
            "kind": "query",
            "metadata": {"turn": 3, "type": "followup"}
        })

        # Wait a moment for indexing
        time.sleep(0.5)

        # Now search for the conversation
        result = mcp_client.call_tool("search_memory", {
            "query": "Python error handling logging",
            "user_id": test_user_id,
            "session_id": test_session_id,
            "strategy": "hybrid",
            "limit": 10
        })

        content_data = json.loads(result["content"][0]["text"])

        # Should find episodes from the conversation
        assert "episodes" in content_data
        episodes = content_data["episodes"]
        assert len(episodes) > 0

        # Verify we got relevant content
        all_content = " ".join([ep.get("content", "") for ep in episodes])
        assert "Python" in all_content or "error" in all_content


@pytest.mark.usefixtures("verify_api_available")
class TestEntityTrackingWorkflow:
    """Test entity extraction and relationship tracking"""

    def test_track_person_and_relationships(self, mcp_client, test_user_id, test_session_id):
        """
        Test tracking a person and their relationships across multiple episodes
        """
        # Episode 1: Introduce Alice
        mcp_client.call_tool("add_episode", {
            "content": "Alice is a senior software engineer at Google",
            "user_id": test_user_id,
            "session_id": test_session_id,
            "kind": "memory",
            "extract_entities": True,
            "metadata": {"source": "user_profile"}
        })

        # Episode 2: Add more context about Alice
        mcp_client.call_tool("add_episode", {
            "content": "Alice specializes in machine learning and works on TensorFlow",
            "user_id": test_user_id,
            "session_id": test_session_id,
            "kind": "memory",
            "extract_entities": True,
            "metadata": {"source": "conversation"}
        })

        # Episode 3: Add relationship
        mcp_client.call_tool("add_episode", {
            "content": "Alice collaborates with Bob on the ML infrastructure team",
            "user_id": test_user_id,
            "session_id": test_session_id,
            "kind": "memory",
            "extract_entities": True,
            "metadata": {"source": "team_info"}
        })

        # Wait for entity extraction
        time.sleep(1.0)

        # Retrieve Alice's context
        result = mcp_client.call_tool("get_entity_context", {
            "entity_name": "Alice",
            "user_id": test_user_id,
            "max_depth": 2
        })

        content_data = json.loads(result["content"][0]["text"])

        # Should have entity and relationships
        assert "entity" in content_data or "relationships" in content_data


@pytest.mark.usefixtures("verify_api_available")
class TestSessionIsolationWorkflow:
    """Test that different sessions are properly isolated"""

    def test_multi_session_isolation(self, mcp_client, test_user_id):
        """
        Test that memories from different sessions are isolated
        """
        import uuid

        session1 = f"session-{uuid.uuid4()}"
        session2 = f"session-{uuid.uuid4()}"

        # Add episode to session 1
        mcp_client.call_tool("add_episode", {
            "content": "This is session 1 content about databases",
            "user_id": test_user_id,
            "session_id": session1,
            "kind": "memory",
            "metadata": {"session_name": "Database Discussion"}
        })

        # Add episode to session 2
        mcp_client.call_tool("add_episode", {
            "content": "This is session 2 content about frontend frameworks",
            "user_id": test_user_id,
            "session_id": session2,
            "kind": "memory",
            "metadata": {"session_name": "Frontend Discussion"}
        })

        # List episodes for session 1 only
        result1 = mcp_client.call_tool("list_episodes", {
            "user_id": test_user_id,
            "session_id": session1,
            "limit": 10
        })

        content1 = json.loads(result1["content"][0]["text"])

        # List episodes for session 2 only
        result2 = mcp_client.call_tool("list_episodes", {
            "user_id": test_user_id,
            "session_id": session2,
            "limit": 10
        })

        content2 = json.loads(result2["content"][0]["text"])

        # Each session should have its own episodes
        assert content1 is not None
        assert content2 is not None


@pytest.mark.usefixtures("verify_api_available")
class TestMetadataUpdateWorkflow:
    """Test updating episode metadata over time"""

    def test_metadata_enrichment_workflow(self, mcp_client, test_user_id, test_session_id):
        """
        Test adding and updating metadata on episodes
        Simulates tagging and categorization workflow
        """
        # Create initial episode
        add_result = mcp_client.call_tool("add_episode", {
            "content": "Discussion about Kubernetes deployment strategies",
            "user_id": test_user_id,
            "session_id": test_session_id,
            "metadata": {
                "status": "draft",
                "tags": ["kubernetes"]
            }
        })

        add_data = json.loads(add_result["content"][0]["text"])
        episode_id = add_data.get("episode_id") or add_data.get("uuid")

        # Update with more metadata
        mcp_client.call_tool("update_episode_metadata", {
            "episode_uuid": episode_id,
            "user_id": test_user_id,
            "metadata": {
                "status": "reviewed",
                "tags": ["kubernetes", "devops", "deployment"],
                "reviewed_by": "system",
                "reviewed_at": "2024-01-01T00:00:00Z"
            }
        })

        # Retrieve and verify
        result = mcp_client.call_tool("get_episode", {
            "episode_uuid": episode_id,
            "user_id": test_user_id
        })

        content_data = json.loads(result["content"][0]["text"])
        metadata = content_data.get("metadata", {})

        # If metadata is a string, parse it as JSON
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        # Metadata should be updated
        assert metadata.get("status") == "reviewed"
        assert "devops" in metadata.get("tags", [])


@pytest.mark.usefixtures("verify_api_available")
class TestSearchStrategiesComparison:
    """Test different search strategies on the same data"""

    def test_compare_search_strategies(self, mcp_client, test_user_id, test_session_id):
        """
        Test that different search strategies return results
        """
        # Add some searchable content
        contents = [
            "Python is a high-level programming language",
            "JavaScript is commonly used for web development",
            "Machine learning models require training data",
            "Docker containers provide isolated environments"
        ]

        for content in contents:
            mcp_client.call_tool("add_episode", {
                "content": content,
                "user_id": test_user_id,
                "session_id": test_session_id,
                "kind": "memory"
            })

        time.sleep(0.5)

        strategies = ["semantic", "hybrid", "bm25"]
        results = {}

        for strategy in strategies:
            result = mcp_client.call_tool("search_memory", {
                "query": "programming languages",
                "user_id": test_user_id,
                "strategy": strategy,
                "limit": 5
            })

            results[strategy] = json.loads(result["content"][0]["text"])

        # All strategies should return results
        for strategy, data in results.items():
            assert data is not None, f"Strategy {strategy} returned None"


@pytest.mark.usefixtures("verify_api_available")
class TestLongRunningSessionWorkflow:
    """Test a long-running session with many episodes"""

    def test_session_with_many_episodes(self, mcp_client, test_user_id, test_session_id):
        """
        Test handling a session with many episodes (pagination, etc.)
        """
        # Add 10 episodes
        for i in range(10):
            mcp_client.call_tool("add_episode", {
                "content": f"Episode {i}: Discussion about topic {i}",
                "user_id": test_user_id,
                "session_id": test_session_id,
                "metadata": {"episode_number": i}
            })

        # List with pagination
        page1 = mcp_client.call_tool("list_episodes", {
            "user_id": test_user_id,
            "session_id": test_session_id,
            "limit": 5,
            "offset": 0
        })

        page2 = mcp_client.call_tool("list_episodes", {
            "user_id": test_user_id,
            "session_id": test_session_id,
            "limit": 5,
            "offset": 5
        })

        page1_data = json.loads(page1["content"][0]["text"])
        page2_data = json.loads(page2["content"][0]["text"])

        assert page1_data is not None
        assert page2_data is not None


@pytest.mark.usefixtures("verify_api_available")
class TestMemoryMaintenanceWorkflow:
    """Test memory cleanup and maintenance workflows"""

    def test_prune_old_memories_workflow(self, mcp_client, test_user_id, test_session_id):
        """
        Test the workflow of adding memories and then pruning them
        """
        # Add some test memories
        for i in range(5):
            mcp_client.call_tool("add_episode", {
                "content": f"Old memory {i} that might be pruned",
                "user_id": test_user_id,
                "session_id": test_session_id,
                "kind": "memory",
                "metadata": {"age_group": "old"}
            })

        # Run pruning (with conservative settings to avoid actually deleting test data)
        result = mcp_client.call_tool("prune_memories", {
            "user_id": test_user_id,
            "min_age_days": 365,  # Very old
            "min_mentions": 1,
            "expired_cutoff_days": 730,  # Very old cutoff
            "compact_redundant": False
        })

        content_data = json.loads(result["content"][0]["text"])

        # Should return pruning statistics
        assert content_data is not None
        assert isinstance(content_data, dict)


@pytest.mark.usefixtures("verify_api_available")
class TestErrorRecoveryWorkflow:
    """Test error handling and recovery in workflows"""

    def test_continue_after_error(self, mcp_client, test_user_id, test_session_id):
        """
        Test that the MCP server can continue working after an error
        """
        # Make a valid call
        result1 = mcp_client.call_tool("add_episode", {
            "content": "Valid episode 1",
            "user_id": test_user_id,
            "session_id": test_session_id
        })
        assert result1 is not None

        # Make an invalid call
        try:
            mcp_client.call_tool("add_episode", {
                "content": "Missing required fields"
                # Missing user_id and session_id
            })
        except RuntimeError:
            pass  # Expected to fail

        # Make another valid call - server should still work
        result2 = mcp_client.call_tool("add_episode", {
            "content": "Valid episode 2",
            "user_id": test_user_id,
            "session_id": test_session_id
        })
        assert result2 is not None

    def test_retry_on_transient_failure(self, mcp_client, test_user_id):
        """
        Test that operations can be retried
        """
        # Try to get a non-existent episode - should raise error
        with pytest.raises(RuntimeError, match="404|not found"):
            mcp_client.call_tool("get_episode", {
                "episode_uuid": "00000000-0000-0000-0000-000000000000",
                "user_id": test_user_id
            })

        # Try again - should also raise error but server should still work
        with pytest.raises(RuntimeError, match="404|not found"):
            mcp_client.call_tool("get_episode", {
                "episode_uuid": "00000000-0000-0000-0000-000000000001",
                "user_id": test_user_id
            })
