"""
Ryumem Chat Demo - Basic Vanilla Usage

A simple interactive chat that demonstrates:
1. Storing conversation messages as episodes
2. Automatically retrieving relevant context from memory
3. Using LLM to generate natural answers from memory
"""

import os
from dotenv import load_dotenv
from ryumem import Ryumem

load_dotenv()


def is_question(text: str) -> bool:
    """Check if the input looks like a question."""
    question_words = ["who", "what", "where", "when", "why", "how", "do", "does", "did", "is", "are", "was", "were", "can", "could", "tell"]
    text_lower = text.lower().strip()
    return text_lower.endswith("?") or any(text_lower.startswith(w) for w in question_words)


def build_context(results) -> str:
    """Build context string from search results."""
    facts = []

    for ep in results.episodes[:5]:
        facts.append(ep.content)

    for entity in results.entities[:5]:
        if entity.summary:
            facts.append(f"{entity.name}: {entity.summary}")

    return "\n".join(facts) if facts else ""


def main():
    print("=" * 60)
    print("  Ryumem Chat Demo")
    print("  Tell me things, then ask questions!")
    print("  Type 'quit' to exit")
    print("=" * 60)

    # Initialize client
    client = Ryumem(
        server_url=os.getenv("RYUMEM_API_URL", "https://api.ryumem.io"),
    )

    user_id = "demo_user"
    session_id = "chat_session_001"
    message_count = 0

    print("\nConnected to Ryumem server!")
    print("Example: Tell me 'My name is Alice and I work at Google'")
    print("Then ask: 'Who am I?' or 'Who works at Google?'\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() == "quit":
            print("Goodbye!")
            break

        # Check if this is a question - if so, search memory and generate answer
        if is_question(user_input):
            # Search memory for relevant context
            results = client.search(
                query=user_input,
                user_id=user_id,
                session_id=session_id,
                strategy="hybrid",
                limit=5,
            )

            context = build_context(results)

            if context:
                # Use LLM to generate a natural response
                response = client.generate(
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant. Answer the user's question based ONLY on the context provided. Be concise and direct. If the context doesn't contain the answer, say you don't know."
                        },
                        {
                            "role": "user",
                            "content": f"Context:\n{context}\n\nQuestion: {user_input}"
                        }
                    ],
                    temperature=0.3,
                    max_tokens=150,
                )
                print(f"Bot: {response.content}\n")
            else:
                print("Bot: I don't have any information about that yet. Tell me more!\n")

            # Store the question in memory
            message_count += 1
            client.add_episode(
                content=f"User asked: {user_input}",
                user_id=user_id,
                session_id=f"{session_id}_msg_{message_count}",
                source="message",
                kind="query",
                metadata={"role": "user", "type": "question"},
            )
        else:
            # This is a statement - store it in memory
            message_count += 1
            episode_id = client.add_episode(
                content=user_input,
                user_id=user_id,
                session_id=f"{session_id}_msg_{message_count}",
                source="message",
                kind="memory",
                metadata={"role": "user", "type": "statement"},
            )

            print(f"Bot: Got it! I'll remember that.\n")

    print("\n" + "=" * 60)
    print(f"Session ended. Stored {message_count} messages.")
    print("=" * 60)


if __name__ == "__main__":
    main()
