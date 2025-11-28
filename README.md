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