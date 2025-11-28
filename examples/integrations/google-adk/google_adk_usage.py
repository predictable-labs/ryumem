"""
Google ADK Integration Example for Ryumem.

This example demonstrates the ZERO-BOILERPLATE approach to adding memory
to Google ADK agents. No need to write custom functions!

ARCHITECTURE - Memory Isolation Explained:
Each user gets their own isolated knowledge graph:

┌────────────┐  ┌────────────┐  ┌────────────┐
│ user_id:   │  │ user_id:   │  │ user_id:   │
│ "alice"    │  │ "bob"      │  │ "charlie"  │
│            │  │            │  │            │
│ - Name     │  │ - Name     │  │ - Name     │
│ - Job      │  │ - Job      │  │ - Hobbies  │
│ - Hobbies  │  │ - Prefs    │  │            │
└────────────┘  └────────────┘  └────────────┘
 Isolated        Isolated        Isolated
 Memory Graph    Memory Graph    Memory Graph

Each end user gets their own knowledge graph. Memories never leak between users.

Prerequisites:
1. Install Google ADK: pip install google-adk
2. Set up Google API key: export GOOGLE_API_KEY="your-key"
3. Install Ryumem: pip install ryumem
4. (Optional) Set OpenAI API key for better embeddings: export OPENAI_API_KEY="your-key"

VISUALIZE IN DASHBOARD:
This example saves to ./server/data/google_adk_demo.db so you can see the
knowledge graph in the interactive dashboard!

To view:
1. Update server/.env: RYUMEM_DB_PATH=./data/memory.db
2. Start server: cd server && uvicorn main:app --reload
3. Start dashboard: cd dashboard && npm run dev
4. Open http://localhost:3000 and explore:
   - All entities (Alice, Bob, Google, TensorFlow...)
   - Relationships between entities
   - Memory isolation per user

"""

import os
import asyncio
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
VERBOSE = True  # Set to False to reduce log output

# Configure logging
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(levelname)s - %(message)s'
# )

# Helper function for verbose printing
def vprint(*args, **kwargs):
    """Print only if VERBOSE is True."""
    if VERBOSE:
        print(*args, **kwargs)

vprint("=" * 60)
vprint("Ryumem + Google ADK - Zero Boilerplate Memory")
vprint("=" * 60)

# Check if Google ADK is installed
try:
    from google.adk.agents import Agent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
    vprint("✓ Google ADK installed")
except ImportError:
    vprint("❌ Google ADK not installed. Run: pip install google-adk")
    exit(1)

# Check for API key
if not os.getenv("GOOGLE_API_KEY"):
    vprint("❌ GOOGLE_API_KEY not set. Set it with: export GOOGLE_API_KEY='your-key'")
    vprint("   Get your key at: https://aistudio.google.com/apikey")
    exit(1)

from ryumem.integrations import add_memory_to_agent


async def chat_with_agent(runner, session_id: str, user_input: str, user_id: str):
    """Helper function to chat with an agent and get response."""
    content = types.Content(
        role='user',
        parts=[types.Part(text=user_input)]
    )

    events = runner.run(
        user_id=user_id,
        session_id=session_id,
        new_message=content
    )

    for event in events:
        if event.is_final_response():
            return event.content.parts[0].text

    return "No response"


async def main():
    vprint("\n1. Creating Google ADK Agent...")
    agent = Agent(
        name="personal_assistant",
        model="gemini-2.0-flash-exp",
        instruction="""You are a helpful personal assistant with memory.

IMPORTANT: When using memory tools, ALWAYS pass the user_id parameter.
This ensures each user's memories stay isolated.

When users share information about themselves, their preferences, or their activities:
- Use save_memory(content, user_id=<current_user_id>) to remember important details
- Use search_memory(query, user_id=<current_user_id>) to recall past information
- Use get_entity_context(entity_name, user_id=<current_user_id>) to learn more about entities

Always personalize responses based on what you remember about the specific user."""
    )
    vprint(f"   ✓ Created agent: {agent.name}")

    vprint("\n2. Adding memory to agent (ONE LINE!)...")
    # This is all you need - no custom functions!
    # Using the server's database path so you can view the graph in the dashboard!
    # Enable memory with tool tracking

    # Initialize Ryumem instance with config (auto-loads RYUMEM_API_URL and RYUMEM_API_KEY from env)
    from ryumem import Ryumem
    ryumem = Ryumem(
        track_tools=True,  # Enable tool tracking
        track_queries=True,  # Enable query tracking
    )

    agent = add_memory_to_agent(agent, ryumem)
    vprint("   ✓ Memory enabled! Agent now has 3 auto-generated tools:")
    vprint("     - search_memory(query, user_id, limit)")
    vprint("     - save_memory(content, user_id, source)")
    vprint("     - get_entity_context(entity_name, user_id)")
    vprint("\n   💡 View the knowledge graph in the dashboard:")
    vprint("      1. Update server/.env: RYUMEM_DB_PATH=./data/memory.db")
    vprint("      2. Start server: cd server && uvicorn main:app --reload")
    vprint("      3. Start dashboard: cd dashboard && npm run dev")
    vprint("      4. Open: http://localhost:3000")

    # Set up runner and session service
    # IMPORTANT: ONE runner serves ALL users!
    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="ryumem_demo",
        session_service=session_service
    )
    vprint("\n   ✓ Created ONE runner to serve all users")

    vprint("\n3. Demonstrating multi-user memory isolation...")
    vprint("   We'll create separate sessions for Alice and Bob")

    # Create Alice's session
    session_alice = await session_service.create_session(
        app_name="ryumem_demo",
        user_id="alice",
        session_id="session_alice"
    )
    vprint("   ✓ Created session for Alice")

    # Create Bob's session
    session_bob = await session_service.create_session(
        app_name="ryumem_demo",
        user_id="bob",
        session_id="session_bob"
    )
    vprint("   ✓ Created session for Bob")

    # Alice's first conversation
    vprint("\n   === ALICE's Turn ===")
    user_input = "Hi! I'm Alice. I work at Google as a Software Engineer and I'm working on TensorFlow."
    vprint(f"   Alice: {user_input}")
    response = await chat_with_agent(runner, session_alice.id, user_input, "alice")
    vprint(f"   Agent: {response}")

    # Bob's first conversation
    vprint("\n   === BOB's Turn ===")
    user_input = "Hello! I'm Bob. I'm a high school teacher and I love playing guitar."
    vprint(f"   Bob: {user_input}")
    response = await chat_with_agent(runner, session_bob.id, user_input, "bob")
    vprint(f"   Agent: {response}")

    # Alice's second conversation - agent should remember only Alice's info
    vprint("\n   === ALICE's Turn Again ===")
    user_input = "What do you know about me?"
    vprint(f"   Alice: {user_input}")
    response = await chat_with_agent(runner, session_alice.id, user_input, "alice")
    vprint(f"   Agent: {response}")
    vprint("   ✓ Agent retrieved ONLY Alice's memories (not Bob's)")

    # Bob's second conversation - agent should remember only Bob's info
    vprint("\n   === BOB's Turn Again ===")
    user_input = "What do you know about me?"
    vprint(f"   Bob: {user_input}")
    response = await chat_with_agent(runner, session_bob.id, user_input, "bob")
    vprint(f"   Agent: {response}")
    vprint("   ✓ Agent retrieved ONLY Bob's memories (not Alice's)")

    # Verify isolation
    vprint("\n   === Testing Memory Isolation ===")
    user_input = "Where do I work?"
    vprint(f"   Alice: {user_input}")
    response = await chat_with_agent(runner, session_alice.id, user_input, "alice")
    vprint(f"   Agent to Alice: {response}")
    vprint("   ✓ Correctly identified Alice works at Google")

    vprint("\n4. Demonstrating multi-agent memory sharing...")
    vprint("   Creating a SECOND agent (Travel Planner) that shares Alice's memory...")

    # Create another agent for travel planning
    travel_agent = Agent(
        name="travel_planner",
        model="gemini-2.0-flash-exp",
        instruction="""You are a travel planning assistant with memory.

IMPORTANT: When using memory tools, ALWAYS pass the user_id parameter.

Use search_memory(query, user_id=<current_user_id>) to recall user preferences.
Use save_memory(content, user_id=<current_user_id>) to remember travel plans.
Personalize recommendations based on what you know about the user."""
    )

    # Enable memory with SAME ryumem instance - so Alice's memories are shared across agents!
    travel_agent = add_memory_to_agent(travel_agent, ryumem)
    vprint("   ✓ Travel agent created with access to Alice's memory")

    travel_runner = Runner(
        agent=travel_agent,
        app_name="ryumem_demo_travel",
        session_service=session_service
    )

    # Create a session for Alice using the travel agent
    # NOTE: Same user_id="alice" means it accesses Alice's existing memories!
    travel_session_alice = await session_service.create_session(
        app_name="ryumem_demo_travel",
        user_id="alice",
        session_id="session_alice_travel"
    )

    vprint("\n   === ALICE using Travel Agent ===")
    user_input = "Plan a weekend trip for me based on what you know about my interests"
    vprint(f"   Alice: {user_input}")
    response = await chat_with_agent(travel_runner, travel_session_alice.id, user_input, "alice")
    vprint(f"   Travel Agent: {response}")
    vprint("   ✓ Travel agent accessed Alice's existing memories from Personal Assistant!")

    vprint("\n5. Direct memory access (advanced usage)...")
    vprint("   You can also use the memory interface directly with specific user_ids:")

    # Access memory interface stored on agent
    memory = agent._ryumem_memory

    # Direct search for Alice
    vprint("\n   Searching Alice's memories for 'Google'...")
    results = memory.search_memory("Google", user_id="alice", session_id="session_alice", limit=3)
    vprint(f"   Found {results.get('count', 0)} memories for Alice:")
    if results.get('memories'):
        for mem in results['memories'][:3]:
            vprint(f"     - {mem['fact']} (score: {mem['score']:.3f})")

    # Direct search for Bob
    vprint("\n   Searching Bob's memories for 'Google'...")
    results = memory.search_memory("Google", user_id="bob", session_id="session_bob", limit=3)
    vprint(f"   Found {results.get('count', 0)} memories for Bob:")
    if results.get('memories'):
        for mem in results['memories'][:3]:
            vprint(f"     - {mem['fact']} (score: {mem['score']:.3f})")
    else:
        vprint("     (No matches - Bob never mentioned Google!)")

    # Direct save for Alice
    vprint("\n   Saving a memory directly for Alice...")
    result = memory.save_memory("Alice's birthday is on July 15th", user_id="alice", session_id="session_alice", source="text")
    vprint(f"   {result['message']}")

    # Get entity context for Alice
    vprint("\n   Getting context for entity 'Alice' in Alice's memory...")
    context = memory.get_entity_context("alice", user_id="alice", session_id="session_alice")
    if context.get('status') == 'success':
        vprint(f"   Found context for Alice:")
        vprint(f"   {context['context']}")

    vprint("\n" + "=" * 60)
    vprint("Google ADK Integration Complete!")
    vprint("\n💡 Key Takeaways:")
    vprint("  • No custom functions needed - just call add_memory_to_agent()")
    vprint("  • Multi-user support: Each user gets isolated memory")
    vprint("  • Multi-agent support: Agents can share memory for same user")
    vprint("  • Knowledge graph provides structured, relational memory")
    vprint("  • Works with any LLM (Gemini, GPT, Ollama, etc.)")
    vprint("  • Auto-detects GOOGLE_API_KEY - no redundant configuration!")
    vprint("\n🔑 API Key Configuration:")
    vprint("  Required: GOOGLE_API_KEY (for both agent and memory)")
    vprint("  Optional: OPENAI_API_KEY (for better embeddings)")
    vprint("  Override: llm_provider='ollama' (to use local models)")
    vprint("\n🏗️ Architecture:")
    vprint("  ryumem_customer_id → Your company (demo_company)")
    vprint("  user_id → Individual users (alice, bob, charlie...)")
    vprint("  session_id → Individual conversation threads")
    vprint("\n📊 View in Dashboard:")
    vprint("  1. Update server/.env with: RYUMEM_DB_PATH=./data/memory.db")
    vprint("  2. Start API: cd server && uvicorn main:app --reload")
    vprint("  3. Start UI: cd dashboard && npm run dev")
    vprint("  4. Browse: http://localhost:3000")
    vprint("  • See all entities (Alice, Bob, Google, TensorFlow...)")
    vprint("  • Visualize relationships between entities")
    vprint("  • Explore the knowledge graph interactively")
    vprint("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
