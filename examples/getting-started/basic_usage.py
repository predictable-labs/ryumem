"""
Basic usage example for Ryumem.

This example demonstrates:
1. Initializing Ryumem
2. Adding episodes
3. Searching for information
4. Getting entity context
"""

import os
import logging
from dotenv import load_dotenv

from ryumem import Ryumem

# Load environment variables
load_dotenv()

# Configure logging to see duplicate detection and important events
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(levelname)s - %(message)s'
# )


def main():
    print("=" * 60)
    print("Ryumem - Basic Usage Example")
    print("=" * 60)

    # Initialize Ryumem
    print("\n1. Initializing Ryumem...")
    ryumem = Ryumem(
        db_path="./data/memory.db",
        llm_provider="ollama",
        llm_model="qwen2.5:7b",
        ollama_base_url="http://localhost:11434/",
    )
    print(f"   ✓ Initialized: {ryumem}")

    # Add some episodes
    print("\n2. Adding episodes...")
    episodes = [
        "Alice works at Google in Mountain View as a Software Engineer.",
        "Bob is Alice's colleague and lives in San Francisco.",
        "Alice graduated from Stanford University in 2018.",
        "Google is headquartered in Mountain View, California.",
        "Bob recently moved from Google to Meta.",
    ]

    episode_ids = []
    for i, content in enumerate(episodes, 1):
        episode_id = ryumem.add_episode(
            content=content,
            group_id="demo_user",
            user_id="demo_user",
            source="text",
        )
        episode_ids.append(episode_id)
        print(f"   ✓ Episode {i}: {episode_id[:8]}... - '{content[:50]}...'")

    # Search for information
    print("\n3. Searching for information...")

    queries = [
        "Where does Alice work?",
        "Tell me about Bob",
        "What do we know about Stanford?",
    ]

    for query in queries:
        print(f"\n   Query: '{query}'")
        results = ryumem.search(
            query=query,
            group_id="demo_user",
            strategy="hybrid",
            limit=5,
        )

        print(f"   Found {len(results.entities)} entities, {len(results.edges)} relationships")

        # Display top entities
        if results.entities:
            print("   Top entities:")
            for entity in results.entities[:3]:
                score = results.scores.get(entity.uuid, 0.0)
                print(f"     - {entity.name} ({entity.entity_type}) - score: {score:.3f}")

        # Display top relationships
        if results.edges:
            print("   Top relationships:")
            for edge in results.edges[:3]:
                score = results.scores.get(edge.uuid, 0.0)
                print(f"     - {edge.fact} - score: {score:.3f}")

    # Get entity context
    print("\n4. Getting entity context...")
    context = ryumem.get_entity_context(
        entity_name="alice",
        group_id="demo_user",
    )

    if context:
        print(f"   Entity: {context['entity']['name']}")
        print(f"   Type: {context['entity']['entity_type']}")
        print(f"   Summary: {context['entity'].get('summary', 'N/A')}")
        print(f"   Relationships: {context['relationship_count']}")

        if context['relationships']:
            print("   Connections:")
            for rel in context['relationships'][:5]:
                print(f"     - {rel['relation_type']}: {rel['other_name']}")

    # Clean up
    print("\n5. Cleaning up...")
    # ryumem.delete_group("demo_user")
    # ryumem.close()
    print("   ✓ Demo completed and cleaned up")

    print("\n" + "=" * 60)
    print("Example completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
