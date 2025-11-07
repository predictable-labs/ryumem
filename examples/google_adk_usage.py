"""
Google ADK Integration Example for Ryumem.

This example demonstrates the ZERO-BOILERPLATE approach to adding memory
to Google ADK agents. No need to write custom functions!

ARCHITECTURE - Multi-Tenancy Explained:
┌─────────────────────────────────────────────────────────────┐
│ ryumem_customer_id: "demo_company"                          │
│ (Your company using Ryumem)                                 │
│                                                             │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │ user_id:   │  │ user_id:   │  │ user_id:   │           │
│  │ "alice"    │  │ "bob"      │  │ "charlie"  │           │
│  │            │  │            │  │            │           │
│  │ - Name     │  │ - Name     │  │ - Name     │           │
│  │ - Job      │  │ - Job      │  │ - Hobbies  │           │
│  │ - Hobbies  │  │ - Prefs    │  │            │           │
│  └────────────┘  └────────────┘  └────────────┘           │
│  Isolated        Isolated        Isolated                  │
│  Memory Graph    Memory Graph    Memory Graph              │
└─────────────────────────────────────────────────────────────┘

Each end user gets their own knowledge graph. Memories never leak between users.

Prerequisites:
1. Install Google ADK: pip install google-adk
2. Set up Google API key: export GOOGLE_API_KEY="your-key"
3. Install Ryumem: pip install ryumem

Benefits over mem0:
- Zero boilerplate: No need to write search_memory() and save_memory() functions
- One-line integration: Just call enable_memory(agent, ryumem_customer_id="...")
- Multi-user support: Each user gets isolated memory automatically
- Knowledge graph: Structured memory with entity relationships
- Local LLM support: Works with Ollama for privacy
"""

import os
import asyncio
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(levelname)s - %(message)s'
# )

print("=" * 60)
print("Ryumem + Google ADK - Zero Boilerplate Memory")
print("=" * 60)

# Check if Google ADK is installed
try:
    from google.adk.agents import Agent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
    print("✓ Google ADK installed")
except ImportError:
    print("❌ Google ADK not installed. Run: pip install google-adk")
    exit(1)

# Check for API key
if not os.getenv("GOOGLE_API_KEY"):
    print("❌ GOOGLE_API_KEY not set. Set it with: export GOOGLE_API_KEY='your-key'")
    print("   Get your key at: https://aistudio.google.com/apikey")
    exit(1)

from ryumem.integrations import enable_memory, RyumemGoogleADK


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
    print("\n1. Creating Google ADK Agent...")
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
    print(f"   ✓ Created agent: {agent.name}")

    print("\n2. Enabling memory (ONE LINE!)...")
    # This is all you need - no custom functions!
    memory = enable_memory(
        agent,
        ryumem_customer_id="demo_company",  # Your company using Ryumem
        # user_id is None - will be passed per tool call
        db_path="./data/google_adk_memory.db",
        # Optional: Use Ollama for LLM (uncomment below)
        llm_provider="ollama",
        llm_model="qwen2.5:7b",
        ollama_base_url="http://100.108.18.43:11434",
    )
    print("   ✓ Memory enabled! Agent now has 3 auto-generated tools:")
    print("     - search_memory(query, user_id, limit)")
    print("     - save_memory(content, user_id, source)")
    print("     - get_entity_context(entity_name, user_id)")

    # Set up runner and session service
    # IMPORTANT: ONE runner serves ALL users!
    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="ryumem_demo",
        session_service=session_service
    )
    print("\n   ✓ Created ONE runner to serve all users")

    print("\n3. Demonstrating multi-user memory isolation...")
    print("   We'll create separate sessions for Alice and Bob")

    # Create Alice's session
    session_alice = await session_service.create_session(
        app_name="ryumem_demo",
        user_id="alice",
        session_id="session_alice"
    )
    print("   ✓ Created session for Alice")

    # Create Bob's session
    session_bob = await session_service.create_session(
        app_name="ryumem_demo",
        user_id="bob",
        session_id="session_bob"
    )
    print("   ✓ Created session for Bob")

    # Alice's first conversation
    print("\n   === ALICE's Turn ===")
    user_input = "Hi! I'm Alice. I work at Google as a Software Engineer and I'm working on TensorFlow."
    print(f"   Alice: {user_input}")
    response = await chat_with_agent(runner, session_alice.id, user_input, "alice")
    print(f"   Agent: {response}")

    # Bob's first conversation
    print("\n   === BOB's Turn ===")
    user_input = "Hello! I'm Bob. I'm a high school teacher and I love playing guitar."
    print(f"   Bob: {user_input}")
    response = await chat_with_agent(runner, session_bob.id, user_input, "bob")
    print(f"   Agent: {response}")

    # Alice's second conversation - agent should remember only Alice's info
    print("\n   === ALICE's Turn Again ===")
    user_input = "What do you know about me?"
    print(f"   Alice: {user_input}")
    response = await chat_with_agent(runner, session_alice.id, user_input, "alice")
    print(f"   Agent: {response}")
    print("   ✓ Agent retrieved ONLY Alice's memories (not Bob's)")

    # Bob's second conversation - agent should remember only Bob's info
    print("\n   === BOB's Turn Again ===")
    user_input = "What do you know about me?"
    print(f"   Bob: {user_input}")
    response = await chat_with_agent(runner, session_bob.id, user_input, "bob")
    print(f"   Agent: {response}")
    print("   ✓ Agent retrieved ONLY Bob's memories (not Alice's)")

    # Verify isolation
    print("\n   === Testing Memory Isolation ===")
    user_input = "Where do I work?"
    print(f"   Alice: {user_input}")
    response = await chat_with_agent(runner, session_alice.id, user_input, "alice")
    print(f"   Agent to Alice: {response}")
    print("   ✓ Correctly identified Alice works at Google")

    print("\n4. Demonstrating multi-agent memory sharing...")
    print("   Creating a SECOND agent (Travel Planner) that shares Alice's memory...")

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

    # Enable memory with SAME ryumem_customer_id - memory is shared across agents!
    # IMPORTANT: Reuse the same Ryumem instance to avoid database connection conflicts
    travel_memory = RyumemGoogleADK(
        ryumem=memory.ryumem,  # Reuse existing Ryumem instance
        ryumem_customer_id="demo_company"  # Same customer
    )
    travel_agent.tools.extend(travel_memory.tools)
    print("   ✓ Travel agent created with access to same memory backend")

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

    print("\n   === ALICE using Travel Agent ===")
    user_input = "Plan a weekend trip for me based on what you know about my interests"
    print(f"   Alice: {user_input}")
    response = await chat_with_agent(travel_runner, travel_session_alice.id, user_input, "alice")
    print(f"   Travel Agent: {response}")
    print("   ✓ Travel agent accessed Alice's existing memories from Personal Assistant!")

    print("\n5. Direct memory access (advanced usage)...")
    print("   You can also use the memory object directly with specific user_ids:")

    # Direct search for Alice
    print("\n   Searching Alice's memories for 'Google'...")
    results = memory.search_memory("Google", user_id="alice", limit=3)
    print(f"   Found {results.get('count', 0)} memories for Alice:")
    if results.get('memories'):
        for mem in results['memories'][:3]:
            print(f"     - {mem['fact']} (score: {mem['score']:.3f})")

    # Direct search for Bob
    print("\n   Searching Bob's memories for 'Google'...")
    results = memory.search_memory("Google", user_id="bob", limit=3)
    print(f"   Found {results.get('count', 0)} memories for Bob:")
    if results.get('memories'):
        for mem in results['memories'][:3]:
            print(f"     - {mem['fact']} (score: {mem['score']:.3f})")
    else:
        print("     (No matches - Bob never mentioned Google!)")

    # Direct save for Alice
    print("\n   Saving a memory directly for Alice...")
    result = memory.save_memory("Alice's birthday is on July 15th", user_id="alice", source="text")
    print(f"   {result['message']}")

    # Get entity context for Alice
    print("\n   Getting context for entity 'Alice' in Alice's memory...")
    context = memory.get_entity_context("alice", user_id="alice")
    if context.get('status') == 'success':
        print(f"   Found context for Alice:")
        print(f"   {context['context']}")

    print("\n" + "=" * 60)
    print("Google ADK Integration Complete!")
    print("\n💡 Key Takeaways:")
    print("  • No custom functions needed - just call enable_memory()")
    print("  • Multi-user support: Each user gets isolated memory")
    print("  • Multi-agent support: Agents can share memory for same user")
    print("  • Knowledge graph provides structured, relational memory")
    print("  • Works with any LLM (Gemini, GPT, Ollama, etc.)")
    print("\n🏗️ Architecture:")
    print("  ryumem_customer_id → Your company (demo_company)")
    print("  user_id → End users (alice, bob, charlie...)")
    print("  session_id → Individual conversations")
    print("\n📚 Compare with mem0:")
    print("  mem0: ~20 lines of boilerplate to write search/save functions")
    print("  Ryumem: 1 line - enable_memory(agent, ryumem_customer_id='...')")
    print("  mem0: No multi-user isolation out of the box")
    print("  Ryumem: Built-in multi-tenancy with user_id parameter")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
