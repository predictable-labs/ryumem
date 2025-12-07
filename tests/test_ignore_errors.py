"""
Test that ignore_errors configuration is respected for API errors.

This test demonstrates the bug where API 500 errors raise exceptions
even when ignore_errors=True.
"""
import pytest
import requests
from unittest.mock import Mock, patch, MagicMock
from ryumem.main import Ryumem
from ryumem.core.config import RyumemConfig, ToolTrackingConfig


@pytest.fixture
def mock_response_500():
    """Create a mock response that simulates a 500 error."""
    response = Mock(spec=requests.Response)
    response.status_code = 500
    response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "500 Server Error: Internal Server Error for url: https://api.ryumem.io/episodes/session/test-session"
    )
    response.json.return_value = {"error": "Internal Server Error"}
    return response


@pytest.fixture
def ryumem_with_ignore_errors_true():
    """Create Ryumem instance with ignore_errors=True."""
    # Uses RYUMEM_API_URL and RYUMEM_API_KEY from environment
    ryumem = Ryumem(ignore_errors=True)
    yield ryumem


@pytest.fixture
def ryumem_with_ignore_errors_false():
    """Create Ryumem instance with ignore_errors=False."""
    # Uses RYUMEM_API_URL and RYUMEM_API_KEY from environment
    ryumem = Ryumem(ignore_errors=False)
    yield ryumem


class TestIgnoreErrorsForAPIErrors:
    """Test suite for ignore_errors configuration with API errors."""

    def test_get_with_500_error_and_ignore_errors_true_should_not_raise(
        self, ryumem_with_ignore_errors_true, mock_response_500
    ):
        """
        EXPECTED BEHAVIOR: When ignore_errors=True and API returns 500,
        _get() should log the error and return None instead of raising.

        CURRENT BEHAVIOR: This test will FAIL because _get() raises HTTPError
        regardless of ignore_errors setting.
        """
        ryumem = ryumem_with_ignore_errors_true

        with patch('requests.get', return_value=mock_response_500):
            # This should NOT raise when ignore_errors=True
            result = ryumem._get("/episodes/session/test-session")

            # Should return None when error is ignored
            assert result is None

    def test_get_with_500_error_and_ignore_errors_false_should_raise(
        self, ryumem_with_ignore_errors_false, mock_response_500
    ):
        """
        EXPECTED BEHAVIOR: When ignore_errors=False and API returns 500,
        _get() should raise HTTPError.

        This test should pass (current behavior is correct for this case).
        """
        ryumem = ryumem_with_ignore_errors_false

        with patch('requests.get', return_value=mock_response_500):
            # This SHOULD raise when ignore_errors=False
            with pytest.raises(requests.exceptions.HTTPError):
                ryumem._get("/episodes/session/test-session")

    def test_get_episode_by_session_id_with_500_and_ignore_errors_true(
        self, ryumem_with_ignore_errors_true, mock_response_500
    ):
        """
        TEST CUSTOMER SCENARIO: Query augmentation calls get_episode_by_session_id()
        which gets a 500 error. With ignore_errors=True, it should return None
        and allow workflow to continue.

        CURRENT BEHAVIOR: This test will FAIL - raises HTTPError and crashes workflow.
        """
        ryumem = ryumem_with_ignore_errors_true

        with patch('requests.get', return_value=mock_response_500):
            # Should return None instead of raising
            result = ryumem.get_episode_by_session_id("test-session")
            assert result is None

    def test_post_with_500_error_and_ignore_errors_true_should_not_raise(
        self, ryumem_with_ignore_errors_true, mock_response_500
    ):
        """
        Test that _post() respects ignore_errors=True for 500 errors.

        CURRENT BEHAVIOR: This test will FAIL.
        """
        ryumem = ryumem_with_ignore_errors_true

        with patch('requests.post', return_value=mock_response_500):
            result = ryumem._post("/some/endpoint", json={"data": "test"})
            assert result is None

    def test_patch_with_500_error_and_ignore_errors_true_should_not_raise(
        self, ryumem_with_ignore_errors_true, mock_response_500
    ):
        """
        Test that _patch() respects ignore_errors=True for 500 errors.

        CURRENT BEHAVIOR: This test will FAIL.
        """
        ryumem = ryumem_with_ignore_errors_true

        with patch('requests.patch', return_value=mock_response_500):
            result = ryumem._patch("/some/endpoint", json={"data": "test"})
            assert result is None

    def test_delete_with_500_error_and_ignore_errors_true_should_not_raise(
        self, ryumem_with_ignore_errors_true, mock_response_500
    ):
        """
        Test that _delete() respects ignore_errors=True for 500 errors.

        CURRENT BEHAVIOR: This test will FAIL.
        """
        ryumem = ryumem_with_ignore_errors_true

        with patch('requests.delete', return_value=mock_response_500):
            result = ryumem._delete("/some/endpoint")
            assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
