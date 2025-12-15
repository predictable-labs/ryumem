"""
Test Entity Extraction - Different Sentence Types

This script tests how the knowledge graph extracts entities and relationships
from various types of sentences. It helps verify:
- Entity detection (people, organizations, locations, products, etc.)
- Relationship extraction (works_at, lives_in, owns, etc.)
- Handling of different sentence structures and lengths

Prerequisites:
    pip install ryumem python-dotenv

Setup:
    export RYUMEM_API_URL=http://localhost:8000
    export RYUMEM_API_KEY=ryu_your_api_key

    # For entity extraction (background worker)
    export GOOGLE_API_KEY=your_google_api_key  # or OPENAI_API_KEY

Usage:
    python examples/test_entity_extraction.py

    # Test specific category
    python examples/test_entity_extraction.py --category people

    # Test with delay between sentences (to see worker processing)
    python examples/test_entity_extraction.py --delay 3
"""

import os
import sys
import time
import argparse
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Test sentences organized by category
TEST_SENTENCES = {
    "people_organizations": [
        # Simple person-org relationships
        "Alice works at Google as a software engineer.",
        "Bob is the CEO of Microsoft.",
        "Sarah joined Amazon last month as a product manager.",

        # Multiple people, one org
        "John, Mary, and Peter all work at Apple.",

        # Person with multiple orgs
        "David previously worked at Facebook before joining Netflix.",
    ],

    "locations": [
        # Person-location
        "Emma lives in San Francisco.",
        "The Smiths moved from New York to Los Angeles last year.",

        # Organization-location
        "Tesla's headquarters is located in Austin, Texas.",
        "SpaceX operates launch facilities in Florida and California.",

        # Multiple locations
        "Our company has offices in London, Tokyo, and Sydney.",
    ],

    "relationships": [
        # Family relationships
        "Tom is married to Jessica and they have two children.",
        "Michael's sister works at the same company as his wife.",

        # Professional relationships
        "Dr. Smith mentors three graduate students at MIT.",
        "The project was led by Jane with support from the engineering team.",

        # Social relationships
        "Alex and Ryan have been best friends since college.",
    ],

    "products_tech": [
        # Product ownership
        "Apple released the iPhone 15 with a new titanium design.",
        "Microsoft announced Windows 12 at their annual conference.",

        # Tech relationships
        "ChatGPT is developed by OpenAI using GPT-4 architecture.",
        "Kubernetes was originally designed by Google engineers.",

        # Usage/preference
        "Our team uses Slack for communication and Jira for project tracking.",
    ],

    "events_time": [
        # Past events
        "The company was founded in 2015 by three Stanford graduates.",
        "Last quarter, revenue increased by 25% compared to the previous year.",

        # Scheduled events
        "The product launch is scheduled for March 2024.",
        "Weekly team meetings happen every Tuesday at 10 AM.",

        # Duration
        "Jennifer has been working on this project for six months.",
    ],

    "complex_multi_fact": [
        # Multiple facts in one sentence
        "Mark Zuckerberg, the founder of Facebook (now Meta), lives in Palo Alto and is married to Priscilla Chan.",

        # Long descriptive sentence
        "The research team at Stanford University, led by Professor Johnson, published groundbreaking findings on machine learning that were later adopted by Google and Microsoft.",

        # Conversational with multiple entities
        "I met with Sarah from the marketing team and David from engineering to discuss the new product launch that's planned for Q2.",
    ],

    "conversational": [
        # First person statements
        "I prefer using Python for data analysis over R.",
        "My favorite restaurant is the Italian place on Main Street.",

        # Questions (should still extract entities)
        "Have you heard about the new project that Lisa is leading?",

        # Casual mentions
        "Oh, I ran into James at the coffee shop - he said he's moving to Seattle.",

        # Opinions
        "I think the new MacBook Pro is better than the Dell XPS for development work.",
    ],

    "edge_cases": [
        # Very short
        "Bob knows Alice.",

        # No clear entities
        "The weather is nice today.",

        # Ambiguous references
        "He works there now.",

        # Numbers and data
        "The report shows 1,500 users with an average session time of 5 minutes.",

        # Special characters
        "Contact support@example.com or visit https://example.com for help.",
    ],

    "paragraphs": [
        # Multi-sentence paragraph
        """Last week, I had a great meeting with the engineering team at Acme Corp.
        Their CTO, Rebecca Chen, showed us their new AI platform.
        The technology was developed in partnership with researchers from MIT and Stanford.
        We're planning to integrate it with our existing systems by next quarter.""",

        # Story-like content
        """John started his career at a small startup in Boston. After five years,
        he moved to San Francisco to join Google's AI research team. There, he met
        his future co-founder, Maria, who had previously worked at DeepMind in London.
        Together, they launched NeuralTech in 2022.""",
    ],
}


def test_entity_extraction(
    api_url: str = None,
    api_key: str = None,
    category: str = None,
    delay: float = 1.0,
    user_id: str = "test_user",
):
    """
    Test entity extraction with various sentence types.

    Args:
        api_url: Ryumem API URL (defaults to env var)
        api_key: Ryumem API key (defaults to env var)
        category: Specific category to test (None = all)
        delay: Delay between sentences in seconds
        user_id: User ID for the test
    """
    from ryumem import Ryumem

    # Initialize client
    ryumem = Ryumem(
        api_url=api_url,
        api_key=api_key,
    )

    print("=" * 80)
    print("Entity Extraction Test Suite")
    print("=" * 80)
    print(f"API URL: {ryumem.api_url}")
    print(f"User ID: {user_id}")
    print(f"Delay between sentences: {delay}s")
    print("=" * 80)
    print()

    # Filter categories if specified
    categories = TEST_SENTENCES.keys() if category is None else [category]

    results = []
    total_sentences = 0

    for cat in categories:
        if cat not in TEST_SENTENCES:
            print(f"Warning: Category '{cat}' not found, skipping...")
            continue

        sentences = TEST_SENTENCES[cat]
        print(f"\n{'='*60}")
        print(f"Category: {cat.upper().replace('_', ' ')}")
        print(f"{'='*60}")

        for i, sentence in enumerate(sentences, 1):
            total_sentences += 1

            # Truncate for display
            display_text = sentence[:100] + "..." if len(sentence) > 100 else sentence
            display_text = display_text.replace('\n', ' ')

            print(f"\n[{i}/{len(sentences)}] Testing: {display_text}")

            try:
                start_time = time.time()

                # Add episode with entity extraction enabled
                episode_id = ryumem.add_episode(
                    content=sentence,
                    user_id=user_id,
                    extract_entities=True,
                    metadata={
                        "test_category": cat,
                        "test_index": i,
                        "test_timestamp": datetime.now().isoformat(),
                    }
                )

                elapsed = time.time() - start_time

                print(f"   Episode ID: {episode_id}")
                print(f"   Time: {elapsed:.2f}s")

                results.append({
                    "category": cat,
                    "sentence": sentence[:50],
                    "episode_id": episode_id,
                    "success": True,
                    "time": elapsed,
                })

            except Exception as e:
                print(f"   ERROR: {e}")
                results.append({
                    "category": cat,
                    "sentence": sentence[:50],
                    "episode_id": None,
                    "success": False,
                    "error": str(e),
                })

            # Delay to allow worker to process
            if delay > 0:
                time.sleep(delay)

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful

    print(f"Total sentences tested: {total_sentences}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")

    if results:
        avg_time = sum(r.get("time", 0) for r in results if r["success"]) / max(successful, 1)
        print(f"Average time per sentence: {avg_time:.2f}s")

    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("""
To verify entity extraction results:

1. Check the worker logs for extraction details:
   - Look for "Extracted X raw entities" messages
   - Look for "Upserted X entities" messages

2. Query the knowledge graph:
   curl -X GET "http://localhost:8000/entities?user_id=test_user" \\
     -H "X-API-Key: YOUR_API_KEY"

3. Search for specific entities:
   curl -X POST "http://localhost:8000/search" \\
     -H "X-API-Key: YOUR_API_KEY" \\
     -H "Content-Type: application/json" \\
     -d '{"query": "Who works at Google?", "user_id": "test_user"}'

4. Get entity details:
   curl -X GET "http://localhost:8000/entity/alice?user_id=test_user" \\
     -H "X-API-Key: YOUR_API_KEY"
""")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Test entity extraction with various sentence types"
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("RYUMEM_API_URL", "http://localhost:8000"),
        help="Ryumem API URL"
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("RYUMEM_API_KEY"),
        help="Ryumem API key"
    )
    parser.add_argument(
        "--category",
        choices=list(TEST_SENTENCES.keys()),
        help="Test specific category only"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between sentences (seconds)"
    )
    parser.add_argument(
        "--user-id",
        default="test_entity_extraction",
        help="User ID for test data"
    )
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="List available categories and exit"
    )

    args = parser.parse_args()

    if args.list_categories:
        print("Available categories:")
        for cat, sentences in TEST_SENTENCES.items():
            print(f"  {cat}: {len(sentences)} sentences")
        return

    if not args.api_key:
        print("ERROR: RYUMEM_API_KEY not set")
        print("Set it via environment variable or --api-key argument")
        sys.exit(1)

    test_entity_extraction(
        api_url=args.api_url,
        api_key=args.api_key,
        category=args.category,
        delay=args.delay,
        user_id=args.user_id,
    )


if __name__ == "__main__":
    main()
