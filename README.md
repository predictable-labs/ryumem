# Ryumem

[![License](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://opensource.org/licenses/AGPL-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://badge.fury.io/py/ryumem.svg)](https://badge.fury.io/py/ryumem)

**Bi-temporal Knowledge Graph Memory System**

Ryumem is an open-source memory system for building intelligent agents with persistent, queryable memory using a bi-temporal knowledge graph architecture.

## Features

- **Episode-first ingestion** - Every piece of information starts as an episode
- **Automatic entity & relationship extraction** - Powered by LLM (OpenAI, Gemini, Ollama, or LiteLLM)
- **Bi-temporal data model** - Track when facts were valid and when they were recorded
- **Advanced hybrid retrieval** - Combines semantic search, BM25 keyword search, and graph traversal
- **Temporal decay scoring** - Recent facts automatically score higher with configurable decay
- **Full multi-tenancy** - Support for user_id, agent_id, session_id, group_id
- **Automatic contradiction handling** - Detects and invalidates outdated facts
- **Incremental updates** - No batch reprocessing required
- **Automatic tool tracking** - Track all tool executions and query patterns
- **Query augmentation** - Enrich queries with historical context from similar past queries
- **Dynamic configuration** - Hot-reload settings without server restart
- **Web dashboard** - Modern Next.js UI with graph visualization
- **MCP Server** - Model Context Protocol integration for Claude Desktop and coding agents

## Architecture

```
                    +------------------+
                    |   Dashboard      |
                    |   (Next.js)      |
                    +--------+---------+
                             |
                             v
+-------------+     +------------------+     +------------------+
|  MCP Server | --> |   API Server     | --> |   Graph DB       |
| (TypeScript)|     |   (FastAPI)      |     |   (ryugraph)     |
+-------------+     +--------+---------+     +------------------+
                             |
                             v
                    +------------------+
                    |   Python SDK     |
                    |   (ryumem)       |
                    +------------------+
```

**Components:**
- **API Server** (`/server`) - FastAPI backend with REST API
- **Dashboard** (`/dashboard`) - Next.js web UI for visualization
- **MCP Server** (`/mcp-server-ts`) - Model Context Protocol server for AI agents
- **Python SDK** (`/src/ryumem`) - Client library for Python applications

## Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/predictable-labs/ryumem.git
cd ryumem

# Configure environment
cp server/.env.example server/.env
# Edit server/.env and add your LLM API key (GOOGLE_API_KEY or OPENAI_API_KEY)

cp dashboard/env.template dashboard/.env
# Edit dashboard/.env if needed

# Start all services
docker-compose up -d

# Dashboard: http://localhost:3000
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Option 2: Local Development

**Prerequisites:**
- Python 3.10+
- Node.js 18+
- An LLM API key (Google Gemini, OpenAI, or local Ollama)

**1. Start the API Server:**

```bash
# Install SDK
pip install -e .

# Install server dependencies
cd server
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and set your LLM API key

# Start server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**2. Start the Dashboard:**

```bash
cd dashboard
npm install
cp env.template .env
npm run dev
```

**3. Register and Get API Key:**

```bash
# Register a customer
curl -X POST "http://localhost:8000/register" \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "my_company"}'

# Response includes your API key (ryu_...)
```

## Python SDK

### Installation

```bash
pip install ryumem
```

Or install from source:

```bash
git clone https://github.com/predictable-labs/ryumem.git
cd ryumem
pip install -e .
```

### Basic Usage

```python
from ryumem import Ryumem

# Initialize client
ryumem = Ryumem(
    api_url="http://localhost:8000",
    api_key="ryu_your_api_key_here"
)

# Add an episode
ryumem.add_episode(
    content="Alice joined Google as a software engineer in 2023",
    user_id="user_123"
)

# Search memories
results = ryumem.search(
    query="Where does Alice work?",
    user_id="user_123",
    strategy="hybrid"
)
```

### Google ADK Integration

```python
from google.adk.agents import Agent
from ryumem import Ryumem
from ryumem.integrations import add_memory_to_agent, wrap_runner_with_tracking

# Initialize Ryumem
ryumem = Ryumem(
    api_url="http://localhost:8000",
    api_key="ryu_your_api_key_here",
    augment_queries=True,
    similarity_threshold=0.3,
)

# Create your agent
agent = Agent(
    model="gemini-2.0-flash-exp",
    name="my_agent",
    instruction="You are a helpful assistant with memory.",
    tools=[...]
)

# Add memory to agent - creates search_memory() and save_memory() tools
agent = add_memory_to_agent(agent, ryumem)

# Wrap runner for automatic tool tracking
runner = wrap_runner_with_tracking(runner, agent)
```

## MCP Server for Coding Agents

Ryumem includes an MCP (Model Context Protocol) server for integration with Claude Desktop and other AI coding agents.

### Installation

```bash
# From npm (when published)
npm install -g @predictable/ryumem-mcp-server

# Or from source
cd mcp-server-ts
npm install
npm run build
```

### Configure for Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "ryumem": {
      "command": "node",
      "args": ["/path/to/ryumem/mcp-server-ts/build/index.js"],
      "env": {
        "RYUMEM_API_URL": "http://localhost:8000",
        "RYUMEM_API_KEY": "ryu_your_api_key_here"
      }
    }
  }
}
```

**Available MCP Tools:**
- `search_memory` - Multi-strategy semantic search
- `add_episode` - Save new memories
- `get_entity_context` - Explore entity relationships
- `batch_add_episodes` - Bulk memory operations
- `list_episodes`, `get_episode`, `update_episode_metadata` - Episode management

See [MCP Server Documentation](mcp-server-ts/README.md) for details.

## Environment Variables

### Server (`server/.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | Yes* | - | Google Gemini API key |
| `OPENAI_API_KEY` | Yes* | - | OpenAI API key |
| `RYUMEM_DB_FOLDER` | Yes | `./data` | Database storage path |
| `ADMIN_API_KEY` | Yes | - | Admin key for registration |
| `LLM_PROVIDER` | No | `gemini` | LLM provider (gemini, openai, ollama, litellm) |
| `LLM_MODEL` | No | `gemini-2.0-flash-exp` | LLM model name |
| `EMBEDDING_PROVIDER` | No | `gemini` | Embedding provider |
| `EMBEDDING_MODEL` | No | `text-embedding-004` | Embedding model |
| `GITHUB_CLIENT_ID` | No | - | GitHub OAuth (optional) |
| `GITHUB_CLIENT_SECRET` | No | - | GitHub OAuth (optional) |
| `CORS_ORIGINS` | No | `http://localhost:3000` | Allowed CORS origins |

*At least one LLM API key is required

### Dashboard (`dashboard/.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | Yes | `http://localhost:8000` | Ryumem API server URL |
| `NEXT_PUBLIC_GITHUB_REDIRECT_URI` | No | - | GitHub OAuth redirect |

### MCP Server

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `RYUMEM_API_URL` | Yes | `http://localhost:8000` | API server URL |
| `RYUMEM_API_KEY` | Yes | - | Your API key |

## Examples

See the [examples/](examples/) directory for complete working examples:

- **Getting Started** - Basic SDK usage
- **Google ADK Integration** - Memory for ADK agents
- **LiteLLM Integration** - Multiple LLM providers
- **Ollama Integration** - Local LLM usage

## Documentation

- [Server Documentation](server/README.md) - API server setup and endpoints
- [Dashboard Documentation](dashboard/README.md) - Web UI setup
- [MCP Server Documentation](mcp-server-ts/README.md) - Claude integration
- [Examples](examples/README.md) - Usage examples

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/
ruff check src/

# Type checking
mypy src/
```

## License

GNU Affero General Public License v3.0 (AGPL-3.0) - See [LICENSE](LICENSE) for details.

---

**Built by [Predictable Labs](https://github.com/predictable-labs)**
