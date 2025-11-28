"""
Simple Tool Tracking Demo - Google ADK + Ryumem

This example shows how to enable automatic tool tracking AND query augmentation with just ONE line of code.
Tool tracking and query augmentation happen completely behind the scenes - no manual work needed!

Features Demonstrated:
    • Automatic tool tracking - all tool executions are logged
    • Query tracking - user queries are saved as episodes
    • Query augmentation - similar past queries enrich new queries with historical tool usage
    • Hierarchical episode tracking - queries link to their tool executions

Prerequisites:
    pip install google-adk ryumem

Setup:
    export GOOGLE_API_KEY=your_api_key
    # Optional: export OPENAI_API_KEY=your_openai_key  # For better embeddings (uses Gemini by default)
"""

import os
import asyncio
from dotenv import load_dotenv
import logging
VERBOSE = True  # Set to False to reduce log output

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

    # ⭐ Add memory + tool tracking + query augmentation in ONE line!
    # This automatically wraps ALL tools for tracking - nothing else needed!
    # print("⭐ Adding memory + automatic tool tracking + query augmentation...")
    
    from ryumem import Ryumem
    # Auto-loads RYUMEM_API_URL and RYUMEM_API_KEY from environment
    ryumem = Ryumem(
        augment_queries=True,      # Enable augmentation
        similarity_threshold=0.3,  # Match queries with 30%+ similarity
        top_k_similar=5,           # Use top 5 similar queries
    )

    weather_sentiment_agent = add_memory_to_agent(weather_sentiment_agent, ryumem)

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

    # ⭐ Wrap runner to automatically track user queries as episodes and augment with history!
    # Config is read from ryumem.config
    runner = wrap_runner_with_tracking(runner, weather_sentiment_agent)

    queries = [
        # "What's the weather in Paris?",
        "What's the weather in London?",
        # "That sounds nice!",
        # "How about Paris?",
        # Add similar query to test augmentation
        # "What's the weather like in London today?",  # Similar to query 1 - should trigger augmentation!
    ]

    for query_idx, query in enumerate(queries):
        print(f"\n{'='*60}")
        print(f"👤 User: {query}")
        print(f"{'='*60}")
        content = types.Content(role='user', parts=[types.Part(text=query)])

        # Run the agent - tools are automatically tracked!
        events = runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content)

        # Collect the final response
        final_response = None
        for event in events:
            if event.is_final_response():
                final_response = event.content.parts[0].text

        if final_response:
            print(f"\n🤖 Agent: {final_response}")


if __name__ == "__main__":
    # Check for required environment variables
    if not os.getenv("GOOGLE_API_KEY"):
        print("ERROR: GOOGLE_API_KEY environment variable not set")
        print("Run: export GOOGLE_API_KEY=your_api_key")
        exit(1)

    # OPENAI_API_KEY is optional - if not set, will use Gemini for embeddings
    if not os.getenv("OPENAI_API_KEY"):
        print("INFO: OPENAI_API_KEY not set, will use Gemini for embeddings")
        print("      For better embedding quality, set: export OPENAI_API_KEY=your_openai_key")

    asyncio.run(main())
