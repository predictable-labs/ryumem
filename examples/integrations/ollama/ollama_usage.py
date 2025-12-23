"""
Ollama usage example for Ryumem.

This example demonstrates using local Ollama models instead of OpenAI.

Prerequisites:
1. Install Ollama: https://ollama.ai
2. Start Ollama: ollama serve
3. Pull a RECOMMENDED model (see below)

RECOMMENDED MODELS FOR RYUMEM:
1. qwen2.5:7b (BEST) - Excellent for structured JSON output
   Install: ollama pull qwen2.5:7b

2. qwen2.5:7b (FAST) - Good balance of speed and quality
   Install: ollama pull qwen2.5:7b

3. mistral:7b (QUALITY) - Best reasoning, good JSON support
   Install: ollama pull mistral:7b

AVOID: gpt-oss and other models not trained for structured output

Benefits of Ollama:
- No API costs
- Full privacy (data stays local)
- Offline usage
- Fast inference on local GPU

Note: Still requires OpenAI API key for embeddings (for now).
"""

import os
import logging
from dotenv import load_dotenv

from ryumem import Ryumem

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)


def main():
    print("=" * 60)
    print("Ryumem with Ollama - Local LLM Example")
    print("=" * 60)

    # Initialize Ryumem with Ollama
    print("\n1. Initializing Ryumem with Ollama...")

    # RECOMMENDED: Use qwen2.5:7b for best JSON structured output
    # You can also try: qwen2.5:7b (faster) or mistral:7b (better reasoning)
    model_name = os.getenv("RYUMEM_OLLAMA_MODEL", "qwen2.5:7b")

    print(f"   Model: {model_name} (local)")
    print("   Embeddings: text-embedding-3-large (OpenAI)")
    print(f"\n   ⚠️  Make sure you have pulled the model: ollama pull {model_name}")

    ryumem = Ryumem(
        db_path="./data/memory.db",
        llm_provider="ollama",  # Use Ollama instead of OpenAI
        llm_model=model_name,  # Local Ollama model
        ollama_base_url=os.getenv("RYUMEM_OLLAMA_BASE_URL", "http://localhost:11434"),  # Default Ollama URL
        openai_api_key=os.getenv("OPENAI_API_KEY"),  # Still needed for embeddings
        embedding_model="text-embedding-3-large",
    )
    print(f"   ✓ Initialized: {ryumem}")

    # Add some episodes
    print("\n2. Adding episodes with local LLM extraction...")
    episodes = [
        "Alice is a software engineer at Google working on TensorFlow.",
        "Bob graduated from Stanford University in 2020 with a CS degree.",
        "Alice and Bob are colleagues and often collaborate on ML projects.",
    ]

    for i, content in enumerate(episodes, 1):
        episode_id = ryumem.add_episode(
            content=content,
            group_id="ollama_user",
            user_id="ollama_user",
            source="text",
        )
        print(f"   ✓ Episode {i}: {episode_id[:8]}... - '{content[:50]}...'")

    # Search for information
    print("\n3. Searching (using local knowledge graph)...")

    queries = [
        "Where does Alice work?",
        "What did Bob study?",
        "How are Alice and Bob related?",
        "My name is John. Hello, how are you?"
    ]

    for query in queries:
        print(f"\n   Query: '{query}'")
        results = ryumem.search(
            query=query,
            group_id="ollama_user",
            strategy="hybrid",
            limit=3,
            min_rrf_score=0.0325,
            min_bm25_score=0.1,
        )

        if results.edges:
            print("   Top facts:")
            for edge in results.edges[:3]:
                score = results.scores.get(edge.uuid, 0.0)
                print(f"     - [Score: {score:.4f}] {edge.fact}")
        else:
            print("   No results found")

    # Clean up
    print("\n4. Cleaning up...")
    # ryumem.delete_group("ollama_user")
    ryumem.close()
    print("   ✓ Demo completed")

    print("\n" + "=" * 60)
    print("Ollama example completed successfully!")
    print("\n💡 Model Recommendations:")
    print("  🏆 qwen2.5:7b - BEST for structured JSON output (recommended)")
    print("  ⚡ qwen2.5:7b - FASTEST, good for quick inference")
    print("  🧠 mistral:7b - BEST reasoning, good JSON support")
    print("\n  To switch models, set environment variable:")
    print("  export RYUMEM_OLLAMA_MODEL=qwen2.5:7b")
    print("\n  Run 'ollama list' to see available models")
    print("=" * 60)


if __name__ == "__main__":
    main()
