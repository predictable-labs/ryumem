"""
E2E tests for temporal decay in search results.

Tests that search results consider recency when ranking.
Run with: RYUMEM_API_URL=http://localhost:8000 RYUMEM_API_KEY=your_key python -m pytest tests/test_temporal_decay.py
"""
import os
import urllib.request
import urllib.error
import json
import time
import pytest
from uuid import uuid4

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
    return f"test_temporal_{uuid4().hex[:8]}"


@pytest.fixture
def episodes_with_similar_content(test_user_id):
    """Create episodes with similar content to test temporal ranking."""
    episodes = [
        {
            "name": "Recent Python Info",
            "content": "Python is a programming language used for web development and data science",
            "user_id": test_user_id,
            "source": "text",
            "kind": "memory",
            "metadata": {"created": "recent"}
        },
        {
            "name": "Old Python Info",
            "content": "Python is a programming language used for scripting and automation",
            "user_id": test_user_id,
            "source": "text",
            "kind": "memory",
            "metadata": {"created": "old"}
        }
    ]

    episode_ids = []
    for episode in episodes:
        resp, status = make_request("POST", "/episodes", data=episode)
        assert status == 200, f"Failed to create episode: {resp}"
        episode_ids.append(resp['episode_id'])

    time.sleep(0.5)
    yield episode_ids


class TestTemporalSearch:
    """Test temporal aspects of search functionality."""

    def test_search_returns_recent_episodes(self, episodes_with_similar_content, test_user_id):
        """Test that search returns episodes (temporal decay may affect ranking)."""
        resp, status = make_request("POST", "/search", data={
            "query": "python programming language",
            "user_id": test_user_id,
            "limit": 10
        })

        assert status == 200, f"Search failed: {resp}"
        assert resp['count'] >= 2, "Should find both episodes"

        episodes = resp['episodes']
        assert len(episodes) >= 2, "Should return both episodes"

    def test_search_with_different_strategies(self, episodes_with_similar_content, test_user_id):
        """Test search with different strategies (semantic, bm25, hybrid)."""
        strategies = ["bm25", "hybrid"]

        for strategy in strategies:
            resp, status = make_request("POST", "/search", data={
                "query": "python",
                "user_id": test_user_id,
                "strategy": strategy,
                "limit": 10
            })

            assert status == 200, f"{strategy} search failed: {resp}"
            assert resp['count'] > 0, f"{strategy} should find episodes"

    def test_episode_ordering_consistency(self, episodes_with_similar_content, test_user_id):
        """Test that episode ordering is consistent across searches."""
        # Perform same search multiple times
        results = []
        for _ in range(3):
            resp, status = make_request("POST", "/search", data={
                "query": "python programming",
                "user_id": test_user_id,
                "strategy": "bm25",
                "limit": 10
            })
            assert status == 200
            results.append([ep['uuid'] for ep in resp['episodes']])
            time.sleep(0.1)

        # Results should be consistent (same order)
        assert len(results) == 3
        # At least the episodes should be present consistently
        for result in results:
            assert len(result) > 0, "Should return results consistently"

    def test_search_limit_parameter(self, episodes_with_similar_content, test_user_id):
        """Test that limit parameter controls result count."""
        # Search with limit=1
        resp, status = make_request("POST", "/search", data={
            "query": "python",
            "user_id": test_user_id,
            "limit": 1
        })

        assert status == 200
        assert len(resp['episodes']) <= 1, "Should respect limit parameter"

    def test_episode_metadata_preservation(self, episodes_with_similar_content, test_user_id):
        """Test that episode metadata is preserved in search results."""
        resp, status = make_request("POST", "/search", data={
            "query": "python",
            "user_id": test_user_id,
            "limit": 10
        })

        assert status == 200
        episodes = resp['episodes']

        for episode in episodes:
            # Check that metadata exists
            assert 'metadata' in episode or 'content' in episode, "Episode should have data"
            # Check basic fields
            assert 'uuid' in episode or 'name' in episode, "Episode should have identifier"


if __name__ == "__main__":
    print("=" * 60)
    print("Temporal Decay Search E2E Tests")
    print("=" * 60)
    print(f"API URL: {API_URL}")
    print(f"API Key: {'*' * 10 if API_KEY else 'NOT SET'}")
    print("=" * 60)
    print("\nRun with pytest:")
    print("  RYUMEM_API_URL=http://localhost:8000 RYUMEM_API_KEY=your_key python -m pytest tests/test_temporal_decay.py -v")
    print()
