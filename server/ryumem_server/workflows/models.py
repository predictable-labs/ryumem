"""
Data models for workflow orchestration.

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


class WorkflowNode(BaseModel):
    """
    Represents a single tool execution in a workflow DAG.

    Nodes can reference session variables using ${session_variables.key} syntax.
    """
    node_id: str = Field(description="Unique identifier for this node")
    tool_name: str = Field(description="Name of the tool to execute")
    input_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Input parameters for the tool. Can reference ${session_variables.key}"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="List of node_ids this node depends on"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "node_id": "node_1",
                "tool_name": "get_weather",
                "input_params": {
                    "location": "${session_variables.user_location}"
                },
                "dependencies": []
            }
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
    query_template: str = Field(description="Original query pattern that this workflow handles")
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
                "query_template": "What's the weather like?",
                "nodes": [
                    {
                        "node_id": "node_1",
                        "tool_name": "get_weather",
                        "input_params": {"location": "${session_variables.user_location}"},
                        "dependencies": []
                    },
                    {
                        "node_id": "node_2",
                        "tool_name": "get_recommendation",
                        "input_params": {"weather": "${session_variables.node_1_output}"},
                        "dependencies": ["node_1"]
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
