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
   - [src/ryumem/utils/llm.py](src/ryumem/utils/llm.py) - GPT-4 with function calling
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

# 2. Install in development mode
pip install -e .

# 3. Set up environment variables
echo "OPENAI_API_KEY=sk-your-key-here" > .env
```

## First Steps

### 1. Basic Usage

Create a file `test_ryumem.py`:

```python
from ryumem import Ryumem

# Initialize
ryumem = Ryumem(
    db_path="./data/test.db",
    openai_api_key="sk-...",  # Or load from .env
)

# Add an episode
episode_id = ryumem.add_episode(
    content="Alice works at Google in Mountain View.",
    group_id="test_user",
)

print(f"Created episode: {episode_id}")

# Search
results = ryumem.search(
    query="Where does Alice work?",
    group_id="test_user",
)

for entity in results.entities:
    print(f"Entity: {entity.name} ({entity.entity_type})")

# Clean up
ryumem.delete_group("test_user")
ryumem.close()
```

### 2. Run the Example

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
    group_id="user_123",
    user_id="user_123",
    source="text",  # or "message" or "json"
)

# Add multiple episodes
episodes = [
    {"content": "Alice works at Google"},
    {"content": "Bob works at Meta"},
]
ryumem.add_episodes_batch(episodes, group_id="user_123")
```

### Search Strategies

```python
# Semantic search (embedding similarity)
results = ryumem.search(
    query="AI researchers",
    group_id="user_123",
    strategy="semantic",
)

# Graph traversal (navigate relationships)
results = ryumem.search(
    query="Alice",
    group_id="user_123",
    strategy="traversal",
    max_depth=2,
)

# Hybrid (best of both - recommended)
results = ryumem.search(
    query="people working in technology",
    group_id="user_123",
    strategy="hybrid",  # Default
)
```

### Entity Context

```python
context = ryumem.get_entity_context(
    entity_name="Alice",
    group_id="user_123",
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
OPENAI_API_KEY=sk-...
RYUMEM_DB_PATH=./data/ryumem.db
RYUMEM_LLM_MODEL=gpt-4
RYUMEM_EMBEDDING_MODEL=text-embedding-3-large
RYUMEM_ENTITY_SIMILARITY_THRESHOLD=0.7
RYUMEM_RELATIONSHIP_SIMILARITY_THRESHOLD=0.8
```

### Via Code

```python
from ryumem import Ryumem, RyumemConfig

config = RyumemConfig(
    db_path="./data/memory.db",
    openai_api_key="sk-...",
    llm_model="gpt-4",
    entity_similarity_threshold=0.7,
    relationship_similarity_threshold=0.8,
    max_context_episodes=5,
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

### Future Enhancements

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for:
- Community detection
- Advanced reranking
- BM25 keyword search
- Performance optimization
- Testing framework

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
