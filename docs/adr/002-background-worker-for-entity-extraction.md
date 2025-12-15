# ADR-002: Background Worker for Entity Extraction

## Status
Accepted

## Context

Entity extraction in Ryumem involves:
1. LLM calls to extract entities from content (~2-5 seconds)
2. LLM calls to extract relationships (~2-5 seconds)
3. Embedding generation for deduplication (~1-2 seconds)
4. Database operations for persistence

This adds 5-12+ seconds to each episode ingestion, making API responses slow and blocking.

### Constraint: Single Database Connection

Ryugraph (Kuzu) only allows **one active connection at a time**. The Ryumem server manages this connection, so any background process cannot directly connect to the database.

### Previous State

Entity extraction was disabled by default (`enable_entity_extraction=False`) to avoid slow API responses. Users had to explicitly enable it per-request, limiting knowledge graph functionality.

## Decision

Implement a **separate Python worker process** that:
1. Pulls extraction jobs from a **Redis queue**
2. Runs LLM-based entity/relationship extraction
3. Calls **HTTP endpoints** on the server to persist results

### Architecture

```
Client --> FastAPI Server --> Redis Queue --> Entity Worker --> HTTP Callbacks --> Server --> Ryugraph
```

### Embedding Strategy

- **Episode content embedding**: Stays synchronous (enables immediate search/dedup)
- **Entity/relationship embeddings**: Moves to worker (async, non-blocking)

## Rationale

### Why Separate Process?

1. **Isolation** - Worker crashes don't affect API server
2. **Scalability** - Can run multiple workers for higher throughput
3. **Resource management** - Worker can use different CPU/memory limits

### Why Redis Queue?

1. **Reliability** - BRPOPLPUSH provides atomic job handoff
2. **Persistence** - Jobs survive process restarts (with Redis persistence)
3. **Visibility** - Easy to monitor queue depth
4. **No external dependencies beyond Redis** - Already common in many deployments

### Why HTTP Callbacks (Not Direct DB)?

1. **Respects single-connection constraint** - Server maintains the only DB connection
2. **Reuses existing logic** - Server handles deduplication, validation
3. **Security** - Worker doesn't need DB credentials
4. **Consistency** - All writes go through same code path

### Alternatives Considered

1. **In-process background tasks** (asyncio/threading)
   - Rejected: Could impact API performance, harder to scale

2. **Direct DB connection from worker**
   - Rejected: Violates Ryugraph single-connection constraint

3. **Message queue (RabbitMQ, SQS)**
   - Rejected: Overkill, adds operational complexity

## Consequences

### Positive

- Entity extraction enabled by default
- API responses return immediately (~100-500ms)
- Knowledge graph builds asynchronously
- Scalable worker pool for high-volume deployments
- Clear separation of concerns

### Negative

- Requires Redis (additional infrastructure)
- Knowledge graph not immediately available after ingestion
- Network overhead for HTTP callbacks
- Need to monitor worker health

### Configuration

New environment variables:
```bash
# Worker settings
RYUMEM_WORKER_ENABLED=true
REDIS_URL=redis://localhost:6379
WORKER_INTERNAL_KEY=shared-secret-for-auth
SERVER_URL=http://localhost:8000

# LLM Provider (gemini is default)
LLM_PROVIDER=gemini              # Options: gemini, openai, ollama, litellm
EMBEDDING_PROVIDER=gemini        # Options: gemini, openai, ollama, litellm

# Gemini (default)
GOOGLE_API_KEY=your-google-api-key
LLM_MODEL=gemini-2.0-flash-exp
EMBEDDING_MODEL=text-embedding-004
EMBEDDING_DIMENSIONS=768

# Or OpenAI (alternative)
# OPENAI_API_KEY=sk-your-key
# LLM_PROVIDER=openai
# EMBEDDING_PROVIDER=openai
# LLM_MODEL=gpt-4
# EMBEDDING_MODEL=text-embedding-3-large
# EMBEDDING_DIMENSIONS=3072
```

### Deployment

Run worker alongside server (from the `server` directory):
```bash
cd server

# Terminal 1: Start Redis
redis-server

# Terminal 2: Start server
uvicorn main:app --port 8000

# Terminal 3: Start worker (separate process)
python -m ryumem_server.worker
```

**Note**: The worker must be run from the `server` directory for Python to find the `ryumem_server` module.

## Implementation

### New Components

1. `server/ryumem_server/worker/queue.py` - Redis queue operations
2. `server/ryumem_server/worker/entity_extraction.py` - Worker logic with multi-provider support
3. `server/ryumem_server/worker/__main__.py` - Entry point

### Supported LLM/Embedding Providers

| Provider | LLM Models | Embedding Models | API Key Required |
|----------|------------|------------------|------------------|
| `gemini` (default) | gemini-2.0-flash-exp, gemini-1.5-pro | text-embedding-004 | GOOGLE_API_KEY |
| `openai` | gpt-4, gpt-4-turbo | text-embedding-3-large | OPENAI_API_KEY |
| `ollama` | qwen2.5:7b, llama3, etc. | nomic-embed-text | None (local) |
| `litellm` | Any supported model | Any supported model | Varies |

### Modified Components

1. `server/main.py` - Internal HTTP endpoints for worker callbacks
2. `server/ryumem_server/ingestion/episode.py` - Queue jobs instead of sync extraction
3. `server/ryumem_server/core/config.py` - WorkerConfig
4. `server/ryumem_server/lib.py` - Wire worker config to ingestion pipeline

### Internal Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /internal/entities/upsert` | Create/update entity with deduplication |
| `POST /internal/relationships/upsert` | Create/update relationship with deduplication |
| `POST /internal/episodes/{id}/extraction-complete` | Mark extraction done |
| `GET /internal/queue/stats` | Queue monitoring |
