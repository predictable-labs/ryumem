"""
Shared workflow data models for both client and server.

Workflows are represented as DAGs (Directed Acyclic Graphs) of tool executions
with session-based variable flow.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class WorkflowExecutionStatus(str, Enum):
    """Status of workflow execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeExecutionStatus(str, Enum):
    """Status of individual node execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class NodeType(str, Enum):
    """Type of workflow node."""
    TOOL = "tool"              # Execute a tool
    MCP = "mcp"                # MCP server operation
    LLM_TRIGGER = "llm_trigger"  # LLM-based decision
    USER_TRIGGER = "user_trigger"  # Wait for user input
    CONDITION = "condition"    # Conditional branching


class RetryConfig(BaseModel):
    """Retry configuration for node execution."""
    enabled: bool = Field(default=False, description="Whether retry is enabled")
    max_attempts: int = Field(default=3, description="Maximum number of retry attempts")
    backoff_strategy: Literal["fixed", "exponential"] = Field(
        default="exponential",
        description="Backoff strategy for retries"
    )
    initial_delay_ms: int = Field(
        default=1000,
        description="Initial delay in milliseconds before first retry"
    )
    max_delay_ms: int = Field(
        default=30000,
        description="Maximum delay in milliseconds between retries"
    )


class ConditionBranch(BaseModel):
    """Single branch in a condition node."""
    branch_id: str = Field(description="Unique identifier for this branch")
    condition_expr: str = Field(description="Condition expression to evaluate")
    next_nodes: List[str] = Field(
        default_factory=list,
        description="Node IDs to execute if condition is true"
    )


class WorkflowNode(BaseModel):
    """
    Represents a single node in a workflow DAG.

    Supports multiple node types (tool, MCP, LLM, user trigger, condition).
    Nodes can reference session variables using ${variable} syntax.
    Previous node outputs are stored as ${node_id}.
    """
    node_id: str = Field(description="Unique identifier for this node")
    node_type: NodeType = Field(default=NodeType.TOOL, description="Type of node")

    # Tool/MCP specific fields
    tool_name: Optional[str] = Field(default=None, description="Name of the tool to execute (for TOOL and MCP types)")
    mcp_server: Optional[str] = Field(default=None, description="MCP server identifier (for MCP type)")

    # LLM Trigger specific fields
    llm_prompt: Optional[str] = Field(default=None, description="Prompt for LLM evaluation (for LLM_TRIGGER type)")
    llm_output_variable: Optional[str] = Field(default=None, description="Variable to store LLM output")

    # User Trigger specific fields
    user_prompt: Optional[str] = Field(default=None, description="Message to show user (for USER_TRIGGER type)")
    user_input_variable: Optional[str] = Field(default=None, description="Variable to store user input")

    # Condition specific fields
    branches: List[ConditionBranch] = Field(
        default_factory=list,
        description="List of conditional branches (for CONDITION type)"
    )
    default_branch: Optional[str] = Field(
        default=None,
        description="Default node ID if no conditions match (for CONDITION type)"
    )

    # Common fields
    input_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Input parameters. Can reference ${variable} or ${node_id}"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="List of node_ids this node depends on"
    )
    retry_config: RetryConfig = Field(
        default_factory=RetryConfig,
        description="Retry configuration for this node"
    )
    timeout_ms: Optional[int] = Field(
        default=None,
        description="Timeout in milliseconds for node execution"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "node_id": "fetch_weather",
                    "node_type": "tool",
                    "tool_name": "get_weather",
                    "input_params": {"location": "${user_location}"},
                    "dependencies": [],
                    "retry_config": {"enabled": True, "max_attempts": 3}
                },
                {
                    "node_id": "check_result",
                    "node_type": "condition",
                    "branches": [
                        {
                            "branch_id": "success",
                            "condition_expr": "status == 'success'",
                            "next_nodes": ["process_success"]
                        },
                        {
                            "branch_id": "error",
                            "condition_expr": "status == 'error'",
                            "next_nodes": ["handle_error"]
                        }
                    ],
                    "default_branch": "fallback_node",
                    "dependencies": ["fetch_weather"]
                }
            ]
        }


class WorkflowDefinition(BaseModel):
    """
    Defines a workflow as a DAG of tool executions.

    Workflows can be stored in the vector DB and retrieved for similar queries.
    """
    workflow_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the workflow"
    )
    name: str = Field(description="Human-readable name for the workflow")
    description: str = Field(description="Description of what the workflow does")
    query_templates: List[str] = Field(description="List of query patterns that trigger this workflow")
    nodes: List[WorkflowNode] = Field(description="List of nodes in the workflow DAG")
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the workflow was created"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the workflow was last updated"
    )
    success_count: int = Field(
        default=0,
        description="Number of successful executions"
    )
    failure_count: int = Field(
        default=0,
        description="Number of failed executions"
    )
    user_id: Optional[str] = Field(
        default=None,
        description="User ID who created this workflow (None = global)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "workflow_id": "wf_123",
                "name": "Weather Workflow",
                "description": "Get weather and provide recommendation",
                "query_templates": [
                    "What's the weather like?",
                    "How's the weather today?",
                    "Tell me about the weather",
                    "What's the temperature?"
                ],
                "nodes": [
                    {
                        "node_id": "fetch_weather",
                        "tool_name": "get_weather",
                        "input_params": {"location": "${user_location}"},
                        "dependencies": []
                    },
                    {
                        "node_id": "generate_recommendation",
                        "tool_name": "get_recommendation",
                        "input_params": {"weather": "${fetch_weather}"},
                        "dependencies": ["fetch_weather"]
                    }
                ],
                "success_count": 5
            }
        }


class NodeExecutionResult(BaseModel):
    """Result of executing a single node."""
    node_id: str
    status: NodeExecutionStatus
    output: Any = None
    error: Optional[str] = None
    duration_ms: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WorkflowExecutionResult(BaseModel):
    """Result of executing a workflow."""
    workflow_id: str
    session_id: str
    status: WorkflowExecutionStatus
    node_results: List[NodeExecutionResult] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    def add_node_result(self, result: NodeExecutionResult) -> None:
        """Add a node execution result."""
        self.node_results.append(result)

    def get_node_result(self, node_id: str) -> Optional[NodeExecutionResult]:
        """Get result for a specific node."""
        for result in self.node_results:
            if result.node_id == node_id:
                return result
        return None
