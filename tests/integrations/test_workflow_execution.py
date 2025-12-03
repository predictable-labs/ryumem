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
from ryumem.workflows.manager import WorkflowManager
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

    # Step 3: Verify workflow structure
    workflow_def = WorkflowDefinition(**best_workflow)
    assert len(workflow_def.nodes) == 2, "Should have 2 nodes"
    assert workflow_def.nodes[0].node_id == "fetch_weather"
    assert workflow_def.nodes[1].node_id == "analyze_weather"
    assert workflow_def.nodes[1].dependencies == ["fetch_weather"]
    print(f"✓ Verified workflow structure with {len(workflow_def.nodes)} nodes")

    # Step 4: Verify workflow can be retrieved
    retrieved_workflow = ryumem_client.get_workflow(workflow_id["workflow_id"])
    assert retrieved_workflow is not None
    assert retrieved_workflow["name"] == workflow.name
    assert len(retrieved_workflow["nodes"]) == 2
    print(f"✓ Successfully retrieved workflow: {retrieved_workflow['name']}")

    # Step 5: Execute the workflow using WorkflowManager
    workflow_manager = WorkflowManager(ryumem_client)

    initial_variables = {
        "user_location": "San Francisco",
        "user_query": user_query,
    }

    execution_result = workflow_manager.execute_workflow(
        workflow_id=workflow_id["workflow_id"],
        session_id=session_id,
        user_id=unique_user,
        initial_variables=initial_variables,
    )

    # Verify execution results
    assert execution_result["status"] == "completed"
    assert execution_result["workflow_id"] == workflow_id["workflow_id"]
    assert execution_result["session_id"] == session_id
    assert len(execution_result["node_results"]) == 2
    assert execution_result["node_results"][0]["node_id"] == "fetch_weather"
    assert execution_result["node_results"][1]["node_id"] == "analyze_weather"
    print(f"✓ Workflow executed successfully with {len(execution_result['node_results'])} nodes")

    # Step 6: Verify execution results stored in context
    final_context = execution_result["final_context"]
    assert "fetch_weather" in final_context
    assert "analyze_weather" in final_context
    assert "user_location" in final_context
    assert "user_query" in final_context
    print(f"✓ Verified {len(final_context)} variables in execution context")

    print(f"\n✓ Workflow lifecycle test completed successfully!")
    print(f"  - Created workflow with {len(workflow.nodes)} nodes")
    print(f"  - Verified semantic search can find the workflow")
    print(f"  - Verified workflow can be retrieved by ID")
    print(f"  - Executed workflow with {len(execution_result['node_results'])} nodes")
    print(f"  - Verified execution context with {len(final_context)} variables")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
