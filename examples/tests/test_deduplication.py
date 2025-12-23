"""
Test script to verify episode deduplication and caching.

Run this script multiple times to see:
1. First run: Full ingestion (~20-25s)
2. Second run: Duplicate detection (<1s)
3. Cache statistics showing hits/misses
"""

import os
import logging
from dotenv import load_dotenv

from ryumem import Ryumem
from ryumem.utils.cache import get_cache_stats

# Load environment variables
load_dotenv()

# Configure logging with DEBUG level to see cache hits
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)


def main():
    print("=" * 70)
    print("Episode Deduplication & Caching Test")
    print("=" * 70)

    # Initialize Ryumem
    print("\n1. Initializing Ryumem...")
    ryumem = Ryumem(
        db_path="./data/memory.db",  # Different DB to avoid conflicts
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        llm_provider="ollama",
        llm_model="qwen2.5:7b",
        ollama_base_url="http://localhost:11434/",
    )
    print(f"   ✓ Initialized")

    # Add the same episode multiple times
    print("\n2. Adding episodes (watch for duplicate detection)...")

    test_episode = "Alice works at Google in Mountain View as a Software Engineer."

    print(f"\n   Episode content: '{test_episode}'")
    print(f"   Adding episode 3 times...\n")

    for i in range(1, 4):
        print(f"   --- Attempt {i} ---")
        episode_id = ryumem.add_episode(
            content=test_episode,
            group_id="dedup_test_user",
            user_id="dedup_test_user",
            source="text",
        )
        print(f"   ✓ Returned episode ID: {episode_id[:8]}...\n")

    # Show cache statistics
    print("\n3. Cache Statistics:")
    stats = get_cache_stats()

    for cache_name, cache_stats in stats.items():
        print(f"\n   {cache_name}:")
        print(f"     - Size: {cache_stats['size']}/{cache_stats['max_size']}")
        print(f"     - Hits: {cache_stats['hits']}")
        print(f"     - Misses: {cache_stats['misses']}")
        print(f"     - Hit rate: {cache_stats['hit_rate']:.1%}")

    # Don't clean up so we can test deduplication on next run
    print("\n4. NOT cleaning up - data preserved for next run")
    print("   Run this script again to see duplicate detection in action!")

    ryumem.close()

    print("\n" + "=" * 70)
    print("Test completed!")
    print("=" * 70)
    print("\nExpected behavior:")
    print("  - 1st run: Full ingestion for attempt 1, duplicates for attempts 2 & 3")
    print("  - 2nd run: All 3 attempts should be detected as duplicates")
    print("  - Cache hit rate should increase with each run")
    print("=" * 70)


if __name__ == "__main__":
    main()
