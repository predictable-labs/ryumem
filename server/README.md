# Ryumem API Server

FastAPI server providing RESTful API endpoints for Ryumem - Bi-temporal Knowledge Graph Memory System.

## Features

✨ **API Endpoints**:
- 📝 **POST /episodes** - Add new episodes (memories)
- 🔍 **POST /search** - Search and query the knowledge graph
- 👤 **GET /entity/{name}** - Get comprehensive entity context
- 📊 **GET /stats** - Get system statistics
- 🌐 **POST /communities/update** - Detect and update communities
- 🧹 **POST /prune** - Prune and compact memories
- ❤️ **GET /health** - Health check endpoint

## Installation

1. **Install dependencies:**

```bash
cd server
pip install -r requirements.txt

# Install ryumem from parent directory
cd ..
pip install -e .
```

2. **Set up environment variables:**

```bash
# Copy the template environment file
cp .env.example .env

# Edit .env and set your database path
nano .env
```

Required environment variables:
- `RYUMEM_DB_PATH` - Path to your Ryumem database (e.g., "./data/ryumem.db")

## Usage

### Start the Server

```bash
# Development mode with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

The server will be available at:
- API: http://localhost:8000
- Interactive API docs: http://localhost:8000/docs
- Alternative docs: http://localhost:8000/redoc

### API Examples

#### 1. Add an Episode

```bash
curl -X POST "http://localhost:8000/episodes" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Alice works at Google as a Software Engineer in Mountain View.",
    "user_id": "user_123",
    "source": "text"
  }'
```

Response:
```json
{
  "episode_id": "abc123...",
  "message": "Episode added successfully",
  "timestamp": "2025-11-07T10:30:00"
}
```

#### 2. Search the Knowledge Graph

```bash
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Where does Alice work?",
    "user_id": "user_123",
    "limit": 10,
    "strategy": "hybrid"
  }'
```

Response:
```json
{
  "entities": [
    {
      "uuid": "entity123",
      "name": "Alice",
      "entity_type": "PERSON",
      "summary": "Software engineer at Google",
      "mentions": 5,
      "score": 0.95
    }
  ],
  "edges": [
    {
      "uuid": "edge456",
      "source_name": "Alice",
      "target_name": "Google",
      "relation_type": "WORKS_AT",
      "fact": "Alice works at Google",
      "mentions": 3,
      "score": 0.92
    }
  ],
  "query": "Where does Alice work?",
  "strategy": "hybrid",
  "count": 2
}
```

#### 3. Get Entity Context

```bash
curl "http://localhost:8000/entity/Alice?user_id=user_123"
```

#### 4. Get System Statistics

```bash
curl "http://localhost:8000/stats"
```

Response:
```json
{
  "total_episodes": 150,
  "total_entities": 45,
  "total_relationships": 120,
  "total_communities": 8,
  "db_path": "./data/ryumem_server.db"
}
```

#### 5. Update Communities

```bash
curl -X POST "http://localhost:8000/communities/update" \
  -H "Content-Type: application/json" \
  -d '{
    "resolution": 1.0,
    "min_community_size": 2
  }'
```

#### 6. Prune Memories

```bash
curl -X POST "http://localhost:8000/prune" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "expired_cutoff_days": 90,
    "min_mentions": 2,
    "compact_redundant": true
  }'
```

### Python Client Example

```python
import requests

BASE_URL = "http://localhost:8000"

# Add an episode
response = requests.post(f"{BASE_URL}/episodes", json={
    "content": "Bob graduated from Stanford University in 2020.",
    "user_id": "user_123",
    "source": "text"
})
print(response.json())

# Search
response = requests.post(f"{BASE_URL}/search", json={
    "query": "Tell me about Bob's education",
    "user_id": "user_123",
    "strategy": "hybrid",
    "limit": 5
})
results = response.json()

# Display results
for entity in results["entities"]:
    print(f"Entity: {entity['name']} - Score: {entity['score']:.3f}")

for edge in results["edges"]:
    print(f"Fact: {edge['fact']} - Score: {edge['score']:.3f}")
```

## API Documentation

### Interactive Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

These provide:
- Complete API reference
- Interactive testing
- Request/response schemas
- Example payloads

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `RYUMEM_DB_PATH` | Database file path | ./data/ryumem.db | ✅ Yes |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | http://localhost:3000 | No |
| `HOST` | Server host | 0.0.0.0 | No |
| `PORT` | Server port | 8000 | No |


### Creating a Ryumem Database

The server reads from an existing Ryumem database. To create a database with episodes and entities, you need to use a separate write instance (e.g., via Python script or CLI).

Example script to populate a database:

```python
from ryumem import Ryumem
from ryumem.core.config import RyumemConfig

# Create config with LLM provider (required for write operations)
config = RyumemConfig()
# API key must be set in environment: OPENAI_API_KEY or GOOGLE_API_KEY

# Create Ryumem instance (not in read-only mode)
with Ryumem(config=config) as ryumem:
    # Add episodes
    ryumem.add_episode(
        content="Alice works at Google as a Software Engineer.",
        user_id="user_123",
        source="text"
    )

    # Search and explore
    results = ryumem.search("Where does Alice work?", user_id="user_123")
    print(results)
```

Once you have a populated database, you can start the server to query it via REST API without needing API keys.

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
│  (This Server)   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Ryumem Core     │
│  (Knowledge      │
│   Graph Engine)  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Ryugraph DB     │
│  (SQLite)        │
└──────────────────┘
```

## Development

### Running Tests

```bash
# Install dev dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest
```

### Code Structure

```
server/
├── main.py              # FastAPI application
├── requirements.txt     # Python dependencies
├── .env.example        # Environment variables template
├── README.md           # This file
└── data/               # Database files (created automatically)
    └── ryumem_server.db
```

## Deployment

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Install ryumem
RUN pip install -e /app/..

# Run server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Production Considerations

1. **Use a proper ASGI server**: Use gunicorn with uvicorn workers
2. **Set up HTTPS**: Use nginx or similar as reverse proxy
3. **Configure CORS**: Set appropriate CORS origins in production
4. **Database backups**: Regular backups of the SQLite database
5. **Monitoring**: Set up logging and monitoring (e.g., Sentry)
6. **Rate limiting**: Add rate limiting for public APIs

## Troubleshooting

### Common Issues

**1. "Ryumem not initialized" error**
- Check that your `.env` file has `RYUMEM_DB_PATH` set correctly
- Ensure the database file exists and is accessible
- Check server logs for initialization errors

**2. CORS errors in browser**
- Add your frontend URL to `CORS_ORIGINS` in `.env`
- Restart the server after changing environment variables

**3. Slow search performance**
- Periodically run `/prune` endpoint to keep graph efficient
- Use appropriate search strategy (semantic, bm25, or hybrid)
- Consider filtering by user_id for multi-tenant scenarios

**4. Database locked errors**
- SQLite has limited concurrent write support
- Consider using a different database backend for high-traffic scenarios

## Support

For issues or questions:
- Check the main [Ryumem README](../README.md)
- Review API docs at http://localhost:8000/docs
- Check server logs for detailed error messages

## License

MIT License - Same as Ryumem parent project

