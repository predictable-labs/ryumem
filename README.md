# Ryumem

**Bi-temporal Knowledge Graph Memory System**

Ryumem is a memory system inspired by the Zep paper, combining the best of mem0 and graphiti, using ryugraph as the graph database layer.

## Features

✨ **Key Capabilities**:
- 📝 **Episode-first ingestion** - Every piece of information starts as an episode
- 🧠 **Automatic entity & relationship extraction** - Powered by GPT-4
- ⏰ **Bi-temporal data model** - Track when facts were valid and when they were recorded
- 🔍 **Advanced hybrid retrieval** - Combines semantic search, BM25 keyword search, and graph traversal
- ⏱️ **Temporal decay scoring** - Recent facts automatically score higher with configurable decay
- 🌐 **Community detection** - Automatic clustering of related entities using Louvain algorithm
- 🧹 **Memory pruning & compaction** - Keep graphs efficient by removing obsolete data
- 👥 **Full multi-tenancy** - Support for user_id, agent_id, session_id, group_id
- ♻️ **Automatic contradiction handling** - Detects and invalidates outdated facts
- 📊 **Incremental updates** - No batch reprocessing required

## Architecture

Ryumem implements the Combined Conceptual Architecture from the Zep paper:

```
┌─────────────┐
│   Episode   │  - Raw data ingestion
└──────┬──────┘
       │
       ▼
┌─────────────────────────┐
│  Entity Extraction      │  - LLM-powered extraction
│  & Resolution           │  - Embedding-based deduplication
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│  Relationship           │  - Extract connections
│  Extraction             │  - Detect contradictions
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│  Bi-Temporal Graph      │  - Ryugraph database
│  (valid_at/invalid_at)  │  - Temporal queries
│                         │  - Community clustering
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│  Hybrid Retrieval       │  - Semantic + BM25 + Traversal
│  (RRF Fusion)           │  - Temporal decay scoring
│                         │  - Sub-second latency
└─────────────────────────┘
       │
       ▼
┌─────────────────────────┐
│  Memory Maintenance     │  - Prune expired facts
│  (Optional)             │  - Compact redundancies
└─────────────────────────┘
```

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd ryumem

# Install dependencies
pip install -e .

# Or install in development mode
pip install -e ".[dev]"
```

## Quick Start

### Using OpenAI (Default)

```python
from ryumem import Ryumem

# Initialize with your OpenAI API key
ryumem = Ryumem(
    db_path="./data/memory.db",
    openai_api_key="sk-...",
)

# Add episodes
ryumem.add_episode(
    content="Alice works at Google in Mountain View as a Software Engineer.",
    group_id="user_123",
)

ryumem.add_episode(
    content="Bob is Alice's colleague and recently moved to Meta.",
    group_id="user_123",
)
```

### Using Ollama (Local LLMs)

For cost savings, privacy, and offline usage, you can use local models via Ollama:

```python
from ryumem import Ryumem

# Prerequisites:
# 1. Install Ollama: https://ollama.ai
# 2. Start Ollama: ollama serve
# 3. Pull a model: ollama pull qwen2.5:7b

# Initialize with Ollama for local LLM inference
ryumem = Ryumem(
    db_path="./data/memory.db",
    llm_provider="ollama",  # Use local Ollama instead of OpenAI
    llm_model="qwen2.5:7b",  # Local model (fast, good quality)
    ollama_base_url="http://100.108.18.43:11434",  # Default Ollama URL
    openai_api_key="sk-...",  # Still required for embeddings
)

# Use exactly the same API - Ollama is a drop-in replacement!
ryumem.add_episode(
    content="Alice works at Google in Mountain View.",
    group_id="user_123",
)
```

**Recommended Ollama models:**
- `qwen2.5:7b` - Fast inference, good quality (recommended for development)
- `mistral:7b` - Excellent reasoning capabilities
- `qwen2.5:7b` - Great for structured output and JSON
- `llama3.1:8b` - Balanced performance and quality

**Note:** Embeddings still require OpenAI API key. Local embedding support coming soon!

See [examples/ollama_usage.py](examples/ollama_usage.py) for a complete example.

### Using LiteLLM (100+ LLM Providers)

For maximum flexibility, use LiteLLM to access 100+ LLM providers through a unified interface. LiteLLM automatically detects the provider from the model name and uses the appropriate API key.

```python
from ryumem import Ryumem
from ryumem.core.config import RyumemConfig

# Example 1: Anthropic Claude
# LiteLLM auto-detects Anthropic from model name
# Uses ANTHROPIC_API_KEY from environment
config = RyumemConfig()
config.llm.provider = "litellm"
config.llm.model = "claude-3-5-sonnet-20241022"
# Embeddings auto-fallback to OpenAI or Gemini (if API keys available)

ryumem = Ryumem(config=config)

# Example 2: OpenAI via LiteLLM
config.llm.model = "gpt-4o-mini"
# Embeddings auto-select to "text-embedding-3-large"

# Example 3: Google Gemini via LiteLLM
config.llm.model = "gemini/gemini-2.0-flash-exp"
# Embeddings auto-select to "text-embedding-004"

# Example 4: AWS Bedrock
config.llm.model = "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0"
# Requires AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION_NAME

# Example 5: Mixed providers (manual override)
config.llm.provider = "litellm"
config.llm.model = "claude-3-5-sonnet-20241022"
config.embedding.provider = "openai"  # Explicit override
config.embedding.model = "text-embedding-3-large"
config.embedding.dimensions = 3072
```

**Supported LiteLLM Providers:**
- **OpenAI** - `gpt-4o`, `gpt-4o-mini`, etc. (requires `OPENAI_API_KEY`)
- **Anthropic** - `claude-3-5-sonnet-20241022`, etc. (requires `ANTHROPIC_API_KEY`)
- **Google Gemini** - `gemini/gemini-2.0-flash-exp`, etc. (requires `GOOGLE_API_KEY`)
- **AWS Bedrock** - `bedrock/anthropic.claude-*`, etc. (requires AWS credentials)
- **Cohere** - `command-r-plus`, etc. (requires `COHERE_API_KEY`)
- **Azure OpenAI** - Requires `AZURE_API_KEY`, `AZURE_API_BASE`, `AZURE_API_VERSION`
- **100+ more** - See [LiteLLM docs](https://docs.litellm.ai/docs/providers)

**Automatic Embedding Selection:**

Ryumem automatically selects the appropriate embedding model based on your LLM choice:
- OpenAI models → `text-embedding-3-large`
- Gemini models → `text-embedding-004`
- Anthropic/Claude → Falls back to OpenAI or Gemini embeddings (whichever API key is available)
- Cohere models → `embed-english-v3.0`

You can always override the automatic selection by explicitly setting the embedding provider and model in the config.

**Environment Variables:**

```bash
# Set the LLM provider
export RYUMEM_LLM_PROVIDER=litellm
export RYUMEM_LLM_MODEL=claude-3-5-sonnet-20241022

# API keys (LiteLLM auto-detects based on model name)
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...          # For embeddings fallback
export GOOGLE_API_KEY=...             # Or use Gemini for embeddings

# Optional: Explicit embedding configuration
export RYUMEM_EMBEDDING_PROVIDER=openai
export RYUMEM_EMBEDDING_MODEL=text-embedding-3-large
```

See [examples/litellm_usage.py](examples/litellm_usage.py) for complete examples with multiple providers.

### Continuing with the API

```python
# Search using hybrid strategy (semantic + BM25 + graph traversal)
results = ryumem.search(
    query="Where does Alice work?",
    group_id="user_123",
    strategy="hybrid",  # Combines all search methods
    limit=10,
)

# Display results
for entity in results.entities:
    score = results.scores.get(entity.uuid, 0.0)
    print(f"{entity.name} ({entity.entity_type}) - {score:.3f}")

for edge in results.edges:
    print(f"{edge.fact}")

# Get comprehensive context for an entity
context = ryumem.get_entity_context(
    entity_name="Alice",
    group_id="user_123",
)

print(f"Entity: {context['entity']['name']}")
print(f"Relationships: {context['relationship_count']}")

# Advanced features
# Detect communities for better organization
num_communities = ryumem.update_communities("user_123")

# Prune old/redundant data
stats = ryumem.prune_memories("user_123")
```

## What's New

Ryumem now implements the **complete** Combined Conceptual Architecture from the Zep paper!

### 🆕 Latest Features

**BM25 Keyword Search**
- Traditional lexical matching complements vector search
- Better for exact keyword queries
- Integrated into hybrid search via RRF fusion

**Temporal Decay Scoring**
- Recent facts automatically score higher
- Exponential decay: `score × 0.95^days_old`
- 20% boost for facts modified in last 7 days
- Fully configurable decay rates and thresholds

**Community Detection**
- Louvain algorithm clusters related entities
- LLM-generated summaries for each community
- Configurable resolution and minimum size
- Enables higher-level reasoning and retrieval

**Memory Pruning & Compaction**
- Remove facts expired > N days ago
- Delete low-value entities (< 2 mentions, > 30 days old)
- Merge near-duplicate facts (95%+ similarity)
- Keep graphs efficient and token-optimized

## Configuration

### Environment Variables

Ryumem uses environment variables for configuration. You can set these in your shell or use a `.env` file in your working directory.

**For Examples:**
Check `examples/.env.example` for a template when running scripts in the `examples/` directory.

**For Server:**
Check `server/.env.example` for a template when running the API server.

**Common Variables:**

```bash
# OpenAI API Key (required for embeddings, and for LLM if using OpenAI)
OPENAI_API_KEY=sk-...

# LLM Provider (optional, default: openai)
RYUMEM_LLM_PROVIDER=openai  # or "ollama", "gemini", "litellm"

# Ollama settings (when using llm_provider="ollama")
RYUMEM_LLM_OLLAMA_BASE_URL=http://100.108.18.43:11434
RYUMEM_LLM_MODEL=qwen2.5:7b

# OpenAI settings (when using llm_provider="openai")
RYUMEM_LLM_MODEL=gpt-4o

# Database Path
RYUMEM_DB_PATH=./data/memory.db
```

### Programmatic Configuration

```python
from ryumem import Ryumem, RyumemConfig

# Option 1: Direct parameters (OpenAI)
ryumem = Ryumem(
    db_path="./data/memory.db",
    openai_api_key="sk-...",
    llm_model="gpt-4",
    embedding_model="text-embedding-3-large",
    entity_similarity_threshold=0.7,
)

# Option 2: Direct parameters (Ollama)
ryumem = Ryumem(
    db_path="./data/memory.db",
    llm_provider="ollama",
    llm_model="qwen2.5:7b",
    ollama_base_url="http://100.108.18.43:11434",
    openai_api_key="sk-...",  # Still needed for embeddings
)

# Option 3: Config object
config = RyumemConfig(
    db_path="./data/memory.db",
    llm_provider="ollama",
    llm_model="qwen2.5:7b",
    openai_api_key="sk-...",
)
ryumem = Ryumem(config=config)

# Option 4: From environment
ryumem = Ryumem()  # Automatically loads from .env
```

## Core Concepts

### Episodes

Episodes are the fundamental unit of ingestion. Every piece of information starts as an episode.

```python
# Text episode
ryumem.add_episode(
    content="Alice graduated from Stanford in 2018.",
    group_id="user_123",
    source="text",
)

# Message episode (conversational)
ryumem.add_episode(
    content="user: Where did you go to school?\nassistant: I went to MIT.",
    group_id="user_123",
    source="message",
)

# JSON episode (structured data)
ryumem.add_episode(
    content='{"person": "Bob", "company": "Meta", "role": "Engineer"}',
    group_id="user_123",
    source="json",
)
```

### Multi-Tenancy

Ryumem supports multiple levels of isolation:

```python
ryumem.add_episode(
    content="...",
    group_id="organization_1",      # Organization level
    user_id="user_123",             # User level
    agent_id="agent_assistant",     # Agent level
    session_id="session_xyz",       # Session level
)

# Search within specific scope
results = ryumem.search(
    query="...",
    group_id="organization_1",
    user_id="user_123",             # Optional: filter by user
)
```

### Bi-Temporal Data Model

Ryumem tracks two timelines for each fact:

1. **valid_at**: When the fact was true in the real world
2. **invalid_at**: When the fact stopped being true
3. **expired_at**: When the fact was superseded/invalidated in the system

### Search Strategies

Ryumem supports four search strategies:

1. **Semantic Search**: Embedding similarity using text-embedding-3-large
2. **BM25 Keyword Search**: Traditional keyword/lexical matching
3. **Graph Traversal**: Navigate relationships with BFS
4. **Hybrid**: Combines all three using RRF fusion (recommended)

All strategies benefit from:
- **Temporal Decay**: Recent facts score higher (configurable)
- **Update-Awareness Boost**: 20% boost for facts modified in last 7 days

```python
# Try different strategies
results = ryumem.search("AI researchers", group_id="user_123", strategy="semantic")
results = ryumem.search("machine learning", group_id="user_123", strategy="bm25")
results = ryumem.search("tech companies", group_id="user_123", strategy="hybrid")

# Customize temporal decay
results = ryumem.search(
    query="recent news",
    group_id="user_123",
    strategy="hybrid",
    # Override temporal decay settings
)
```

### Community Detection

Automatically cluster related entities into communities using the Louvain algorithm:

```python
# Detect communities periodically
num_communities = ryumem.update_communities("user_123")
print(f"Created {num_communities} communities")

# Fine-tune clustering
num_communities = ryumem.update_communities(
    "user_123",
    resolution=1.5,  # Higher = more fine-grained communities
    min_community_size=3,  # Minimum entities per community
)
```

Each community gets an LLM-generated summary describing the common theme and relationships.

### Memory Pruning

Keep your knowledge graph efficient and compact:

```python
# Prune old/redundant data periodically
stats = ryumem.prune_memories("user_123")
print(f"Pruning results: {stats}")
# Output: {'expired_edges_deleted': 15, 'entities_deleted': 3, 'edges_merged': 8}

# Customize pruning aggressiveness
stats = ryumem.prune_memories(
    "user_123",
    expired_cutoff_days=60,  # Delete facts expired > 60 days ago
    min_mentions=3,  # Keep only entities with 3+ mentions
    compact_redundant=True,  # Merge near-duplicate facts
)
```

## Integrations

### 🚀 Google ADK Integration (Zero Boilerplate!)

Ryumem provides **one-line memory integration** for Google's Agent Developer Kit:

```python
from google import genai
from ryumem.integrations import add_memory_to_agent

# Create your agent
agent = genai.Agent(
    name="assistant",
    model="gemini-2.0-flash-exp",
    instruction="You are a helpful assistant with memory."
)

# Enable memory - that's it! 🎉
add_memory_to_agent(
    agent,
    ryumem_customer_id="my_company",
    user_id="user_123",
    extract_entities=False  # Disable entity extraction to reduce token usage (default: False)
)

# Agent now has 3 auto-generated memory tools:
# - search_memory() - Find relevant information
# - save_memory() - Store new information
# - get_entity_context() - Get full context about entities
```

**Entity Extraction Control:**
- `extract_entities=False` (default): Episodes are stored but entities/relationships are NOT extracted (saves 30-50% tokens)
- `extract_entities=True`: Full knowledge graph extraction (entities, relationships, contradictions)
- `extract_entities=None`: Uses config setting from `enable_entity_extraction` in RyumemConfig

You can also control entity extraction per memory save:
```python
# Override at tool call level
memory.save_memory(
    content="Important fact to extract entities from",
    extract_entities=True  # Enable for this specific save
)
```

**Why Ryumem > mem0?**

| Feature          | mem0       | Ryumem                  |
| ---------------- | ---------- | ----------------------- |
| Setup Code       | ~20 lines  | **1 line**              |
| Custom Functions | Must write | **Auto-generated**      |
| Memory Type      | Flat       | **Knowledge Graph**     |
| Local LLMs       | Limited    | **Full Ollama Support** |

See [docs/GOOGLE_ADK_INTEGRATION.md](docs/GOOGLE_ADK_INTEGRATION.md) for the complete guide.

### Coming Soon

- 🔜 **LangChain** integration
- 🔜 **LlamaIndex** integration
- 🔜 **Vercel AI SDK** integration (TypeScript)

## Examples

See the [examples/](examples/) directory for more examples:
- [basic_usage.py](examples/basic_usage.py) - Complete walkthrough of core features
- [ollama_usage.py](examples/ollama_usage.py) - Using local Ollama models instead of OpenAI
- [google_adk_usage.py](examples/google_adk_usage.py) - Zero-boilerplate Google ADK integration

## Documentation

For full documentation, see [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## License

MIT License

## Performance & Maintenance

### Best Practices

1. **Periodic Community Detection**: Run after adding significant data
   ```python
   ryumem.update_communities("user_123")
   ```

2. **Regular Pruning**: Keep graphs efficient
   ```python
   # Weekly maintenance
   ryumem.prune_memories("user_123", expired_cutoff_days=90)
   ```

3. **Search Strategy Selection**:
   - Use `"hybrid"` for best overall results (default)
   - Use `"bm25"` for exact keyword matching
   - Use `"semantic"` for conceptual similarity
   - Use `"traversal"` for relationship-focused queries

### Architecture Status

✅ **100% Complete Implementation** of the Combined Conceptual Architecture from the Zep paper:

1. ✅ Ingestion & Extraction (Episodes, Entities, Relationships)
2. ✅ Entity & Fact Resolution (Deduplication, Contradiction Detection)
3. ✅ Memory Storage Layer (Bi-temporal Graph with Ryugraph)
4. ✅ Summarization & Compaction (Communities, Pruning)
5. ✅ Retrieval & Query (Semantic + BM25 + Traversal + Temporal Decay)
6. ✅ Agent Integration (Clean Python API)

## Acknowledgments

- **Zep Paper**: For the Combined Conceptual Architecture design
- **mem0**: For kuzu integration patterns and database operations
- **graphiti**: For bi-temporal model and LLM extraction prompts
- **ryugraph/kuzu**: For the high-performance graph database backend
