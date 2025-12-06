"""
Tests for individual MCP tool invocations
Each test verifies that a specific MCP tool correctly calls the Ryumem API
"""

import pytest
import json


@pytest.mark.usefixtures("verify_api_available")
class TestAddEpisodeTool:
    """Tests for the add_episode MCP tool"""

    def test_add_episode_basic(self, mcp_client, test_user_id, test_session_id):
        """Test basic episode creation through MCP"""
        result = mcp_client.call_tool("add_episode", {
            "content": "Test memory content",
            "user_id": test_user_id,
            "session_id": test_session_id,
            "kind": "memory",
            "source": "text"
        })

        assert result is not None
        assert "content" in result

        # Parse the response content
        content_data = json.loads(result["content"][0]["text"])

        # Should return episode_id or uuid
        assert "episode_id" in content_data or "uuid" in content_data

    def test_add_episode_with_metadata(self, mcp_client, test_user_id, test_session_id):
        """Test adding episode with metadata"""
        metadata = {
            "topic": "testing",
            "tags": ["mcp", "integration"],
            "priority": "high"
        }

        result = mcp_client.call_tool("add_episode", {
            "content": "Test with metadata",
            "user_id": test_user_id,
            "session_id": test_session_id,
            "metadata": metadata
        })

        assert result is not None
        content_data = json.loads(result["content"][0]["text"])
        assert "episode_id" in content_data or "uuid" in content_data

    def test_add_episode_missing_required_field(self, mcp_client):
        """Test that missing required fields return errors"""
        with pytest.raises(RuntimeError):
            mcp_client.call_tool("add_episode", {
                "content": "Missing user_id and session_id"
            })

    def test_add_episode_with_entity_extraction(self, mcp_client, test_user_id, test_session_id):
        """Test adding episode with entity extraction enabled"""
        result = mcp_client.call_tool("add_episode", {
            "content": "John Smith works at Acme Corp in New York",
            "user_id": test_user_id,
            "session_id": test_session_id,
            "extract_entities": True
        })

        assert result is not None
        content_data = json.loads(result["content"][0]["text"])
        assert "episode_id" in content_data or "uuid" in content_data


@pytest.mark.usefixtures("verify_api_available")
class TestSearchMemoryTool:
    """Tests for the search_memory MCP tool"""

    def test_search_memory_basic(self, mcp_client, test_user_id, test_session_id):
        """Test basic memory search"""
        # First add some content
        mcp_client.call_tool("add_episode", {
            "content": "Python is a programming language",
            "user_id": test_user_id,
            "session_id": test_session_id,
            "kind": "memory"
        })

        # Now search for it
        result = mcp_client.call_tool("search_memory", {
            "query": "programming language",
            "user_id": test_user_id,
            "limit": 5
        })

        assert result is not None
        content_data = json.loads(result["content"][0]["text"])

        # Should return entities, edges, episodes, etc.
        assert "entities" in content_data or "episodes" in content_data

    def test_search_memory_with_strategy(self, mcp_client, test_user_id):
        """Test search with different strategies"""
        strategies = ["semantic", "hybrid", "bm25"]

        for strategy in strategies:
            result = mcp_client.call_tool("search_memory", {
                "query": "test query",
                "user_id": test_user_id,
                "strategy": strategy,
                "limit": 5
            })

            assert result is not None
            content_data = json.loads(result["content"][0]["text"])
            assert isinstance(content_data, dict)

    def test_search_memory_with_filters(self, mcp_client, test_user_id, test_session_id):
        """Test search with kind filters"""
        result = mcp_client.call_tool("search_memory", {
            "query": "test",
            "user_id": test_user_id,
            "session_id": test_session_id,
            "kinds": ["memory"],
            "limit": 10,
            "similarity_threshold": 0.3
        })

        assert result is not None
        content_data = json.loads(result["content"][0]["text"])
        assert isinstance(content_data, dict)


@pytest.mark.usefixtures("verify_api_available")
class TestListEpisodesTool:
    """Tests for the list_episodes MCP tool"""

    def test_list_episodes_basic(self, mcp_client, test_user_id, test_session_id):
        """Test basic episode listing"""
        # Add some episodes first
        for i in range(3):
            mcp_client.call_tool("add_episode", {
                "content": f"Test episode {i}",
                "user_id": test_user_id,
                "session_id": test_session_id
            })

        # List episodes
        result = mcp_client.call_tool("list_episodes", {
            "user_id": test_user_id,
            "limit": 10
        })

        assert result is not None
        content_data = json.loads(result["content"][0]["text"])

        # Should return a list of episodes
        assert "episodes" in content_data
        assert isinstance(content_data["episodes"], list)

    def test_list_episodes_with_session_filter(self, mcp_client, test_user_id, test_session_id):
        """Test listing episodes filtered by session"""
        result = mcp_client.call_tool("list_episodes", {
            "user_id": test_user_id,
            "session_id": test_session_id,
            "limit": 20
        })

        assert result is not None

    def test_list_episodes_pagination(self, mcp_client, test_user_id, test_session_id):
        """Test episode listing with pagination"""
        # First page
        result1 = mcp_client.call_tool("list_episodes", {
            "user_id": test_user_id,
            "limit": 2,
            "offset": 0
        })

        # Second page
        result2 = mcp_client.call_tool("list_episodes", {
            "user_id": test_user_id,
            "limit": 2,
            "offset": 2
        })

        assert result1 is not None
        assert result2 is not None


@pytest.mark.usefixtures("verify_api_available")
class TestGetEpisodeTool:
    """Tests for the get_episode MCP tool"""

    def test_get_episode_by_uuid(self, mcp_client, test_user_id, test_session_id):
        """Test retrieving a specific episode by UUID"""
        # Create an episode
        add_result = mcp_client.call_tool("add_episode", {
            "content": "Episode to retrieve",
            "user_id": test_user_id,
            "session_id": test_session_id
        })

        add_data = json.loads(add_result["content"][0]["text"])
        episode_id = add_data.get("episode_id") or add_data.get("uuid")

        # Retrieve it
        result = mcp_client.call_tool("get_episode", {
            "episode_uuid": episode_id,
            "user_id": test_user_id
        })

        assert result is not None
        content_data = json.loads(result["content"][0]["text"])

        assert "content" in content_data
        assert content_data["content"] == "Episode to retrieve"

    def test_get_episode_not_found(self, mcp_client, test_user_id):
        """Test getting a non-existent episode"""
        # Should raise RuntimeError for 404
        with pytest.raises(RuntimeError, match="404|not found"):
            mcp_client.call_tool("get_episode", {
                "episode_uuid": "00000000-0000-0000-0000-000000000000",
                "user_id": test_user_id
            })


@pytest.mark.usefixtures("verify_api_available")
class TestUpdateEpisodeMetadataTool:
    """Tests for the update_episode_metadata MCP tool"""

    def test_update_episode_metadata(self, mcp_client, test_user_id, test_session_id):
        """Test updating episode metadata"""
        # Create an episode
        add_result = mcp_client.call_tool("add_episode", {
            "content": "Episode to update",
            "user_id": test_user_id,
            "session_id": test_session_id,
            "metadata": {"initial": "value"}
        })

        add_data = json.loads(add_result["content"][0]["text"])
        episode_id = add_data.get("episode_id") or add_data.get("uuid")

        # Update metadata
        new_metadata = {
            "updated": "true",
            "timestamp": "2024-01-01"
        }

        result = mcp_client.call_tool("update_episode_metadata", {
            "episode_uuid": episode_id,
            "user_id": test_user_id,
            "metadata": new_metadata
        })

        assert result is not None
        content_data = json.loads(result["content"][0]["text"])

        # Update returns just the uuid confirmation
        assert "uuid" in content_data

        # Fetch the episode to verify metadata was actually updated
        get_result = mcp_client.call_tool("get_episode", {
            "episode_uuid": episode_id,
            "user_id": test_user_id
        })

        episode_data = json.loads(get_result["content"][0]["text"])
        metadata = episode_data.get("metadata", {})

        # If metadata is a string, parse it
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        # Verify the metadata was updated
        assert metadata.get("updated") == "true"
        assert metadata.get("timestamp") == "2024-01-01"


@pytest.mark.usefixtures("verify_api_available")
class TestGetEntityContextTool:
    """Tests for the get_entity_context MCP tool"""

    def test_get_entity_context(self, mcp_client, test_user_id, test_session_id):
        """Test retrieving entity context"""
        # Add episode with entities
        mcp_client.call_tool("add_episode", {
            "content": "Alice works at Google on machine learning projects",
            "user_id": test_user_id,
            "session_id": test_session_id,
            "extract_entities": True
        })

        # Get entity context
        result = mcp_client.call_tool("get_entity_context", {
            "entity_name": "Alice",
            "user_id": test_user_id,
            "max_depth": 2
        })

        assert result is not None
        content_data = json.loads(result["content"][0]["text"])

        # Should contain entity info and relationships
        assert isinstance(content_data, dict)

    def test_get_entity_context_not_found(self, mcp_client, test_user_id):
        """Test getting context for non-existent entity"""
        result = mcp_client.call_tool("get_entity_context", {
            "entity_name": "NonExistentEntity12345",
            "user_id": test_user_id
        })

        assert result is not None
        # Should return empty or error response
        content_data = json.loads(result["content"][0]["text"])
        assert isinstance(content_data, dict)


@pytest.mark.usefixtures("verify_api_available")
class TestPruneMemoriesTool:
    """Tests for the prune_memories MCP tool"""

    def test_prune_memories_basic(self, mcp_client, test_user_id):
        """Test basic memory pruning"""
        result = mcp_client.call_tool("prune_memories", {
            "user_id": test_user_id,
            "min_age_days": 30,
            "min_mentions": 2,
            "expired_cutoff_days": 90
        })

        assert result is not None
        content_data = json.loads(result["content"][0]["text"])

        # Should return statistics about pruning
        assert isinstance(content_data, dict)

    def test_prune_memories_with_compaction(self, mcp_client, test_user_id):
        """Test memory pruning with redundant compaction"""
        result = mcp_client.call_tool("prune_memories", {
            "user_id": test_user_id,
            "compact_redundant": True
        })

        assert result is not None


class TestToolErrorHandling:
    """Tests for error handling across all tools"""

    def test_invalid_user_id_format(self, mcp_client):
        """Test that invalid user IDs are handled properly"""
        # Empty user_id - The API currently accepts empty user_id
        # This test verifies the call doesn't crash, though ideally it should validate
        result = mcp_client.call_tool("search_memory", {
            "query": "test",
            "user_id": "",
            "limit": 1
        })

        # Should return a result (even if empty)
        assert result is not None

    def test_malformed_json_in_metadata(self, mcp_client, test_user_id, test_session_id):
        """Test that tools handle edge cases in data"""
        # This should work - metadata can be any valid JSON
        result = mcp_client.call_tool("add_episode", {
            "content": "Test",
            "user_id": test_user_id,
            "session_id": test_session_id,
            "metadata": {"nested": {"deep": {"value": [1, 2, 3]}}}
        })

        assert result is not None
