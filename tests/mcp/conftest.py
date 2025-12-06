"""
Pytest fixtures for MCP integration tests
"""

import json
import subprocess
import time
from typing import Dict, Any, Optional
import pytest
import requests
from pathlib import Path


@pytest.fixture(scope="session")
def mcp_server_path():
    """Path to the built MCP server"""
    project_root = Path(__file__).parent.parent.parent
    server_path = project_root / "mcp-server-ts" / "build" / "index.js"

    if not server_path.exists():
        pytest.skip(f"MCP server not built at {server_path}. Run 'npm run build' in mcp-server-ts/")

    return str(server_path)


@pytest.fixture(scope="session")
def ryumem_api_url():
    """URL for the Ryumem API (can be mocked or real)"""
    import os
    # Use local test server if available, otherwise skip
    url = os.getenv("RYUMEM_TEST_API_URL", "http://localhost:8000")
    return url


@pytest.fixture(scope="session")
def ryumem_api_key():
    """API key for testing"""
    import os
    return os.getenv("RYUMEM_API_KEY", "test-api-key")


class MCPServerClient:
    """Client for interacting with the MCP server via stdio"""

    def __init__(self, server_path: str, api_url: str, api_key: str):
        self.server_path = server_path
        self.api_url = api_url
        self.api_key = api_key
        self.process: Optional[subprocess.Popen] = None
        self._request_id = 0

    def start(self):
        """Start the MCP server process"""
        env = {
            "RYUMEM_API_URL": self.api_url,
            "RYUMEM_API_KEY": self.api_key,
            "NODE_ENV": "test"
        }

        self.process = subprocess.Popen(
            ["node", self.server_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**subprocess.os.environ, **env},
            text=True,
            bufsize=1
        )

        # Give server time to start
        time.sleep(0.5)

        if self.process.poll() is not None:
            stderr = self.process.stderr.read() if self.process.stderr else ""
            raise RuntimeError(f"MCP server failed to start: {stderr}")

    def stop(self):
        """Stop the MCP server process"""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

    def send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON-RPC request to the MCP server"""
        if not self.process or self.process.poll() is not None:
            raise RuntimeError("MCP server is not running")

        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params
        }

        # Send request
        request_str = json.dumps(request) + "\n"
        self.process.stdin.write(request_str)
        self.process.stdin.flush()

        # Read response
        response_str = self.process.stdout.readline()
        if not response_str:
            stderr = self.process.stderr.read() if self.process.stderr else ""
            raise RuntimeError(f"No response from MCP server. stderr: {stderr}")

        response = json.loads(response_str)

        if "error" in response:
            raise RuntimeError(f"MCP error: {response['error']}")

        result = response.get("result", {})

        # Check if the tool call returned an error
        if isinstance(result, dict) and result.get("isError"):
            # Extract error message from content
            content = result.get("content", [])
            if content and isinstance(content, list) and len(content) > 0:
                error_text = content[0].get("text", "Unknown error")
                raise RuntimeError(error_text)
            raise RuntimeError("Tool call failed with unknown error")

        return result

    def list_tools(self) -> Dict[str, Any]:
        """List available tools"""
        return self.send_request("tools/list", {})

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool"""
        return self.send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })


@pytest.fixture
def mcp_client(mcp_server_path, ryumem_api_url, ryumem_api_key):
    """
    Fixture that provides an MCP client connected to the server
    """
    client = MCPServerClient(mcp_server_path, ryumem_api_url, ryumem_api_key)
    client.start()

    yield client

    client.stop()


@pytest.fixture
def mock_api_server():
    """
    Fixture that provides a mock Ryumem API server for testing
    This can be used when you don't want to rely on a real API server
    """
    from unittest.mock import Mock

    # TODO: Implement a mock HTTP server if needed
    # For now, tests will use a real API server
    pytest.skip("Mock API server not implemented yet")


@pytest.fixture
def test_user_id():
    """Generate a unique user ID for testing"""
    import uuid
    return f"test-user-{uuid.uuid4()}"


@pytest.fixture
def test_session_id():
    """Generate a unique session ID for testing"""
    import uuid
    return f"test-session-{uuid.uuid4()}"


@pytest.fixture
def sample_episode_data(test_user_id, test_session_id):
    """Sample episode data for testing"""
    return {
        "content": "This is a test memory about machine learning concepts.",
        "user_id": test_user_id,
        "session_id": test_session_id,
        "kind": "memory",
        "source": "text",
        "metadata": {
            "topic": "machine-learning",
            "tags": ["test", "ml"]
        }
    }


@pytest.fixture
def verify_api_available(ryumem_api_url):
    """
    Verify that the Ryumem API is available before running tests
    """
    try:
        response = requests.get(f"{ryumem_api_url}/health", timeout=2)
        if response.status_code != 200:
            pytest.skip(f"Ryumem API not healthy at {ryumem_api_url}")
    except requests.exceptions.RequestException:
        pytest.skip(f"Ryumem API not available at {ryumem_api_url}")
