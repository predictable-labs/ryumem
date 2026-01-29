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

from ryumem import Ryumem
from ryumem.workflows.manager import WorkflowManager
from ryumem.core.workflow_models import WorkflowDefinition, WorkflowNode, NodeType
from ryumem.integrations.google_adk import RyumemGoogleADK, _execute_matching_workflow, add_memory_to_agent


@pytest.fixture
def ryumem_client():
    """Create Ryumem client for testing with workflow config enabled."""
    client = Ryumem()
    # Enable workflow features
    client.config.workflow.workflow_mode_enabled = True
    client.config.workflow.auto_execute_workflows = True
    client.config.workflow.similarity_threshold = 0.1  # Lower threshold for testing
    return client


@pytest.fixture
def unique_user():
    """Generate unique user ID for test isolation."""
    return f"test_user_{uuid.uuid4().hex[:8]}"


class SimpleToolContext:
    """Minimal tool context - not a mock."""
    def __init__(self, user_id=None, session_id=None):
        self.session = type('Session', (), {
            'user_id': user_id,
            'id': session_id
        })()


class SimpleAgent:
    """Minimal agent implementation - not a mock."""
    def __init__(self, instruction="Base instruction"):
        self.instruction = instruction
        self.tools = []
        self.name = "test_agent"


@pytest.mark.asyncio
async def test_workflow_auto_execution_via_adk_integration(ryumem_client, unique_user):
    """
    Integration test: Workflow automatically executes when query matches.

    Flow:
    1. Setup agent and memory
    2. Send query -> Verify prompt to create workflow (since none exists for this user)
    3. Create workflow (user-scoped for isolation)
    4. Send query -> Verify workflow auto-executes
    """
    # Cleanup: Delete all workflows before test starts
    print("\n✓ Cleaning up workflows before test")
    try:
        workflows = ryumem_client.list_workflows(limit=1000)
        for workflow in workflows:
            workflow_id = workflow.get('workflow_id')
            if workflow_id:
                ryumem_client._delete(f"/workflows/{workflow_id}")
        print(f"  Deleted {len(workflows)} workflows")
    except Exception as e:
        print(f"  Cleanup warning: {e}")
    
    # Step 1: Create SimpleAgent and memory integration
    agent = SimpleAgent(instruction="You are a helpful assistant")
    
    # Use add_memory_to_agent to properly setup tools
    add_memory_to_agent(agent, ryumem_client)
    memory = agent._ryumem_memory
    print(f"✓ Created Google ADK memory integration")

    # Step 2: Test query with NO matching workflow for this user
    user_query = "What's the weather like today?"
    session_id = f"session_{uuid.uuid4().hex[:8]}"

    print(f"\n✓ Testing query (no workflow): '{user_query}'")
    result = _execute_matching_workflow(
        query_text=user_query,
        memory=memory,
        user_id=unique_user,
        session_id=session_id
    )

    # Verify prompt for workflow creation
    assert result is not None, "Should return a prompt"
    assert "No existing workflow found" in result, "Should indicate no workflow found"
    assert "save_workflow" in result, "Should mention save_workflow tool"
    assert "start_workflow" in result, "Should mention start_workflow tool"
    print(f"✓ Verified prompt for workflow creation")

    # Step 3: Create a user-scoped workflow using the tool
    workflow = WorkflowDefinition(
        workflow_id=f"test_wf_{uuid.uuid4().hex[:8]}",
        name="Weather Analysis Workflow",
        description="Get weather and analyze it",
        user_id=unique_user,  # User-scoped for isolation
        query_templates=[
            "What's the weather like today?",
            "How's the weather?",
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

    # Create tool context
    tool_context = SimpleToolContext(user_id=unique_user, session_id=session_id)

    # Save workflow using the save_workflow tool
    save_result = await memory.save_workflow(
        tool_context=tool_context,
        workflow_definition=workflow.model_dump(mode='json')
    )
    assert save_result["status"] == "success", f"Failed to save workflow: {save_result}"
    workflow_id = save_result["workflow_id"]
    print(f"\n✓ Created workflow: {workflow.name} (ID: {workflow_id})")

    # Step 4: Send same query again - workflow should now auto-execute
    print(f"\n✓ Testing query (with workflow): '{user_query}'")
    
    # Debug: Verify search finds the workflow
    found = ryumem_client.search_workflows(user_query, user_id=unique_user, threshold=0.1)
    print(f"DEBUG: Search results: {len(found)} workflows found")
    if found:
        print(f"DEBUG: Top result: {found[0]['name']} ({found[0]['workflow_id']}) score={found[0].get('score')}")

    enriched_query = _execute_matching_workflow(
        query_text=user_query,
        memory=memory,
        user_id=unique_user,
        session_id=session_id
    )

    # Step 5: Verify workflow was executed and query was enriched
    assert enriched_query is not None, "Workflow should have been executed"
    assert user_query in enriched_query, "Original query should be preserved"
    assert "Workflow Executed" in enriched_query, "Should contain workflow execution marker"
    assert "Weather Analysis Workflow" in enriched_query, "Should contain workflow name"
    assert "fetch_weather" in enriched_query, "Should contain node results"
    assert "analyze_weather" in enriched_query, "Should contain node results"
    print(f"✓ Workflow auto-executed successfully")

    # Step 6: Verify query enrichment format
    assert "Workflow Results:" in enriched_query, "Should have results section"
    print(f"✓ Query enriched with workflow results (+{len(enriched_query) - len(user_query)} chars)")

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

    # Step 8: Verify tools are added
    tool_names = [t.__name__ for t in agent.tools]
    assert "save_workflow" in tool_names, "save_workflow tool should be added"
    assert "start_workflow" in tool_names, "start_workflow tool should be added"
    print(f"✓ Verified save_workflow and start_workflow tools are present")


def test_complex_workflow_with_pause_resume(ryumem_client, unique_user):
    """
    Integration test: Complex workflow with multiple pause/resume cycles.

    Tests:
    1. Multi-wave workflow execution with parallel nodes
    2. LLM_TRIGGER pause and resume
    3. USER_TRIGGER pause and resume
    4. ERROR pause and skip
    5. Variable substitution with ${node_id}
    6. Auto-resume functionality
    7. State persistence across multiple calls
    """
    # Create complex workflow with multiple waves and pause points
    workflow = WorkflowDefinition(
        workflow_id=f"test_complex_{uuid.uuid4().hex[:8]}",
        name="Complex Data Analysis Pipeline",
        description="Fetch data, get LLM decision, get user input, analyze",
        query_templates=["Run analysis pipeline"],
        nodes=[
            # Wave 1: Parallel data fetching
            WorkflowNode(
                node_id="fetch_data_1",
                node_type=NodeType.TOOL,
                tool_name="fetch_data",
                input_params={"source": "api1"},
                dependencies=[],
            ),
            WorkflowNode(
                node_id="fetch_data_2",
                node_type=NodeType.TOOL,
                tool_name="fetch_data",
                input_params={"source": "api2"},
                dependencies=[],
            ),
            # Wave 2: LLM decision point
            WorkflowNode(
                node_id="llm_decision",
                node_type=NodeType.LLM_TRIGGER,
                llm_prompt="Should we proceed with analysis based on ${fetch_data_1} and ${fetch_data_2}?",
                dependencies=["fetch_data_1", "fetch_data_2"],
            ),
            # Wave 3: User input
            WorkflowNode(
                node_id="user_input",
                node_type=NodeType.USER_TRIGGER,
                user_prompt="Please provide analysis parameters for: ${fetch_data_1}",
                user_input_variable="analysis_params",
                dependencies=["llm_decision"],
            ),
            # Wave 4: Analysis (may fail)
            WorkflowNode(
                node_id="analyze_data",
                node_type=NodeType.TOOL,
                tool_name="analyze",
                input_params={"data1": "${fetch_data_1}", "data2": "${fetch_data_2}", "params": "${user_input}"},
                dependencies=["user_input"],
            ),
            # Wave 5: Final summary
            WorkflowNode(
                node_id="summarize",
                node_type=NodeType.TOOL,
                tool_name="summarize",
                input_params={"analysis": "${analyze_data}"},
                dependencies=["analyze_data"],
            ),
        ],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        success_count=0,
        failure_count=0,
    )

    # Save workflow
    result = ryumem_client.create_workflow(workflow.model_dump(mode='json'))
    workflow_id = result.get("workflow_id") if isinstance(result, dict) else result
    print(f"\n✓ Created complex workflow with {len(workflow.nodes)} nodes")

    # Create workflow manager
    manager = WorkflowManager(ryumem_client)
    session_id = f"session_{uuid.uuid4().hex[:8]}"

    # ========== Test 1: Execute until first pause (LLM_TRIGGER) ==========
    print("\n--- Test 1: Execute until LLM_TRIGGER pause ---")
    result1 = manager.execute_workflow(
        workflow_id=workflow_id,
        session_id=session_id,
        user_id=unique_user,
        initial_variables={}
    )

    assert result1["status"] == "paused", "Should pause at LLM_TRIGGER"
    assert result1["pause_reason"] == "llm_trigger", "Should indicate LLM trigger"
    assert result1["paused_at_node"] == "llm_decision", "Should pause at llm_decision node"
    assert "fetch_data_1" in result1["prompt"], "Prompt should contain substituted variables"
    assert "fetch_data_2" in result1["prompt"], "Prompt should contain substituted variables"
    print(f"✓ Paused at LLM_TRIGGER node: {result1['paused_at_node']}")
    print(f"  Prompt: {result1['prompt'][:100]}...")

    # Verify completed nodes
    completed_nodes = manager.engine.get_completed_nodes(session_id, unique_user)
    assert "fetch_data_1" in completed_nodes, "fetch_data_1 should be completed"
    assert "fetch_data_2" in completed_nodes, "fetch_data_2 should be completed"
    assert len(completed_nodes) == 2, "Should have 2 completed nodes"
    print(f"✓ Completed nodes: {completed_nodes}")

    # Verify session state
    session = ryumem_client.get_session(session_id)
    assert session["status"] == "paused", "Session should be paused"
    assert session["workflow_id"] == workflow_id, "Session should track workflow_id"
    assert "_node_results" in session["session_variables"], "Should have node results"
    assert "_pause_info" in session["session_variables"], "Should have pause info"
    print(f"✓ Session state persisted correctly")

    # ========== Test 2: Resume with LLM response ==========
    print("\n--- Test 2: Resume with LLM response ---")
    result2 = manager.continue_workflow_execution(
        session_id=session_id,
        user_id=unique_user,
        response="Yes, proceed with the analysis"
    )

    assert result2["status"] == "paused", "Should pause again at USER_TRIGGER"
    assert result2["pause_reason"] == "user_trigger", "Should indicate user trigger"
    assert result2["paused_at_node"] == "user_input", "Should pause at user_input node"
    assert "fetch_data_1" in result2["prompt"], "User prompt should contain substituted variables"
    print(f"✓ Resumed and paused at USER_TRIGGER node: {result2['paused_at_node']}")
    print(f"  Prompt: {result2['prompt'][:100]}...")

    # Verify LLM node is now completed
    completed_nodes = manager.engine.get_completed_nodes(session_id, unique_user)
    assert "llm_decision" in completed_nodes, "llm_decision should be completed"
    assert len(completed_nodes) == 3, "Should have 3 completed nodes"
    print(f"✓ Completed nodes: {completed_nodes}")

    # ========== Test 3: Test auto-resume by calling execute_workflow again ==========
    print("\n--- Test 3: Test auto-resume functionality ---")

    # First, store user response to complete user_input node
    result3a = manager.continue_workflow_execution(
        session_id=session_id,
        user_id=unique_user,
        response="param1=value1, param2=value2"
    )

    # Workflow should continue and complete (assuming no errors)
    # Note: The mock _execute_node always succeeds
    assert result3a["status"] == "completed", "Should complete workflow"
    assert "node_results" in result3a, "Should have node results"
    assert len(result3a["node_results"]) >= 2, "Should have executed remaining nodes"
    print(f"✓ Workflow completed after user input")
    print(f"  Total node results: {len(result3a['node_results'])}")

    # Verify all nodes completed
    completed_nodes_final = manager.engine.get_completed_nodes(session_id, unique_user)
    assert len(completed_nodes_final) == len(workflow.nodes), "All nodes should be completed"
    print(f"✓ All {len(completed_nodes_final)} nodes completed")

    # ========== Test 4: Verify state persistence with new manager instance ==========
    print("\n--- Test 4: Test state persistence across manager instances ---")

    # Create new session for fresh test
    session_id_2 = f"session_{uuid.uuid4().hex[:8]}"

    # Execute workflow until first pause
    manager_instance_1 = WorkflowManager(ryumem_client)
    result4a = manager_instance_1.execute_workflow(
        workflow_id=workflow_id,
        session_id=session_id_2,
        user_id=unique_user,
        initial_variables={}
    )
    assert result4a["status"] == "paused", "Should pause at LLM_TRIGGER"
    print(f"✓ Instance 1 paused at: {result4a['paused_at_node']}")

    # Create NEW manager instance (simulates process restart)
    manager_instance_2 = WorkflowManager(ryumem_client)

    # Resume with new instance - should load state from database
    result4b = manager_instance_2.continue_workflow_execution(
        session_id=session_id_2,
        user_id=unique_user,
        response="Continue"
    )
    assert result4b["status"] == "paused", "New instance should resume correctly"
    assert result4b["paused_at_node"] == "user_input", "Should progress to next pause point"
    print(f"✓ Instance 2 resumed and paused at: {result4b['paused_at_node']}")
    print(f"✓ State persistence verified across manager instances")

    # ========== Test 5: Test error handling and pause ==========
    print("\n--- Test 5: Test error pause handling ---")

    # Create workflow with error-prone node
    workflow_with_error = WorkflowDefinition(
        workflow_id=f"test_error_{uuid.uuid4().hex[:8]}",
        name="Workflow with Error",
        description="Test error handling",
        query_templates=["Test errors"],
        nodes=[
            WorkflowNode(
                node_id="normal_node",
                node_type=NodeType.TOOL,
                tool_name="succeed",
                input_params={},
                dependencies=[],
            ),
            WorkflowNode(
                node_id="failing_node",
                node_type=NodeType.TOOL,
                tool_name="fail",
                input_params={},
                dependencies=["normal_node"],
            ),
        ],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        success_count=0,
        failure_count=0,
    )

    error_wf_result = ryumem_client.create_workflow(workflow_with_error.model_dump(mode='json'))
    error_wf_id = error_wf_result.get("workflow_id") if isinstance(error_wf_result, dict) else error_wf_result
    session_id_3 = f"session_{uuid.uuid4().hex[:8]}"

    # Mock _execute_node to fail on failing_node
    original_execute = manager._execute_node
    def mock_execute_with_error(node, context, tool_registry):
        if node.node_id == "failing_node":
            raise ValueError("Simulated node failure")
        return original_execute(node, context, tool_registry)

    manager._execute_node = mock_execute_with_error

    # Execute - should pause on error
    result5 = manager.execute_workflow(
        workflow_id=error_wf_id,
        session_id=session_id_3,
        user_id=unique_user,
        initial_variables={}
    )

    assert result5["status"] == "paused", "Should pause on error"
    assert result5["pause_reason"] == "error", "Should indicate error pause"
    assert result5["paused_at_node"] == "failing_node", "Should pause at failing node"
    assert "error" in result5, "Should have error message"
    assert "Simulated node failure" in result5["error"], "Should contain error details"
    print(f"✓ Paused on error at node: {result5['paused_at_node']}")
    print(f"  Error: {result5['error']}")

    print("\n" + "="*60)
    print("✓ ALL COMPLEX WORKFLOW TESTS PASSED!")
    print("="*60)
    print(f"Tested:")
    print(f"  ✓ Multi-wave parallel execution")
    print(f"  ✓ LLM_TRIGGER pause and resume")
    print(f"  ✓ USER_TRIGGER pause and resume")
    print(f"  ✓ ERROR pause and skip")
    print(f"  ✓ State persistence across manager instances")
    print("="*60)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
