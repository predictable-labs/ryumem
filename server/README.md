# Ryumem API Server

FastAPI server providing RESTful API endpoints for Ryumem - Bi-temporal Knowledge Graph Memory System.

## Features

✨ **API Endpoints**:
- 🔐 **Authentication** - Secure multi-tenant API key access
- 🆕 **Customer Registration** - Self-service API key generation
- 📝 **Episode Management** - Add, retrieve, and manage memories
- 🔍 **Advanced Search** - Hybrid search with multiple strategies
- 👤 **Entity & Relationship Queries** - Rich knowledge graph exploration
- ⚙️ **Dynamic Configuration** - Hot-reload settings without restart
- 📊 **Statistics & Analytics** - Real-time system metrics
- 🌐 **Community Detection** - Automatic entity clustering
- 🧹 **Memory Maintenance** - Pruning and compaction
- 🔧 **Custom Cypher Queries** - Direct database access
- ❤️ **Health Monitoring** - Service health checks

## Installation

### Prerequisites

- Python 3.10+
- pip or conda

### Setup

1. **Install dependencies:**

```bash
cd server
pip install -r requirements.txt

# Install ryumem SDK from parent directory
cd ..
pip install -e .
```

2. **Configure environment:**

```bash
# Copy template
cp .env.example .env

# Edit .env and set your configuration
nano .env
```

**Required environment variables:**
```bash
# API Keys (at least one required for entity extraction)
OPENAI_API_KEY=sk-...      # For OpenAI
GOOGLE_API_KEY=...         # For Gemini

# LLM Configuration
RYUMEM_LLM_PROVIDER=openai  # or ollama, gemini, litellm
RYUMEM_LLM_MODEL=gpt-4o-mini

# Database
RYUMEM_DB_FOLDER=./data    # Where customer databases are stored

# Server
RYUMEM_SYSTEM_CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

## Usage

### Start the Server

```bash
# Development mode with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production mode with multiple workers
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# Using PM2 for production
pm2 start ecosystem.config.js
```

Server will be available at:
- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

## API Reference

### Quick Reference

The server provides RESTful endpoints organized into categories:

**Authentication & Registration:**
- `POST /register` - Register new customer and receive API key
- All other endpoints require `X-API-Key` header

**Core Endpoints:**
- `POST /episodes` - Add episodes with entity extraction
- `GET /episodes` - List episodes with filtering
- `POST /search` - Search using hybrid retrieval (semantic + BM25 + traversal)
- `GET /entity/{name}` - Get entity context and relationships

**Configuration:**
- `GET /api/settings` - Get all settings grouped by category
- `GET /api/settings/{category}` - Get category-specific settings
- `PUT /api/settings` - Update settings with hot-reload
- `POST /api/settings/validate` - Validate before saving
- `POST /api/settings/reset-defaults` - Reset to defaults

**System & Analytics:**
- `GET /stats` - System statistics and metrics
- `GET /users` - List all users
- `GET /health` - Health check

**Advanced Operations:**
- `POST /communities/update` - Run community detection (Louvain algorithm)
- `POST /prune` - Prune expired memories and compact
- `POST /cypher/execute` - Execute custom Cypher queries

### Interactive API Documentation

For complete endpoint documentation with request/response schemas, examples, and testing:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Quick Start Example

```bash
# 1. Register customer
curl -X POST "http://localhost:8000/register" \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "my_company"}'

# 2. Add episode
curl -X POST "http://localhost:8000/episodes" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ryu_abc123..." \
  -d '{"content": "Alice works at Google", "user_id": "user_123"}'

# 3. Search
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
         ▼
┌──────────────────┐
│  FastAPI Server  │
│  - Auth          │
│  - Endpoints     │
│  - Config Mgmt   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Ryumem Core     │
│  - Per-customer  │
│  - Cached        │
│  - Hot-reload    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Customer DBs    │
│  {id}.db files   │
│  (Graph DB)      │
└──────────────────┘
```

### Multi-Tenancy Model

- **Customer Level**: Complete isolation via separate databases
- **User Level**: Logical scoping within customer database
- **Cache Management**: Per-customer Ryumem instance caching
- **Config Isolation**: Each customer has independent configuration

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OPENAI_API_KEY` | OpenAI API key | - | If using OpenAI |
| `GOOGLE_API_KEY` | Google Gemini API key | - | If using Gemini |
| `RYUMEM_DB_FOLDER` | Database folder path | ./data | Yes |
| `RYUMEM_LLM_PROVIDER` | LLM provider | openai | No |
| `RYUMEM_LLM_MODEL` | LLM model name | gpt-4o-mini | No |
| `RYUMEM_ENTITY_ENABLED` | Enable entity extraction | false | No |
| `RYUMEM_SYSTEM_CORS_ORIGINS` | CORS origins | localhost:3000 | No |

All configuration can be updated at runtime via `/api/settings` endpoints.

### Database-Backed Configuration

All settings are persisted to the database:
- **Hot-reload**: Changes apply without restart
- **Per-customer**: Each customer has independent config
- **Validation**: Settings validated before saving
- **Defaults**: Configurable default values
- **Categories**: Organized by category for easy management

## Development

### Project Structure

```
server/
├── main.py                      # FastAPI application
├── requirements.txt             # Dependencies
├── .env.example                # Environment template
├── ecosystem.config.js         # PM2 configuration
├── ryumem_server/
│   ├── __init__.py
│   ├── lib.py                  # Ryumem wrapper
│   └── core/
│       ├── config.py           # Config models
│       ├── config_service.py   # Config management
│       ├── graph_db.py         # Database operations
│       └── models.py           # API models
└── data/                       # Customer databases
    ├── customer1.db
    ├── customer2.db
    └── master_auth.db          # Authentication
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

# With debugging
uvicorn main:app --reload --log-level debug
```

## Deployment

### Production with PM2

```bash
# Start server
pm2 start ecosystem.config.js

# Monitor
pm2 monit

# Logs
pm2 logs

# Restart
pm2 restart ryumem-server
```

### Docker Deployment

The server Dockerfile must be built from the **project root** (not from `server/`) because it depends on the `ryumem` SDK package.

**Build:**
```bash
# From project root
cd /path/to/ryumem
docker build -t ryumem-server -f server/Dockerfile .
```

**Run with environment variables:**
```bash
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-... \
  -e RYUMEM_DB_FOLDER=/data \
  -e GITHUB_CLIENT_ID=your_client_id \
  -e GITHUB_CLIENT_SECRET=your_secret \
  -v ./data:/data \
  ryumem-server
```

**Run with env file:**
```bash
# Create .env file with your configuration
docker run -p 8000:8000 \
  --env-file server/.env \
  -v ./data:/data \
  ryumem-server
```

**Required environment variables:**
| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` or `GOOGLE_API_KEY` | LLM provider API key |
| `RYUMEM_DB_FOLDER` | Database storage path (mount as volume) |

**Optional environment variables:**
| Variable | Description |
|----------|-------------|
| `GITHUB_CLIENT_ID` | GitHub OAuth client ID |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth client secret |
| `RYUMEM_LLM_PROVIDER` | LLM provider (openai, gemini, ollama) |
| `RYUMEM_LLM_MODEL` | Model name |

### Production Considerations

1. **ASGI Server**: Use gunicorn with uvicorn workers
   ```bash
   gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
   ```

2. **Reverse Proxy**: Use nginx for HTTPS and load balancing

3. **CORS**: Configure appropriate origins in production

4. **Database Backups**: Regular backups of `./data` folder

5. **Monitoring**: Set up logging, metrics, and health checks

6. **Rate Limiting**: Add rate limiting for public APIs

7. **API Key Rotation**: Implement key rotation policy

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

**Database locked errors**
- Multiple write operations competing
- Consider using connection pooling
- Reduce concurrent requests

**CORS errors**
- Add frontend URL to `RYUMEM_SYSTEM_CORS_ORIGINS`
- Restart server after changing CORS settings

## Client Integration

### Python SDK

Use the official Ryumem Python SDK for easier integration:

```python
from ryumem import Ryumem

# Initialize client
ryumem = Ryumem()  # Loads from RYUMEM_API_URL and RYUMEM_API_KEY

# Use with Google ADK
from ryumem.integrations import add_memory_to_agent
agent = add_memory_to_agent(agent, ryumem)
```

See [main README](../README.md) for complete SDK documentation.

### Direct HTTP API

For other languages, use standard HTTP requests:

```python
import requests

headers = {"X-API-Key": "ryu_abc123..."}

# Add episode
requests.post("http://localhost:8000/episodes",
    json={"content": "Alice works at Google", "user_id": "user_123"},
    headers=headers)

# Search
response = requests.post("http://localhost:8000/search",
    json={"query": "Where does Alice work?", "strategy": "hybrid"},
    headers=headers)
```

## Support

For issues or questions:
- Check [main README](../README.md)
- Review [Dashboard docs](../dashboard/README.md)
- Visit interactive docs at http://localhost:8000/docs
- Check server logs for detailed errors

## License

MIT License - Same as Ryumem parent project
