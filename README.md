# Ryumem

**Bi-temporal Knowledge Graph Memory System**

Ryumem is a production-ready memory system for building intelligent agents with persistent, queryable memory using a bi-temporal knowledge graph architecture.

## Features

✨ **Key Capabilities**:
- 📝 **Episode-first ingestion** - Every piece of information starts as an episode
- 🧠 **Automatic entity & relationship extraction** - Powered by LLM (OpenAI, Gemini, Ollama, or LiteLLM)
- ⏰ **Bi-temporal data model** - Track when facts were valid and when they were recorded
- 🔍 **Advanced hybrid retrieval** - Combines semantic search, BM25 keyword search, and graph traversal
- ⏱️ **Temporal decay scoring** - Recent facts automatically score higher with configurable decay
- 🌐 **Community detection** - Automatic clustering of related entities using Louvain algorithm
- 🧹 **Memory pruning & compaction** - Keep graphs efficient by removing obsolete data
- 👥 **Full multi-tenancy** - Support for user_id, agent_id, session_id, group_id
- ♻️ **Automatic contradiction handling** - Detects and invalidates outdated facts
- 📊 **Incremental updates** - No batch reprocessing required
- 🔧 **Automatic tool tracking** - Track all tool executions and query patterns
- 🔄 **Query augmentation** - Enrich queries with historical context from similar past queries
- ⚙️ **Dynamic configuration** - Hot-reload settings without server restart
- 🎨 **Beautiful web dashboard** - Modern Next.js UI with graph visualization

## Quick Start

### Getting Access

To use Ryumem, request API access from **contact@predictable.sh**. You'll receive:
- API endpoint URL
- API key (starts with `ryu_`)

### Installation

```bash
pip install ryumem
```

### Basic Usage with Google ADK

```python
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from ryumem import Ryumem
from ryumem.integrations import add_memory_to_agent, wrap_runner_with_tracking

# Initialize Ryumem - auto-loads from environment variables
# RYUMEM_API_URL and RYUMEM_API_KEY
ryumem = Ryumem(
    augment_queries=True,      # Enable query augmentation
    similarity_threshold=0.3,  # Match queries with 30%+ similarity
    top_k_similar=5,           # Use top 5 similar queries for context
)

# Create your agent with tools
agent = Agent(
    model="gemini-2.0-flash-exp",
    name="my_agent",
    instruction="You are a helpful assistant with memory.",
    tools=[...]  # Your tools here
)

# Add memory to agent - automatically creates search_memory() and save_memory() tools
agent = add_memory_to_agent(agent, ryumem)

# Wrap runner for automatic tool tracking and query augmentation
runner = wrap_runner_with_tracking(runner, agent)
```

### Environment Setup

```bash
# Required - Get from contact@predictable.sh
export RYUMEM_API_URL="https://api.ryumem.io"  # Your endpoint
export RYUMEM_API_KEY="ryu_..."                # Your API key

# Required - LLM API key for your provider
export GOOGLE_API_KEY="your_google_key"        # For Gemini
# or
export OPENAI_API_KEY="your_openai_key"        # For OpenAI (better embeddings)
```

## Architecture

Ryumem implements a comprehensive bi-temporal knowledge graph architecture:

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
│  Bi-Temporal Graph      │  - Graph database
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

## Python SDK Usage

### Initialization

The Ryumem client automatically loads configuration from environment variables:

```python
from ryumem import Ryumem

# Basic initialization - loads RYUMEM_API_URL and RYUMEM_API_KEY from env
ryumem = Ryumem()

# With query augmentation enabled
ryumem = Ryumem(
    augment_queries=True,      # Enable augmentation with historical context
    similarity_threshold=0.3,  # Match queries with 30%+ similarity
    top_k_similar=5,           # Use top 5 similar queries
)

# With tool tracking enabled
ryumem = Ryumem(
    track_tools=True,          # Automatically track all tool executions
    augment_queries=True,      # Augment with historical tool usage
)
```

### Configuration Options

```python
ryumem = Ryumem(
    # Query Augmentation
    augment_queries=True,            # Enable query augmentation (default: False)
    similarity_threshold=0.3,        # Similarity threshold for augmentation (default: 0.5)
    top_k_similar=5,                 # Number of similar queries to use (default: 3)

    # Tool Tracking
    track_tools=True,                # Enable automatic tool tracking (default: False)

    # Entity Extraction
    extract_entities=True,           # Enable entity extraction (default: True)

    # Search Settings
    default_strategy="hybrid",       # Default search strategy
)
```

### Core Operations

```python
# The SDK provides auto-generated tools when integrated with agents:
# - search_memory(query: str) -> results
# - save_memory(content: str) -> confirmation

# These tools are automatically available to your agent after:
agent = add_memory_to_agent(agent, ryumem)
```

## Google ADK Integration

### Complete Example

```python
import asyncio
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from ryumem import Ryumem
from ryumem.integrations import add_memory_to_agent, wrap_runner_with_tracking

# App configuration
APP_NAME = "my_app"
USER_ID = "user_123"
SESSION_ID = "session_456"

# Define your tools
def get_weather(city: str) -> dict:
    """Get weather for a city."""
    return {"status": "success", "report": f"Weather in {city} is sunny"}

weather_tool = FunctionTool(func=get_weather)

# Create agent
agent = Agent(
    model="gemini-2.0-flash-exp",
    name="weather_agent",
    instruction="You are a helpful weather assistant with memory.",
    tools=[weather_tool]
)

# Add memory + tool tracking + query augmentation in ONE line!
ryumem = Ryumem(
    augment_queries=True,
    similarity_threshold=0.3,
    top_k_similar=5,
)

agent = add_memory_to_agent(agent, ryumem)

# Setup session and runner
async def main():
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID
    )

    runner = Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=session_service
    )

    # Wrap runner to automatically track queries and augment with history
    runner = wrap_runner_with_tracking(runner, agent)

    # Use the runner
    content = types.Content(
        role='user',
        parts=[types.Part(text="What's the weather in London?")]
    )

    events = runner.run(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=content
    )

    # Process response
    for event in events:
        if event.is_final_response():
            print(event.content.parts[0].text)

asyncio.run(main())
```

### Features Demonstrated

- **Automatic Tool Tracking**: All tool executions are logged with:
  - Tool name and parameters
  - Execution results
  - Timestamp and user context
  - Hierarchical episode tracking (queries link to tool executions)

- **Query Augmentation**: Similar past queries enrich new queries with:
  - Historical tool usage patterns
  - Previous results and context
  - Learned patterns and relationships

- **Memory Integration**: Agent automatically gets two new tools:
  - `search_memory(query)` - Search the knowledge graph
  - `save_memory(content)` - Store new information

## Examples

See the [examples/](examples/) directory for complete working examples:

### Key Examples

1. **[simple_tool_tracking_demo.py](examples/simple_tool_tracking_demo.py)**
   - Demonstrates automatic tool tracking and query augmentation
   - Weather + sentiment analysis agent
   - Shows how similar queries share context

2. **[password_guessing_game.py](examples/password_guessing_game.py)**
   - Tests query augmentation with a password guessing game
   - Agent learns from previous attempts
   - Demonstrates pattern recognition across similar queries

### Other Examples

- [basic_usage.py](examples/basic_usage.py) - Core features walkthrough
- [ollama_usage.py](examples/ollama_usage.py) - Local Ollama models
- [litellm_usage.py](examples/litellm_usage.py) - Multiple LLM providers

## Web Dashboard

Access the web dashboard to visualize and manage your knowledge graph:

### Features
- 🔐 **Secure Login** - API key authentication
- 💬 **Chat Interface** - Query your knowledge graph
- 📊 **Graph Visualization** - Interactive entity/relationship visualization (when entity extraction enabled)
- 🗂️ **Entity Browser** - Browse and explore entities with filtering (when entity extraction enabled)
- 📝 **Episode Management** - Add and view episodes
- 🔍 **Query History** - View augmented queries with historical context
- 🛠️ **Tool Analytics** - Track tool usage and performance
- ⚙️ **System Settings** - Configure LLM providers, API keys, search settings
- 👤 **Agent Settings** - Configure agent instructions and behavior
- 📈 **Real-time Stats** - Monitor system health

### Conditional Features
- **Graph** and **Entity** tabs only appear when entity extraction is enabled
- Disabling entity extraction saves 30-50% on LLM tokens

See [dashboard/README.md](dashboard/README.md) for setup and usage details.

## Multi-Tenancy & Authentication

Ryumem is designed as a multi-tenant system from the ground up.

### Getting Access

Contact **contact@predictable.sh** to:
- Register your organization
- Receive your API key (starts with `ryu_`)
- Get your API endpoint URL

### Customer Isolation

- **Customers**: Top-level tenants (companies/organizations) with complete data isolation
- **API Keys**: Access controlled via API keys
- **Separate Databases**: Each customer gets their own isolated database file
- **Secure**: API key required for all requests

### User-Level Scoping

Within a customer, further isolation via:
- `user_id`: Scope memories to specific end-users
- `session_id`: Track specific interaction sessions
- `agent_id`: Separate different agent contexts

## Configuration

### Required Environment Variables

```bash
# Ryumem Server Access (get from contact@predictable.sh)
RYUMEM_API_URL=https://api.ryumem.io
RYUMEM_API_KEY=ryu_...

# LLM API Key (for your chosen provider)
GOOGLE_API_KEY=...           # For Gemini models
# or
OPENAI_API_KEY=sk-...        # For OpenAI models (better embeddings)
```

### Optional Configuration

```bash
# Query Augmentation
RYUMEM_AUGMENT_QUERIES=true
RYUMEM_SIMILARITY_THRESHOLD=0.3
RYUMEM_TOP_K_SIMILAR=5

# Tool Tracking
RYUMEM_TRACK_TOOLS=true

# Entity Extraction
RYUMEM_EXTRACT_ENTITIES=true  # Set to false to save 30-50% tokens

# Search Strategy
RYUMEM_DEFAULT_STRATEGY=hybrid  # hybrid, semantic, bm25, or traversal
```

### Programmatic Configuration

```python
from ryumem import Ryumem

# All configuration through initialization
ryumem = Ryumem(
    augment_queries=True,
    similarity_threshold=0.3,
    top_k_similar=5,
    track_tools=True,
    extract_entities=True,
    default_strategy="hybrid"
)
```

## Key Features

### Query Augmentation

Automatically enriches queries with historical context:

```python
# Enable augmentation
ryumem = Ryumem(
    augment_queries=True,
    similarity_threshold=0.3,  # Match queries with 30%+ similarity
    top_k_similar=5,           # Use top 5 similar past queries
)

# Similar queries like "What's the weather in London?" and
# "How's the weather in London today?" will share context
```

**Benefits:**
- Agent learns from past interactions
- Similar queries get historical tool usage context
- Improved response quality over time
- Pattern recognition across conversations

### Tool Tracking

Automatically track all tool executions:

```python
# Enable tool tracking
ryumem = Ryumem(track_tools=True)

# Then wrap your runner
runner = wrap_runner_with_tracking(runner, agent)

# All tool executions are now automatically logged with:
# - Tool name and parameters
# - Execution results
# - User and session context
# - Hierarchical tracking (queries → tool executions)
```

**Tracked Information:**
- Tool invocations with parameters
- Execution results and errors
- Timing and performance metrics
- User/session/agent context
- Query → Tool execution hierarchy

### Search Strategies

Four powerful search strategies:

1. **Hybrid** (Recommended) - RRF fusion of all methods
2. **Semantic** - Embedding-based similarity
3. **BM25** - Keyword/lexical matching
4. **Traversal** - Graph relationship navigation

All strategies include temporal decay scoring (recent facts score higher).

### Entity Extraction Control

Toggle entity extraction to optimize costs:

```python
# Disable entity extraction to save 30-50% on LLM tokens
ryumem = Ryumem(extract_entities=False)

# Enable for rich knowledge graph features
ryumem = Ryumem(extract_entities=True)
```

**When Disabled:**
- Saves 30-50% on LLM API costs
- Still supports episode storage and search
- Graph and Entity UI tabs hidden in dashboard

**When Enabled:**
- Full knowledge graph with entities and relationships
- Graph visualization in dashboard
- Entity browser and filtering
- Community detection
- Relationship traversal search

## Performance Best Practices

1. **Use Query Augmentation**
   ```python
   ryumem = Ryumem(augment_queries=True, similarity_threshold=0.3)
   ```
   - Improves response quality over time
   - Helps agent learn from past interactions

2. **Enable Tool Tracking**
   ```python
   ryumem = Ryumem(track_tools=True)
   runner = wrap_runner_with_tracking(runner, agent)
   ```
   - Provides visibility into agent behavior
   - Enables debugging and optimization

3. **Choose Search Strategy Wisely**
   - `hybrid` - Best overall results (default)
   - `semantic` - Conceptual understanding
   - `bm25` - Exact keyword matching
   - `traversal` - Relationship-focused

4. **Toggle Entity Extraction**
   - Disable when not needed: saves 30-50% tokens
   - Enable for rich graph features

