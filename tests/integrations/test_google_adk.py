import pytest
import os
from unittest.mock import MagicMock, patch
from ryumem.integrations.google_adk import add_memory_to_agent, wrap_runner_with_tracking
from ryumem.core.config import RyumemConfig
from ryumem.main import Ryumem

class TestGoogleADKConfig:
    @pytest.fixture
    def mock_server_config(self):
        """Server config returned when ryumem.config is accessed"""
        config = RyumemConfig()
        config.agent.memory_enabled = True
        config.agent.enhance_agent_instruction = True
        config.tool_tracking.track_tools = True
        config.tool_tracking.sample_rate = 0.5
        config.entity_extraction.enabled = False
        return config

    @pytest.fixture
    def mock_agent(self):
        agent = MagicMock()
        agent.instruction = "Base instruction"
        agent.tools = []
        return agent

    def test_config_from_ryumem_instance(self, mock_server_config, mock_agent):
        """Test that config is read from ryumem.config"""
        # Create mock Ryumem with config property
        mock_ryumem = MagicMock(spec=Ryumem)
        mock_ryumem.config = mock_server_config

        # Add memory to agent
        result = add_memory_to_agent(
            agent=mock_agent,
            ryumem_instance=mock_ryumem,
        )

        # Should return the same agent (builder pattern)
        assert result is mock_agent

        # Memory interface should be stored on agent
        assert hasattr(mock_agent, '_ryumem_memory')

        # Verify config is used from ryumem.config
        assert mock_agent._ryumem_memory.ryumem.config.agent.memory_enabled is True

    def test_config_overrides_in_ryumem(self, mock_server_config, mock_agent):
        """Test that config overrides are passed to Ryumem instance"""
        # Create Ryumem with overrides (auto-loads server_url and api_key from env)
        with patch('ryumem.main.requests') as mock_requests:
            # Mock the server config response
            mock_response = MagicMock()
            mock_response.json.return_value = {
                'agent': {'memory_enabled': True, 'enhance_agent_instruction': True},
                'tool_tracking': {'track_tools': True, 'sample_rate': 0.5},
                'entity_extraction': {'enabled': False},
            }
            mock_requests.get.return_value = mock_response

            ryumem = Ryumem(
                memory_enabled=False,  # Override
                sample_rate=0.1,  # Override
            )

            # Verify overrides are stored
            assert ryumem._config_overrides['agent']['memory_enabled'] is False
            assert ryumem._config_overrides['tool_tracking']['sample_rate'] == 0.1

            result = add_memory_to_agent(mock_agent, ryumem)

            # Verify agent was returned (builder pattern)
            assert result is mock_agent

    def test_wrap_runner_with_tracking(self, mock_server_config, mock_agent):
        """Test wrap_runner_with_tracking extracts memory from agent"""
        # Setup mock Ryumem
        mock_ryumem = MagicMock(spec=Ryumem)
        mock_ryumem.config = mock_server_config

        # Add memory to agent first
        agent = add_memory_to_agent(mock_agent, mock_ryumem)

        # Create mock runner with a real function for run_async
        mock_runner = MagicMock()
        original_run_async = MagicMock()
        mock_runner.run_async = original_run_async

        # Wrap runner
        result = wrap_runner_with_tracking(mock_runner, agent)

        # Should return the same runner (builder pattern)
        assert result is mock_runner

        # run_async should be wrapped (it should be a different function now)
        assert mock_runner.run_async != original_run_async

    def test_wrap_runner_requires_memory(self):
        """Test that wrap_runner fails if agent doesn't have memory"""
        mock_runner = MagicMock()

        # Create an agent without _ryumem_memory attribute
        # Use a simple object instead of MagicMock to avoid auto-attribute creation
        class AgentWithoutMemory:
            def __init__(self):
                self.name = "test_agent"

        agent_without_memory = AgentWithoutMemory()

        # Should raise ValueError
        with pytest.raises(ValueError, match="agent_with_memory must be an agent enhanced"):
            wrap_runner_with_tracking(mock_runner, agent_without_memory)

    def test_chaining_pattern(self, mock_server_config, mock_agent):
        """Test that both functions can be chained"""
        mock_ryumem = MagicMock(spec=Ryumem)
        mock_ryumem.config = mock_server_config
        mock_runner = MagicMock()

        # Chain both operations
        agent = add_memory_to_agent(mock_agent, mock_ryumem)
        runner = wrap_runner_with_tracking(mock_runner, agent)

        assert agent is mock_agent
        assert runner is mock_runner
        assert hasattr(agent, '_ryumem_memory')

    def test_config_ttl_caching(self):
        """Test that config is cached with TTL"""
        with patch('ryumem.main.requests') as mock_requests:
            # Mock successful config fetch
            mock_response = MagicMock()
            mock_response.json.return_value = {
                'agent': {'memory_enabled': True, 'enhance_agent_instruction': True},
                'tool_tracking': {'track_tools': True, 'sample_rate': 0.5},
                'entity_extraction': {'enabled': False},
            }
            mock_requests.get.return_value = mock_response

            # Uses RYUMEM_API_URL and RYUMEM_API_KEY from environment
            ryumem = Ryumem(config_ttl=300)

            # First access - should fetch from server
            config1 = ryumem.config
            assert mock_requests.get.call_count == 1

            # Second access within TTL - should use cache
            config2 = ryumem.config
            assert mock_requests.get.call_count == 1  # Still 1, no new fetch

            # Should return same cached instance
            assert config1 is config2
