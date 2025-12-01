"""
Comprehensive tests for ToolTracker with minimal mocking.

These tests use real Ryumem instances and test actual functionality.
Only external dependencies and Google ADK components are mocked.
"""

import pytest
import os
import uuid
import time
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from ryumem import Ryumem
from ryumem.integrations.tool_tracker import ToolTracker
from ryumem.core.metadata_models import EpisodeMetadata, QueryRun


# ===== Pytest Hooks for Test Result Tracking =====

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to capture test results for cleanup logic."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


# ===== Minimal Mock Objects =====

class SimpleAgent:
    """Minimal agent for testing."""
    def __init__(self):
        self.name = "test_agent"
        self.tools = []


def simple_sync_tool(x: int, y: int) -> int:
    """Add two numbers."""
    return x + y


async def simple_async_tool(text: str) -> str:
    """Echo text back."""
    return f"Echo: {text}"


# ===== Test Fixtures =====

@pytest.fixture(scope="session")
def ryumem_session():
    """Session-scoped Ryumem instance for cleanup."""
    return Ryumem()


@pytest.fixture
def ryumem():
    """Real Ryumem instance - NO MOCKING."""
    return Ryumem()


@pytest.fixture
def tracker(ryumem):
    """Real ToolTracker instance."""
    return ToolTracker(ryumem=ryumem)


@pytest.fixture
def unique_user(request, ryumem_session):
    """Generate unique user ID for test isolation with cleanup."""
    user_id = f"test_user_{uuid.uuid4().hex[:8]}"

    # Register cleanup to delete all test data after test completes successfully
    def cleanup():
        # Only clean up if test passed (no exceptions)
        # Check if rep_call exists and if the test passed
        if hasattr(request.node, 'rep_call') and request.node.rep_call.passed:
            try:
                ryumem_session.reset_database()
                print(f"✓ Cleaned up test data for {user_id}")
            except Exception as e:
                print(f"Warning: Cleanup failed for {user_id}: {e}")
        else:
            # Test failed or status unavailable - skip cleanup to preserve data for debugging
            print(f"⚠ Test failed or status unavailable - skipping cleanup for {user_id} (data preserved for debugging)")

    request.addfinalizer(cleanup)
    return user_id


# ===== Test Classes =====

class TestToolTrackerInitialization:
    """Test ToolTracker initialization."""

    def test_init_with_ryumem(self, ryumem):
        """Test tracker initializes with real Ryumem."""
        tracker = ToolTracker(ryumem=ryumem)

        assert tracker.ryumem is ryumem
        assert tracker._execution_count == 0
        assert tracker.async_classification is True
        assert isinstance(tracker._background_tasks, set)

    def test_reads_config_from_ryumem(self, ryumem):
        """Test tracker reads configuration from Ryumem."""
        tracker = ToolTracker(ryumem=ryumem)

        # Should have access to config
        assert hasattr(tracker.ryumem, 'config')
        assert hasattr(tracker.ryumem.config, 'tool_tracking')


class TestToolRegistration:
    """Test tool registration functionality."""

    def test_register_single_tool(self, tracker):
        """Test registering a single tool."""
        tools = [
            {
                "name": f"test_tool_{uuid.uuid4().hex[:8]}",
                "description": "A test tool that does testing"
            }
        ]

        # Should not raise
        tracker.register_tools(tools)

    def test_register_multiple_tools(self, tracker):
        """Test registering multiple tools."""
        base_name = uuid.uuid4().hex[:8]
        tools = [
            {"name": f"tool_a_{base_name}", "description": "Tool A"},
            {"name": f"tool_b_{base_name}", "description": "Tool B"},
            {"name": f"tool_c_{base_name}", "description": "Tool C"},
        ]

        tracker.register_tools(tools)

    def test_register_tool_without_name(self, tracker):
        """Test registering tool without name is skipped."""
        tools = [
            {"description": "Tool without name"}
        ]

        # Should not raise, just skip
        tracker.register_tools(tools)

    def test_register_duplicate_tool_skipped(self, tracker):
        """Test that duplicate tools are skipped."""
        tool_name = f"duplicate_tool_{uuid.uuid4().hex[:8]}"
        tools = [
            {"name": tool_name, "description": "First registration"}
        ]

        # Register first time
        tracker.register_tools(tools)

        # Register again - should be skipped
        tracker.register_tools(tools)


class TestSamplingRate:
    """Test sampling rate functionality."""

    def test_should_track_with_100_percent(self, ryumem):
        """Test tracking happens 100% with sample_rate=1.0."""
        # Force sample rate to 100%
        with_tracking = ToolTracker(ryumem=ryumem)

        # Patch the config temporarily
        original_rate = ryumem.config.tool_tracking.sample_rate
        try:
            ryumem.config.tool_tracking.sample_rate = 1.0

            # Should always return True
            results = [with_tracking._should_track() for _ in range(10)]
            assert all(results), "All samples should be tracked at 100%"
        finally:
            ryumem.config.tool_tracking.sample_rate = original_rate

    def test_should_track_with_0_percent(self, ryumem):
        """Test tracking never happens with sample_rate=0.0."""
        tracker = ToolTracker(ryumem=ryumem)

        original_rate = ryumem.config.tool_tracking.sample_rate
        try:
            ryumem.config.tool_tracking.sample_rate = 0.0

            # Should always return False
            results = [tracker._should_track() for _ in range(10)]
            assert not any(results), "No samples should be tracked at 0%"
        finally:
            ryumem.config.tool_tracking.sample_rate = original_rate


class TestPIISanitization:
    """Test PII sanitization functionality."""

    def test_sanitize_email(self, tracker):
        """Test email sanitization."""
        original_rate = tracker.ryumem.config.tool_tracking.sanitize_pii
        try:
            tracker.ryumem.config.tool_tracking.sanitize_pii = True

            text = "Contact me at john.doe@example.com for details"
            sanitized = tracker._sanitize_value(text)

            assert "[EMAIL]" in sanitized
            assert "john.doe@example.com" not in sanitized
        finally:
            tracker.ryumem.config.tool_tracking.sanitize_pii = original_rate

    def test_sanitize_phone(self, tracker):
        """Test phone number sanitization."""
        original_rate = tracker.ryumem.config.tool_tracking.sanitize_pii
        try:
            tracker.ryumem.config.tool_tracking.sanitize_pii = True

            text = "Call me at 555-123-4567"
            sanitized = tracker._sanitize_value(text)

            assert "[PHONE]" in sanitized
            assert "555-123-4567" not in sanitized
        finally:
            tracker.ryumem.config.tool_tracking.sanitize_pii = original_rate

    def test_sanitize_disabled(self, tracker):
        """Test that sanitization can be disabled."""
        original_rate = tracker.ryumem.config.tool_tracking.sanitize_pii
        try:
            tracker.ryumem.config.tool_tracking.sanitize_pii = False

            text = "Email: test@example.com, Phone: 555-1234"
            sanitized = tracker._sanitize_value(text)

            # Should not sanitize when disabled
            assert sanitized == text
        finally:
            tracker.ryumem.config.tool_tracking.sanitize_pii = original_rate

    def test_sanitize_params_redacts_sensitive_keys(self, tracker):
        """Test that sensitive parameter keys are redacted."""
        params = {
            "username": "john",
            "password": "secret123",
            "api_key": "abc123",
            "data": "public info"
        }

        sanitized = tracker._sanitize_params(params)

        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["api_key"] == "[REDACTED]"
        assert sanitized["username"] == "john"
        assert sanitized["data"] == "public info"


class TestOutputSummarization:
    """Test output summarization functionality."""

    def test_summarize_short_string(self, tracker):
        """Test short strings are not truncated."""
        output = "Short result"
        summary = tracker._summarize_output(output)

        assert summary == "Short result"

    def test_summarize_long_string(self, tracker):
        """Test long strings are truncated based on config."""
        original_max = tracker.ryumem.config.tool_tracking.max_output_chars
        original_summarize = tracker.ryumem.config.tool_tracking.summarize_outputs
        try:
            tracker.ryumem.config.tool_tracking.summarize_outputs = True
            tracker.ryumem.config.tool_tracking.max_output_chars = 50

            output = "x" * 100
            summary = tracker._summarize_output(output)

            # Should be truncated or at least not longer than original
            assert len(summary) <= len(output), "Summary should not be longer than original"

            # If summarization is working, it should be truncated
            if tracker.ryumem.config.tool_tracking.summarize_outputs and len(output) > tracker.ryumem.config.tool_tracking.max_output_chars:
                assert len(summary) <= tracker.ryumem.config.tool_tracking.max_output_chars + 35
        finally:
            tracker.ryumem.config.tool_tracking.max_output_chars = original_max
            tracker.ryumem.config.tool_tracking.summarize_outputs = original_summarize

    def test_summarize_dict(self, tracker):
        """Test dict outputs are converted to JSON."""
        output = {"status": "success", "count": 42}
        summary = tracker._summarize_output(output)

        assert isinstance(summary, str)
        assert "status" in summary
        assert "success" in summary

    def test_summarize_none(self, tracker):
        """Test None output is handled."""
        output = None
        summary = tracker._summarize_output(output)

        assert summary == "None"


class TestToolWrapping:
    """Test tool function wrapping."""

    def test_create_wrapper_for_sync_function(self, tracker):
        """Test creating wrapper for synchronous function."""
        wrapper = tracker.create_wrapper(
            func=simple_sync_tool,
            tool_name="simple_sync_tool",
            tool_description="Adds two numbers"
        )

        # Wrapper should be callable
        assert callable(wrapper)

        # Wrapper should work
        result = wrapper(5, 3)
        assert result == 8

    @pytest.mark.asyncio
    async def test_create_wrapper_for_async_function(self, tracker):
        """Test creating wrapper for async function."""
        wrapper = tracker.create_wrapper(
            func=simple_async_tool,
            tool_name="simple_async_tool",
            tool_description="Echoes text"
        )

        # Wrapper should be callable
        assert callable(wrapper)

        # Wrapper should work
        result = await wrapper("hello")
        assert result == "Echo: hello"


class TestAgentToolsWrapping:
    """Test wrapping all tools on an agent."""

    def test_wrap_agent_tools(self, tracker):
        """Test wrapping tools on an agent."""
        agent = SimpleAgent()

        # Add some mock tools
        tool1 = Mock()
        tool1.__name__ = "tool_one"
        tool1.name = "tool_one"

        tool2 = Mock()
        tool2.__name__ = "tool_two"
        tool2.name = "tool_two"

        agent.tools = [tool1, tool2]

        # Wrap the tools
        tracker.wrap_agent_tools(agent)

        # Tools should still be in the list
        assert len(agent.tools) >= 2


class TestErrorHandling:
    """Test error handling in various scenarios."""

    def test_register_tools_error_with_ignore_errors(self, ryumem):
        """Test that errors are ignored when ignore_errors=True."""
        tracker = ToolTracker(ryumem=ryumem)

        original_ignore = ryumem.config.tool_tracking.ignore_errors
        try:
            ryumem.config.tool_tracking.ignore_errors = True

            # This should not raise even if there's an error
            # Pass invalid tool data
            tools = [{"name": None}]  # Will cause issues but should be ignored
            tracker.register_tools(tools)
        finally:
            ryumem.config.tool_tracking.ignore_errors = original_ignore

    def test_sanitize_non_string_value(self, tracker):
        """Test sanitizing non-string values doesn't crash."""
        values = [123, None, {"key": "value"}, [1, 2, 3]]

        for value in values:
            result = tracker._sanitize_value(value)
            # Should return as-is for non-strings
            assert result == value


class TestBackgroundTasks:
    """Test background task management."""

    def test_background_tasks_set_exists(self, tracker):
        """Test that background tasks set is initialized."""
        assert hasattr(tracker, '_background_tasks')
        assert isinstance(tracker._background_tasks, set)

    def test_async_classification_enabled_by_default(self, tracker):
        """Test async classification is enabled by default."""
        assert tracker.async_classification is True


class TestTrackExecution:
    """Test the main track_execution method."""

    def test_track_execution_basic(self, tracker, unique_user):
        """Test basic execution tracking."""
        session_id = f"session_{uuid.uuid4().hex[:8]}"

        # Force sampling to 100%
        original_rate = tracker.ryumem.config.tool_tracking.sample_rate
        try:
            tracker.ryumem.config.tool_tracking.sample_rate = 1.0

            tracker.track_execution(
                tool_name="test_tool",
                tool_description="A test tool",
                input_params={"x": 1, "y": 2},
                output="3",
                success=True,
                error=None,
                duration_ms=100,
                user_id=unique_user,
                session_id=session_id
            )

            # Should increment execution count
            assert tracker._execution_count > 0
        finally:
            tracker.ryumem.config.tool_tracking.sample_rate = original_rate

    def test_track_execution_with_error(self, tracker, unique_user):
        """Test tracking failed execution."""
        session_id = f"session_{uuid.uuid4().hex[:8]}"

        original_rate = tracker.ryumem.config.tool_tracking.sample_rate
        try:
            tracker.ryumem.config.tool_tracking.sample_rate = 1.0

            tracker.track_execution(
                tool_name="failing_tool",
                tool_description="A failing tool",
                input_params={"value": "bad"},
                output=None,
                success=False,
                error="ValueError: Invalid input",
                duration_ms=50,
                user_id=unique_user,
                session_id=session_id
            )

            assert tracker._execution_count > 0
        finally:
            tracker.ryumem.config.tool_tracking.sample_rate = original_rate

    def test_track_execution_skipped_by_sampling(self, tracker, unique_user):
        """Test execution is skipped when sampling says no."""
        session_id = f"session_{uuid.uuid4().hex[:8]}"

        original_rate = tracker.ryumem.config.tool_tracking.sample_rate
        try:
            # Set to 0% - nothing should be tracked
            tracker.ryumem.config.tool_tracking.sample_rate = 0.0

            initial_count = tracker._execution_count

            tracker.track_execution(
                tool_name="test_tool",
                tool_description="A test tool",
                input_params={},
                output="result",
                success=True,
                error=None,
                duration_ms=100,
                user_id=unique_user,
                session_id=session_id
            )

            # Count should not change
            assert tracker._execution_count == initial_count
        finally:
            tracker.ryumem.config.tool_tracking.sample_rate = original_rate


class TestIntegrationWithRyumem:
    """Test integration with real Ryumem operations."""

    def test_tracker_uses_real_ryumem_config(self, ryumem):
        """Test tracker uses real Ryumem configuration."""
        tracker = ToolTracker(ryumem=ryumem)

        # Should have access to real config
        assert tracker.ryumem.config.tool_tracking.sample_rate >= 0
        assert tracker.ryumem.config.tool_tracking.sample_rate <= 1.0

    def test_tracker_can_access_ryumem_methods(self, ryumem):
        """Test tracker can call Ryumem methods."""
        tracker = ToolTracker(ryumem=ryumem)

        # Should be able to call Ryumem methods
        assert hasattr(tracker.ryumem, 'embed')
        assert hasattr(tracker.ryumem, 'save_tool')
        assert hasattr(tracker.ryumem, 'get_tool_by_name')


class TestParentChildToolTracking:
    """Integration tests for parent-child tool tracking with real Ryumem."""

    def _create_test_episode(self, ryumem, user_id, session_id):
        """Helper to create a test episode."""
        from datetime import datetime

        query_run = QueryRun(
            run_id=f"run_{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            timestamp=datetime.utcnow().isoformat(),
            query="Test query",
            agent_response="Test response",
            tools_used=[]
        )

        episode_metadata = EpisodeMetadata(
            integration="test",
            sessions={session_id: [query_run]}
        )

        # Save episode to Ryumem with source="message" so tool metrics query finds it
        episode_result = ryumem.add_episode(
            content="Test query",
            user_id=user_id,
            session_id=session_id,
            source="message",  # Required for tool metrics to work
            metadata=episode_metadata.model_dump()
        )

        return episode_result

    def _wait_for_tracking(self, timeout=2.0):
        """Wait for background tracking tasks to complete."""
        time.sleep(timeout)

    def test_parent_child_tracking_sync(self, tracker, ryumem, unique_user):
        """Test that parent tool calling child tool is tracked correctly."""
        session_id = f"session_{uuid.uuid4().hex[:8]}"

        # Force 100% sampling and synchronous tracking
        original_rate = tracker.ryumem.config.tool_tracking.sample_rate
        original_async = tracker.async_classification
        try:
            tracker.ryumem.config.tool_tracking.sample_rate = 1.0
            tracker.async_classification = False  # Use sync for simpler testing

            # Step 1: Register tools first (e2e flow)
            # Only register base tools - nested variants will be auto-registered on first use
            tracker.register_tools([
                {"name": "child_tool", "description": "Child tool"},
                {"name": "parent_tool", "description": "Parent tool"}
            ])

            # Step 2: Create episode to track against
            self._create_test_episode(ryumem, unique_user, session_id)

            # Step 3: Create child function
            def child_tool(user_id=None, session_id=None):
                return "child_result"

            # Create parent function that calls child
            def parent_tool(user_id=None, session_id=None):
                result = wrapped_child(user_id=user_id, session_id=session_id)
                return f"parent_result: {result}"

            # Wrap both functions
            wrapped_child = tracker.create_wrapper(
                child_tool,
                tool_name="child_tool",
                tool_description="Child tool"
            )

            wrapped_parent = tracker.create_wrapper(
                parent_tool,
                tool_name="parent_tool",
                tool_description="Parent tool"
            )

            # Execute parent (which calls child)
            result = wrapped_parent(user_id=unique_user, session_id=session_id)

            # Verify result
            assert result == "parent_result: child_result"

            # Wait for async tracking
            self._wait_for_tracking()

            # Verify tracking through episode metadata
            episode = ryumem.get_episode_by_session_id(session_id)
            assert episode is not None, "Episode should exist"

            metadata = EpisodeMetadata(**episode.metadata)
            latest_run = metadata.get_latest_run(session_id)
            assert latest_run is not None, "Run should exist"

            tools_used = latest_run.tools_used
            assert len(tools_used) == 2, f"Should have 2 tool executions, got {len(tools_used)}"

            # Child executes first (called from parent)
            child_exec = tools_used[0]
            assert child_exec.tool_name == "parent_tool.child_tool"
            assert child_exec.parent_tool_name == "parent_tool"

            # Parent completes second
            parent_exec = tools_used[1]
            assert parent_exec.tool_name == "parent_tool"
            assert parent_exec.parent_tool_name is None

        finally:
            tracker.ryumem.config.tool_tracking.sample_rate = original_rate
            tracker.async_classification = original_async

    def test_standalone_tool_no_parent(self, tracker, ryumem, unique_user):
        """Test that standalone tool has no parent."""
        session_id = f"session_{uuid.uuid4().hex[:8]}"

        # Force 100% sampling and synchronous tracking
        original_rate = tracker.ryumem.config.tool_tracking.sample_rate
        original_async = tracker.async_classification
        try:
            tracker.ryumem.config.tool_tracking.sample_rate = 1.0
            tracker.async_classification = False  # Use sync for simpler testing

            # Step 1: Register tool first (e2e flow)
            tracker.register_tools([
                {"name": "standalone_tool", "description": "Standalone tool"}
            ])

            # Step 2: Create episode
            self._create_test_episode(ryumem, unique_user, session_id)

            # Step 3: Create standalone function
            def standalone_tool(user_id=None, session_id=None):
                return "standalone_result"

            # Wrap function
            wrapped_standalone = tracker.create_wrapper(
                standalone_tool,
                tool_name="standalone_tool",
                tool_description="Standalone tool"
            )

            # Execute
            result = wrapped_standalone(user_id=unique_user, session_id=session_id)

            # Verify result
            assert result == "standalone_result"

            # Wait for async tracking
            self._wait_for_tracking()

            # Verify tracking
            episode = ryumem.get_episode_by_session_id(session_id)
            assert episode is not None

            metadata = EpisodeMetadata(**episode.metadata)
            latest_run = metadata.get_latest_run(session_id)
            tools_used = latest_run.tools_used

            assert len(tools_used) == 1
            exec_data = tools_used[0]
            assert exec_data.tool_name == "standalone_tool"
            assert exec_data.parent_tool_name is None

        finally:
            tracker.ryumem.config.tool_tracking.sample_rate = original_rate
            tracker.async_classification = original_async

    def test_recursive_tool_tracking(self, tracker, ryumem, unique_user):
        """Test that tool calling itself is tracked correctly."""
        session_id = f"session_{uuid.uuid4().hex[:8]}"

        # Force 100% sampling and synchronous tracking
        original_rate = tracker.ryumem.config.tool_tracking.sample_rate
        original_async = tracker.async_classification
        try:
            tracker.ryumem.config.tool_tracking.sample_rate = 1.0
            tracker.async_classification = False  # Use sync for simpler testing

            # Step 1: Register tool first (e2e flow)
            # Only register base tool - nested variant will be auto-registered on recursive call
            tracker.register_tools([
                {"name": "recursive_tool", "description": "Recursive tool"}
            ])

            # Step 2: Create episode
            self._create_test_episode(ryumem, unique_user, session_id)

            # Step 3: Create recursive function
            def recursive_tool(depth=0, user_id=None, session_id=None):
                if depth < 1:
                    return wrapped_recursive(depth=depth + 1, user_id=user_id, session_id=session_id)
                return "base_case"

            # Wrap function
            wrapped_recursive = tracker.create_wrapper(
                recursive_tool,
                tool_name="recursive_tool",
                tool_description="Recursive tool"
            )

            # Execute
            result = wrapped_recursive(depth=0, user_id=unique_user, session_id=session_id)

            # Verify result
            assert result == "base_case"

            # Wait for async tracking
            self._wait_for_tracking()

            # Verify tracking
            episode = ryumem.get_episode_by_session_id(session_id)
            assert episode is not None

            metadata = EpisodeMetadata(**episode.metadata)
            latest_run = metadata.get_latest_run(session_id)
            tools_used = latest_run.tools_used

            assert len(tools_used) == 2

            # Second (nested) call completes first
            second_exec = tools_used[0]
            assert second_exec.tool_name == "recursive_tool.recursive_tool"
            assert second_exec.parent_tool_name == "recursive_tool"

            # First (outer) call completes second
            first_exec = tools_used[1]
            assert first_exec.tool_name == "recursive_tool"
            assert first_exec.parent_tool_name is None

        finally:
            tracker.ryumem.config.tool_tracking.sample_rate = original_rate
            tracker.async_classification = original_async
