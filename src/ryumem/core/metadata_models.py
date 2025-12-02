"""
Pydantic models for episode metadata.

These models provide type safety and validation for episode metadata structures.
"""

from pydantic import BaseModel, Field
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ToolExecution(BaseModel):
    """Metadata for a single tool execution."""

    tool_name: str
    success: bool
    duration_ms: int = 0
    timestamp: str
    input_params: dict = Field(default_factory=dict)
    output_summary: str = ""
    error: Optional[str] = None
    parent_tool_name: Optional[str] = Field(
        default=None,
        description="Name of immediate parent tool if called from another tool"
    )


class QueryRun(BaseModel):
    """A single query execution/run."""

    run_id: str
    user_id: str
    timestamp: str
    query: str
    augmented_query: Optional[str] = None  # Query with historical context added
    agent_response: str = ""
    tools_used: list[ToolExecution] = Field(default_factory=list)
    llm_saved_memory: str = ""  # Memory saved by LLM during this run


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

    def get_simple_tool_usage_summary(self) -> str:
        """
        Create concise tool usage summary (grouped by success/fail).

        Returns:
            String showing inputs that worked/failed for each tool with response sizes and errors
        """
        from collections import defaultdict

        def get_response_size(output_summary: str) -> str:
            """Calculate response size based on type."""
            if not output_summary or output_summary.strip() in ['', 'None', 'null', 'N/A']:
                return 'None'

            return f"{len(output_summary)} chars"

        # Group by tool name, then by input params
        tool_data = defaultdict(lambda: {'worked': [], 'failed': [], 'empty': []})

        for tool in self.get_all_tools_used():
            name = tool.tool_name

            # Skip if no input params
            if not tool.input_params:
                continue

            # Convert input params to simple string
            input_str = ', '.join([f"{k}={v}" for k, v in tool.input_params.items()])

            # Get response size
            response_size = get_response_size(tool.output_summary)

            # Create entry with size information
            entry = f"{input_str} (response: {response_size})"

            # Add error if present
            if tool.error:
                entry += f" [error: {tool.error}]"

            # Check if output was empty
            is_empty = not tool.output_summary or tool.output_summary.strip() in ['', 'None', 'null', 'N/A']

            if is_empty:
                tool_data[name]['empty'].append(entry)
            elif tool.success:
                tool_data[name]['worked'].append(entry)
            else:
                tool_data[name]['failed'].append(entry)

        summaries = []
        for name, data in tool_data.items():
            parts = [f"{name}"]

            if data['worked']:
                parts.append(f" with [{', '.join(data['worked'])}]")
            if data['failed']:
                if data['worked']:
                    parts.append("; failed")
                parts.append(f" with [{', '.join(data['failed'])}]")
            if data['empty']:
                if data['worked'] or data['failed']:
                    parts.append("; returned empty")
                else:
                    parts.append(f" returned empty")
                parts.append(f" for [{', '.join(data['empty'])}]")

            summaries.append(''.join(parts))

        return ', '.join(summaries)

    def get_tool_usage_summary(self) -> str:
        """
        Create detailed tool usage summary including return values.
        
        Returns:
            String showing inputs and outputs for each tool execution.
            Format: tool_name with [input] -> [output]
        """
        summaries = []
        
        for tool in self.get_all_tools_used():
            name = tool.tool_name
            
            # Format input
            input_str = ""
            if tool.input_params:
                input_str = ', '.join([f"{k}={v}" for k, v in tool.input_params.items()])
            
            # Format output
            output_str = "[]"
            if tool.output_summary and tool.output_summary.strip() not in ['', 'None', 'null', 'N/A']:
                output_str = tool.output_summary
            
            # Construct summary string
            if input_str:
                summary = f"{name} with [{input_str}] -> {output_str}"
            else:
                summary = f"{name} -> {output_str}"
                
            summaries.append(summary)
            
        return ', '.join(summaries)
