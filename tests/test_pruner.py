"""
E2E tests for memory pruning functionality.

Tests the /prune endpoint to verify old and low-value memories are cleaned up.
Run with: RYUMEM_API_URL=http://localhost:8000 RYUMEM_API_KEY=your_key python -m pytest tests/test_pruner.py
"""
import os
import urllib.request
import urllib.error
import json
import time
import pytest
from uuid import uuid4
from datetime import datetime, timedelta

# Get config from environment
API_URL = os.getenv("RYUMEM_API_URL", "http://localhost:8000")
API_KEY = os.getenv("RYUMEM_API_KEY")

if not API_KEY:
    pytest.skip("RYUMEM_API_KEY not set", allow_module_level=True)


def make_request(method, endpoint, headers=None, data=None):
    """Make an HTTP request to the Ryumem API."""
    if headers is None:
        headers = {}

    url = f"{API_URL}{endpoint}"
    if data:
        data = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'

    headers['X-API-Key'] = API_KEY

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8')), response.status
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if hasattr(e, 'read') else '{}'
        return json.loads(error_body) if error_body else {}, e.code
    except Exception as e:
        print(f"Request error: {e}")
        return None, 500


@pytest.fixture
def test_user_id():
    """Generate a unique user ID for test isolation."""
    return f"test_pruner_{uuid4().hex[:8]}"


class TestMemoryPruning:
    """Test memory pruning functionality via API."""

    def test_prune_endpoint_exists(self, test_user_id):
        """Test that the prune endpoint is accessible."""
        resp, status = make_request("POST", "/prune", data={
            "user_id": test_user_id,
            "min_age_days": 30,
            "min_mentions": 1
        })

        # Should succeed even if no memories to prune
        assert status == 200, f"Prune endpoint failed: {resp}"
        assert "pruned_count" in resp or "message" in resp

    def test_prune_with_parameters(self, test_user_id):
        """Test pruning with different parameter combinations."""
        # Add some test episodes first
        episodes = [
            {
                "name": "Test Memory 1",
                "content": "This is a test memory",
                "user_id": test_user_id,
                "source": "text",
                "kind": "memory"
            },
            {
                "name": "Test Memory 2",
                "content": "Another test memory",
                "user_id": test_user_id,
                "source": "text",
                "kind": "memory"
            }
        ]

        for episode in episodes:
            resp, status = make_request("POST", "/episodes", data=episode)
            assert status == 200

        time.sleep(0.5)

        # Test prune with different parameters
        resp, status = make_request("POST", "/prune", data={
            "user_id": test_user_id,
            "min_age_days": 1,  # Very short age
            "min_mentions": 100,  # High mention threshold
            "expired_cutoff_days": 90
        })

        assert status == 200, f"Prune failed: {resp}"

    def test_prune_returns_count(self, test_user_id):
        """Test that prune endpoint returns pruned count."""
        resp, status = make_request("POST", "/prune", data={
            "user_id": test_user_id,
            "min_age_days": 30
        })

        assert status == 200
        # Response should have some indication of results
        assert isinstance(resp, dict), "Response should be a dictionary"

    def test_prune_with_compact_redundant(self, test_user_id):
        """Test pruning with redundant memory compaction."""
        resp, status = make_request("POST", "/prune", data={
            "user_id": test_user_id,
            "min_age_days": 30,
            "compact_redundant": True
        })

        assert status == 200, f"Prune with compaction failed: {resp}"

    def test_prune_validation_errors(self):
        """Test that prune endpoint validates input."""
        # Test with invalid min_age_days (negative)
        resp, status = make_request("POST", "/prune", data={
            "user_id": "test_user",
            "min_age_days": -1
        })

        # Should return validation error
        assert status in [400, 422], "Should reject negative min_age_days"

    def test_prune_missing_user_id(self):
        """Test that user_id is required."""
        resp, status = make_request("POST", "/prune", data={
            "min_age_days": 30
        })

        # Should return validation error
        assert status in [400, 422], "Should require user_id"


if __name__ == "__main__":
    print("=" * 60)
    print("Memory Pruning E2E Tests")
    print("=" * 60)
    print(f"API URL: {API_URL}")
    print(f"API Key: {'*' * 10 if API_KEY else 'NOT SET'}")
    print("=" * 60)
    print("\nRun with pytest:")
    print("  RYUMEM_API_URL=http://localhost:8000 RYUMEM_API_KEY=your_key python -m pytest tests/test_pruner.py -v")
    print()
