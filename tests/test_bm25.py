"""
E2E tests for BM25 keyword search index episode persistence.

Tests that episodes are indexed in BM25 and searchable via the API.
Run with: RYUMEM_API_URL=http://localhost:8000 RYUMEM_API_KEY=your_key python -m pytest tests/test_bm25.py
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
    return f"test_user_{uuid4().hex[:8]}"


@pytest.fixture
def test_episodes(test_user_id):
    """Create test episodes and clean up after test."""
    episodes = [
        {
            "content": "Python is a high-level programming language known for readability",
            "user_id": test_user_id,
            "source": "text",
            "kind": "memory",
            "metadata": {"tags": ["python", "programming"], "test": True}
        },
        {
            "content": "JavaScript is used for web development and runs in browsers",
            "user_id": test_user_id,
            "source": "text",
            "kind": "memory",
            "metadata": {"tags": ["javascript", "web"], "test": True}
        },
        {
            "content": "PostgreSQL is a powerful relational database system",
            "user_id": test_user_id,
            "source": "text",
            "kind": "memory",
            "metadata": {"tags": ["database", "postgresql"], "test": True}
        }
    ]

    episode_ids = []
    for episode in episodes:
        resp, status = make_request("POST", "/episodes", data=episode)
        assert status == 200, f"Failed to create episode: {resp}"
        episode_ids.append(resp['episode_id'])

    # Give BM25 index time to update
    time.sleep(0.5)

    yield episode_ids

    # Cleanup is handled by using unique user_id per test


class TestBM25Search:
    """Test BM25 keyword search functionality via API."""

    def test_add_and_search_episodes(self, test_episodes, test_user_id):
        """Test that episodes are indexed and searchable via BM25."""
        # Search for Python-related content
        resp, status = make_request("POST", "/search", data={
            "query": "programming language",
            "user_id": test_user_id,
            "strategy": "bm25",
            "limit": 5
        })

        assert status == 200, f"Search failed: {resp}"
        assert resp['count'] > 0, "No episodes found"

        episodes = resp['episodes']
        contents = [ep['content'] for ep in episodes]
        assert any("Python" in content and "programming language" in content for content in contents), \
            f"Python programming language episode not found. Found: {contents}"

    def test_search_multiple_keywords(self, test_episodes, test_user_id):
        """Test BM25 search with multiple keywords."""
        resp, status = make_request("POST", "/search", data={
            "query": "python readability",
            "user_id": test_user_id,
            "strategy": "bm25",
            "limit": 5
        })

        assert status == 200, f"Search failed: {resp}"
        assert resp['count'] > 0, "No episodes found for multi-keyword search"

        episodes = resp['episodes']
        contents = [ep['content'] for ep in episodes]
        assert any("Python" in content and "readability" in content for content in contents), \
            "Python episode with readability should be found"

    def test_search_no_results_for_nonexistent(self, test_episodes, test_user_id):
        """Test that irrelevant queries return no or low-ranked results."""
        resp, status = make_request("POST", "/search", data={
            "query": "quantum physics superposition",
            "user_id": test_user_id,
            "strategy": "bm25",
            "min_bm25_score": 1.0,  # High threshold
            "limit": 5
        })

        assert status == 200, f"Search failed: {resp}"
        # Should return 0 or very few results with high threshold
        assert resp['count'] <= 1, "Irrelevant query should not match well"

    def test_bm25_hybrid_comparison(self, test_episodes, test_user_id):
        """Test that BM25 and hybrid strategies both work."""
        # BM25 search
        bm25_resp, status = make_request("POST", "/search", data={
            "query": "web development",
            "user_id": test_user_id,
            "strategy": "bm25",
            "limit": 5
        })
        assert status == 200, f"BM25 search failed: {bm25_resp}"

        # Hybrid search (should also include BM25 results)
        hybrid_resp, status = make_request("POST", "/search", data={
            "query": "web development",
            "user_id": test_user_id,
            "strategy": "hybrid",
            "limit": 5
        })
        assert status == 200, f"Hybrid search failed: {hybrid_resp}"

        # Both should find results
        assert bm25_resp['count'] > 0, "BM25 should find results"
        assert hybrid_resp['count'] > 0, "Hybrid should find results"

    def test_episode_persistence_check(self, test_episodes, test_user_id):
        """Test that episodes persist in the database."""
        # List all episodes for this user
        resp, status = make_request("GET", f"/episodes?user_id={test_user_id}&limit=100")

        assert status == 200, f"Failed to list episodes: {resp}"
        episodes = resp['episodes']

        # Should have at least our test episodes
        assert len(episodes) >= 3, f"Expected at least 3 episodes, got {len(episodes)}"

        # Verify our episodes are in the list by checking content
        episode_contents = [ep['content'] for ep in episodes]
        assert any("Python" in content and "programming language" in content for content in episode_contents), \
            "Python episode not found in persisted episodes"
        assert any("JavaScript" in content and "web development" in content for content in episode_contents), \
            "JavaScript episode not found in persisted episodes"
        assert any("PostgreSQL" in content and "database system" in content for content in episode_contents), \
            "PostgreSQL episode not found in persisted episodes"


class TestBM25EdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_query_search(self, test_user_id):
        """Test BM25 search with empty query."""
        resp, status = make_request("POST", "/search", data={
            "query": "",
            "user_id": test_user_id,
            "strategy": "bm25",
            "limit": 5
        })

        # Should handle gracefully (return empty or all results depending on implementation)
        assert status in [200, 400, 422], f"Unexpected status for empty query: {status}"

    def test_search_nonexistent_user(self):
        """Test search for user with no episodes."""
        nonexistent_user = f"nonexistent_user_{uuid4().hex[:8]}"
        resp, status = make_request("POST", "/search", data={
            "query": "test",
            "user_id": nonexistent_user,
            "strategy": "bm25",
            "limit": 5
        })

        assert status == 200, f"Search failed: {resp}"
        assert resp['count'] == 0, "Should return 0 results for user with no episodes"

    def test_case_insensitive_search(self, test_episodes, test_user_id):
        """Test that BM25 search is case-insensitive."""
        # Search with different casing
        resp1, status1 = make_request("POST", "/search", data={
            "query": "PYTHON",
            "user_id": test_user_id,
            "strategy": "bm25",
            "limit": 5
        })

        resp2, status2 = make_request("POST", "/search", data={
            "query": "python",
            "user_id": test_user_id,
            "strategy": "bm25",
            "limit": 5
        })

        assert status1 == 200 and status2 == 200
        # Should return same results (BM25 tokenization is lowercase)
        assert resp1['count'] == resp2['count'], "Case should not affect search results"


if __name__ == "__main__":
    print("=" * 60)
    print("BM25 Episode Persistence E2E Tests")
    print("=" * 60)
    print(f"API URL: {API_URL}")
    print(f"API Key: {'*' * 10 if API_KEY else 'NOT SET'}")
    print("=" * 60)
    print("\nRun with pytest:")
    print("  RYUMEM_API_URL=http://localhost:8000 RYUMEM_API_KEY=your_key python -m pytest tests/test_bm25.py -v")
    print()
