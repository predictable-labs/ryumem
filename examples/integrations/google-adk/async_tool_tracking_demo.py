"""
Async Tool Tracking Demo - Google ADK + Ryumem (using run_async)

This example demonstrates using runner.run_async() instead of runner.run()
to test if the current wrap_runner_with_tracking() implementation supports async execution.

NOTE: The current implementation may NOT work with run_async because:
- wrap_runner_with_tracking() wraps the synchronous run() method
- It returns a regular generator, not an async generator
- This script will help test and identify what needs to be fixed

Features to Test:
    • Does tool tracking work with run_async?
    • Does query tracking work with run_async?
    • Does query augmentation work with run_async?
    • Are episodes properly linked with run_async?

Prerequisites:
    pip install google-adk ryumem

Setup:
    export GOOGLE_API_KEY=your_api_key
    export OPENAI_API_KEY=your_openai_key  # For embeddings and classification
"""

import os
import asyncio
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)

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

from ryumem.integrations import add_memory_to_agent, wrap_runner_with_tracking

# App configuration
APP_NAME = "weather_sentiment_agent_async"
USER_ID = "user_async_test"
SESSION_ID = "session_async_test"
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
    """Main function to test run_async with automatic tool tracking."""

    print("=" * 60)
    print("Async Tool Tracking Demo - Google ADK + Ryumem")
    print("Testing runner.run_async() compatibility")
    print("=" * 60)
    print()

    # Create tools
    weather_tool = FunctionTool(func=get_weather_report)
    sentiment_tool = FunctionTool(func=analyze_sentiment)

    # Create agent
    weather_sentiment_agent = Agent(
        model=MODEL_ID,
        name='weather_sentiment_agent_async',
        instruction="""You are a helpful assistant that provides weather information and analyzes sentiment.
If the user asks about weather, use get_weather_report tool.
If the user gives feedback about weather, use analyze_sentiment tool to understand their sentiment.""",
        tools=[weather_tool, sentiment_tool]
    )

    print("✓ Agent created with tools")
    print()

    # Add memory + tool tracking + query augmentation
    from ryumem import Ryumem
    # Auto-loads RYUMEM_API_URL and RYUMEM_API_KEY from environment
    ryumem = Ryumem(
        track_tools=True,          # 🎯 Track all tool usage
        track_queries=True,        # 🎯 Track user queries as episodes
        augment_queries=True,      # ✨ Augment queries with historical context
        similarity_threshold=0.3,  # Match queries with 30%+ similarity
        top_k_similar=5,           # Use top 5 similar queries
        extract_entities=True,
    )

    weather_sentiment_agent = add_memory_to_agent(weather_sentiment_agent, ryumem)

    print("✓ Memory and tracking configured")
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

    print("✓ Runner created")
    print()

    # Wrap runner to automatically track user queries as episodes and augment with history
    # Config is read from ryumem.config
    runner = wrap_runner_with_tracking(runner, weather_sentiment_agent)

    print("✓ Runner wrapped with tracking")
    print()

    queries = [
        "What's the weather in London?",
        "That sounds nice!",
    ]

    for query_idx, query in enumerate(queries, 1):
        print(f"\n{'='*60}")
        print(f"Query {query_idx}/{len(queries)}")
        print(f"👤 User: {query}")
        print(f"{'='*60}")
        content = types.Content(role='user', parts=[types.Part(text=query)])

        try:
            # 🔥 KEY CHANGE: Using run_async instead of run
            print("🔄 Calling runner.run_async()...")
            event_stream = runner.run_async(
                user_id=USER_ID,
                session_id=SESSION_ID,
                new_message=content
            )

            # Collect the final response using async iteration
            final_response = None
            async for event in event_stream:
                if event.is_final_response():
                    final_response = event.content.parts[0].text

            if final_response:
                print(f"\n🤖 Agent: {final_response}")

            print(f"\n✅ Query {query_idx} completed successfully")

        except AttributeError as e:
            print(f"\n❌ ERROR: {e}")
            print("This likely means wrap_runner_with_tracking() doesn't support run_async")
            print("The wrapper only wraps runner.run(), not runner.run_async()")
            return False
        except Exception as e:
            print(f"\n❌ Unexpected error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False

    print(f"\n{'='*60}")
    print("✅ All queries completed successfully!")
    print("The integration WORKS with run_async!")
    print(f"{'='*60}")
    return True


if __name__ == "__main__":
    # Check for required environment variables
    if not os.getenv("GOOGLE_API_KEY"):
        print("ERROR: GOOGLE_API_KEY environment variable not set")
        print("Run: export GOOGLE_API_KEY=your_api_key")
        exit(1)

    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY environment variable not set")
        print("This may affect embeddings quality")

    success = asyncio.run(main())

    if success:
        exit(0)
    else:
        print("\n" + "="*60)
        print("❌ TEST FAILED")
        print("The current implementation does NOT support run_async")
        print("="*60)
        exit(1)
