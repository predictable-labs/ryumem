# Ryumem API Server

FastAPI server providing RESTful API endpoints for Ryumem - Bi-temporal Knowledge Graph Memory System.

## Features

- **Authentication** - Secure multi-tenant API key access
- **Customer Registration** - Self-service API key generation
- **Episode Management** - Add, retrieve, and manage memories
- **Advanced Search** - Hybrid search with multiple strategies
- **Entity & Relationship Queries** - Rich knowledge graph exploration
- **Dynamic Configuration** - Hot-reload settings without restart
- **Statistics & Analytics** - Real-time system metrics
- **Community Detection** - Automatic entity clustering
- **Memory Maintenance** - Pruning and compaction
- **Custom Cypher Queries** - Direct graph database access
- **Health Monitoring** - Service health checks
- **GitHub OAuth** - Optional OAuth authentication

## Quick Start

### Option 1: Docker (Recommended)

```bash
# From project root
cd /path/to/ryumem

# Configure environment
cp server/.env.example server/.env
# Edit server/.env and add your LLM API key

# Build and run
docker build -t ryumem-server -f server/Dockerfile .
docker run -p 8000:8000 \
  --env-file server/.env \
  -e RYUMEM_DB_FOLDER=/app/data \
  -v ./server/data:/app/data \
  ryumem-server
```

### Option 2: Local Development

**Prerequisites:**
- Python 3.10+
- An LLM API key (Google Gemini, OpenAI, or Ollama running locally)

**Setup:**

```bash
# Install ryumem SDK from project root
cd /path/to/ryumem
pip install -e .

# Install server dependencies
cd server
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and set your configuration

# Start server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Server will be available at:
- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `GOOGLE_API_KEY` or `OPENAI_API_KEY` | LLM provider API key (at least one required) |
| `RYUMEM_DB_FOLDER` | Database storage path (e.g., `./data`) |
| `ADMIN_API_KEY` | Admin key for customer registration |

### LLM Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `gemini` | Provider: `gemini`, `openai`, `ollama`, `litellm` |
| `LLM_MODEL` | `gemini-2.0-flash-exp` | Model name |
| `EMBEDDING_PROVIDER` | `gemini` | Embedding provider |
| `EMBEDDING_MODEL` | `text-embedding-004` | Embedding model name |
| `EMBEDDING_DIMENSIONS` | `768` | Embedding dimensions |

### Ollama Configuration (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `RYUMEM_LLM_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |

### OAuth Configuration (Optional)

| Variable | Description |
|----------|-------------|
| `GITHUB_CLIENT_ID` | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth App client secret |

### System Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed CORS origins (comma-separated) |
| `LOG_LEVEL` | `INFO` | Logging level |

### Background Worker (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `RYUMEM_WORKER_ENABLED` | `false` | Enable background worker |
| `REDIS_URL` | `redis://localhost:6379` | Redis URL for worker |
| `WORKER_INTERNAL_KEY` | - | Internal worker authentication |
| `SERVER_URL` | `http://localhost:8000` | Server URL for worker callbacks |

## API Reference

### Authentication

All endpoints (except `/register` and `/health`) require the `X-API-Key` header.

```bash
curl -H "X-API-Key: ryu_your_api_key" http://localhost:8000/episodes
```

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/register` | Register new customer, get API key |
| `POST` | `/episodes` | Add episode with entity extraction |
| `GET` | `/episodes` | List episodes with filtering |
| `GET` | `/episodes/{uuid}` | Get specific episode |
| `POST` | `/search` | Hybrid search (semantic + BM25 + graph) |
| `GET` | `/entity/{name}` | Get entity context and relationships |
| `GET` | `/stats` | System statistics |
| `GET` | `/health` | Health check |

### Configuration Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/settings` | Get all settings |
| `GET` | `/api/settings/{category}` | Get category settings |
| `PUT` | `/api/settings` | Update settings (hot-reload) |
| `POST` | `/api/settings/validate` | Validate before saving |
| `POST` | `/api/settings/reset-defaults` | Reset to defaults |

### Advanced Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/communities/update` | Run community detection |
| `POST` | `/prune` | Prune expired memories |
| `POST` | `/cypher/execute` | Execute custom Cypher |
| `GET` | `/users` | List all users |

### Quick Examples

```bash
# Register customer
curl -X POST "http://localhost:8000/register" \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "my_company"}'

# Add episode
curl -X POST "http://localhost:8000/episodes" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ryu_abc123..." \
  -d '{"content": "Alice works at Google", "user_id": "user_123"}'

# Search
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ryu_abc123..." \
  -d '{"query": "Where does Alice work?", "strategy": "hybrid"}'
```

## Architecture

```
┌──────────────────┐
│  Client/UI       │
│  (Dashboard)     │
└────────┬─────────┘
         │ HTTP/REST
         v
┌──────────────────┐
│  FastAPI Server  │
│  - Auth          │
│  - Endpoints     │
│  - Config Mgmt   │
└────────┬─────────┘
         │
         v
┌──────────────────┐
│  Ryumem Core     │
│  - Per-customer  │
│  - Cached        │
│  - Hot-reload    │
└────────┬─────────┘
         │
         v
┌──────────────────┐
│  Customer DBs    │
│  {id}.db files   │
│  (Graph DB)      │
└──────────────────┘
```

### Multi-Tenancy

- **Customer Level**: Complete isolation via separate databases
- **User Level**: Logical scoping within customer database
- **Cache Management**: Per-customer Ryumem instance caching
- **Config Isolation**: Each customer has independent configuration

## Docker Deployment

The server Dockerfile must be built from the **project root** because it depends on the `ryumem` SDK package.

**Build:**
```bash
# From project root
docker build -t ryumem-server -f server/Dockerfile .
```

**Run:**
```bash
docker run -p 8000:8000 \
  -e GOOGLE_API_KEY=your_key \
  -e RYUMEM_DB_FOLDER=/app/data \
  -e ADMIN_API_KEY=your_admin_key \
  -v ./server/data:/app/data \
  ryumem-server
```

**With env file:**
```bash
docker run -p 8000:8000 \
  --env-file server/.env \
  -e RYUMEM_DB_FOLDER=/app/data \
  -v ./server/data:/app/data \
  ryumem-server
```

## Development

### Project Structure

```
server/
├── main.py                      # FastAPI application
├── requirements.txt             # Dependencies
├── .env.example                 # Environment template
├── Dockerfile                   # Container build
├── ryumem_server/
│   ├── __init__.py
│   ├── lib.py                   # Ryumem wrapper
│   └── core/
│       ├── config.py            # Config models
│       ├── config_service.py    # Config management
│       ├── graph_db.py          # Database operations
│       └── models.py            # API models
└── data/                        # Customer databases
    ├── customer1.db
    └── master_auth.db           # Authentication
```

### Running Tests

```bash
# Install dev dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest

# Run with coverage
pytest --cov=ryumem_server
```

### Development Server

```bash
# With auto-reload
uvicorn main:app --reload

# With specific port
uvicorn main:app --reload --port 8080

# With debug logging
uvicorn main:app --reload --log-level debug
```

## Troubleshooting

### Common Issues

**"Customer not found" error**
- Register customer first via `/register` endpoint
- Check API key is correct and starts with `ryu_`

**"Config validation failed"**
- Check API keys are set when switching providers
- Validate settings before saving using `/api/settings/validate`

**Settings changes not taking effect**
- Cache invalidation happens automatically
- Try `/api/settings/reset-defaults` to reset

**Slow search performance**
- Run `/prune` endpoint periodically
- Use appropriate search strategy
- Filter by `user_id` for multi-tenant

**CORS errors**
- Add frontend URL to `CORS_ORIGINS`
- Restart server after changing CORS settings

## License

Apache License 2.0 - See [LICENSE](../LICENSE) for details.
