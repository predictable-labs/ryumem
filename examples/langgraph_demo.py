import os
import time
import uuid
from typing import Dict, Any
from ryumem import Ryumem
from ryumem.integrations.langgraph import LangGraphRouter, register_tool, track_usage

# Initialize Ryumem
# Ensure RYUMEM_API_URL is set or server is running at localhost:8000
ryumem = Ryumem(
    api_key="ryu_yaYi2MhZ5TJTUetyMBSBvUS3XPJb1ZKHITfC_e_s81I"
)

# Initialize Router
# We use a deterministic sequence for this demo
router = LangGraphRouter(
    ryumem=ryumem,
    strategy="deterministic",
    sequence=["search", "analyze", "summarize"]
)

# Define Tools
@register_tool("search")
@track_usage
def search_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    print(f"  [Tool] Searching for: {state.get('query')}")
    # Simulate work
    time.sleep(0.1)
    state["search_results"] = ["Result A", "Result B"]
    state["current_node"] = "search"
    return state

@register_tool("analyze")
@track_usage
def analyze_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    print(f"  [Tool] Analyzing results...")
    time.sleep(0.1)
    state["analysis"] = "Analysis complete: Positive trend."
    state["current_node"] = "analyze"
    return state

@register_tool("summarize")
@track_usage
def summarize_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    print(f"  [Tool] Summarizing...")
    time.sleep(0.1)
    state["summary"] = "Summary: Everything looks good."
    state["current_node"] = "summarize"
    return state

# Register tools with router (optional if we had auto-discovery, but manual for now)
router.register_tool(search_tool)
router.register_tool(analyze_tool)
router.register_tool(summarize_tool)

def run_demo():
    session_id = f"session_{uuid.uuid4().hex[:8]}"
    user_id = "demo_user"
    
    print(f"Starting LangGraph Demo Session: {session_id}")
    
    state = {
        "session_id": session_id,
        "user_id": user_id,
        "query": "market trends",
        "current_node": None # Start
    }
    
    # Simulate LangGraph execution loop
    with router:
        while True:
            # 1. Router decides next node
            state = router(state)
            next_node = state.get("next_node")
            
            print(f"Router decided next node: {next_node}")
            
            if next_node == "__end__":
                break
                
            # 2. Execute node
            if next_node == "search":
                state = search_tool(state)
            elif next_node == "analyze":
                state = analyze_tool(state)
            elif next_node == "summarize":
                state = summarize_tool(state)
            else:
                print(f"Unknown node: {next_node}")
                break
            
    print("\nWorkflow Complete.")
    print("-" * 50)
    
    # Verify History in Ryumem
    print("Verifying History in Ryumem...")
    episode = ryumem.get_episode_by_session_id(session_id)
    
    if episode:
        print(f"Episode found: {episode.uuid}")
        print(f"Content: {episode.content}")
        print(f"Metadata Integration: {episode.metadata.get('integration')}")
        
        # Check tools used
        # Note: metadata is a dict here because Ryumem client parses it
        sessions = episode.metadata.get("sessions", {})
        if session_id in sessions:
            runs = sessions[session_id]
            print(f"Found {len(runs)} runs.")
            for run in runs:
                print(f"Run ID: {run.get('run_id')}")
                tools = run.get("tools_used", [])
                print(f"Tools used: {len(tools)}")
                for tool in tools:
                    print(f" - {tool.get('tool_name')} (Success: {tool.get('success')})")
    else:
        print("Episode NOT found!")

if __name__ == "__main__":
    run_demo()
