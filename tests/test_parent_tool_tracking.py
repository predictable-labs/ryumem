"""
Tests for parent tool tracking functionality.
"""

import pytest
import asyncio
import threading
from unittest.mock import Mock, MagicMock
from ryumem.integrations.tool_tracker import (
    _current_tool,
    _set_current_tool,
    _clear_current_tool,
    _get_parent_tool,
    ToolTracker,
)
from ryumem.core.metadata_models import EpisodeMetadata, QueryRun


class TestContextManagement:
    """Test context variable set/get/clear operations."""

    def test_initial_state(self):
        """Test that context starts with None."""
        assert _get_parent_tool() is None

    def test_set_and_get(self):
        """Test setting and getting current tool."""
        token = _set_current_tool("test_tool")
        try:
            assert _get_parent_tool() == "test_tool"
        finally:
            _clear_current_tool(token)

    def test_clear_with_token(self):
        """Test clearing current tool using token."""
        token = _set_current_tool("test_tool")
        _clear_current_tool(token)
        assert _get_parent_tool() is None

    def test_nested_set_clear(self):
        """Test nested tool execution contexts."""
        # Set parent tool
        parent_token = _set_current_tool("parent_tool")
        try:
            assert _get_parent_tool() == "parent_tool"

            # Set child tool (overwrites)
            child_token = _set_current_tool("child_tool")
            try:
                assert _get_parent_tool() == "child_tool"
            finally:
                _clear_current_tool(child_token)

            # After clearing child, should be back to parent
            assert _get_parent_tool() == "parent_tool"
        finally:
            _clear_current_tool(parent_token)

        # After clearing all, should be None
        assert _get_parent_tool() is None

    def test_exception_safety(self):
        """Test that cleanup happens even with exceptions."""
        token = _set_current_tool("test_tool")
        try:
            assert _get_parent_tool() == "test_tool"
            raise ValueError("Test exception")
        except ValueError:
            pass
        finally:
            _clear_current_tool(token)

        # Should be cleaned up
        assert _get_parent_tool() is None

    def test_thread_isolation(self):
        """Test that context is isolated between threads."""
        results = {}

        def thread_1():
            token = _set_current_tool("thread_1_tool")
            try:
                results['thread_1'] = _get_parent_tool()
            finally:
                _clear_current_tool(token)

        def thread_2():
            token = _set_current_tool("thread_2_tool")
            try:
                results['thread_2'] = _get_parent_tool()
            finally:
                _clear_current_tool(token)

        # Run threads
        t1 = threading.Thread(target=thread_1)
        t2 = threading.Thread(target=thread_2)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Each thread should see its own value
        assert results['thread_1'] == 'thread_1_tool'
        assert results['thread_2'] == 'thread_2_tool'

        # Main thread should still be None
        assert _get_parent_tool() is None

    @pytest.mark.asyncio
    async def test_async_context_propagation(self):
        """Test that context propagates through async/await."""
        token = _set_current_tool("async_parent")
        try:
            # Context should be available before await
            assert _get_parent_tool() == "async_parent"

            # Wait a bit
            await asyncio.sleep(0.01)

            # Context should still be available after await
            assert _get_parent_tool() == "async_parent"
        finally:
            _clear_current_tool(token)

    @pytest.mark.asyncio
    async def test_async_nested_contexts(self):
        """Test nested async contexts."""
        async def child_function():
            # Child sees parent context before setting its own
            parent = _get_parent_tool()
            assert parent == "async_parent"

            # Set child context
            child_token = _set_current_tool("async_child")
            try:
                assert _get_parent_tool() == "async_child"
                await asyncio.sleep(0.01)
                assert _get_parent_tool() == "async_child"
            finally:
                _clear_current_tool(child_token)

        # Set parent context
        parent_token = _set_current_tool("async_parent")
        try:
            await child_function()
            # After child function, should be back to parent
            assert _get_parent_tool() == "async_parent"
        finally:
            _clear_current_tool(parent_token)

    @pytest.mark.asyncio
    async def test_concurrent_async_tasks(self):
        """Test that async tasks have isolated contexts."""
        results = {}

        async def task_1():
            token = _set_current_tool("task_1_tool")
            try:
                await asyncio.sleep(0.01)
                results['task_1'] = _get_parent_tool()
            finally:
                _clear_current_tool(token)

        async def task_2():
            token = _set_current_tool("task_2_tool")
            try:
                await asyncio.sleep(0.01)
                results['task_2'] = _get_parent_tool()
            finally:
                _clear_current_tool(token)

        # Run tasks concurrently
        await asyncio.gather(task_1(), task_2())

        # Each task should see its own value
        assert results['task_1'] == 'task_1_tool'
        assert results['task_2'] == 'task_2_tool'


class TestToolTrackerIntegration:
    """Integration tests for parent-child tool tracking."""

    @pytest.fixture
    def mock_ryumem(self):
        """Create a mock Ryumem client."""
        mock = Mock()
        # Set up nested config structure properly
        mock.config.tool_tracking.ignore_errors = False
        mock.config.tool_tracking.sampling_rate = 1.0  # Track everything
        mock.config.tool_tracking.sample_rate = 1.0  # Also set sample_rate for __init__
        mock.config.tool_tracking.max_output_chars = 5000  # Output limit

        # Mock episode storage - store Mock objects with proper attributes
        mock.episode_storage = {}

        def get_episode_by_session(session_id):
            if session_id in mock.episode_storage:
                return mock.episode_storage[session_id]
            return None

        def get_episode_by_id(uuid):
            # Search all episodes for matching uuid
            for episode_obj in mock.episode_storage.values():
                if episode_obj.uuid == uuid:
                    return episode_obj
            return None

        def update_episode(uuid, metadata):
            for session_id, episode_obj in mock.episode_storage.items():
                if episode_obj.uuid == uuid:
                    episode_obj.metadata = metadata
                    break

        mock.get_episode_by_session_id = Mock(side_effect=get_episode_by_session)
        mock.get_episode_by_uuid = Mock(side_effect=get_episode_by_id)
        mock.update_episode_metadata = Mock(side_effect=update_episode)

        return mock

    @pytest.fixture
    def tool_tracker(self, mock_ryumem):
        """Create a ToolTracker instance with mocked Ryumem."""
        tracker = ToolTracker(ryumem=mock_ryumem)
        tracker.async_classification = False  # Use sync for simpler testing
        return tracker

    def test_parent_child_tracking_sync(self, tool_tracker, mock_ryumem):
        """Test that parent tool calling child tool is tracked correctly."""
        # Setup episode
        session_id = "test_session"
        episode_metadata = EpisodeMetadata(integration="test")
        episode_mock = Mock()
        episode_mock.uuid = 'test-episode-uuid'
        episode_mock.metadata = episode_metadata.model_dump()  # Convert to dict
        mock_ryumem.episode_storage[session_id] = episode_mock

        # Track executions manually
        executions = []

        original_store = tool_tracker._store_tool_execution_async

        async def capture_store(*args, **kwargs):
            executions.append({
                'tool_name': args[0] if args else kwargs.get('tool_name'),
                'parent_tool_name': args[10] if len(args) > 10 else kwargs.get('parent_tool_name'),
            })
            return await original_store(*args, **kwargs)

        tool_tracker._store_tool_execution_async = capture_store

        # Create child function
        def child_tool(user_id=None, session_id=None):
            return "child_result"

        # Create parent function that calls child
        def parent_tool(user_id=None, session_id=None):
            result = wrapped_child(user_id=user_id, session_id=session_id)
            return f"parent_result: {result}"

        # Wrap both functions
        wrapped_child = tool_tracker.create_wrapper(
            child_tool,
            tool_name="child_tool",
            tool_description="Child tool"
        )

        wrapped_parent = tool_tracker.create_wrapper(
            parent_tool,
            tool_name="parent_tool",
            tool_description="Parent tool"
        )

        # Execute parent (which calls child)
        result = wrapped_parent(user_id="test_user", session_id=session_id)

        # Verify result
        assert result == "parent_result: child_result"

        # Verify tracking
        assert len(executions) == 2

        # Child executes first (called from parent)
        child_exec = executions[0]
        assert child_exec['tool_name'] == "parent_tool.child_tool"
        assert child_exec['parent_tool_name'] == "parent_tool"

        # Parent completes second
        parent_exec = executions[1]
        assert parent_exec['tool_name'] == "parent_tool"
        assert parent_exec['parent_tool_name'] is None

    def test_no_nesting(self, tool_tracker, mock_ryumem):
        """Test that standalone tool has no parent."""
        # Setup episode
        session_id = "test_session"
        episode_metadata = EpisodeMetadata(integration="test")
        episode_mock = Mock()
        episode_mock.uuid = 'test-episode-uuid'
        episode_mock.metadata = episode_metadata.model_dump()  # Convert to dict
        mock_ryumem.episode_storage[session_id] = episode_mock

        executions = []

        original_store = tool_tracker._store_tool_execution_async

        async def capture_store(*args, **kwargs):
            executions.append({
                'tool_name': args[0] if args else kwargs.get('tool_name'),
                'parent_tool_name': args[10] if len(args) > 10 else kwargs.get('parent_tool_name'),
            })
            return await original_store(*args, **kwargs)

        tool_tracker._store_tool_execution_async = capture_store

        # Create standalone function
        def standalone_tool(user_id=None, session_id=None):
            return "standalone_result"

        # Wrap function
        wrapped_standalone = tool_tracker.create_wrapper(
            standalone_tool,
            tool_name="standalone_tool",
            tool_description="Standalone tool"
        )

        # Execute
        result = wrapped_standalone(user_id="test_user", session_id=session_id)

        # Verify
        assert result == "standalone_result"
        assert len(executions) == 1

        exec_data = executions[0]
        assert exec_data['tool_name'] == "standalone_tool"
        assert exec_data['parent_tool_name'] is None

    def test_self_recursion(self, tool_tracker, mock_ryumem):
        """Test that tool calling itself is tracked correctly."""
        # Setup episode
        session_id = "test_session"
        episode_metadata = EpisodeMetadata(integration="test")
        episode_mock = Mock()
        episode_mock.uuid = 'test-episode-uuid'
        episode_mock.metadata = episode_metadata.model_dump()  # Convert to dict
        mock_ryumem.episode_storage[session_id] = episode_mock

        executions = []

        original_store = tool_tracker._store_tool_execution_async

        async def capture_store(*args, **kwargs):
            executions.append({
                'tool_name': args[0] if args else kwargs.get('tool_name'),
                'parent_tool_name': args[10] if len(args) > 10 else kwargs.get('parent_tool_name'),
            })
            return await original_store(*args, **kwargs)

        tool_tracker._store_tool_execution_async = capture_store

        # Create recursive function
        def recursive_tool(depth=0, user_id=None, session_id=None):
            if depth < 1:
                return wrapped_recursive(depth=depth + 1, user_id=user_id, session_id=session_id)
            return "base_case"

        # Wrap function
        wrapped_recursive = tool_tracker.create_wrapper(
            recursive_tool,
            tool_name="recursive_tool",
            tool_description="Recursive tool"
        )

        # Execute
        result = wrapped_recursive(depth=0, user_id="test_user", session_id=session_id)

        # Verify
        assert result == "base_case"
        assert len(executions) == 2

        # Second (nested) call completes first
        second_exec = executions[0]
        assert second_exec['tool_name'] == "recursive_tool.recursive_tool"
        assert second_exec['parent_tool_name'] == "recursive_tool"

        # First (outer) call completes second
        first_exec = executions[1]
        assert first_exec['tool_name'] == "recursive_tool"
        assert first_exec['parent_tool_name'] is None
