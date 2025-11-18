"""
Password Guessing Game - Google ADK + Ryumem (Synchronous Version)

This example demonstrates how Ryumem's query augmentation helps an agent learn from
previous attempts to guess a password more intelligently.

The Game:
    • Agent has 10 attempts to guess a 4-character password
    • Each character can be: A, B, C, or D
    • Agent gets feedback on how many characters are correct (but not which ones)
    • Agent can use tools to validate guesses and get hints

Why This Tests Augmentation:
    • Similar queries like "try ABCD" and "try ABDC" should be recognized
    • Previous validation results should inform new guesses
    • Agent should learn patterns (e.g., if ABCD has 2 correct, ABDC with 1 correct means B isn't position 2)
    • Query augmentation provides historical context of what's been tried and what feedback was received

Prerequisites:
    pip install google-adk ryumem

Setup:
    export GOOGLE_API_KEY=your_api_key
    # Optional: export OPENAI_API_KEY=your_openai_key  # For better embeddings
"""

import os
import asyncio
from dotenv import load_dotenv
import logging
import random
from typing import Dict, List

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
APP_NAME = "password_guessing_game"
USER_ID = "player_1"
SESSION_ID = "game_session_1"
MODEL_ID = "gemini-2.0-flash-exp"

# Game state
CORRECT_PASSWORD = None  # Will be set randomly
ATTEMPTS_REMAINING = 10
GUESS_HISTORY = []


def initialize_game() -> str:
    """Initialize a new game with a random password."""
    global CORRECT_PASSWORD, ATTEMPTS_REMAINING, GUESS_HISTORY

    # Generate random 4-character password using A, B, C, D
    chars = ['A', 'B', 'C', 'D']
    CORRECT_PASSWORD = ''.join(random.choices(chars, k=4))
    ATTEMPTS_REMAINING = 10
    GUESS_HISTORY = []

    return CORRECT_PASSWORD


def validate_password_guess(guess: str) -> Dict:
    """
    Validates a password guess and returns feedback.

    Args:
        guess: A 4-character string containing only A, B, C, or D

    Returns:
        dict: Contains:
            - valid: bool - whether the guess format is valid
            - correct: bool - whether the password is completely correct
            - correct_positions: int - how many characters are in the right position
            - attempts_remaining: int - how many attempts are left
            - message: str - feedback message
    """
    global ATTEMPTS_REMAINING, GUESS_HISTORY

    # Validate format
    if not guess or len(guess) != 4:
        return {
            "valid": False,
            "correct": False,
            "correct_positions": 0,
            "attempts_remaining": ATTEMPTS_REMAINING,
            "message": "Invalid guess! Password must be exactly 4 characters."
        }

    guess = guess.upper()

    if not all(c in ['A', 'B', 'C', 'D'] for c in guess):
        return {
            "valid": False,
            "correct": False,
            "correct_positions": 0,
            "attempts_remaining": ATTEMPTS_REMAINING,
            "message": "Invalid characters! Only A, B, C, D are allowed."
        }

    # Check if already guessed
    if guess in GUESS_HISTORY:
        return {
            "valid": False,
            "correct": False,
            "correct_positions": 0,
            "attempts_remaining": ATTEMPTS_REMAINING,
            "message": f"You already tried '{guess}'! Try a different combination."
        }

    # Count correct positions
    correct_positions = sum(1 for i in range(4) if guess[i] == CORRECT_PASSWORD[i])

    # Update game state
    ATTEMPTS_REMAINING -= 1
    GUESS_HISTORY.append(guess)

    # Check if won
    if guess == CORRECT_PASSWORD:
        return {
            "valid": True,
            "correct": True,
            "correct_positions": 4,
            "attempts_remaining": ATTEMPTS_REMAINING,
            "message": f"🎉 Correct! The password is '{guess}'! You won with {ATTEMPTS_REMAINING} attempts remaining!"
        }

    # Check if lost
    if ATTEMPTS_REMAINING == 0:
        return {
            "valid": True,
            "correct": False,
            "correct_positions": correct_positions,
            "attempts_remaining": 0,
            "message": f"❌ Game Over! You ran out of attempts. The password was '{CORRECT_PASSWORD}'."
        }

    # Continue game
    return {
        "valid": True,
        "correct": False,
        "correct_positions": correct_positions,
        "attempts_remaining": ATTEMPTS_REMAINING,
        "message": f"'{guess}' has {correct_positions} characters in the correct position. {ATTEMPTS_REMAINING} attempts remaining."
    }


def get_attempts_remaining() -> Dict:
    """
    Returns the number of attempts remaining.

    Returns:
        dict: Contains attempts_remaining and message
    """
    return {
        "attempts_remaining": ATTEMPTS_REMAINING,
        "message": f"You have {ATTEMPTS_REMAINING} attempts remaining."
    }


def get_guess_history() -> Dict:
    """
    Returns all previous guesses and their results.

    Returns:
        dict: Contains history of guesses
    """
    if not GUESS_HISTORY:
        return {
            "history": [],
            "message": "No guesses yet! Start by trying a 4-character combination of A, B, C, D."
        }

    history_text = "\n".join([f"  - {guess}" for guess in GUESS_HISTORY])

    return {
        "history": GUESS_HISTORY,
        "total_guesses": len(GUESS_HISTORY),
        "message": f"You have tried {len(GUESS_HISTORY)} guesses so far:\n{history_text}"
    }


def get_hint() -> Dict:
    """
    Provides a strategic hint based on previous guesses.

    Returns:
        dict: Contains a hint message
    """
    if len(GUESS_HISTORY) == 0:
        return {
            "hint": "Start with a systematic approach. Try 'AAAA' to see how many A's are in the password."
        }

    if len(GUESS_HISTORY) == 1:
        return {
            "hint": "Try 'BBBB' next to see how many B's are in the password. Compare with your previous result."
        }

    if len(GUESS_HISTORY) == 2:
        return {
            "hint": "Now try 'CCCC' to check for C's. This will help you understand the character distribution."
        }

    # Generic hints for later attempts
    hints = [
        "Look for patterns in your previous guesses. Which positions gave you more correct characters?",
        "Try swapping characters between positions based on your previous results.",
        "Consider combinations that eliminate what you've already ruled out.",
        "Focus on the positions that have been consistently correct across multiple guesses."
    ]

    return {
        "hint": random.choice(hints)
    }


async def main():
    """Main function to run the password guessing game with automatic tool tracking."""

    print("=" * 80)
    print("🔐 Password Guessing Game - Google ADK + Ryumem (Sync Version)")
    print("=" * 80)
    print()
    print("GAME RULES:")
    print("  • Guess the 4-character password")
    print("  • Each character can be: A, B, C, or D")
    print("  • You have 10 attempts")
    print("  • You'll get feedback on how many characters are in the correct position")
    print()
    print("WHY THIS TESTS AUGMENTATION:")
    print("  • Similar queries are recognized (e.g., 'try ABCD' vs 'guess ABCD')")
    print("  • Previous validation results inform new guesses")
    print("  • Agent learns patterns from historical feedback")
    print("=" * 80)
    print()

    # Initialize game
    password = initialize_game()
    print(f"🎮 Game initialized! (Password: {'*' * 4} - hidden)")
    print(f"   [DEBUG - Actual password: {password}]")
    print()

    # Create tools
    validate_tool = FunctionTool(func=validate_password_guess)
    attempts_tool = FunctionTool(func=get_attempts_remaining)
    history_tool = FunctionTool(func=get_guess_history)
    hint_tool = FunctionTool(func=get_hint)

    # Create agent with detailed instructions
    password_agent = Agent(
        model=MODEL_ID,
        name='password_guesser',
        instruction="""You are a strategic password guesser playing a game.

GAME RULES:
- The password is 4 characters long
- Each character can only be A, B, C, or D
- You have 10 attempts total
- For each guess, you'll get feedback on how many characters are in the correct position (but not which ones)

AVAILABLE TOOLS:
1. validate_password_guess(guess) - Make a guess and get feedback
2. get_attempts_remaining() - Check how many attempts you have left
3. get_guess_history() - See all your previous guesses
4. get_hint() - Get a strategic hint

WINNING STRATEGY:
1. Start systematically (e.g., try 'AAAA' to see how many A's are in the password)
2. Use the feedback to narrow down possibilities
3. Keep track of what you've learned from each guess
4. Be strategic - don't waste attempts on random guesses
5. Use the hint tool if you're stuck

IMPORTANT:
- Always validate your guess using validate_password_guess()
- Pay attention to the feedback (correct_positions)
- Don't guess the same password twice
- Think strategically based on previous results

When the user asks you to guess or try a password, use the validate_password_guess tool.
If the user asks for your progress or history, use get_guess_history.
If the user wants a hint, use get_hint.""",
        tools=[validate_tool, attempts_tool, history_tool, hint_tool]
    )

    print("✓ Agent created with 4 tools")
    print()

    # ⭐ Add memory + tool tracking + query augmentation
    memory = add_memory_to_agent(
        password_agent,
        user_id=USER_ID,
        ryumem_customer_id="password_game",
    )

    print("✓ Memory and tool tracking enabled")
    print()

    # Session and Runner Setup
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID
    )

    runner = Runner(
        agent=password_agent,
        app_name=APP_NAME,
        session_service=session_service
    )

    # ⭐ Wrap runner to automatically track user queries and augment with history
    runner = wrap_runner_with_tracking(
        runner,
        memory,
        augment_queries=True,      # ✨ Enable augmentation - this is key!
        similarity_threshold=0.3,  # Match queries with 30%+ similarity
        top_k_similar=5            # Use top 5 similar queries for context
    )

    print("✓ Runner wrapped with query tracking and augmentation")
    print()

    # Game conversation flow
    queries = [
        "Let's start! Try AAAA first to see how many A's are in the password.",
        "Now try BBBB to check for B's.",
        "Try CCCC next.",
        "Based on the results so far, make your best strategic guess.",
        "Keep going with your strategy.",
        "Try another guess based on what you've learned.",
        "You're getting close! Make another educated guess.",
        "Use the patterns you've seen to narrow it down further.",
        "What's your next best guess?",
        "Final guess - what do you think the password is?"
    ]

    game_won = False

    for query_idx, query in enumerate(queries, 1):
        if ATTEMPTS_REMAINING == 0 or game_won:
            break

        print(f"\n{'='*80}")
        print(f"Attempt {11 - ATTEMPTS_REMAINING}/{10}")
        print(f"👤 User: {query}")
        print(f"{'='*80}")

        content = types.Content(role='user', parts=[types.Part(text=query)])

        # Run the agent - tools are automatically tracked!
        # Query augmentation will provide context from similar previous queries
        events = runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content)

        # Collect the final response
        final_response = None
        for event in events:
            if event.is_final_response():
                final_response = event.content.parts[0].text

        if final_response:
            print(f"\n🤖 Agent: {final_response}")

        # Check if game is won
        if ATTEMPTS_REMAINING > 0 and len(GUESS_HISTORY) > 0:
            last_guess = GUESS_HISTORY[-1]
            if last_guess == CORRECT_PASSWORD:
                game_won = True
                print("\n" + "="*80)
                print("🎉 GAME WON! 🎉")
                print("="*80)
                break

    # Game summary
    print("\n" + "="*80)
    print("📊 GAME SUMMARY")
    print("="*80)
    print(f"Password: {CORRECT_PASSWORD}")
    print(f"Total guesses: {len(GUESS_HISTORY)}")
    print(f"Attempts remaining: {ATTEMPTS_REMAINING}")
    print(f"Result: {'🎉 WON!' if game_won else '❌ LOST'}")
    print(f"\nGuess history:")
    for i, guess in enumerate(GUESS_HISTORY, 1):
        correct_pos = sum(1 for j in range(4) if guess[j] == CORRECT_PASSWORD[j])
        status = "✓" if guess == CORRECT_PASSWORD else f"{correct_pos}/4"
        print(f"  {i}. {guess} - {status}")
    print("="*80)

    print("\n💡 AUGMENTATION TEST RESULTS:")
    print("   The agent should have learned from previous guesses through query augmentation.")
    print("   Check if similar queries (e.g., 'try ABCD' vs 'guess ABCD') shared context.")
    print("   The agent should have improved its guessing strategy based on historical feedback.")


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

    asyncio.run(main())
