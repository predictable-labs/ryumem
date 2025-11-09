"""
Simple Tool Tracking Demo - Google ADK + Ryumem

This example shows how to enable automatic tool tracking with just ONE line of code.
Tool tracking happens completely behind the scenes - no need to access wrapped functions!

Prerequisites:
    pip install google-adk ryumem

Setup:
    export GOOGLE_API_KEY=your_api_key
    export OPENAI_API_KEY=your_openai_key  # For embeddings and classification
"""

import os
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Check if Google ADK is installed
try:
    from google.adk.agents import Agent
    from google.adk.tools import FunctionTool
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
except ImportError:
    print("ERROR: Google ADK not installed. Run: pip install google-adk")
    exit(1)

from ryumem.integrations import enable_memory

# App configuration
APP_NAME = "weather_sentiment_agent"
USER_ID = "user1234"
SESSION_ID = "1234"
MODEL_ID = "gemini-2.0-flash-exp"


# Tool 1: Get weather report
def get_weather_report(city: str) -> dict:
    """Retrieves the current weather report for a specified city.

    Returns:
        dict: A dictionary containing the weather information with a 'status' key
              ('success' or 'error') and a 'report' key with the weather details.
    """
    if city.lower() == "london":
        return {
            "status": "success",
            "report": "The current weather in London is cloudy with a temperature of 18 degrees Celsius and a chance of rain."
        }
    elif city.lower() == "paris":
        return {
            "status": "success",
            "report": "The weather in Paris is sunny with a temperature of 25 degrees Celsius."
        }
    else:
        return {
            "status": "error",
            "error_message": f"Weather information for '{city}' is not available."
        }


# Tool 2: Analyze sentiment
def analyze_sentiment(text: str) -> dict:
    """Analyzes the sentiment of the given text.

    Returns:
        dict: A dictionary with 'sentiment' ('positive', 'negative', or 'neutral')
              and a 'confidence' score.
    """
    if "good" in text.lower() or "sunny" in text.lower():
        return {"sentiment": "positive", "confidence": 0.8}
    elif "rain" in text.lower() or "bad" in text.lower():
        return {"sentiment": "negative", "confidence": 0.7}
    else:
        return {"sentiment": "neutral", "confidence": 0.6}


async def main():
    """Main function to run the agent with automatic tool tracking."""

    print("=" * 60)
    print("Simple Tool Tracking Demo - Google ADK + Ryumem")
    print("=" * 60)
    print()

    # Create tools
    weather_tool = FunctionTool(func=get_weather_report)
    sentiment_tool = FunctionTool(func=analyze_sentiment)

    # Create agent
    weather_sentiment_agent = Agent(
        model=MODEL_ID,
        name='weather_sentiment_agent',
        instruction="""You are a helpful assistant that provides weather information and analyzes sentiment.
If the user asks about weather, use get_weather_report tool.
If the user gives feedback about weather, use analyze_sentiment tool to understand their sentiment.""",
        tools=[weather_tool, sentiment_tool]
    )

    print("✓ Agent created with tools")
    print()

    # ⭐ Enable memory + tool tracking in ONE line!
    # This automatically wraps ALL tools for tracking - nothing else needed!
    print("⭐ Enabling memory + automatic tool tracking...")
    memory = enable_memory(
        weather_sentiment_agent,
        ryumem_customer_id="demo_company",
        user_id=USER_ID,
        db_path="./server/data/google_adk_demo.db",
        track_tools=True,  # 🎯 This is all you need for tool tracking!
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        async_classification=True,  # Use synchronous for now to avoid event loop issues
    )
    print("✓ Tool tracking enabled automatically!")
    print()

    # Session and Runner Setup (standard Google ADK usage)
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID
    )

    runner = Runner(
        agent=weather_sentiment_agent,
        app_name=APP_NAME,
        session_service=session_service
    )

    # Agent Interaction - use the agent normally, tracking happens automatically!
    print("-" * 60)
    print("Agent Conversation:")
    print("-" * 60)
    print()

    queries = [
        "What's the weather in London?",
        "That sounds nice!",
        "How about Paris?",
    ]

    for query in queries:
        print(f"👤 User: {query}")
        content = types.Content(role='user', parts=[types.Part(text=query)])

        # Run the agent - tools are automatically tracked!
        events = runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content)

        for event in events:
            if event.is_final_response():
                final_response = event.content.parts[0].text
                print(f"🤖 Agent: {final_response}")
                print()

    # Wait for async classification to complete
    print("Waiting for async tool classification...")
    await asyncio.sleep(10)  # Wait for background async tasks to complete
    print("Done waiting")
    print()

    # # Show tool analytics
    # print("=" * 60)
    # print("📊 Tool Analytics:")
    # print("=" * 60)
    # print()

    # # Get tools used for information retrieval
    # print("Tools used for information retrieval:")
    # tools = memory.ryumem.get_tools_for_task(
    #     task_type="information_retrieval",
    #     group_id="demo_company",
    #     limit=5
    # )
    # if tools:
    #     for tool in tools:
    #         print(f"  • {tool['tool_name']}: {tool['usage_count']} uses, "
    #               f"{tool['success_rate']*100:.1f}% success")
    # else:
    #     print("  (No results yet - BM25 index updating)")
    # print()

    # # Get user's tool preferences
    # print("User tool preferences:")
    # prefs = memory.ryumem.get_user_tool_preferences(
    #     user_id=USER_ID,
    #     group_id="demo_company",
    #     limit=5
    # )
    # if prefs:
    #     for pref in prefs:
    #         print(f"  • {pref['tool_name']}: {pref['usage_count']} uses")
    # else:
    #     print("  (No results yet - BM25 index updating)")
    # print()

    # print("=" * 60)
    # print()
    # print("✅ Demo completed!")
    # print()
    # print("💡 Key takeaway: Tool tracking happened automatically!")
    # print("   You used the agent normally via runner.run() - no wrapped functions needed!")
    # print()
    # print("Next steps:")
    # print("  - View tracked data in dashboard: http://localhost:3000")
    # print("  - Check entities for TOOL and TASK_TYPE in the graph")
    # print("  - See TOOL_TRACKING_CONSIDERATIONS.md for details")
    # print()


if __name__ == "__main__":
    # Check for required environment variables
    if not os.getenv("GOOGLE_API_KEY"):
        print("ERROR: GOOGLE_API_KEY environment variable not set")
        print("Run: export GOOGLE_API_KEY=your_api_key")
        exit(1)

    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY environment variable not set")
        print("Run: export OPENAI_API_KEY=your_openai_key")
        exit(1)

    asyncio.run(main())
