"""
Client-side workflow execution engine.

Handles DAG execution, topological sorting, and parallel execution.
Tool execution is handled by google_adk integration.
"""

import logging
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Dict, List, Tuple

from ryumem.workflows.models import (
    WorkflowDefinition,
    WorkflowNode,
    WorkflowExecutionStatus,
    NodeExecutionStatus,
    NodeExecutionResult,
    WorkflowExecutionResult,
)

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """
    Client-side workflow execution engine.

    Coordinates DAG execution:
    - Topological sorting for execution order
    - Parallel execution of independent nodes
    - Session state tracking

    Actual tool execution is handled by google_adk.
    """

    def __init__(self, ryumem_client: Any):
        """
        Initialize workflow engine.

        Args:
            ryumem_client: Ryumem SDK instance for API calls
        """
        self.ryumem = ryumem_client

    def build_execution_plan(self, nodes: List[WorkflowNode]) -> List[List[WorkflowNode]]:
        """
        Build execution plan using topological sort.

        Returns list of "waves" where each wave contains nodes that can execute in parallel.

        Args:
            nodes: List of workflow nodes

        Returns:
            List of waves, each wave is a list of nodes that can execute in parallel

        Raises:
            ValueError: If circular dependency detected
        """
        # Build dependency graph
        node_map = {node.node_id: node for node in nodes}
        in_degree = {node.node_id: 0 for node in nodes}
        dependents = defaultdict(list)

        for node in nodes:
            for dep in node.dependencies:
                if dep not in node_map:
                    raise ValueError(f"Node {node.node_id} depends on unknown node {dep}")
                dependents[dep].append(node.node_id)
                in_degree[node.node_id] += 1

        # Topological sort with wave detection
        waves = []
        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])

        while queue:
            # All nodes in queue have no remaining dependencies - they form a wave
            wave = []
            wave_size = len(queue)

            for _ in range(wave_size):
                node_id = queue.popleft()
                wave.append(node_map[node_id])

                # Reduce in-degree for dependent nodes
                for dependent_id in dependents[node_id]:
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        queue.append(dependent_id)

            waves.append(wave)

        # Check for circular dependencies
        if sum(in_degree.values()) > 0:
            remaining = [node_id for node_id, degree in in_degree.items() if degree > 0]
            raise ValueError(f"Circular dependency detected in nodes: {remaining}")

        return waves

    def store_node_result(
        self,
        node_id: str,
        result: Any,
        session_id: str,
        user_id: str,
    ) -> None:
        """
        Store node execution result in session variables.

        Args:
            node_id: Node identifier
            result: Tool execution result
            session_id: Session ID
            user_id: User ID
        """
        # Get current session
        session = self.ryumem.get_session(session_id)
        if not session:
            session_variables = {}
        else:
            session_variables = session.get("session_variables", {})

        # Store result using node_id as key
        session_variables[node_id] = result

        # Update session
        self.ryumem.update_session(
            session_id=session_id,
            user_id=user_id,
            session_variables=session_variables,
            current_node=node_id,
            status="active",
        )

        logger.info(f"Stored result for node {node_id} in session {session_id}")

    def mark_workflow_complete(
        self,
        workflow_id: str,
        session_id: str,
        user_id: str,
        success: bool,
        error: str = None,
    ) -> None:
        """
        Mark workflow as complete (success or failure).

        Args:
            workflow_id: Workflow ID
            session_id: Session ID
            user_id: User ID
            success: Whether workflow succeeded
            error: Error message if failed
        """
        # Update session status
        self.ryumem.update_session(
            session_id=session_id,
            user_id=user_id,
            status="completed" if success else "error",
        )

        # Mark workflow success/failure
        if success:
            self.ryumem.mark_workflow_success(
                workflow_id=workflow_id,
                session_id=session_id,
            )
            logger.info(f"Workflow {workflow_id} completed successfully")
        else:
            self.ryumem.mark_workflow_failure(
                workflow_id=workflow_id,
                session_id=session_id,
                error=error,
            )
            logger.error(f"Workflow {workflow_id} failed: {error}")

    def get_next_nodes(
        self,
        workflow_def: WorkflowDefinition,
        completed_nodes: set,
    ) -> List[WorkflowNode]:
        """
        Get next nodes that are ready to execute.

        Args:
            workflow_def: Workflow definition
            completed_nodes: Set of node_ids that have been completed

        Returns:
            List of nodes ready to execute (all dependencies met)
        """
        ready_nodes = []

        for node in workflow_def.nodes:
            if node.node_id in completed_nodes:
                continue

            # Check if all dependencies are satisfied
            dependencies_met = all(dep in completed_nodes for dep in node.dependencies)

            if dependencies_met:
                ready_nodes.append(node)

        return ready_nodes
