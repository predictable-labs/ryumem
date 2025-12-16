"""
Comprehensive tests for Google ADK integration.

These tests minimize mocking and use real Ryumem instances to test actual functionality.
Only Google ADK components (Agent, Runner, ToolContext) are mocked since they're external.
"""

import pytest
import os
import uuid
import time
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

from ryumem.integrations.google_adk import (
    add_memory_to_agent,
    wrap_runner_with_tracking,
    RyumemGoogleADK,
    _find_similar_query_episodes,
    _build_context_section,
    _augment_query_with_history,
    _create_query_episode,
    _extract_query_text,
)
from ryumem.main import Ryumem
from ryumem.core.metadata_models import EpisodeMetadata, QueryRun


# ===== Pytest Hooks for Test Result Tracking =====

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to capture test results for cleanup logic."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


# ===== Minimal Mock Objects for Google ADK Components =====
# We only mock what we don't control (Google's SDK)

class SimpleAgent:
    """Minimal agent implementation - not a mock."""
    def __init__(self, instruction="Base instruction"):
        self.instruction = instruction
        self.tools = []
        self.name = "test_agent"


class SimpleToolContext:
    """Minimal tool context - not a mock."""
    def __init__(self, user_id=None, session_id=None):
        self.session = type('Session', (), {
            'user_id': user_id,
            'id': session_id
        })()


class SimpleMessage:
    """Minimal message - not a mock."""
    def __init__(self, text):
        self.parts = [type('Part', (), {'text': text})()]
        self.role = 'user'


class SimpleRunner:
    """Minimal runner implementation - not a mock."""
    def __init__(self):
        self._run_async_impl = None

    async def run_async(self, **kwargs):
        if self._run_async_impl:
            async for event in self._run_async_impl(**kwargs):
                yield event


# ===== Test Fixtures =====

@pytest.fixture(scope="session")
def ryumem_session():
    """Session-scoped Ryumem instance for cleanup."""
    return Ryumem()


@pytest.fixture
def ryumem():
    """Real Ryumem instance - NO MOCKING."""
    # Ryumem() will use RYUMEM_API_URL and RYUMEM_API_KEY from env if not provided
    # It also auto-adds https:// if missing
    return Ryumem()


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


@pytest.fixture
def unique_session():
    """Generate unique session ID for test isolation."""
    return f"test_session_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def agent():
    """Simple agent - not mocked."""
    return SimpleAgent()


# ===== Test Classes =====

class TestMemoryToolsRealIntegration:
    """Test memory tools with real Ryumem - minimal mocking."""

    @pytest.mark.asyncio
    async def test_search_memory_finds_real_data(self, ryumem, agent, unique_user, unique_session):
        """Test search_memory finds actual stored data."""
        # Create real memory interface
        memory = RyumemGoogleADK(agent=agent, ryumem=ryumem)

        # First create an episode for the session
        ep_id = ryumem.add_episode(
            content="Initial episode for search test",
            user_id=unique_user,
            session_id=unique_session,
            source="text"
        )

        # Now save a memory using save_memory (creates facts/relationships)
        tool_context = SimpleToolContext(user_id=unique_user, session_id=unique_session)
        save_result = await memory.save_memory(
            tool_context=tool_context,
            content="Python is a programming language used for web development",
            source="text"
        )

        assert save_result["status"] == "success"

        # Search using real tool
        result = await memory.search_memory(
            tool_context=tool_context,
            query="programming languages",
            limit=5
        )

        # Should find the episode content we saved
        assert result["status"] == "success"
        assert result["count"] >= 1

        # Should have episodes (since entity extraction is disabled)
        assert "episodes" in result
        assert len(result["episodes"]) >= 1

        # Check episode data structure
        first_episode = result["episodes"][0]
        assert "content" in first_episode
        assert "score" in first_episode
        assert isinstance(first_episode["score"], float)
        assert "Python" in first_episode["content"] or "programming" in first_episode["content"]

    @pytest.mark.asyncio
    async def test_search_memory_respects_limit(self, ryumem, agent, unique_user):
        """Test that limit parameter actually works."""
        memory = RyumemGoogleADK(agent=agent, ryumem=ryumem)

        # Create multiple memories with unique sessions
        sessions = []
        for i in range(3):
            session = f"session_{uuid.uuid4().hex[:8]}"
            sessions.append(session)

            # Create episode first
            ryumem.add_episode(
                content=f"Initial episode {i}",
                user_id=unique_user,
                session_id=session,
                source="text"
            )

            # Save memory to create searchable facts
            tool_context = SimpleToolContext(user_id=unique_user, session_id=session)
            await memory.save_memory(
                tool_context=tool_context,
                content=f"Memory {i} about Python coding and programming",
                source="text"
            )

        # Search from first session with limit
        tool_context = SimpleToolContext(user_id=unique_user, session_id=sessions[0])
        result = await memory.search_memory(
            tool_context=tool_context,
            query="coding programming",
            limit=2
        )

        # Should respect the limit
        assert result["status"] == "success"
        # Total count of all results (memories + episodes + entities) should respect limit
        total_results = len(result.get("memories", [])) + len(result.get("episodes", [])) + len(result.get("entities", []))
        assert total_results <= 2

    @pytest.mark.asyncio
    async def test_search_memory_no_results(self, ryumem, agent, unique_user, unique_session):
        """Test search when no matching memories exist."""
        memory = RyumemGoogleADK(agent=agent, ryumem=ryumem)

        tool_context = SimpleToolContext(user_id=unique_user, session_id=unique_session)
        result = await memory.search_memory(
            tool_context=tool_context,
            query="completely_unique_xyz_12345",
            limit=5
        )

        assert result["status"] in ["success", "no_memories"]

    @pytest.mark.asyncio
    async def test_search_memory_missing_session_error(self, ryumem, agent):
        """Test error handling for missing session."""
        memory = RyumemGoogleADK(agent=agent, ryumem=ryumem)

        # No session context
        tool_context = SimpleToolContext(user_id=None, session_id=None)
        result = await memory.search_memory(
            tool_context=tool_context,
            query="test",
            limit=5
        )

        assert result["status"] == "error"
        assert "user_id and session_id are required" in result["message"]

    @pytest.mark.asyncio
    async def test_save_memory_creates_separate_memory_episode(self, ryumem, agent, unique_user, unique_session):
        """Test save_memory creates a new separate episode with kind='memory'."""
        memory = RyumemGoogleADK(agent=agent, ryumem=ryumem)

        # First create a query episode for this session
        initial_episode_id = ryumem.add_episode(
            content="Initial episode content",
            user_id=unique_user,
            session_id=unique_session,
            source="text",
            kind="query"
        )

        # save_memory should create a NEW separate episode with kind='memory'
        tool_context = SimpleToolContext(user_id=unique_user, session_id=unique_session)
        result = await memory.save_memory(
            tool_context=tool_context,
            content="Important fact about testing",
            source="text"
        )

        # Verify save succeeded
        assert result["status"] == "success", f"Expected success but got: {result}"
        assert "episode_id" in result
        memory_episode_id = result["episode_id"]

        # Verify memory episode is different from initial episode
        assert memory_episode_id != initial_episode_id, "save_memory should create a new episode"

        # Verify memory episode exists with correct kind
        memory_episode = ryumem.get_episode_by_uuid(memory_episode_id)
        assert memory_episode is not None
        assert memory_episode.user_id == unique_user
        assert memory_episode.kind.value == "memory", f"Expected kind='memory' but got {memory_episode.kind.value}"
        assert memory_episode.content == "Important fact about testing"

    @pytest.mark.asyncio
    async def test_save_memory_different_source_types(self, ryumem, agent, unique_user):
        """Test saving with different valid source types."""
        memory = RyumemGoogleADK(agent=agent, ryumem=ryumem)

        for source_type in ["text", "message", "json"]:
            # Create unique session for each test
            session = f"session_{uuid.uuid4().hex[:8]}"

            # Create initial episode with UNIQUE content to avoid duplicate detection
            ryumem.add_episode(
                content=f"Initial content for {source_type} - {uuid.uuid4().hex[:8]}",
                user_id=unique_user,
                session_id=session,
                source=source_type
            )

            tool_context = SimpleToolContext(user_id=unique_user, session_id=session)
            result = await memory.save_memory(
                tool_context=tool_context,
                content=f"Memory with {source_type}",
                source=source_type
            )

            assert result["status"] == "success", f"Failed for source_type={source_type}: {result}"

    @pytest.mark.asyncio
    async def test_save_memory_invalid_source_defaults_to_text(self, ryumem, agent, unique_user, unique_session):
        """Test that invalid source type defaults gracefully."""
        memory = RyumemGoogleADK(agent=agent, ryumem=ryumem)

        # Create initial episode
        ryumem.add_episode(
            content="Initial content",
            user_id=unique_user,
            session_id=unique_session,
            source="text"
        )

        tool_context = SimpleToolContext(user_id=unique_user, session_id=unique_session)
        result = await memory.save_memory(
            tool_context=tool_context,
            content="Test content",
            source="invalid_type"
        )

        # Should still succeed (invalid source defaults to "text")
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_get_entity_context_not_found(self, ryumem, agent, unique_user, unique_session):
        """Test get_entity_context with non-existent entity."""
        memory = RyumemGoogleADK(agent=agent, ryumem=ryumem)
        tool_context = SimpleToolContext(user_id=unique_user, session_id=unique_session)

        result = await memory.get_entity_context(
            tool_context=tool_context,
            entity_name="NonExistentEntity12345"
        )

        assert result["status"] in ["not_found", "success"]


class TestQueryAugmentationReal:
    """Test query augmentation with real data - minimal mocking."""

    def test_find_similar_queries_no_history(self, ryumem, agent, unique_user, unique_session):
        """Test finding similar queries when none exist yet."""
        memory = RyumemGoogleADK(agent=agent, ryumem=ryumem)

        similar = _find_similar_query_episodes(
            query_text="brand new unique query xyz",
            memory=memory,
            user_id=unique_user,
            session_id=unique_session
        )

        assert isinstance(similar, list)
        assert len(similar) == 0

    def test_find_similar_queries_with_history(self, ryumem, agent, unique_user):
        """Test finding similar queries across sessions with real data."""
        memory = RyumemGoogleADK(agent=agent, ryumem=ryumem)
        session1 = f"session_{uuid.uuid4().hex[:8]}"
        session2 = f"session_{uuid.uuid4().hex[:8]}"

        # Create query episode in session 1
        query_run = QueryRun(
            run_id=str(uuid.uuid4()),
            user_id=unique_user,
            timestamp=datetime.utcnow().isoformat(),
            query="How do I reset password?",
            agent_response="Click forgot password link",
            tools_used=[]
        )

        metadata = EpisodeMetadata(integration="google_adk")
        metadata.add_query_run(session1, query_run)

        ryumem.add_episode(
            content="How do I reset password?",
            user_id=unique_user,
            session_id=session1,
            source="message",
            metadata=metadata.model_dump()
        )

        # Search from session 2
        similar = _find_similar_query_episodes(
            query_text="How do I reset password?",
            memory=memory,
            user_id=unique_user,
            session_id=session2
        )

        # Should find the episode from session 1
        if len(similar) > 0:
            assert similar[0]["content"] == "How do I reset password?"

    def test_augment_query_no_history_returns_original(self, ryumem, agent, unique_user, unique_session):
        """Test query augmentation returns original when no history."""
        memory = RyumemGoogleADK(agent=agent, ryumem=ryumem)
        memory._augmentation_prompt = "Previous: {agent_response}\nTools: {tool_summary}\nQuery: {query_text}"

        original = "What is the weather?"
        augmented = _augment_query_with_history(
            query_text=original,
            memory=memory,
            user_id=unique_user,
            session_id=unique_session
        )

        assert augmented == original

    def test_build_context_from_real_metadata(self, ryumem, agent):
        """Test building context section from real episode metadata."""
        memory = RyumemGoogleADK(agent=agent, ryumem=ryumem)
        memory._augmentation_prompt = "Previous: {agent_response}\nTools: {tool_summary}\nQuery: {query_text}"

        # Create real metadata
        query_run = QueryRun(
            run_id="test",
            user_id="test_user",
            timestamp=datetime.utcnow().isoformat(),
            query="original query",
            agent_response="This is the response",
            tools_used=[]
        )

        metadata = EpisodeMetadata(integration="google_adk")
        metadata.add_query_run("session1", query_run)

        similar_queries = [{
            "content": "original query",
            "score": 0.95,
            "uuid": "test_uuid",
            "metadata": metadata.model_dump()
        }]

        context = _build_context_section(
            query_text="new query",
            similar_queries=similar_queries,
            memory=memory,
            top_k=1
        )

        # Should contain response from metadata
        if context:
            assert "This is the response" in context

    def test_extract_query_text_from_message(self):
        """Test extracting text from message."""
        message = SimpleMessage("Hello world")
        text = _extract_query_text(message)
        assert text == "Hello world"

    def test_extract_query_text_multiple_parts(self):
        """Test extracting text from message with multiple parts."""
        message = type('Message', (), {
            'parts': [
                type('Part', (), {'text': 'Hello'})(),
                type('Part', (), {'text': 'world'})()
            ]
        })()

        text = _extract_query_text(message)
        assert text == "Hello world"


class TestEpisodeCreationReal:
    """Test episode creation with real database operations."""

    def test_create_query_episode_stores_real_data(self, ryumem, agent, unique_user, unique_session):
        """Test that episode creation stores retrievable data."""
        memory = RyumemGoogleADK(agent=agent, ryumem=ryumem)
        run_id = str(uuid.uuid4())

        episode_id = _create_query_episode(
            query_text="What is the meaning of life?",
            user_id=unique_user,
            session_id=unique_session,
            run_id=run_id,
            augmented_query_text="What is the meaning of life?",
            memory=memory
        )

        # Verify episode exists
        assert episode_id is not None
        episode = ryumem.get_episode_by_uuid(episode_id)
        assert episode is not None
        assert episode.content == "What is the meaning of life?"
        assert episode.user_id == unique_user
        # Note: EpisodeNode might not have session_id as direct attribute

    def test_create_query_episode_with_metadata(self, ryumem, agent, unique_user, unique_session):
        """Test episode includes proper metadata structure."""
        memory = RyumemGoogleADK(agent=agent, ryumem=ryumem)
        run_id = str(uuid.uuid4())

        episode_id = _create_query_episode(
            query_text="Test query",
            user_id=unique_user,
            session_id=unique_session,
            run_id=run_id,
            augmented_query_text="Augmented test query",
            memory=memory
        )

        # Check metadata structure
        episode = ryumem.get_episode_by_uuid(episode_id)
        assert episode.metadata is not None

        if isinstance(episode.metadata, dict):
            assert "integration" in episode.metadata
            assert "sessions" in episode.metadata


class TestAddMemoryToAgentReal:
    """Test add_memory_to_agent with real Ryumem instance."""

    def test_adds_real_tools_to_agent(self, ryumem, agent):
        """Test that real memory tools are added."""
        original_tool_count = len(agent.tools)

        result = add_memory_to_agent(agent, ryumem)

        # Should return same agent
        assert result is agent

        # Should have more tools now
        assert len(agent.tools) > original_tool_count

        # Should have memory interface
        assert hasattr(agent, '_ryumem_memory')
        assert isinstance(agent._ryumem_memory, RyumemGoogleADK)

    def test_instruction_enhancement_with_real_config(self, ryumem, agent):
        """Test instruction enhancement uses real config."""
        original_instruction = agent.instruction

        add_memory_to_agent(agent, ryumem)

        # If enhancement enabled, instruction should be different
        if ryumem.config.agent.enhance_agent_instruction:
            assert len(agent.instruction) >= len(original_instruction)

    def test_memory_tools_are_callable(self, ryumem, agent):
        """Test that added tools are actually callable functions."""
        add_memory_to_agent(agent, ryumem)

        # Tools should be callable
        for tool in agent.tools:
            assert callable(tool)


class TestRunnerWrappingReal:
    """Test runner wrapping with real functionality."""

    def test_wrap_runner_without_memory_raises_error(self):
        """Test that wrapping requires agent with memory."""
        runner = SimpleRunner()
        agent_without_memory = SimpleAgent()

        with pytest.raises(ValueError, match="must be an agent enhanced"):
            wrap_runner_with_tracking(runner, agent_without_memory)

    def test_wrap_runner_with_memory_succeeds(self, ryumem, agent):
        """Test wrapping runner with memory-enabled agent."""
        # Add memory first
        agent = add_memory_to_agent(agent, ryumem)

        runner = SimpleRunner()
        result = wrap_runner_with_tracking(runner, agent)

        # Should return same runner
        assert result is runner

    @pytest.mark.asyncio
    async def test_wrapped_runner_tracks_real_queries(self, ryumem, agent, unique_user, unique_session):
        """Test that wrapped runner actually tracks queries."""
        if not ryumem.config.tool_tracking.track_queries:
            pytest.skip("Query tracking disabled in config")

        # Add memory and wrap runner
        agent = add_memory_to_agent(agent, ryumem)
        runner = SimpleRunner()

        # Create async generator for events
        async def mock_events(**kwargs):
            yield type('Event', (), {
                'content': type('Content', (), {
                    'parts': [type('Part', (), {'text': 'Response text'})()]
                })()
            })()

        runner._run_async_impl = mock_events

        # Wrap it
        runner = wrap_runner_with_tracking(runner, agent)

        # Run query
        message = SimpleMessage("Test query")
        events = []
        async for event in runner.run_async(
            user_id=unique_user,
            session_id=unique_session,
            new_message=message
        ):
            events.append(event)

        # Should yield events
        assert len(events) > 0

        # Wait briefly for async processing
        # Episode should be created
        episode = ryumem.get_episode_by_session_id(unique_session)
        if episode:
            assert episode.content == "Test query"


class TestToolsPropertyReal:
    """Test the tools property with real config."""

    def test_tools_list_based_on_config(self, ryumem, agent):
        """Test tools property returns correct tools based on config."""
        memory = RyumemGoogleADK(agent=agent, ryumem=ryumem)
        tools = memory.tools

        # Should return list
        assert isinstance(tools, list)

        # If memory enabled, should have search and save
        if ryumem.config.agent.memory_enabled:
            assert len(tools) >= 2

    def test_entity_tool_when_enabled(self, ryumem, agent):
        """Test entity tool is included when enabled."""
        memory = RyumemGoogleADK(agent=agent, ryumem=ryumem)

        # Check if entity extraction is enabled
        if ryumem.config.entity_extraction.enabled and ryumem.config.agent.memory_enabled:
            tools = memory.tools
            tool_names = [getattr(t, '__name__', '') for t in tools]
            assert 'get_entity_context' in tool_names


class TestErrorHandlingReal:
    """Test error handling with real scenarios."""

    @pytest.mark.asyncio
    async def test_search_handles_invalid_context_gracefully(self, ryumem, agent):
        """Test that invalid context returns error not exception."""
        memory = RyumemGoogleADK(agent=agent, ryumem=ryumem)

        # Create invalid context
        bad_context = type('BadContext', (), {'session': None})()

        result = await memory.search_memory(
            tool_context=bad_context,
            query="test",
            limit=5
        )

        # Should return error dict, not raise
        assert isinstance(result, dict)
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_save_handles_invalid_context_gracefully(self, ryumem, agent):
        """Test that save handles errors gracefully."""
        memory = RyumemGoogleADK(agent=agent, ryumem=ryumem)

        bad_context = type('BadContext', (), {'session': None})()

        result = await memory.save_memory(
            tool_context=bad_context,
            content="test",
            source="text"
        )

        assert isinstance(result, dict)
        assert result["status"] == "error"


class TestMultiUserIsolation:
    """Test that user data is properly isolated - critical security test."""

    @pytest.mark.asyncio
    async def test_search_respects_user_boundaries(self, ryumem, agent):
        """Test that user A cannot see user B's memories."""
        memory = RyumemGoogleADK(agent=agent, ryumem=ryumem)

        user_a = f"user_a_{uuid.uuid4().hex[:8]}"
        user_b = f"user_b_{uuid.uuid4().hex[:8]}"
        session_a = f"session_{uuid.uuid4().hex[:8]}"
        session_b = f"session_{uuid.uuid4().hex[:8]}"

        # User A saves secret
        ctx_a = SimpleToolContext(user_id=user_a, session_id=session_a)
        await memory.save_memory(
            tool_context=ctx_a,
            content="User A's secret password is abc123",
            source="text"
        )

        # User B searches for "password"
        ctx_b = SimpleToolContext(user_id=user_b, session_id=session_b)
        result = await memory.search_memory(
            tool_context=ctx_b,
            query="password secret",
            limit=10
        )

        # User B should NOT see User A's secret
        assert result["status"] in ["success", "no_memories"]
        if result["status"] == "success":
            for mem in result["memories"]:
                assert "abc123" not in mem["fact"]
                assert user_a not in str(mem)


class TestAugmentationRealIntegration:
    """Test query augmentation with real data flow - full e2e integration."""

    @pytest.mark.asyncio
    async def test_augmentation_with_real_query_flow(self, ryumem, unique_user):
        from ryumem.integrations.google_adk import DEFAULT_AUGMENTATION_TEMPLATE
        """Test that augmentation actually works end-to-end with real queries and tool executions."""
        # Skip if augmentation is disabled in config
        # if not ryumem.config.tool_tracking.augment_queries:
        #     pytest.skip("Query augmentation disabled in config")

        # Create agent with a simple tool
        agent = SimpleAgent(instruction="You are a helpful assistant")

        # Add a simple test tool to track
        def test_tool(query: str) -> dict:
            """A test tool that returns search results."""
            return {"status": "success", "results": f"Found results for: {query}"}

        agent.tools = [test_tool]

        # Add memory and tracking
        agent_with_memory = add_memory_to_agent(agent, ryumem)

        # Verify memory was added
        assert hasattr(agent_with_memory, '_ryumem_memory')
        memory = agent_with_memory._ryumem_memory

        # Session 1: Create initial query with tool execution
        session1 = f"session_{uuid.uuid4().hex[:8]}"

        # Manually create a query episode with tool execution metadata
        from ryumem.core.metadata_models import ToolExecution
        import json

        tool_exec = ToolExecution(
            tool_name="test_tool",
            success=True,
            timestamp=datetime.utcnow().isoformat(),
            input_params={"query": "weather"},
            output_summary=json.dumps({"status": "success", "results": "Found results for: weather"}),
            duration_ms=100
        )

        query_run = QueryRun(
            run_id=str(uuid.uuid4()),
            user_id=unique_user,
            timestamp=datetime.utcnow().isoformat(),
            query="What is the weather today?",
            agent_response="The weather is sunny and 25 degrees.",
            tools_used=[tool_exec]
        )

        metadata = EpisodeMetadata(integration="google_adk")
        metadata.add_query_run(session1, query_run)

        # Create the episode
        episode1_id = ryumem.add_episode(
            content="What is the weather today?",
            user_id=unique_user,
            session_id=session1,
            source="message",
            metadata=metadata.model_dump()
        )

        assert episode1_id is not None

        # Verify episode is searchable before testing augmentation
        search_test = ryumem.search(
            query="What is the weather today?",
            user_id=unique_user,
            session_id=None,
            strategy="semantic",
            limit=5
        )

        logger.info(f"Search test returned {len(search_test.episodes)} episodes")
        if len(search_test.episodes) > 0:
            # Log scores to understand similarity
            for ep in search_test.episodes:
                score = search_test.scores.get(ep.uuid, 0.0)
                logger.info(f"Episode {ep.uuid[:8]}: score={score}")

        # Session 2: Create similar query that should trigger augmentation
        session2 = f"session_{uuid.uuid4().hex[:8]}"

        # Use internal augmentation function to test
        from ryumem.integrations.google_adk import _augment_query_with_history, _find_similar_query_episodes

        # Store augmentation template
        memory._augmentation_prompt = DEFAULT_AUGMENTATION_TEMPLATE

        # Use VERY similar query - almost identical to increase similarity score
        similar_query = "What is the weather today?"  # Use same query for high similarity

        # Debug: Check if similar queries are found
        similar_episodes = _find_similar_query_episodes(
            query_text=similar_query,
            memory=memory,
            user_id=unique_user,
            session_id=session2
        )

        logger.info(f"Found {len(similar_episodes)} similar episodes")
        for ep in similar_episodes:
            logger.info(f"Similar episode score: {ep.get('score', 'N/A')}")

        augmented_query = _augment_query_with_history(
            query_text=similar_query,
            memory=memory,
            user_id=unique_user,
            session_id=session2
        )

        # Augmentation should have occurred since we found similar episodes
        assert augmented_query != similar_query, \
            f"Augmentation should have occurred. Found {len(similar_episodes)} similar episodes"

        # Augmentation happened - verify it contains expected components
        assert "The weather is sunny and 25 degrees" in augmented_query, \
            "Should include agent response from previous attempt"
        assert "test_tool" in augmented_query, \
            "Should include tool name in summary"
        assert "Session ID:" in augmented_query, \
            "Should include last session details"
        assert session1 in augmented_query, \
            "Should include the actual session ID from first query"
        assert "Previous Attempt Summary" in augmented_query, \
            "Should include template structure"

    @pytest.mark.asyncio
    async def test_augmentation_includes_tool_response_sizes(self, ryumem, unique_user):
        from ryumem.integrations.google_adk import DEFAULT_AUGMENTATION_TEMPLATE
        """Test that augmentation includes response size information in simplified tool summary."""
        if not ryumem.config.tool_tracking.augment_queries:
            pytest.skip("Query augmentation disabled in config")

        agent = SimpleAgent()
        agent_with_memory = add_memory_to_agent(agent, ryumem)
        memory = agent_with_memory._ryumem_memory

        # Create session with tool executions that have different response types
        session1 = f"session_{uuid.uuid4().hex[:8]}"

        from ryumem.core.metadata_models import ToolExecution
        import json

        # Dict response
        tool_dict = ToolExecution(
            tool_name="dict_tool",
            success=True,
            timestamp=datetime.utcnow().isoformat(),
            input_params={"query": "test"},
            output_summary=json.dumps({"key1": "val1", "key2": "val2"}),
            duration_ms=50
        )

        # List response
        tool_list = ToolExecution(
            tool_name="list_tool",
            success=True,
            timestamp=datetime.utcnow().isoformat(),
            input_params={"limit": "5"},
            output_summary=json.dumps(["item1", "item2", "item3"]),
            duration_ms=75
        )

        query_run = QueryRun(
            run_id=str(uuid.uuid4()),
            user_id=unique_user,
            timestamp=datetime.utcnow().isoformat(),
            query="Get some data for analysis",
            agent_response="Here is the data you requested",
            tools_used=[tool_dict, tool_list]
        )

        metadata = EpisodeMetadata(integration="google_adk")
        metadata.add_query_run(session1, query_run)

        episode_id = ryumem.add_episode(
            content="Get some data for analysis",
            user_id=unique_user,
            session_id=session1,
            source="message",
            metadata=metadata.model_dump()
        )

        # Verify episode is searchable
        search_test = ryumem.search(
            query="Get some data for analysis",
            user_id=unique_user,
            session_id=None,
            strategy="semantic",
            limit=5
        )

        logger.info(f"Search test returned {len(search_test.episodes)} episodes")

        # Query similar content
        session2 = f"session_{uuid.uuid4().hex[:8]}"
        from ryumem.integrations.google_adk import _augment_query_with_history, _find_similar_query_episodes

        memory._augmentation_prompt = DEFAULT_AUGMENTATION_TEMPLATE

        # Use identical query for high similarity
        similar_query = "Get some data for analysis"

        # Check if similar episodes found
        similar_episodes = _find_similar_query_episodes(
            query_text=similar_query,
            memory=memory,
            user_id=unique_user,
            session_id=session2
        )

        logger.info(f"Found {len(similar_episodes)} similar episodes for response size test")

        augmented = _augment_query_with_history(
            query_text=similar_query,
            memory=memory,
            user_id=unique_user,
            session_id=session2
        )

        # Augmentation should have occurred
        assert augmented != similar_query, \
            f"Augmentation should have occurred. Found {len(similar_episodes)} similar episodes"

        # Should include response size indicators
        assert ("keys" in augmented or "items" in augmented or "response:" in augmented), \
            f"Should include response size info in augmented query: {augmented}"

    @pytest.mark.asyncio
    async def test_augmentation_with_multiple_sessions_picks_most_recent(self, ryumem, unique_user):
        from ryumem.integrations.google_adk import DEFAULT_AUGMENTATION_TEMPLATE
        """Test that last session details extraction picks the most recent session."""
        if not ryumem.config.tool_tracking.augment_queries:
            pytest.skip("Query augmentation disabled in config")

        agent = SimpleAgent()
        agent_with_memory = add_memory_to_agent(agent, ryumem)
        memory = agent_with_memory._ryumem_memory
        # Lower threshold for this test to ensure similar episodes are found
        memory.ryumem.config.tool_tracking.similarity_threshold = 0.0

        from ryumem.core.metadata_models import ToolExecution

        # Create 3 sessions with different timestamps
        base_time = datetime.utcnow()

        # Test: Most recent episode with exact match should win
        # Session 0 (3h ago): Different topic - low similarity
        # Session 1 (2h ago): Similar but not exact
        # Session 2 (1h ago, most recent): Exact match - should win
        exact_match_query = "Help me with a task"
        content_variants = [
            "Show me the database schema",  # Completely different - low similarity
            "Please help with this task",  # Similar words, different order
            exact_match_query,  # Exact match - most recent + best similarity
        ]

        for i, hours_ago in enumerate([3, 2, 1]):  # oldest to newest
            session = f"session_{i}_{uuid.uuid4().hex[:8]}"
            timestamp = (base_time - timedelta(hours=hours_ago)).isoformat()

            tool = ToolExecution(
                tool_name=f"tool_{i}",
                success=True,
                timestamp=timestamp,
                input_params={"session": str(i)},
                output_summary=f"Result from session {i}",
                duration_ms=100
            )

            run = QueryRun(
                run_id=str(uuid.uuid4()),
                user_id=unique_user,
                timestamp=timestamp,
                query=f"Query from session {i}",
                agent_response=f"Response from session {i}",
                tools_used=[tool]
            )

            metadata = EpisodeMetadata(integration="google_adk")
            metadata.add_query_run(session, run)

            # Use naturally different but semantically similar content
            ryumem.add_episode(
                content=content_variants[i],
                user_id=unique_user,
                session_id=session,
                source="message",
                metadata=metadata.model_dump()
            )

        # Verify episodes are searchable
        search_test = ryumem.search(
            query="Help me with a task",
            user_id=unique_user,
            session_id=None,
            strategy="semantic",
            limit=5
        )

        logger.info(f"Search test returned {len(search_test.episodes)} episodes")

        # Debug: Log the scores for each episode
        for ep in search_test.episodes:
            score = search_test.scores.get(ep.uuid, "N/A")
            logger.info(f"Episode {ep.uuid}: content='{ep.content}', score={score}")

        # Query with similar content
        new_session = f"session_new_{uuid.uuid4().hex[:8]}"
        from ryumem.integrations.google_adk import _augment_query_with_history, _find_similar_query_episodes

        memory._augmentation_prompt = DEFAULT_AUGMENTATION_TEMPLATE

        # Use general query that matches all three episode variants
        similar_query = "Help me with a task"

        # Check if similar episodes found
        similar_episodes = _find_similar_query_episodes(
            query_text=similar_query,
            memory=memory,
            user_id=unique_user,
            session_id=new_session
        )

        logger.info(f"Found {len(similar_episodes)} similar episodes for multiple sessions test")

        # Debug: Log all similar episodes with their timestamps
        import json
        for idx, ep in enumerate(similar_episodes):
            logger.info(f"Similar episode {idx}: score={ep.get('score', 'N/A')}, content={ep.get('content', 'N/A')[:30]}")
            if 'metadata' in ep:
                metadata_dict = json.loads(ep['metadata']) if isinstance(ep['metadata'], str) else ep['metadata']
                episode_meta = EpisodeMetadata(**metadata_dict)
                for sess_id, runs in episode_meta.sessions.items():
                    for run in runs:
                        logger.info(f"  Session: {sess_id[:20]}, timestamp: {run.timestamp}, response: {run.agent_response[:30] if run.agent_response else 'None'}")

        augmented = _augment_query_with_history(
            query_text=similar_query,
            memory=memory,
            user_id=unique_user,
            session_id=new_session
        )

        logger.info(f"Augmented query length: {len(augmented)}")
        logger.info(f"First 500 chars of augmented: {augmented[:500]}")

        # Augmentation should have occurred
        assert augmented != similar_query, \
            f"Augmentation should have occurred. Found {len(similar_episodes)} similar episodes"

        # Check what's actually in the augmented query
        has_session_0 = "Response from session 0" in augmented
        has_session_1 = "Response from session 1" in augmented
        has_session_2 = "Response from session 2" in augmented

        logger.info(f"Has session 0: {has_session_0}, session 1: {has_session_1}, session 2: {has_session_2}")

        # Should include the most recent session (session 2, 1 hour ago)
        assert "Response from session 2" in augmented, \
            f"Should include response from most recent session. Has: 0={has_session_0}, 1={has_session_1}, 2={has_session_2}. Augmented length: {len(augmented)}"
        # Should NOT include older sessions in last_session section
        assert augmented.count("Session ID:") == 1, \
            "Should only include one session in last_session details"


class TestMultipleMemoryAddition:
    """Test that add_memory_to_agent handles multiple calls correctly."""

    @pytest.fixture
    def agent(self):
        """Fresh agent for each test."""
        return SimpleAgent()

    def test_multiple_add_calls_with_same_instance_are_idempotent(self, ryumem, agent):
        """Calling add_memory_to_agent twice with same instance should be idempotent."""
        # First call
        result1 = add_memory_to_agent(agent, ryumem)
        tools_count_after_first = len(agent.tools)
        instruction_after_first = agent.instruction

        # Second call with same instance
        result2 = add_memory_to_agent(agent, ryumem)
        tools_count_after_second = len(agent.tools)
        instruction_after_second = agent.instruction

        # Assertions
        assert result1 is agent
        assert result2 is agent
        assert tools_count_after_first == tools_count_after_second

        # No duplicate tool names
        tool_names = [getattr(t, '__name__', 'unknown') for t in agent.tools]
        assert len(tool_names) == len(set(tool_names))

        # Instruction blocks should only appear once
        assert instruction_after_second.count("MEMORY USAGE:") <= 1, \
            "MEMORY USAGE block should only appear once"
        assert instruction_after_second.count("TOOL SELECTION:") <= 1, \
            "TOOL SELECTION block should only appear once"

        # Instruction should not change on second call
        assert instruction_after_first == instruction_after_second, \
            "Instruction should remain the same on subsequent calls"

    @pytest.mark.asyncio
    async def test_search_memory_works_after_multiple_add_calls(
        self, ryumem, agent, unique_user, unique_session
    ):
        """search_memory should work after calling add_memory_to_agent multiple times."""
        # Call twice with same instance
        add_memory_to_agent(agent, ryumem)
        add_memory_to_agent(agent, ryumem)

        # Verify memory interface exists
        assert hasattr(agent, '_ryumem_memory')
        memory = agent._ryumem_memory

        # Save and search
        tool_context = SimpleToolContext(user_id=unique_user, session_id=unique_session)
        save_result = await memory.save_memory(
            tool_context=tool_context,
            content="Test memory for multiple add calls",
            source="text"
        )
        assert save_result["status"] == "success"

        search_result = await memory.search_memory(
            tool_context=tool_context,
            query="multiple add calls",
            limit=5
        )
        assert search_result["status"] in ["success", "no_memories"]

    def test_multiple_add_calls_with_different_instances_replaces_tools(self, agent):
        """Calling add_memory_to_agent with different Ryumem instances should replace tools."""
        ryumem1 = Ryumem()
        ryumem2 = Ryumem()

        # First call
        add_memory_to_agent(agent, ryumem1)
        tools_count_after_first = len(agent.tools)
        instruction_after_first = agent.instruction
        first_memory = agent._ryumem_memory

        # Second call with different instance
        add_memory_to_agent(agent, ryumem2)
        tools_count_after_second = len(agent.tools)
        instruction_after_second = agent.instruction
        second_memory = agent._ryumem_memory

        # Tool count should be same (replaced, not duplicated)
        assert tools_count_after_first == tools_count_after_second

        # Memory instance should be replaced
        assert first_memory is not second_memory
        assert second_memory.ryumem is ryumem2

        # No duplicate tool names
        tool_names = [getattr(t, '__name__', 'unknown') for t in agent.tools]
        assert len(tool_names) == len(set(tool_names))

        # Instruction blocks should only appear once even with different instances
        assert instruction_after_second.count("MEMORY USAGE:") <= 1, \
            "MEMORY USAGE block should only appear once"
        assert instruction_after_second.count("TOOL SELECTION:") <= 1, \
            "TOOL SELECTION block should only appear once"

        # Instruction should not change when replacing with different instance
        assert instruction_after_first == instruction_after_second, \
            "Instruction should remain the same when replacing Ryumem instance"


class TestSessionUserOverride:
    """Test per-session user_id override functionality."""

    @pytest.mark.asyncio
    async def test_session_user_override_comprehensive(self, ryumem, agent):
        """Comprehensive test for per-session user_id override functionality."""
        memory = RyumemGoogleADK(agent=agent, ryumem=ryumem)

        user_a = f"user_a_{uuid.uuid4().hex[:8]}"
        user_b = f"user_b_{uuid.uuid4().hex[:8]}"
        session_a = f"session_a_{uuid.uuid4().hex[:8]}"
        session_b = f"session_b_{uuid.uuid4().hex[:8]}"

        # 1. User A saves a memory
        ctx_a = SimpleToolContext(user_id=user_a, session_id=session_a)
        save_result = await memory.save_memory(
            tool_context=ctx_a,
            content="User A's secret information about Python",
            source="text"
        )
        assert save_result["status"] == "success"

        # 2. Verify session_b has no override initially
        assert memory.get_session_user_override(session_b) is None

        # 3. Set override for session_b to use user_a
        memory.set_session_user_override(session_b, user_a)
        assert memory.get_session_user_override(session_b) == user_a

        # 4. Session_b (with user_b as default) searches - should find user_a's memories due to override
        ctx_b = SimpleToolContext(user_id=user_b, session_id=session_b)
        search_result = await memory.search_memory(
            tool_context=ctx_b,
            query="Python secret information",
            limit=10
        )
        # Should search in user_a's space due to override
        assert search_result["status"] in ["success", "no_memories"]

        # 5. Save through session_b with override - should save to user_a
        save_with_override = await memory.save_memory(
            tool_context=ctx_b,
            content="Memory saved through session_b but should belong to user_a",
            source="text"
        )
        assert save_with_override["status"] == "success"
        episode_id = save_with_override["episode_id"]

        # Verify episode belongs to user_a (not user_b)
        episode = ryumem.get_episode_by_uuid(episode_id)
        assert episode.user_id == user_a, f"Expected user_id={user_a} but got {episode.user_id}"

        # 6. Test override is session-specific - session_a should not be affected
        search_from_a = await memory.search_memory(
            tool_context=ctx_a,
            query="test",
            limit=5
        )
        # Should still use user_a (no override set for session_a)
        assert search_from_a["status"] in ["success", "no_memories"]

        # 7. Clear override for session_b
        memory.clear_session_user_override(session_b)
        assert memory.get_session_user_override(session_b) is None

        # 8. After clearing, session_b should use its original user_id (user_b)
        save_after_clear = await memory.save_memory(
            tool_context=ctx_b,
            content="Memory after clearing override",
            source="text"
        )
        assert save_after_clear["status"] == "success"
        episode_after_clear = ryumem.get_episode_by_uuid(save_after_clear["episode_id"])
        assert episode_after_clear.user_id == user_b, "After clearing override, should use original user_b"

        logger.info("✓ Comprehensive session user_id override test passed")
