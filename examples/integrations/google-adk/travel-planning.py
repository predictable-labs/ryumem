"""
Google-ADK Multi-Tool Chatbot Demo with Ryumem Memory
Interrelated Tools → Flight Search → Budget → Itinerary → Final Plan

This example demonstrates how Ryumem's memory and tool tracking helps maintain
context across a multi-step travel planning workflow.
"""

import os
import asyncio
from dotenv import load_dotenv
from typing import Dict

from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from ryumem import Ryumem
from ryumem.integrations import add_memory_to_agent, wrap_runner_with_tracking

# Load environment variables
load_dotenv()

# App configuration
APP_NAME = "travel_planning_demo"
USER_ID = "traveler_1"
SESSION_ID = "session_1"
MODEL_ID = "gemini-2.0-flash-exp"


# ------------------------------------------
# TOOL 1 — Search Flights
# ------------------------------------------
def search_flights(origin: str, destination: str) -> Dict:
    """
    Return dummy flight price data.
    The output feeds into the budget tool.
    """
    prices = {
        "Mumbai-Delhi": 5500,
        "Delhi-Mumbai": 5300,
        "Mumbai-Bangalore": 4200,
        "Bangalore-Delhi": 4700,
    }
    key = f"{origin}-{destination}"
    return {
        "origin": origin,
        "destination": destination,
        "flight_price": prices.get(key, 6000),
    }


# ------------------------------------------
# TOOL 2 — Budget Estimator
# ------------------------------------------
def estimate_budget(flight_price: int, hotel_nights: int) -> Dict:
    """
    Estimate total cost: flight + hotel + food.
    Depends on output from search_flights.
    """
    hotel_rate = 2500
    food_cost_per_day = 800

    total = flight_price + hotel_rate * hotel_nights + food_cost_per_day * hotel_nights

    return {
        "flight_price": flight_price,
        "hotel_nights": hotel_nights,
        "hotel_cost": hotel_rate * hotel_nights,
        "food_cost": food_cost_per_day * hotel_nights,
        "total_budget": total,
    }


# ------------------------------------------
# TOOL 3 — Create Itinerary
# ------------------------------------------
def create_itinerary(destination: str, budget: int) -> Dict:
    """
    Build a small 2-day itinerary based on leftover budget.
    Takes destination + budget from previous tools.
    """
    spots = {
        "Delhi": ["India Gate", "Qutub Minar", "Humayun's Tomb"],
        "Mumbai": ["Marine Drive", "Gateway of India", "Bandra Fort"],
        "Bangalore": ["Cubbon Park", "Lalbagh", "MG Road"],
    }

    return {
        "destination": destination,
        "budget": budget,
        "itinerary": spots.get(destination, ["Explore local sights"]),
    }


# ------------------------------------------
# TOOL 4 — Final Combiner
# ------------------------------------------
def finalize_trip(
    origin: str,
    destination: str,
    flight_price: int,
    hotel_cost: int,
    food_cost: int,
    total_budget: int,
    itinerary_spot_1: str,
    itinerary_spot_2: str,
    itinerary_spot_3: str
) -> str:
    """
    Combine the outputs from all 3 tools into a final summary.

    Args:
        origin: Starting city
        destination: Destination city
        flight_price: Cost of the flight
        hotel_cost: Total hotel cost
        food_cost: Total food cost
        total_budget: Complete trip budget
        itinerary_spot_1: First tourist spot
        itinerary_spot_2: Second tourist spot
        itinerary_spot_3: Third tourist spot
    """

    summary = f"""
✈️ Trip Summary
----------------
From: {origin}
To: {destination}

Flight Price: ₹{flight_price}
Hotel Cost: ₹{hotel_cost}
Food Cost: ₹{food_cost}
Total Budget Required: ₹{total_budget}

🗒️ Itinerary:
- {itinerary_spot_1}
- {itinerary_spot_2}
- {itinerary_spot_3}

Budget Remaining After Flight: ₹{total_budget - flight_price}
"""

    return summary.strip()


# ------------------------------------------
# BUILD THE AGENT
# ------------------------------------------
def build_agent():
    """Creates and configures the travel planning agent with Ryumem memory."""
    # Create tools
    search_flights_tool = FunctionTool(func=search_flights)
    estimate_budget_tool = FunctionTool(func=estimate_budget)
    create_itinerary_tool = FunctionTool(func=create_itinerary)
    finalize_trip_tool = FunctionTool(func=finalize_trip)

    # Create agent with detailed instructions
    agent = Agent(
        model=MODEL_ID,
        name='travel_planner',
        instruction="""You are a travel planning agent.

When the user asks for a trip plan:
1. First call search_flights to get flight pricing
2. Use its output to call estimate_budget to calculate total costs
3. Use that output to call create_itinerary to build an itinerary
4. Finally call finalize_trip with all individual values from the previous tools to create a complete summary

DO NOT answer directly. Always orchestrate a multi-step tool workflow.
Make sure to use the actual data from each tool call in the next step.

Example workflow:
- User: "Plan a trip from Mumbai to Delhi for 3 nights"
- Step 1: Call search_flights(origin="Mumbai", destination="Delhi")
  Returns: {"origin": "Mumbai", "destination": "Delhi", "flight_price": 5500}

- Step 2: Call estimate_budget(flight_price=5500, hotel_nights=3)
  Returns: {"flight_price": 5500, "hotel_nights": 3, "hotel_cost": 7500, "food_cost": 2400, "total_budget": 15400}

- Step 3: Call create_itinerary(destination="Delhi", budget=15400)
  Returns: {"destination": "Delhi", "budget": 15400, "itinerary": ["India Gate", "Qutub Minar", "Humayun's Tomb"]}

- Step 4: Call finalize_trip with individual parameters:
  finalize_trip(
    origin="Mumbai",
    destination="Delhi",
    flight_price=5500,
    hotel_cost=7500,
    food_cost=2400,
    total_budget=15400,
    itinerary_spot_1="India Gate",
    itinerary_spot_2="Qutub Minar",
    itinerary_spot_3="Humayun's Tomb"
  )

- Step 5: Present the final summary to the user
""",
        tools=[search_flights_tool, estimate_budget_tool, create_itinerary_tool, finalize_trip_tool]
    )

    return agent


# ------------------------------------------
# CHAT LOOP WITH RYUMEM INTEGRATION
# ------------------------------------------
async def run_chat_loop():
    """Main async function to run the interactive chat loop with Ryumem."""
    print("=" * 80)
    print("🤖 Google-ADK Multi-Tool Travel Planning Chatbot + Ryumem")
    print("=" * 80)
    print()
    print("FEATURES:")
    print("  • Multi-step tool workflow for travel planning")
    print("  • Memory-enhanced context across conversations")
    print("  • Tool tracking for better decision making")
    print("  • Query augmentation for similar requests")
    print()
    print("Type 'exit' or 'quit' to end the session")
    print("=" * 80)
    print()

    # Build the agent
    agent = build_agent()
    print("✓ Agent created with 4 tools")
    print()

    # Initialize Ryumem with memory and tool tracking
    ryumem = Ryumem(
        track_tools=True,        # Enable tool tracking
        augment_queries=True,    # Enable query augmentation
        similarity_threshold=0.3,  # Match queries with 30%+ similarity
        top_k_similar=5,         # Use top 5 similar queries for context
    )

    # Add memory to the agent
    agent = add_memory_to_agent(agent, ryumem)
    print("✓ Memory and tool tracking enabled")
    print()

    # Set up session service
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID
    )

    # Create runner
    runner = Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=session_service
    )

    # Wrap runner with tracking
    runner = wrap_runner_with_tracking(runner, agent)
    print("✓ Runner wrapped with query tracking and augmentation")
    print()

    # Interactive chat loop
    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit"]:
                print("\n👋 Goodbye!")
                break

            print()

            # Create content object
            content = types.Content(role='user', parts=[types.Part(text=user_input)])

            # Run the agent
            events = runner.run(
                user_id=USER_ID,
                session_id=SESSION_ID,
                new_message=content
            )

            # Collect and display the response
            final_response = None
            for event in events:
                if event.is_final_response():
                    final_response = event.content.parts[0].text

            if final_response:
                print(f"Assistant: {final_response}")
            print()

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {type(e).__name__}: {e}")
            print()


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
        print()

    # Run the async chat loop
    asyncio.run(run_chat_loop())
