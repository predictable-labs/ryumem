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
    export OPENAI_API_KEY=your_openai_key  # For embeddings and classification
"""

import os
import asyncio
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# # Configure logging - only show important messages
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     datefmt='%H:%M:%S'
# )

# # Show only warnings and errors from verbose libraries
# logging.getLogger('google.adk').setLevel(logging.WARNING)
# logging.getLogger('google.genai').setLevel(logging.WARNING)
# logging.getLogger('httpx').setLevel(logging.WARNING)
# logging.getLogger('httpcore').setLevel(logging.WARNING)
# logging.getLogger('urllib3').setLevel(logging.WARNING)
# logging.getLogger('asyncio').setLevel(logging.WARNING)

# Enable INFO logs for ryumem to see augmentation messages
# logging.getLogger('ryumem.integrations.google_adk').setLevel(logging.INFO)

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

from ryumem.integrations import enable_memory, create_query_tracking_runner
import json

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


def log_request_payload(func_name, *args, **kwargs):
    """Helper to log function calls with their arguments."""
    logger = logging.getLogger(__name__)
    logger.info(f"\n{'='*60}")
    logger.info(f"🔍 {func_name} called")
    logger.info(f"Args: {args}")
    logger.info(f"Kwargs: {json.dumps({k: str(v)[:200] for k, v in kwargs.items()}, indent=2)}")
    logger.info(f"{'='*60}\n")


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

    # ⭐ Enable memory + tool tracking + query augmentation in ONE line!
    # This automatically wraps ALL tools for tracking - nothing else needed!
    # print("⭐ Enabling memory + automatic tool tracking + query augmentation...")
    memory = enable_memory(
        weather_sentiment_agent,
        ryumem_customer_id="demo_company",
        user_id=USER_ID,
        db_path="./server/data/google_adk_demo.db",
        track_tools=True,  # 🎯 Track all tool usage
        track_queries=True,  # 🎯 Track user queries as episodes
        augment_queries=True,  # ✨ Augment queries with historical context
        similarity_threshold=0.3,  # Match queries with 30%+ similarity
        top_k_similar=5,  # Use top 5 similar queries
        llm_provider="ollama",
        llm_model="qwen2.5:7b",
        ollama_base_url="http://100.108.18.43:11434/"
    )
    # print("✓ Tool tracking enabled automatically!")
    # print("✓ Query augmentation enabled!")
    # print()

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
    runner = create_query_tracking_runner(
        runner,
        memory,
        augment_queries=True,      # Enable augmentation
        similarity_threshold=0.3,  # Match queries with 30%+ similarity
        top_k_similar=5            # Use top 5 similar queries
    )
    # print("✓ Query tracking enabled - all user queries will be saved as episodes!")
    # print("✓ Query augmentation enabled - similar past queries will enrich new queries!")
    # print()

    # # Agent Interaction - use the agent normally, tracking happens automatically!
    # print("-" * 60)
    # print("Agent Conversation:")
    # print("-" * 60)

    queries = [
        "What's the weather in London?",
        # "That sounds nice!",
        # "How about Paris?",
        # Add similar query to test augmentation
        "What's the weather like in London today?",  # Similar to query 1 - should trigger augmentation!
    ]

    for query_idx, query in enumerate(queries):
        print(f"\n{'='*60}")
        print(f"👤 User: {query}")
        print(f"{'='*60}")
        content = types.Content(role='user', parts=[types.Part(text=query)])

        # Run the agent - tools are automatically tracked!
        events = runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content)
        logger.warn("########################################################")

        # Collect the final response
        final_response = None
        for event in events:
            if event.is_final_response():
                final_response = event.content.parts[0].text

        if final_response:
            print(f"\n🤖 Agent: {final_response}")
        print()

    # Tool tracking happens automatically during execution - no waiting needed!

    # Save detailed logs to file
    # with open(log_file, 'w') as f:
    #     json.dump(request_log, f, indent=2)
    # print(f"\n💾 Detailed request/response log saved to: {log_file}")
    # print()

    # Show tool analytics
    # print("=" * 60)
    # print("📊 Tool Analytics:")
    # print("=" * 60)
    # print()

    # Get user's tool preferences (this works immediately!)
    # print(f"Tools used by {USER_ID}:")
    # prefs = memory.ryumem.get_user_tool_preferences(
    #     user_id=USER_ID,
    #     group_id="demo_company",
    #     limit=5
    # )
    # if prefs:
    #     for pref in prefs:
    #         task_types = ', '.join(pref.get('task_types', []))
    #         print(f"  • {pref['tool_name']}")
    #         print(f"    - {pref['usage_count']} uses, {pref['success_rate']*100:.0f}% success")
    #         print(f"    - Used for: {task_types}")
    # else:
    #     print("  (No tools tracked yet)")
    # print()

    # print("=" * 60)
    # print()
    # print("✅ Demo completed!")
    # print()
    # print("💡 Key takeaways:")
    # print("   • User queries AND tool executions are both tracked as episodes")
    # print("   • Tool executions are automatically linked to the queries that triggered them")
    # print("   • Similar queries are augmented with historical tool usage patterns")
    # print("   • You used the agent normally via runner.run() - no manual tracking needed!")
    # print()
    # print("What was tracked:")
    # print("  • 4 user query episodes (message source)")
    # print("  • Tool execution episodes (json source)")
    # print("  • Hierarchical relationships: Query -[TRIGGERED]-> Tool Execution")
    # print("  • Query augmentation: Similar queries enriched with past tool usage")
    # print()
    # print("Query Augmentation:")
    # print("  • Query #4 'What's the weather like in London today?' is similar to Query #1")
    # print("  • The system automatically detected similarity and augmented it with:")
    # print("    - Past tool executions (get_weather_report)")
    # print("    - Tool arguments (city=London)")
    # print("    - Tool outputs and success rates")
    # print("  • Look for the ✨ 🔍 AUGMENTED QUERY log above!")
    # print()
    # print("Next steps:")
    # print("  - View tracked data in dashboard: http://localhost:3000")
    # print("  - Check episodes: Both queries and tool executions")
    # print("  - Check entities: TOOL and TASK_TYPE nodes")
    # print("  - Check relationships: TRIGGERED edges between episodes")
    # print("  - Read augmentation docs: AUGMENTING_QUERY_IMPLEMENTATION.md")
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
