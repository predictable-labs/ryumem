"""
Advanced usage example for Ryumem.

This example demonstrates:
1. BM25 keyword search
2. Temporal decay scoring
3. Community detection
4. Memory pruning and compaction
5. Hybrid search strategies
"""

import os
import time
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

from ryumem import Ryumem

# Load environment variables
load_dotenv()


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main():
    print_section("Ryumem - Advanced Features Demo")

    # Initialize Ryumem
    print("\n1. Initializing Ryumem with custom configuration...")
    ryumem = Ryumem(
        db_path="./data/memory.db",
        llm_provider="ollama",
        llm_model="qwen2.5:7b",
        ollama_base_url="http://localhost:11434/",
    )
    print(f"   ✓ Initialized: {ryumem}")

    # Add diverse episodes to build a knowledge graph
    print_section("2. Building Knowledge Graph")

    tech_episodes = [
        "Alice is a Machine Learning Engineer at Google working on TensorFlow.",
        "Bob is a Data Scientist at Meta focusing on recommendation systems.",
        "Alice graduated from Stanford University with a PhD in Computer Science.",
        "Bob and Alice collaborated on a natural language processing research paper.",
        "Google acquired DeepMind to advance artificial intelligence research.",
        "Meta is developing Llama, an open-source large language model.",
        "Stanford University is a leading institution for AI research.",
        "Alice recently moved from Google to OpenAI to work on GPT models.",  # This will invalidate the first fact!
    ]

    academic_episodes = [
        "Professor Chen teaches Machine Learning at MIT.",
        "Professor Chen published a breakthrough paper on neural networks.",
        "MIT has partnerships with tech companies for AI research.",
        "Professor Chen mentored Alice during her undergraduate studies.",
    ]

    personal_episodes = [
        "Alice enjoys rock climbing on weekends.",
        "Bob is learning to play the guitar.",
        "Alice and Bob are close friends from their time at Stanford.",
    ]

    all_episodes = tech_episodes + academic_episodes + personal_episodes

    print(f"\n   Adding {len(all_episodes)} episodes...")
    for i, episode in enumerate(all_episodes, 1):
        ryumem.add_episode(
            content=episode,
            group_id="demo_advanced",
            user_id="demo_user",
            source="text",
        )
        print(f"   [{i:2d}/{len(all_episodes)}] Added: {episode[:60]}...")
        time.sleep(0.5)  # Small delay to space out API calls

    print(f"\n   ✓ Knowledge graph populated with {len(all_episodes)} episodes")

    # Demonstrate BM25 Keyword Search
    print_section("3. BM25 Keyword Search")

    print("\n   Using BM25 for exact keyword matching...")
    print("   Query: 'machine learning natural language processing'")

    bm25_results = ryumem.search(
        query="machine learning natural language processing",
        group_id="demo_advanced",
        strategy="bm25",  # Use pure BM25 search
        limit=5,
    )

    print(f"\n   Found {len(bm25_results.entities)} entities:")
    for entity in bm25_results.entities[:5]:
        score = bm25_results.scores.get(entity.uuid, 0.0)
        print(f"     - {entity.name} ({entity.entity_type})")
        print(f"       Summary: {entity.summary[:80]}...")
        print(f"       BM25 Score: {score:.3f}\n")

    # Demonstrate Semantic vs BM25 vs Hybrid
    print_section("4. Comparing Search Strategies")

    query = "Who works on AI?"
    print(f"\n   Query: '{query}'\n")

    strategies = ["semantic", "bm25", "hybrid"]

    for strategy in strategies:
        print(f"   Strategy: {strategy.upper()}")
        results = ryumem.search(
            query=query,
            group_id="demo_advanced",
            strategy=strategy,
            limit=3,
        )

        print(f"   Results: {len(results.entities)} entities, {len(results.edges)} relationships")
        if results.entities:
            top_entity = results.entities[0]
            score = results.scores.get(top_entity.uuid, 0.0)
            print(f"   Top result: {top_entity.name} (score: {score:.3f})\n")

    # Demonstrate Temporal Decay
    print_section("5. Temporal Decay Scoring")

    print("\n   Searching with temporal decay enabled...")
    print("   Recent facts will score higher than old facts\n")

    # Search with temporal decay enabled (default)
    results_with_decay = ryumem.search(
        query="Alice's job",
        group_id="demo_advanced",
        strategy="hybrid",
        limit=5,
    )

    print("   WITH temporal decay (recent facts boosted):")
    for edge in results_with_decay.edges[:3]:
        score = results_with_decay.scores.get(edge.uuid, 0.0)
        age_days = (datetime.now(timezone.utc) - edge.created_at).days
        print(f"     - {edge.fact}")
        print(f"       Age: {age_days} days | Score: {score:.3f}\n")

    # Search with temporal decay disabled
    from ryumem.core.models import SearchConfig

    config_no_decay = SearchConfig(
        query="Alice's job",
        group_id="demo_advanced",
        strategy="hybrid",
        limit=5,
        apply_temporal_decay=False,  # Disable temporal decay
    )

    results_no_decay = ryumem.search_engine.search(config_no_decay)

    print("   WITHOUT temporal decay (all facts equal):")
    for edge in results_no_decay.edges[:3]:
        score = results_no_decay.scores.get(edge.uuid, 0.0)
        age_days = (datetime.now(timezone.utc) - edge.created_at).days
        print(f"     - {edge.fact}")
        print(f"       Age: {age_days} days | Score: {score:.3f}\n")

    # Demonstrate Community Detection
    print_section("6. Community Detection")

    print("\n   Detecting communities in the knowledge graph...")
    print("   Using Louvain algorithm with LLM-generated summaries...\n")

    num_communities = ryumem.detect_communities(
        group_id="demo_advanced",
        resolution=1.0,  # Standard resolution
        min_community_size=2,  # At least 2 entities per community
    )

    print(f"   ✓ Detected {num_communities} communities\n")

    # Get communities
    communities = ryumem.db.get_all_communities("demo_advanced")

    for i, community in enumerate(communities, 1):
        print(f"   Community {i}: {community['name']}")
        print(f"   Summary: {community['summary']}")
        print(f"   Members: {len(community.get('members', []))} entities\n")

    # Search within communities
    print("\n   Searching with community-aware context...")
    results = ryumem.search(
        query="AI research",
        group_id="demo_advanced",
        strategy="hybrid",
        limit=5,
    )

    print(f"   Found {len(results.entities)} entities across communities")

    # Demonstrate Memory Pruning
    print_section("7. Memory Pruning & Compaction")

    print("\n   Running memory maintenance operations...\n")

    # Show current stats
    all_entities = ryumem.db.get_all_entities("demo_advanced")
    all_edges = ryumem.db.get_all_edges("demo_advanced")

    print(f"   Before pruning:")
    print(f"     - Entities: {len(all_entities)}")
    print(f"     - Relationships: {len(all_edges)}\n")

    # Run pruning
    pruning_stats = ryumem.prune_memories(
        group_id="demo_advanced",
        expired_cutoff_days=30,  # Remove facts expired > 30 days ago
        min_mentions=1,  # Keep entities with at least 1 mention
        compact_redundant=True,  # Merge similar relationships
    )

    print(f"   Pruning results:")
    print(f"     - Expired edges deleted: {pruning_stats['expired_edges_deleted']}")
    print(f"     - Low-value entities deleted: {pruning_stats['low_mention_entities_deleted']}")
    print(f"     - Redundant edges merged: {pruning_stats['redundant_edges_merged']}\n")

    # Show updated stats
    all_entities = ryumem.db.get_all_entities("demo_advanced")
    all_edges = ryumem.db.get_all_edges("demo_advanced")

    print(f"   After pruning:")
    print(f"     - Entities: {len(all_entities)}")
    print(f"     - Relationships: {len(all_edges)}")

    # Demonstrate Edge Invalidation (Temporal Logic)
    print_section("8. Temporal Edge Invalidation")

    print("\n   Checking for invalidated/contradicting facts...\n")

    # Search for Alice's job history
    alice_context = ryumem.get_entity_context(
        entity_name="alice",
        group_id="demo_advanced",
    )

    if alice_context and alice_context['relationships']:
        print("   Alice's employment history (showing temporal changes):\n")

        # Group by relation type
        work_relations = [
            rel for rel in alice_context['relationships']
            if 'work' in rel.get('relation_type', '').lower()
        ]

        for rel in work_relations:
            status = ""
            if rel.get('invalid_at'):
                status = " [INVALIDATED - superseded by newer information]"
            elif rel.get('expired_at'):
                status = " [EXPIRED]"

            print(f"     - {rel['fact']}{status}")
            print(f"       Valid from: {rel.get('valid_at', 'N/A')}")
            if rel.get('invalid_at'):
                print(f"       Invalidated: {rel['invalid_at']}")
            print()

    # Demonstrate Custom Temporal Decay Settings
    print_section("9. Custom Temporal Decay Settings")

    print("\n   Comparing different decay rates...\n")

    decay_factors = [0.99, 0.95, 0.90]  # 1%, 5%, 10% decay per day

    for decay in decay_factors:
        config = SearchConfig(
            query="Stanford research",
            group_id="demo_advanced",
            strategy="semantic",
            limit=3,
            apply_temporal_decay=True,
            temporal_decay_factor=decay,
        )

        results = ryumem.search_engine.search(config)

        print(f"   Decay factor {decay} ({int((1-decay)*100)}% per day):")
        if results.entities:
            top_score = results.scores.get(results.entities[0].uuid, 0.0)
            print(f"     Top result score: {top_score:.4f}")
            print(f"     Results count: {len(results.entities)}\n")

    # Performance Insights
    print_section("10. Performance Insights")

    print("\n   Knowledge graph statistics:\n")

    all_entities = ryumem.db.get_all_entities("demo_advanced")
    all_edges = ryumem.db.get_all_edges("demo_advanced")
    all_episodes = ryumem.db.get_all_episodes("demo_advanced")

    print(f"     - Total episodes: {len(all_episodes)}")
    print(f"     - Total entities: {len(all_entities)}")
    print(f"     - Total relationships: {len(all_edges)}")

    # Entity type distribution
    entity_types = {}
    for entity in all_entities:
        entity_type = entity.get('entity_type', 'unknown')
        entity_types[entity_type] = entity_types.get(entity_type, 0) + 1

    print(f"\n     Entity types:")
    for entity_type, count in sorted(entity_types.items(), key=lambda x: -x[1]):
        print(f"       - {entity_type}: {count}")

    # BM25 index stats
    print(f"\n     BM25 index:")
    bm25_stats = ryumem.search_engine.bm25_index.stats()
    print(f"       - Indexed entities: {bm25_stats['entity_count']}")
    print(f"       - Indexed edges: {bm25_stats['edge_count']}")

    # Cleanup
    print_section("11. Cleanup")

    print("\n   Cleaning up demo data...")
    ryumem.delete_group("demo_advanced")
    ryumem.close()
    print("   ✓ Demo completed and cleaned up")

    print("\n" + "=" * 70)
    print("  Advanced Features Demo Completed Successfully!")
    print("=" * 70)
    print("\n  Key Takeaways:")
    print("  - BM25 search provides exact keyword matching")
    print("  - Temporal decay prioritizes recent information")
    print("  - Community detection organizes large knowledge graphs")
    print("  - Memory pruning keeps the graph compact and efficient")
    print("  - Hybrid search combines the best of all strategies")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
