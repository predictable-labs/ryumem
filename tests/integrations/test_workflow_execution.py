"""
Integration test for workflow search and execution.

Tests the complete workflow lifecycle:
1. Create a workflow
2. Search for it using a query
3. Execute the workflow
"""

import pytest
import os
import uuid
from datetime import datetime

from ryumem import Ryumem
from ryumem.workflows.engine import WorkflowEngine
from ryumem.core.workflow_models import WorkflowDefinition, WorkflowNode


@pytest.fixture
def ryumem_client():
    """Create Ryumem client for testing."""
    return Ryumem()


@pytest.fixture
def unique_user():
    """Generate unique user ID for test isolation."""
    return f"test_user_{uuid.uuid4().hex[:8]}"


def test_search_and_execute_workflow(ryumem_client, unique_user):
    """
    Integration test: Search for workflow by query and execute it.

    Flow:
    1. Create a sample workflow
    2. Search for it using a user query
    3. Build execution plan and execute workflow
    """
    # Step 1: Create a sample workflow
    workflow = WorkflowDefinition(
        workflow_id=f"test_wf_{uuid.uuid4().hex[:8]}",
        name="Weather Analysis Workflow",
        description="Get weather and analyze it",
        query_templates=[
            "What's the weather like?",
            "How's the weather today?",
            "Tell me about the weather",
        ],
        nodes=[
            WorkflowNode(
                node_id="fetch_weather",
                node_type="tool",
                tool_name="get_weather",
                input_params={"location": "${user_location}"},
                dependencies=[],
            ),
            WorkflowNode(
                node_id="analyze_weather",
                node_type="tool",
                tool_name="analyze_data",
                input_params={"data": "${fetch_weather}"},
                dependencies=["fetch_weather"],
            ),
        ],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        success_count=0,
        failure_count=0,
    )

    workflow_id = ryumem_client.create_workflow(workflow.model_dump(mode='json'))
    assert workflow_id is not None
    print(f"\n✓ Created workflow: {workflow.name}")

    # Step 2: User asks a question - search for matching workflow
    user_query = "How's the weather today?"
    session_id = f"session_{uuid.uuid4().hex[:8]}"

    matching_workflows = ryumem_client.search_workflows(
        query=user_query,
        user_id=unique_user,
        threshold=0.5,
    )

    assert len(matching_workflows) > 0, "Should find matching workflow"
    best_workflow = matching_workflows[0]
    print(f"✓ Found workflow via search: {best_workflow['name']}")

    # Step 3: Build execution plan
    workflow_def = WorkflowDefinition(**best_workflow)
    engine = WorkflowEngine(ryumem_client)
    execution_plan = engine.build_execution_plan(workflow_def.nodes)

    assert len(execution_plan) == 2, "Should have 2 execution waves"
    assert execution_plan[0][0].node_id == "fetch_weather"
    assert execution_plan[1][0].node_id == "analyze_weather"
    print(f"✓ Built execution plan with {len(execution_plan)} waves")

    # Step 4: Initialize session and execute
    initial_variables = {
        "user_location": "San Francisco",
        "user_query": user_query,
    }

    # Create session with workflow
    ryumem_client.get_or_create_session(session_id=session_id, user_id=unique_user)
    ryumem_client.update_session(
        session_id=session_id,
        user_id=unique_user,
        workflow_id=workflow_id,
        session_variables=initial_variables,
        status="active",
    )

    # Simulate execution by storing results for each node
    # In real execution, this would call actual tools
    completed_nodes = set()

    for wave_num, wave in enumerate(execution_plan, 1):
        print(f"✓ Executing wave {wave_num}: {[n.node_id for n in wave]}")

        for node in wave:
            # Simulate node execution
            node_result = {"status": "completed", "data": f"result_of_{node.node_id}"}

            # Store result in session
            engine.store_node_result(
                node_id=node.node_id,
                result=node_result,
                session_id=session_id,
                user_id=unique_user,
            )
            completed_nodes.add(node.node_id)

    # Mark workflow as complete
    engine.mark_workflow_complete(
        workflow_id=workflow_id,
        session_id=session_id,
        user_id=unique_user,
        success=True,
    )

    # Verify execution completed
    final_session = ryumem_client.get_session(session_id)
    assert final_session["status"] == "completed"
    assert "fetch_weather" in final_session["session_variables"]
    assert "analyze_weather" in final_session["session_variables"]

    # Verify metrics updated
    final_workflow = ryumem_client.get_workflow(workflow_id)
    assert final_workflow["success_count"] == 1

    print(f"✓ Workflow executed successfully!")
    print(f"  - Completed {len(completed_nodes)} nodes")
    print(f"  - Session status: {final_session['status']}")
    print(f"  - Workflow success count: {final_workflow['success_count']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
