"""
Client-side workflow execution engine.

Handles DAG execution, topological sorting, and parallel execution.
Tool execution is handled by google_adk integration.
"""

import logging
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Dict, List, Tuple

from ryumem.core.workflow_models import (
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

    def get_completed_nodes(self, session_id: str, user_id: str) -> set[str]:
        """
        Get completed nodes from session.

        Args:
            session_id: Session ID
            user_id: User ID

        Returns:
            Set of completed node IDs
        """
        session = self.ryumem.get_session(session_id)
        if not session:
            return set()

        session_vars = session.get("session_variables", {})
        node_results = session_vars.get("_node_results", {})

        # Return nodes with status="completed"
        return {
            node_id for node_id, result in node_results.items()
            if result.get("status") == "completed"
        }

    def build_execution_plan(
        self,
        workflow: WorkflowDefinition,
        completed_nodes: set[str] = None
    ) -> List[List[WorkflowNode]]:
        """
        Build execution plan using topological sort.

        Returns list of "waves" where each wave contains nodes that can execute in parallel.

        Args:
            workflow: Workflow definition
            completed_nodes: Set of already completed node IDs to skip

        Returns:
            List of waves, each wave is a list of nodes that can execute in parallel

        Raises:
            ValueError: If circular dependency detected
        """
        if completed_nodes is None:
            completed_nodes = set()

        # Filter out completed nodes
        nodes = [n for n in workflow.nodes if n.node_id not in completed_nodes]

        if not nodes:
            return []  # All nodes completed

        # Build dependency graph
        node_map = {node.node_id: node for node in nodes}
        in_degree = {node.node_id: 0 for node in nodes}
        dependents = defaultdict(list)

        for node in nodes:
            for dep in node.dependencies:
                # Dependency must be either in current execution plan or already completed
                if dep not in node_map and dep not in completed_nodes:
                    raise ValueError(f"Node {node.node_id} depends on unknown node {dep}")
                # Only track dependencies that are in current execution plan
                if dep in node_map:
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
        result: Dict[str, Any],
        session_id: str,
        user_id: str,
        workflow_id: str = None,
    ) -> None:
        """
        Store node execution result in session variables.

        Args:
            node_id: Node identifier
            result: Full result object with node_id, node_type, status, output, error, duration_ms, timestamp
            session_id: Session ID
            user_id: User ID
            workflow_id: Workflow ID (optional, will be included if provided)
        """
        # Get current session
        session = self.ryumem.get_session(session_id)
        if not session:
            session_variables = {}
        else:
            session_variables = session.get("session_variables", {})

        # Initialize _node_results if not exists
        if "_node_results" not in session_variables:
            session_variables["_node_results"] = {}

        # Store full result object in _node_results namespace
        session_variables["_node_results"][node_id] = result

        # Update session
        update_kwargs = {
            "session_id": session_id,
            "user_id": user_id,
            "session_variables": session_variables,
            "current_node": node_id,
            "status": "active",
        }
        if workflow_id:
            update_kwargs["workflow_id"] = workflow_id

        self.ryumem.update_session(**update_kwargs)

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

    def get_pause_info(self, session_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get pause info from _pause_info if session is paused.

        Args:
            session_id: Session ID
            user_id: User ID

        Returns:
            Pause info dict or None if not paused
        """
        session = self.ryumem.get_session(session_id)
        if not session:
            return None

        session_vars = session.get("session_variables", {})
        return session_vars.get("_pause_info")

    def set_paused(
        self,
        session_id: str,
        user_id: str,
        paused_at_node: str,
        pause_reason: str,
        prompt: str = None,
        error_details: str = None,
    ) -> None:
        """
        Set session to paused state with reason.

        Args:
            session_id: Session ID
            user_id: User ID
            paused_at_node: Node ID where workflow paused
            pause_reason: Reason for pause ("llm_trigger", "user_trigger", "error")
            prompt: Prompt text for LLM or user (optional)
            error_details: Error details if pause_reason is "error" (optional)
        """
        session = self.ryumem.get_session(session_id)
        if not session:
            session_variables = {}
        else:
            session_variables = session.get("session_variables", {})

        # Create pause info
        pause_info = {
            "paused_at_node": paused_at_node,
            "pause_reason": pause_reason,
            "paused_at": datetime.utcnow().isoformat(),
        }

        if prompt:
            pause_info["prompt"] = prompt

        if error_details:
            pause_info["error_details"] = error_details

        # Store pause info
        session_variables["_pause_info"] = pause_info

        # Update session status
        self.ryumem.update_session(
            session_id=session_id,
            user_id=user_id,
            session_variables=session_variables,
            current_node=paused_at_node,
            status="paused",
        )

        logger.info(f"Session {session_id} paused at node {paused_at_node}, reason: {pause_reason}")

    def clear_pause(self, session_id: str, user_id: str) -> None:
        """
        Clear _pause_info and set session status to active.

        Args:
            session_id: Session ID
            user_id: User ID
        """
        session = self.ryumem.get_session(session_id)
        if not session:
            return

        session_variables = session.get("session_variables", {})

        # Remove pause info
        if "_pause_info" in session_variables:
            del session_variables["_pause_info"]

        # Update session status
        self.ryumem.update_session(
            session_id=session_id,
            user_id=user_id,
            session_variables=session_variables,
            status="active",
        )

        logger.info(f"Cleared pause state for session {session_id}")

    def get_node_result(
        self,
        session_id: str,
        user_id: str,
        node_id: str,
    ) -> Dict[str, Any]:
        """
        Get specific node result from _node_results.

        Args:
            session_id: Session ID
            user_id: User ID
            node_id: Node ID

        Returns:
            Node result dict or None if not found
        """
        session = self.ryumem.get_session(session_id)
        if not session:
            return None

        session_vars = session.get("session_variables", {})
        node_results = session_vars.get("_node_results", {})

        return node_results.get(node_id)
