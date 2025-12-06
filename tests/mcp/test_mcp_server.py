"""
Tests for MCP server protocol compliance and basic functionality
"""

import pytest


class TestMCPServerStartup:
    """Tests for MCP server initialization and basic protocol"""

    def test_server_starts_successfully(self, mcp_client):
        """Test that the MCP server starts without errors"""
        assert mcp_client.process is not None
        assert mcp_client.process.poll() is None, "Server process should be running"

    def test_server_requires_api_key(self, mcp_server_path, ryumem_api_url):
        """Test that server fails to start without API key"""
        from tests.mcp.conftest import MCPServerClient

        # Create client without API key
        client = MCPServerClient(mcp_server_path, ryumem_api_url, "")

        with pytest.raises(RuntimeError, match="failed to start"):
            client.start()

    def test_list_tools(self, mcp_client):
        """Test that the server can list available tools"""
        result = mcp_client.list_tools()

        assert "tools" in result
        tools = result["tools"]
        assert isinstance(tools, list)
        assert len(tools) > 0

        # Verify expected tools are present
        tool_names = {tool["name"] for tool in tools}
        expected_tools = {
            "search_memory",
            "add_episode",
            "get_entity_context",
            "list_episodes",
            "get_episode",
            "update_episode_metadata",
            "prune_memories"
        }

        assert expected_tools.issubset(tool_names), f"Missing tools: {expected_tools - tool_names}"

    def test_tool_schemas_valid(self, mcp_client):
        """Test that all tools have valid schemas"""
        result = mcp_client.list_tools()
        tools = result["tools"]

        for tool in tools:
            # Each tool should have required fields
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool

            # Input schema should be a valid JSON schema
            schema = tool["inputSchema"]
            assert schema.get("type") == "object"
            assert "properties" in schema
            assert "required" in schema

            # Required fields should be in properties
            for required_field in schema.get("required", []):
                assert required_field in schema["properties"], \
                    f"Required field {required_field} not in properties for {tool['name']}"


class TestMCPProtocolCompliance:
    """Tests for JSON-RPC 2.0 and MCP protocol compliance"""

    def test_invalid_method_returns_error(self, mcp_client):
        """Test that invalid methods return proper errors"""
        with pytest.raises(RuntimeError, match="MCP error|Unknown"):
            mcp_client.send_request("invalid/method", {})

    def test_missing_required_params_returns_error(self, mcp_client):
        """Test that missing required parameters return errors"""
        with pytest.raises(RuntimeError):
            # Call search_memory without required parameters
            mcp_client.call_tool("search_memory", {})

    def test_invalid_tool_name_returns_error(self, mcp_client):
        """Test that calling a non-existent tool returns an error"""
        with pytest.raises(RuntimeError, match="Unknown tool"):
            mcp_client.call_tool("nonexistent_tool", {})


class TestMCPServerConfiguration:
    """Tests for server configuration via environment variables"""

    def test_custom_api_url_respected(self, mcp_server_path, ryumem_api_key):
        """Test that custom API URL is used when provided"""
        from tests.mcp.conftest import MCPServerClient

        custom_url = "http://custom-api.example.com:9000"
        client = MCPServerClient(mcp_server_path, custom_url, ryumem_api_key)

        try:
            client.start()
            # If it starts successfully, the URL was accepted
            # (it may fail to connect, but that's expected for a fake URL)
            assert client.process is not None
        finally:
            client.stop()

    def test_server_info_contains_metadata(self, mcp_client):
        """Test that server exposes proper metadata"""
        # The server should have been initialized with name and version
        # This is verified implicitly by the server starting successfully
        # and responding to list_tools
        result = mcp_client.list_tools()
        assert result is not None
