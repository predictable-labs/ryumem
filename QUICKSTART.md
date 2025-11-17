# Ryumem - Quick Start Guide

## 🎉 Implementation Complete!

Ryumem is now fully implemented and ready to use! This guide will help you get started quickly.

## What's Been Built

### ✅ Core Components (All Implemented)

1. **Data Models** - [src/ryumem/core/models.py](src/ryumem/core/models.py)
   - EpisodeNode, EntityNode, CommunityNode
   - EntityEdge, EpisodicEdge, CommunityEdge
   - SearchConfig, SearchResult
   - Full Pydantic validation

2. **Database Layer** - [src/ryumem/core/graph_db.py](src/ryumem/core/graph_db.py)
   - Ryugraph integration (adapted from mem0's kuzu)
   - Bi-temporal schema (valid_at, invalid_at, expired_at)
   - Embedding-based similarity search
   - Multi-tenancy support

3. **LLM & Embedding Utilities**
   - [src/ryumem/utils/llm.py](src/ryumem/utils/llm.py) - OpenAI GPT-4 with function calling
   - [src/ryumem/utils/llm_ollama.py](src/ryumem/utils/llm_ollama.py) - Ollama local models adapter
   - [src/ryumem/utils/embeddings.py](src/ryumem/utils/embeddings.py) - text-embedding-3-large

4. **Extraction Pipeline**
   - [src/ryumem/ingestion/entity_extractor.py](src/ryumem/ingestion/entity_extractor.py) - Entity extraction & resolution
   - [src/ryumem/ingestion/relation_extractor.py](src/ryumem/ingestion/relation_extractor.py) - Relationship extraction & contradiction detection
   - [src/ryumem/ingestion/episode.py](src/ryumem/ingestion/episode.py) - Full ingestion orchestration

5. **Search & Retrieval** - [src/ryumem/retrieval/search.py](src/ryumem/retrieval/search.py)
   - Semantic search
   - Graph traversal search
   - Hybrid search with RRF fusion

6. **Main API** - [src/ryumem/main.py](src/ryumem/main.py)
   - Clean, intuitive API
   - Context manager support
   - Flexible configuration

## Installation

```bash
# 1. Navigate to the ryumem directory
cd /Users/saksham115/Projects/Predictable/ryumem

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install ryumem in development mode
pip install -e .

# 4. Set up environment variables
cp .env.example .env
# Then edit .env and add your OPENAI_API_KEY
```

**Alternative (without installation):**
```bash
# Run examples directly with PYTHONPATH
PYTHONPATH=src python examples/basic_usage.py
```

## First Steps

### 1. Basic Usage (OpenAI)

Create a file `test_ryumem.py`:

```python
from ryumem import Ryumem

# Initialize with OpenAI
ryumem = Ryumem(
    db_path="./data/test.db",
    openai_api_key="sk-...",  # Or load from .env
)

# Add an episode
episode_id = ryumem.add_episode(
    content="Alice works at Google in Mountain View.",
    user_id="test_user",
)

print(f"Created episode: {episode_id}")

# Search
results = ryumem.search(
    query="Where does Alice work?",
    user_id="test_user",
)

for entity in results.entities:
    print(f"Entity: {entity.name} ({entity.entity_type})")

# Clean up
ryumem.delete_group("test_user")
ryumem.close()
```

### 2. Basic Usage (Ollama - Local LLMs)

For local inference without API costs:

```python
from ryumem import Ryumem

# Prerequisites:
# 1. Install Ollama: https://ollama.ai
# 2. Start Ollama: ollama serve
# 3. Pull a model: ollama pull llama3.2:3b

# Initialize with Ollama
ryumem = Ryumem(
    db_path="./data/test.db",
    llm_provider="ollama",
    llm_model="llama3.2:3b",  # or mistral:7b, qwen2.5:7b
    ollama_base_url="http://localhost:11434",
    openai_api_key="sk-...",  # Still needed for embeddings
)

# Use the exact same API!
episode_id = ryumem.add_episode(
    content="Alice works at Google in Mountain View.",
    user_id="test_user",
)

results = ryumem.search(
    query="Where does Alice work?",
    user_id="test_user",
)

for entity in results.entities:
    print(f"Entity: {entity.name} ({entity.entity_type})")

ryumem.delete_group("test_user")
ryumem.close()
```

**Recommended models:**
- `llama3.2:3b` - Fast, good quality (best for development)
- `mistral:7b` - Excellent reasoning
- `qwen2.5:7b` - Great for structured JSON output

See [examples/ollama_usage.py](examples/ollama_usage.py) for a complete example.

### 3. Run the Examples

```bash
python examples/basic_usage.py
```

This will demonstrate:
- Adding multiple episodes
- Entity and relationship extraction
- Searching with different strategies
- Getting entity context

## Key Features Demonstrated

### Episode Ingestion

```python
# Add a single episode
ryumem.add_episode(
    content="Bob graduated from Stanford in 2018.",
    user_id="user_123",
    user_id="user_123",
    source="text",  # or "message" or "json"
)

# Add multiple episodes
episodes = [
    {"content": "Alice works at Google"},
    {"content": "Bob works at Meta"},
]
ryumem.add_episodes_batch(episodes, user_id="user_123")
```

### Search Strategies

```python
# Semantic search (embedding similarity)
results = ryumem.search(
    query="AI researchers",
    user_id="user_123",
    strategy="semantic",
)

# Graph traversal (navigate relationships)
results = ryumem.search(
    query="Alice",
    user_id="user_123",
    strategy="traversal",
    max_depth=2,
)

# Hybrid (best of both - recommended)
results = ryumem.search(
    query="people working in technology",
    user_id="user_123",
    strategy="hybrid",  # Default
)
```

### Entity Context

```python
context = ryumem.get_entity_context(
    entity_name="Alice",
    user_id="user_123",
)

print(f"Name: {context['entity']['name']}")
print(f"Type: {context['entity']['entity_type']}")
print(f"Relationships: {context['relationship_count']}")

for rel in context['relationships']:
    print(f"  - {rel['relation_type']}: {rel['other_name']}")
```

## How It Works

### Ingestion Pipeline

```
Episode → Entity Extraction → Entity Resolution → Relationship Extraction
    → Contradiction Detection → Graph Update → Summary Update
```

1. **Episode Created** - Raw content stored with metadata
2. **Entity Extraction** - LLM identifies entities (people, places, concepts)
3. **Entity Resolution** - Deduplicate using embedding similarity
4. **Relationship Extraction** - LLM identifies connections between entities
5. **Contradiction Detection** - Identify outdated facts
6. **Graph Update** - Store in bi-temporal graph
7. **Summary Update** - Update entity summaries with new context

### Search Pipeline

```
Query → Embedding → Semantic Search → Graph Traversal → RRF Fusion → Results
```

1. **Query Embedding** - Convert query to vector
2. **Semantic Search** - Find similar entities/facts by embedding
3. **Graph Traversal** - Navigate relationships from matched entities
4. **RRF Fusion** - Combine results using Reciprocal Rank Fusion
5. **Return Results** - Ranked entities and relationships

## Configuration Options

### Via Environment Variables

```bash
# OpenAI (default provider)
OPENAI_API_KEY=sk-...
RYUMEM_DB_PATH=./data/memory.db
RYUMEM_LLM_PROVIDER=openai
RYUMEM_LLM_MODEL=gpt-4
RYUMEM_EMBEDDING_MODEL=text-embedding-3-large

# Or use Ollama for local LLMs
OPENAI_API_KEY=sk-...  # Still needed for embeddings
RYUMEM_LLM_PROVIDER=ollama
RYUMEM_LLM_MODEL=llama3.2:3b
RYUMEM_OLLAMA_BASE_URL=http://localhost:11434

# Other settings
RYUMEM_ENTITY_SIMILARITY_THRESHOLD=0.7
RYUMEM_RELATIONSHIP_SIMILARITY_THRESHOLD=0.8
```

### Via Code

```python
from ryumem import Ryumem, RyumemConfig

# OpenAI configuration
config = RyumemConfig(
    db_path="./data/memory.db",
    openai_api_key="sk-...",
    llm_provider="openai",
    llm_model="gpt-4",
    entity_similarity_threshold=0.7,
    relationship_similarity_threshold=0.8,
    max_context_episodes=5,
)
ryumem = Ryumem(config=config)

# Or Ollama configuration
config = RyumemConfig(
    db_path="./data/memory.db",
    llm_provider="ollama",
    llm_model="llama3.2:3b",
    ollama_base_url="http://localhost:11434",
    openai_api_key="sk-...",  # Still needed for embeddings
)
ryumem = Ryumem(config=config)
```

## Next Steps

### Testing Your Implementation

1. **Run the basic example**:
   ```bash
   python examples/basic_usage.py
   ```

2. **Test with your own data**:
   - Create a new Python file
   - Add episodes with your domain-specific content
   - Query and verify results

3. **Experiment with strategies**:
   - Try different search strategies
   - Adjust similarity thresholds
   - Test multi-tenancy features

### Advanced Features

**All advanced features are now fully implemented!** See sections below for:
- BM25 keyword search
- Temporal decay scoring
- Community detection
- Memory pruning and compaction

## Advanced Features Guide

### BM25 Keyword Search

BM25 provides traditional keyword/lexical matching as a complement to semantic search.

```python
# Pure BM25 search (exact keyword matching)
results = ryumem.search(
    query="machine learning natural language processing",
    user_id="user_123",
    strategy="bm25",
    limit=10,
)

# BM25 is also included in hybrid search automatically
results = ryumem.search(
    query="machine learning",
    user_id="user_123",
    strategy="hybrid",  # Combines semantic + BM25 + graph traversal
)
```

**When to use BM25:**
- Searching for specific technical terms
- Exact phrase matching
- Acronyms and abbreviations
- Names and proper nouns

### Temporal Decay Scoring

Recent facts automatically score higher than old facts with configurable decay rates.

```python
# Temporal decay is enabled by default
results = ryumem.search(
    query="Alice's job",
    user_id="user_123",
    strategy="hybrid",
)
# Recent facts will rank higher automatically

# Customize decay settings
from ryumem.core.models import SearchConfig

config = SearchConfig(
    query="current projects",
    user_id="user_123",
    apply_temporal_decay=True,
    temporal_decay_factor=0.99,  # 1% decay per day (slower)
    # Or use 0.95 for 5% decay per day (faster)
)

results = ryumem.search_engine.search(config)
```

**Decay factor guidelines:**
- `0.99` = 1% per day (gentle, prefer recent with minimal bias)
- `0.95` = 5% per day (moderate, clear recency preference) - **default**
- `0.90` = 10% per day (aggressive, heavily favor recent info)

### Community Detection

Automatically cluster related entities into communities for better organization and retrieval.

```python
# Detect communities in your knowledge graph
num_communities = ryumem.detect_communities(
    user_id="user_123",
    resolution=1.0,  # Higher = more granular communities
    min_community_size=2,  # Minimum entities per community
)

print(f"Detected {num_communities} communities")

# Get all communities
communities = ryumem.db.get_all_communities("user_123")

for community in communities:
    print(f"Community: {community['name']}")
    print(f"Summary: {community['summary']}")  # LLM-generated!
    print(f"Members: {len(community['members'])} entities")

# Update communities as graph grows
ryumem.update_communities("user_123", resolution=1.0)
```

**Community benefits:**
- Organizes large knowledge graphs
- LLM-generated summaries for each cluster
- Faster retrieval by searching within relevant communities
- Better context understanding

### Memory Pruning & Compaction

Keep your knowledge graph clean and efficient by removing obsolete data.

```python
# Run comprehensive pruning
stats = ryumem.prune_memories(
    user_id="user_123",
    expired_cutoff_days=90,  # Remove facts expired >90 days ago
    min_mentions=2,  # Keep entities with at least 2 mentions
    compact_redundant=True,  # Merge near-duplicate relationships
)

print(f"Pruning results:")
print(f"  Expired edges deleted: {stats['expired_edges_deleted']}")
print(f"  Low-value entities deleted: {stats['low_mention_entities_deleted']}")
print(f"  Redundant edges merged: {stats['redundant_edges_merged']}")
```

**What gets pruned:**
- **Expired edges**: Facts invalidated long ago (contradicted/superseded)
- **Low-mention entities**: Likely extraction errors or noise
- **Redundant relationships**: Near-duplicate facts get merged

**Best practices:**
- Run pruning periodically (e.g., weekly/monthly)
- Adjust `min_mentions` based on your data quality
- Use longer `expired_cutoff_days` if historical context matters

## Complete Example Workflows

### Workflow 1: Knowledge Accumulation with Temporal Awareness

```python
# Build knowledge over time
episodes = [
    "Alice works at Google as a software engineer.",
    "Alice is working on TensorFlow project.",
    "Alice moved to OpenAI to work on GPT models.",  # This invalidates first fact!
]

for episode in episodes:
    ryumem.add_episode(episode, user_id="user_123")
    time.sleep(1)  # Space out over time

# Search with temporal decay
results = ryumem.search(
    query="Alice's current job",
    user_id="user_123",
    strategy="hybrid",
)

# Recent facts (OpenAI) will rank higher than old ones (Google)
for edge in results.edges:
    print(f"{edge.fact} - Score: {results.scores.get(edge.uuid, 0):.3f}")
```

### Workflow 2: Large Graph with Community Organization

```python
# Build a large knowledge graph
for i in range(100):
    ryumem.add_episode(your_episodes[i], user_id="user_123")

# Organize into communities
num_communities = ryumem.detect_communities("user_123")

# Search is now community-aware for better context
results = ryumem.search(
    query="AI research topics",
    user_id="user_123",
    strategy="hybrid",
)

# Periodic maintenance
stats = ryumem.prune_memories("user_123")
```

### Workflow 3: Multi-Strategy Comparison

```python
query = "machine learning research"

# Try each strategy
for strategy in ["semantic", "bm25", "hybrid"]:
    results = ryumem.search(
        query=query,
        user_id="user_123",
        strategy=strategy,
        limit=5,
    )

    print(f"\n{strategy.upper()} strategy:")
    print(f"  Found: {len(results.entities)} entities")
    if results.entities:
        top = results.entities[0]
        score = results.scores.get(top.uuid, 0)
        print(f"  Top: {top.name} (score: {score:.3f})")
```

## Running the Examples

### Basic Example (OpenAI)

```bash
python examples/basic_usage.py
```

Demonstrates core functionality: ingestion, search, entity context.

### Ollama Example (Local LLMs)

```bash
# Make sure Ollama is running first
ollama serve  # In a separate terminal

# Pull a model if you haven't
ollama pull llama3.2:3b

# Run the example
python examples/ollama_usage.py
```

Demonstrates using local Ollama models for cost-free, private inference.

### Advanced Example

```bash
python examples/advanced_usage.py
```

Demonstrates all advanced features:
- BM25 keyword search
- Temporal decay with different settings
- Community detection with LLM summaries
- Memory pruning and compaction
- Strategy comparison
- Edge invalidation (temporal logic)

## Troubleshooting

### Common Issues

**"ryugraph not installed"**
```bash
pip install ryugraph
```

**"OpenAI API key not found"**
- Check your .env file
- Or pass `openai_api_key` parameter

**Slow performance**
- Reduce `max_context_episodes`
- Use batch ingestion
- Check OpenAI API quota

**Database errors**
- Ensure database directory exists
- Check file permissions
- Try deleting and recreating: `ryumem.reset()`

## Architecture Highlights

### What Makes Ryumem Special

1. **Bi-Temporal Model** - Track both real-world time and system time
2. **Automatic Contradiction Handling** - Old facts are invalidated, not deleted
3. **Hybrid Retrieval** - Combines semantic search with graph navigation
4. **Incremental Updates** - No batch reprocessing needed
5. **Full Multi-Tenancy** - Isolated namespaces at multiple levels

### Code Reuse

Ryumem intelligently combines:
- **mem0's kuzu integration** → Adapted for ryugraph
- **graphiti's temporal model** → Bi-temporal edges
- **graphiti's extraction prompts** → Entity/relationship extraction
- **Zep paper's architecture** → Overall system design

## File Structure

```
ryumem/
├── src/ryumem/
│   ├── __init__.py           # Public API exports
│   ├── main.py               # Main Ryumem class
│   ├── core/
│   │   ├── models.py         # Data models
│   │   ├── graph_db.py       # Ryugraph layer
│   │   └── config.py         # Configuration
│   ├── ingestion/
│   │   ├── episode.py        # Ingestion pipeline
│   │   ├── entity_extractor.py
│   │   └── relation_extractor.py
│   ├── retrieval/
│   │   └── search.py         # Search engine
│   └── utils/
│       ├── llm.py            # LLM client
│       └── embeddings.py     # Embedding client
├── examples/
│   └── basic_usage.py        # Complete example
├── README.md                 # Main documentation
├── IMPLEMENTATION_PLAN.md    # Detailed plan
├── QUICKSTART.md            # This file
└── pyproject.toml           # Dependencies
```

## Support

- **Documentation**: See [README.md](README.md)
- **Implementation Details**: See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
- **Examples**: See [examples/](examples/)

---

**Ready to build with Ryumem! 🚀**

Start with `examples/basic_usage.py` and adapt it to your use case.
