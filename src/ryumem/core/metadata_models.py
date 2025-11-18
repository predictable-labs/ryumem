"""
Pydantic models for episode metadata.

These models provide type safety and validation for episode metadata structures.
"""

from pydantic import BaseModel, Field
from typing import Optional


class ToolExecution(BaseModel):
    """Metadata for a single tool execution."""

    tool_name: str
    success: bool
    duration_ms: int = 0
    timestamp: str
    input_params: dict = Field(default_factory=dict)
    output_summary: str = ""
    error: Optional[str] = None


class QueryRun(BaseModel):
    """A single query execution/run."""

    run_id: str
    timestamp: str
    query: str
    agent_response: str = ""
    tools_used: list[ToolExecution] = Field(default_factory=list)


class EpisodeMetadata(BaseModel):
    """
    Metadata for an episode (multiple query runs grouped by session).

    Structure:
        - integration: Integration type (e.g., "google_adk")
        - sessions: Map of session_id -> list of query runs

    Example:
        {
            "integration": "google_adk",
            "sessions": {
                "session_123": [
                    {
                        "run_id": "run_1",
                        "timestamp": "2024-01-01T00:00:00",
                        "query": "What is the weather?",
                        "agent_response": "It's sunny",
                        "tools_used": [...]
                    }
                ],
                "session_456": [...]
            }
        }
    """

    integration: str = "google_adk"
    sessions: dict[str, list[QueryRun]] = Field(default_factory=dict)

    def add_query_run(self, session_id: str, query_run: QueryRun) -> None:
        """Add a query run to a specific session."""
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        self.sessions[session_id].append(query_run)

    def get_latest_run(self, session_id: str) -> Optional[QueryRun]:
        """Get the most recent query run for a session."""
        if session_id in self.sessions and self.sessions[session_id]:
            return self.sessions[session_id][-1]
        return None

    def get_all_tools_used(self) -> list[ToolExecution]:
        """Get all tool executions across all sessions."""
        all_tools = []
        for runs in self.sessions.values():
            for run in runs:
                all_tools.extend(run.tools_used)
        return all_tools

    def get_tool_stats(self, tool_name: str) -> dict:
        """
        Get statistics for a specific tool across all sessions.

        Args:
            tool_name: Name of the tool to get stats for

        Returns:
            Dictionary with usage_count, success_count, failure_count, total_duration_ms, recent_errors
        """
        stats = {
            'tool_name': tool_name,
            'usage_count': 0,
            'success_count': 0,
            'failure_count': 0,
            'total_duration_ms': 0,
            'recent_errors': [],
        }

        for runs in self.sessions.values():
            for run in runs:
                for tool in run.tools_used:
                    if tool.tool_name == tool_name:
                        stats['usage_count'] += 1

                        if tool.success:
                            stats['success_count'] += 1
                        else:
                            stats['failure_count'] += 1
                            if len(stats['recent_errors']) < 5:
                                stats['recent_errors'].append({
                                    'error': tool.error or '',
                                    'timestamp': tool.timestamp,
                                })

                        stats['total_duration_ms'] += tool.duration_ms

        return stats

    def get_all_tool_usage(self) -> dict[str, dict]:
        """
        Get usage statistics for all tools.

        Returns:
            Dictionary mapping tool_name -> stats dict
        """
        tool_usage = {}

        for runs in self.sessions.values():
            for run in runs:
                for tool in run.tools_used:
                    if tool.tool_name not in tool_usage:
                        tool_usage[tool.tool_name] = {
                            'tool_name': tool.tool_name,
                            'usage_count': 0,
                            'success_count': 0,
                        }

                    tool_usage[tool.tool_name]['usage_count'] += 1
                    if tool.success:
                        tool_usage[tool.tool_name]['success_count'] += 1

        return tool_usage
