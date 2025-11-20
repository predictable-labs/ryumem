"""
Client Usage Example for Ryumem.

This example demonstrates how to use the Ryumem client to interact with a running Ryumem server.
It relies on the RYUMEM_API_URL environment variable (or defaults to http://localhost:8000).
"""

import os
import time
from dotenv import load_dotenv
from ryumem import Ryumem

# Load environment variables from .env file
load_dotenv()

def main():
    print("=" * 60)
    print("Ryumem - Client Usage Example")
    print("=" * 60)

    # Initialize Ryumem Client
    # It will automatically pick up RYUMEM_API_URL from environment
    print("\n1. Connecting to Ryumem Server...")
    ryumem = Ryumem()
    print(f"   ✓ Connected to: {ryumem.base_url}")

    # Add an episode
    print("\n2. Adding an episode...")
    try:
        episode_id = ryumem.add_episode(
            content="Charlie works at OpenAI in San Francisco as a Research Scientist.",
            user_id="client_demo_user",
            source="text",
        )
        print(f"   ✓ Episode added: {episode_id}")
    except Exception as e:
        print(f"   ❌ Failed to add episode: {e}")
        return

    # Wait a moment for processing (if async)
    time.sleep(1)

    # Search for information
    print("\n3. Searching for information...")
    try:
        results = ryumem.search(
            query="Where does Charlie work?",
            user_id="client_demo_user",
            strategy="hybrid",
            limit=5,
        )

        print(f"   Found {len(results.entities)} entities, {len(results.edges)} relationships")

        if results.entities:
            print("   Top entities:")
            for entity in results.entities:
                print(f"     - {entity.name} ({entity.entity_type})")
        
        if results.edges:
            print("   Top facts:")
            for edge in results.edges:
                print(f"     - {edge.fact}")

    except Exception as e:
        print(f"   ❌ Search failed: {e}")

    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
