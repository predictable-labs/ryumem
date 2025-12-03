"""
Integration test for ToolTracker with LangChain BaseTool and Google ADK.

Tests tool tracking using real LangChain BaseTool converted to
Google ADK FunctionTool for use in agents.
"""

import pytest
import os
import uuid
import asyncio
import time
from typing import Any, Type
from datetime import datetime

# Check if required packages are installed
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from ryumem import Ryumem
from ryumem.integrations import add_memory_to_agent, wrap_runner_with_tracking
from ryumem.core.metadata_models import EpisodeMetadata


# ===== Pytest Hooks for Test Result Tracking =====

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to capture test results for cleanup logic."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


# ===== LangChain Tool Definitions =====

class SimpleToolInput(BaseModel):
    """Input schema for SimpleTool."""
    message: str = Field(description="The message to process")


class SimpleTool(BaseTool):
    """A simple tool that processes a message."""

    name: str = "simple_tool"
    description: str = "A simple tool that processes a message"
    args_schema: Type[BaseModel] = SimpleToolInput

    def _run(self, message: str) -> str:
        """Process the message."""
        return f"Processed: {message}"


class CalculatorToolInput(BaseModel):
    """Input schema for CalculatorTool."""
    expression: str = Field(description="The mathematical expression to evaluate")


class CalculatorTool(BaseTool):
    """A simple calculator tool."""

    name: str = "calculator_tool"
    description: str = "A calculator that evaluates mathematical expressions"
    args_schema: Type[BaseModel] = CalculatorToolInput

    def _run(self, expression: str) -> str:
        """Evaluate the mathematical expression."""
        try:
            result = eval(expression)
            return f"Result: {result}"
        except Exception as e:
            return f"Error: {str(e)}"


# ===== Tool Conversion Helper =====

def create_instrumented_adk_tool(langchain_tool: BaseTool) -> FunctionTool:
    """
    Convert a LangChain BaseTool to a Google ADK FunctionTool.

    This simulates your InstrumentedLangchainTool pattern where you wrap
    LangChain tools for use in Google ADK agents.

    Args:
        langchain_tool: The LangChain tool to convert

    Returns:
        A FunctionTool that wraps the LangChain tool
    """
    # Get the _run method
    run_method = langchain_tool._run

    # Create a wrapper function that preserves the signature
    # We need to extract the underlying function from the bound method
    import functools
    import inspect

    # Get the signature from the _run method
    sig = inspect.signature(run_method)

    # Create a wrapper that calls the tool's _run
    @functools.wraps(run_method.__func__)
    def wrapper(*args, **kwargs):
        return langchain_tool._run(*args, **kwargs)

    # Set the proper metadata
    wrapper.__name__ = langchain_tool.name
    wrapper.__doc__ = langchain_tool.description
    wrapper.__signature__ = sig

    # Convert to FunctionTool
    return FunctionTool(func=wrapper)


# ===== Test Fixtures =====

@pytest.fixture(scope="session")
def ryumem_session():
    """Session-scoped Ryumem instance for cleanup."""
    return Ryumem()


@pytest.fixture
def ryumem():
    """Real Ryumem instance."""
    return Ryumem()


@pytest.fixture
def unique_user(request, ryumem_session):
    """Generate unique user ID for test isolation with cleanup."""
    user_id = f"test_user_{uuid.uuid4().hex[:8]}"

    def cleanup():
        if hasattr(request.node, 'rep_call') and request.node.rep_call.passed:
            try:
                ryumem_session.reset_database()
                print(f"✓ Cleaned up test data for {user_id}")
            except Exception as e:
                print(f"Warning: Cleanup failed for {user_id}: {e}")
        else:
            print(f"⚠ Test failed - skipping cleanup for {user_id}")

    request.addfinalizer(cleanup)
    return user_id


@pytest.fixture
def unique_session():
    """Generate unique session ID for test isolation."""
    return f"test_session_{uuid.uuid4().hex[:8]}"


# Skip if Google API key is not set
def check_google_api_key():
    """Check if GOOGLE_API_KEY is set in environment."""
    return os.getenv("GOOGLE_API_KEY") is not None


@pytest.fixture(autouse=True)
def skip_if_no_google_key():
    """Skip test if GOOGLE_API_KEY is not set."""
    if not check_google_api_key():
        pytest.skip("GOOGLE_API_KEY environment variable not set")


# ===== Test Class =====

class TestInstrumentedLangchainToolTracking:
    """Integration tests for tool tracking with LangChain tools in Google ADK."""

    @pytest.mark.asyncio
    async def test_multiple_langchain_tools_tracked(
        self, ryumem, unique_user, unique_session
    ):
        """Test that multiple LangChain tools are properly tracked when called by agent."""
        # Force 100% sampling for deterministic testing
        original_rate = ryumem.config.tool_tracking.sample_rate
        try:
            ryumem.config.tool_tracking.sample_rate = 1.0

            # Create LangChain tools
            simple_tool = SimpleTool()
            calculator_tool = CalculatorTool()

            # Convert to ADK FunctionTool
            instrumented_simple = create_instrumented_adk_tool(simple_tool)
            instrumented_calculator = create_instrumented_adk_tool(calculator_tool)

            # Create Google ADK agent with instrumented tools
            agent = Agent(
                model="gemini-2.0-flash-exp",
                name="test_agent",
                instruction=(
                    "You are a test agent. When asked to process a message, "
                    "use simple_tool to process it. When asked to calculate, "
                    "use calculator_tool."
                ),
                tools=[instrumented_simple, instrumented_calculator]
            )

            # Add memory and tool tracking to agent
            agent = add_memory_to_agent(agent, ryumem)

            # Create session
            session_service = InMemorySessionService()
            await session_service.create_session(
                app_name="test_app",
                user_id=unique_user,
                session_id=unique_session
            )

            # Create runner
            runner = Runner(
                agent=agent,
                app_name="test_app",
                session_service=session_service
            )

            # Wrap runner with query tracking
            runner = wrap_runner_with_tracking(runner, agent)

            # Execute a query that triggers tool usage
            query = "Process this message: hello world"
            content = types.Content(role='user', parts=[types.Part(text=query)])

            # Run the agent
            events = runner.run(
                user_id=unique_user,
                session_id=unique_session,
                new_message=content
            )

            # Collect response
            final_response = None
            for event in events:
                if event.is_final_response():
                    final_response = event.content.parts[0].text

            assert final_response is not None, "Should get a response from the agent"

            # Wait briefly for async tracking to complete
            await asyncio.sleep(2.0)

            # Verify episode was created
            episode = ryumem.get_episode_by_session_id(unique_session)
            assert episode is not None, "Episode should be created"

            # Verify metadata structure
            metadata = EpisodeMetadata(**episode.metadata)
            latest_run = metadata.get_latest_run(unique_session)
            assert latest_run is not None, "Run should exist"

            tools_used = latest_run.tools_used

            # Verify tools were tracked
            assert len(tools_used) > 0, f"Should have tracked tool executions, got {len(tools_used)}"

            print(f"\n✅ Successfully tracked {len(tools_used)} tool execution(s)")
            for tool_exec in tools_used:
                print(f"   - {tool_exec.tool_name} (success: {tool_exec.success})")

            # Verify at least one tool was called
            assert any(t.tool_name == "simple_tool" for t in tools_used), \
                "simple_tool should have been called"

        finally:
            ryumem.config.tool_tracking.sample_rate = original_rate

    @pytest.mark.asyncio
    async def test_single_langchain_tool_tracked(
        self, ryumem, unique_user, unique_session
    ):
        """Test that a single LangChain tool is properly tracked when called by agent."""
        # Force 100% sampling
        original_rate = ryumem.config.tool_tracking.sample_rate
        try:
            ryumem.config.tool_tracking.sample_rate = 1.0

            # Create a single LangChain tool
            simple_tool = SimpleTool()

            # Convert to ADK FunctionTool
            instrumented_tool = create_instrumented_adk_tool(simple_tool)

            # Create agent with tool
            agent = Agent(
                model="gemini-2.0-flash-exp",
                name="test_agent",
                instruction=(
                    "You are a test agent. When asked to process something, "
                    "use simple_tool."
                ),
                tools=[instrumented_tool]
            )

            # Add memory and tool tracking
            agent = add_memory_to_agent(agent, ryumem)

            # Create session
            session_service = InMemorySessionService()
            await session_service.create_session(
                app_name="test_app",
                user_id=unique_user,
                session_id=unique_session
            )

            # Create and wrap runner
            runner = Runner(
                agent=agent,
                app_name="test_app",
                session_service=session_service
            )
            runner = wrap_runner_with_tracking(runner, agent)

            # Execute query
            query = "Process this message: hello world"
            content = types.Content(role='user', parts=[types.Part(text=query)])

            events = runner.run(
                user_id=unique_user,
                session_id=unique_session,
                new_message=content
            )

            # Collect response
            for event in events:
                if event.is_final_response():
                    break

            # Wait for tracking
            await asyncio.sleep(2.0)

            # Verify episode
            episode = ryumem.get_episode_by_session_id(unique_session)
            assert episode is not None, "Episode should be created"

            metadata = EpisodeMetadata(**episode.metadata)
            latest_run = metadata.get_latest_run(unique_session)
            assert latest_run is not None, "Run should exist"

            tools_used = latest_run.tools_used

            # Verify tools were tracked
            assert len(tools_used) > 0, f"Should have tracked tool executions, got {len(tools_used)}"

            print(f"\n✅ Successfully tracked {len(tools_used)} tool execution(s)")
            for tool_exec in tools_used:
                print(f"   - {tool_exec.tool_name} (success: {tool_exec.success})")

        finally:
            ryumem.config.tool_tracking.sample_rate = original_rate
