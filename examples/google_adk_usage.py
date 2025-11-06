"""
Google ADK Integration Example for Ryumem.

This example demonstrates the ZERO-BOILERPLATE approach to adding memory
to Google ADK agents. No need to write custom functions!

Prerequisites:
1. Install Google ADK: pip install google-adk
2. Set up Google API key: export GOOGLE_API_KEY="your-key"
3. Install Ryumem: pip install ryumem

Benefits over mem0:
- Zero boilerplate: No need to write search_memory() and save_memory() functions
- One-line integration: Just call enable_memory(agent, user_id="...")
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
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)

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

When users share information about themselves, their preferences, or their activities:
- Use save_memory() to remember important details
- Use search_memory() to recall past information
- Use get_entity_context() to learn more about specific people, places, or things

Always try to personalize responses based on what you remember about the user."""
    )
    print(f"   ✓ Created agent: {agent.name}")

    print("\n2. Enabling memory (ONE LINE!)...")
    # This is all you need - no custom functions!
    memory = enable_memory(
        agent,
        user_id="demo_user",
        db_path="./data/google_adk_memory.db",
        # Optional: Use Ollama for LLM (uncomment below)
        llm_provider="ollama",
        llm_model="qwen2.5:7b",
        ollama_base_url="http://100.108.18.43:11434",
    )
    print("   ✓ Memory enabled! Agent now has 3 auto-generated tools:")
    print("     - search_memory(query, limit)")
    print("     - save_memory(content, source)")
    print("     - get_entity_context(entity_name)")

    # Set up runner and session
    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="ryumem_demo",
        session_service=session_service
    )

    # Create a session for this conversation
    session = await session_service.create_session(
        app_name="ryumem_demo",
        user_id="demo_user",
        session_id="session_demo_user"
    )

    print("\n3. Testing memory with conversations...")

    # Conversation 1: User shares information
    print("\n   Conversation 1: Sharing information")
    user_input = "Hi! I'm Alice. I work at Google as a Software Engineer."
    print(f"   User: {user_input}")
    response = await chat_with_agent(runner, session.id, user_input, "demo_user")
    print(f"   Agent: {response}")

    # Conversation 2: More information
    print("\n   Conversation 2: More details")
    user_input = "I'm working on TensorFlow and I love hiking in my free time."
    print(f"   User: {user_input}")
    response = await chat_with_agent(runner, session.id, user_input, "demo_user")
    print(f"   Agent: {response}")

    # Conversation 3: Testing recall
    print("\n   Conversation 3: Testing memory recall")
    user_input = "What do you know about me?"
    print(f"   User: {user_input}")
    response = await chat_with_agent(runner, session.id, user_input, "demo_user")
    print(f"   Agent: {response}")

    # Conversation 4: Specific query
    print("\n   Conversation 4: Specific information")
    user_input = "Where do I work?"
    print(f"   User: {user_input}")
    response = await chat_with_agent(runner, session.id, user_input, "demo_user")
    print(f"   Agent: {response}")

    print("\n4. Demonstrating multi-agent memory sharing...")
    print("   Creating a second agent with SHARED memory...")

    # Create another agent with the SAME memory
    travel_agent = Agent(
        name="travel_planner",
        model="gemini-2.0-flash-exp",
        instruction="""You are a travel planning assistant with memory.

Use search_memory() to recall user preferences and past trips.
Use save_memory() to remember travel preferences and planned trips.
Personalize recommendations based on what you know about the user."""
    )

    # Enable memory with SAME user_id - they share memories!
    # IMPORTANT: Reuse the same memory instance to avoid database connection conflicts
    travel_memory = RyumemGoogleADK(
        ryumem=memory.ryumem,  # Reuse existing Ryumem instance
        user_id="demo_user"
    )
    travel_agent.tools.extend(travel_memory.tools)
    print("   ✓ Travel agent created with shared memory")

    travel_runner = Runner(
        agent=travel_agent,
        app_name="ryumem_demo_travel",
        session_service=session_service
    )

    # Create a separate session for travel agent
    travel_session = await session_service.create_session(
        app_name="ryumem_demo_travel",
        user_id="demo_user",
        session_id="session_demo_user_travel"
    )

    print("\n   User (to travel agent): Plan a weekend trip for me")
    user_input = "Plan a weekend trip for me based on what you know about my interests"
    print(f"   User: {user_input}")
    response = await chat_with_agent(travel_runner, travel_session.id, user_input, "demo_user")
    print(f"   Travel Agent: {response}")

    print("\n5. Direct memory access (advanced usage)...")
    print("   You can also use the memory object directly:")

    # Direct search
    print("\n   Searching for 'Google'...")
    results = memory.search_memory("Google", limit=3)
    print(f"   Found {results.get('count', 0)} memories:")
    if results.get('memories'):
        for mem in results['memories'][:3]:
            print(f"     - {mem['fact']} (score: {mem['score']:.3f})")

    # Direct save
    print("\n   Saving a memory directly...")
    result = memory.save_memory("Alice's birthday is on July 15th", source="text")
    print(f"   {result['message']}")

    # Get entity context
    print("\n   Getting context for entity 'Alice'...")
    context = memory.get_entity_context("alice")
    if context.get('status') == 'success':
        print(f"   Found context for Alice:")
        print(f"   {context['context']}")

    print("\n" + "=" * 60)
    print("Google ADK Integration Complete!")
    print("\n💡 Key Takeaways:")
    print("  • No custom functions needed - just call enable_memory()")
    print("  • Multiple agents can share memory via user_id")
    print("  • Knowledge graph provides structured, relational memory")
    print("  • Works with any LLM (Gemini, GPT, Ollama, etc.)")
    print("\n📚 Compare with mem0:")
    print("  mem0: ~20 lines of boilerplate to write search/save functions")
    print("  Ryumem: 1 line - enable_memory(agent, user_id='...')")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
