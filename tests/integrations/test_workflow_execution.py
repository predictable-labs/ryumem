"""
Integration test for automatic workflow execution via Google ADK integration.

Tests the complete workflow auto-execution lifecycle:
1. Create a workflow with query templates
2. Enable workflow auto-execution in config
3. Send a query through Google ADK integration
4. Verify workflow was automatically executed
5. Verify query was enriched with workflow results
"""

import pytest
import os
import uuid
from datetime import datetime
from unittest.mock import Mock, MagicMock

from ryumem import Ryumem
from ryumem.workflows.manager import WorkflowManager
from ryumem.core.workflow_models import WorkflowDefinition, WorkflowNode
from ryumem.integrations.google_adk import RyumemGoogleADK, _execute_matching_workflow


@pytest.fixture
def ryumem_client():
    """Create Ryumem client for testing with workflow config enabled."""
    client = Ryumem()
    # Enable workflow features
    client.config.workflow.workflow_mode_enabled = True
    client.config.workflow.auto_execute_workflows = True
    client.config.workflow.similarity_threshold = 0.5
    return client


@pytest.fixture
def unique_user():
    """Generate unique user ID for test isolation."""
    return f"test_user_{uuid.uuid4().hex[:8]}"


def test_workflow_auto_execution_via_adk_integration(ryumem_client, unique_user):
    """
    Integration test: Workflow automatically executes when query matches.

    Flow:
    1. Create a sample workflow with query templates
    2. Send query through Google ADK integration
    3. Verify workflow was auto-executed
    4. Verify query was enriched with workflow results
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
                input_params={"location": "San Francisco"},
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

    # Step 2: Create mock Google ADK agent and memory integration
    mock_agent = Mock()
    mock_agent.tools = []
    mock_agent.instruction = "You are a helpful assistant"

    memory = RyumemGoogleADK(
        agent=mock_agent,
        ryumem=ryumem_client,
        tool_tracker=None
    )
    print(f"✓ Created Google ADK memory integration")

    # Step 3: Simulate user query - workflow should auto-execute
    user_query = "How's the weather today?"
    session_id = f"session_{uuid.uuid4().hex[:8]}"

    print(f"\n✓ Testing query: '{user_query}'")
    print(f"  - Workflow mode enabled: {ryumem_client.config.workflow.workflow_mode_enabled}")
    print(f"  - Auto-execute enabled: {ryumem_client.config.workflow.auto_execute_workflows}")
    print(f"  - Similarity threshold: {ryumem_client.config.workflow.similarity_threshold}")

    # Call the workflow execution function directly (this is what happens in the ADK integration)
    enriched_query = _execute_matching_workflow(
        query_text=user_query,
        memory=memory,
        user_id=unique_user,
        session_id=session_id
    )

    # Step 4: Verify workflow was executed and query was enriched
    assert enriched_query is not None, "Workflow should have been executed"
    assert user_query in enriched_query, "Original query should be preserved"
    assert "Workflow Executed" in enriched_query, "Should contain workflow execution marker"
    assert "Weather Analysis Workflow" in enriched_query, "Should contain workflow name"
    assert "fetch_weather" in enriched_query, "Should contain node results"
    assert "analyze_weather" in enriched_query, "Should contain node results"
    print(f"✓ Workflow auto-executed successfully")

    # Step 5: Verify query enrichment format
    assert "Workflow Results:" in enriched_query, "Should have results section"
    print(f"✓ Query enriched with workflow results (+{len(enriched_query) - len(user_query)} chars)")

    # Step 6: Verify enriched query structure
    enriched_lines = enriched_query.split('\n')
    assert len(enriched_lines) > 3, "Should have multiple lines in enriched query"
    print(f"✓ Enriched query has {len(enriched_lines)} lines")

    # Step 7: Test with workflow config disabled
    ryumem_client.config.workflow.auto_execute_workflows = False
    enriched_query_disabled = _execute_matching_workflow(
        query_text=user_query,
        memory=memory,
        user_id=unique_user,
        session_id=session_id
    )
    assert enriched_query_disabled is None, "Should not execute when disabled"
    print(f"✓ Workflow correctly skipped when auto_execute_workflows=False")

    print(f"\n✓ Workflow auto-execution test completed successfully!")
    print(f"  - Created workflow with {len(workflow.nodes)} nodes")
    print(f"  - Verified config-based workflow execution")
    print(f"  - Verified query enrichment with workflow results")
    print(f"  - Verified workflow execution can be disabled via config")
    print(f"\nEnriched query preview:")
    print(f"{'='*60}")
    print(enriched_query[:500] + "..." if len(enriched_query) > 500 else enriched_query)
    print(f"{'='*60}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
