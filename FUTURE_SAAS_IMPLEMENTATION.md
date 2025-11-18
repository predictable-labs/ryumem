# Ryumem SaaS Implementation Strategy

> **Purpose:** This document outlines the strategy for converting ryumem from a self-hosted library into a hosted SaaS API service. This provides **maximum IP protection** by keeping all proprietary algorithms server-side while users access functionality through a lightweight SDK.

**Last Updated:** 2025-11-18

---

## Table of Contents

1. [Why SaaS?](#why-saas)
2. [Architecture Overview](#architecture-overview)
3. [Implementation Phases](#implementation-phases)
4. [Technical Specifications](#technical-specifications)
5. [Security & Compliance](#security--compliance)
6. [Pricing & Business Model](#pricing--business-model)
7. [Migration Strategy](#migration-strategy)
8. [Timeline & Resources](#timeline--resources)

---

## Why SaaS?

### IP Protection Benefits

1. **Zero Code Access:** Users never see proprietary algorithms
2. **No Reverse Engineering:** Core logic stays on your servers
3. **Version Control:** Push updates without user awareness
4. **License Enforcement:** Control access via API keys
5. **Usage Monitoring:** Track how users interact with your system

### Additional Advantages

- **Revenue Model:** Recurring subscription income
- **Easier Distribution:** No complex installation/setup
- **Better Support:** Centralized monitoring and debugging
- **Faster Iteration:** Deploy fixes immediately
- **Scalability:** Handle traffic centrally

---

## Architecture Overview

### Current State

```
┌─────────────────┐
│  User's Machine │
├─────────────────┤
│ ryumem library  │  ← Full code access
│ FastAPI server  │  ← Can inspect
│ Next.js dash    │  ← Can modify
│ Graph database  │  ← Local data
└─────────────────┘
```

### Target State (SaaS)

```
┌────────────────────┐              ┌──────────────────┐
│  User's Machine    │              │  Your Cloud      │
├────────────────────┤              ├──────────────────┤
│ ryumem_client SDK  │ ◄── HTTPS ───┤ FastAPI Server   │
│   (thin wrapper)   │   (API Key)  │   + Auth         │
│                    │              │   + Rate Limit   │
│   Just 100KB!      │              │                  │
└────────────────────┘              │ Core Logic:      │
                                    │ - Entity Extract │
                                    │ - Hybrid Search  │
       User can only                │ - Communities    │
       see API calls                │ - Pruning        │
                                    │                  │
                                    │ Graph Database   │
                                    │ BM25 Indexes     │
                                    └──────────────────┘
```

### Component Breakdown

| Component | Current | SaaS Version | IP Protection |
|-----------|---------|--------------|---------------|
| **Core Library** | Local Python package | Hosted API only | ✅ 100% Protected |
| **Graph Database** | Local file | Cloud-hosted | ✅ Data isolated |
| **Entity Extraction** | Local LLM calls | Server-side | ✅ Prompts hidden |
| **Search Algorithms** | Local code | Server-side | ✅ Logic hidden |
| **Dashboard UI** | Self-hosted | Web app (optional) | ⚠️ Frontend visible |
| **Client SDK** | Full library | HTTP wrapper | ⚠️ Only API interface visible |

---

## Implementation Phases

### Phase 1: API Infrastructure & Authentication (2 weeks)

**Goal:** Secure the FastAPI server with authentication and usage tracking.

#### 1.1 Database Schema Updates

Add authentication tables:

```sql
-- API Keys table
CREATE TABLE api_keys (
    id UUID PRIMARY KEY,
    key_hash TEXT NOT NULL,  -- SHA-256 hash of actual key
    user_email TEXT NOT NULL,
    tier TEXT NOT NULL,  -- 'free', 'pro', 'enterprise'
    created_at TIMESTAMP,
    last_used TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- Usage tracking
CREATE TABLE api_usage (
    id UUID PRIMARY KEY,
    api_key_id UUID REFERENCES api_keys(id),
    endpoint TEXT,
    method TEXT,
    timestamp TIMESTAMP,
    response_time_ms INTEGER,
    status_code INTEGER
);

-- Quotas
CREATE TABLE quotas (
    api_key_id UUID REFERENCES api_keys(id),
    month TEXT,  -- 'YYYY-MM'
    episodes_count INTEGER DEFAULT 0,
    api_calls_count INTEGER DEFAULT 0
);
```

#### 1.2 Authentication Service

Create `src/ryumem/auth/service.py`:

```python
import hashlib
import secrets
from datetime import datetime
from typing import Optional

class AuthService:
    def __init__(self, db):
        self.db = db

    def generate_api_key(self, user_email: str, tier: str = 'free') -> str:
        """Generate new API key for user."""
        # Format: rym_live_32randomchars or rym_test_32randomchars
        prefix = "rym_live_"
        key = prefix + secrets.token_urlsafe(32)

        # Store hash only
        key_hash = hashlib.sha256(key.encode()).hexdigest()

        # Insert into database
        query = """
        INSERT INTO api_keys (id, key_hash, user_email, tier, created_at, is_active)
        VALUES ($id, $key_hash, $user_email, $tier, $created_at, true)
        """
        self.db.execute(query, {
            "id": str(uuid.uuid4()),
            "key_hash": key_hash,
            "user_email": user_email,
            "tier": tier,
            "created_at": datetime.utcnow()
        })

        return key  # Return only once

    def validate_api_key(self, key: str) -> Optional[dict]:
        """Validate API key and return user info."""
        key_hash = hashlib.sha256(key.encode()).hexdigest()

        query = """
        MATCH (k:ApiKey)
        WHERE k.key_hash = $key_hash AND k.is_active = true
        RETURN k.user_email, k.tier, k.id
        """

        result = self.db.execute(query, {"key_hash": key_hash})

        if result:
            # Update last_used timestamp
            self._update_last_used(result[0]["id"])
            return result[0]

        return None

    def check_quota(self, api_key_id: str, tier: str) -> bool:
        """Check if user is within quota for current month."""
        # Define tier limits
        TIER_LIMITS = {
            'free': {'episodes': 1000, 'api_calls': 10000},
            'pro': {'episodes': 50000, 'api_calls': 500000},
            'enterprise': {'episodes': -1, 'api_calls': -1}  # Unlimited
        }

        # Get current month usage
        current_month = datetime.utcnow().strftime('%Y-%m')

        query = """
        MATCH (q:Quota)
        WHERE q.api_key_id = $api_key_id AND q.month = $month
        RETURN q.episodes_count, q.api_calls_count
        """

        result = self.db.execute(query, {
            "api_key_id": api_key_id,
            "month": current_month
        })

        if not result:
            return True  # No usage yet

        usage = result[0]
        limits = TIER_LIMITS[tier]

        # Check limits (-1 means unlimited)
        if limits['episodes'] != -1 and usage['episodes_count'] >= limits['episodes']:
            return False
        if limits['api_calls'] != -1 and usage['api_calls_count'] >= limits['api_calls']:
            return False

        return True
```

#### 1.3 FastAPI Authentication Middleware

Modify `server/main.py`:

```python
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Dependency to verify API key on every request."""
    api_key = credentials.credentials

    # Validate key
    user_info = auth_service.validate_api_key(api_key)

    if not user_info:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    # Check quota
    if not auth_service.check_quota(user_info['id'], user_info['tier']):
        raise HTTPException(
            status_code=402,  # Payment Required
            detail=f"Quota exceeded for {user_info['tier']} tier. Upgrade to continue."
        )

    return user_info

# Apply to all endpoints
@app.post("/episodes")
async def add_episode(
    request: AddEpisodeRequest,
    user_info: dict = Depends(verify_api_key)
):
    # Track usage
    auth_service.increment_usage(user_info['id'], 'episodes')

    # Original logic...
    episode_id = ryumem.add_episode(...)

    return AddEpisodeResponse(episode_id=episode_id, ...)
```

#### 1.4 Rate Limiting

Use Redis for distributed rate limiting:

```python
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

# Initialize with Redis
@app.on_event("startup")
async def startup():
    redis = await aioredis.create_redis_pool("redis://localhost")
    await FastAPILimiter.init(redis)

# Apply per endpoint
@app.post("/search")
@app.limiter.limit("100/minute")  # 100 requests per minute
async def search(
    request: SearchRequest,
    user_info: dict = Depends(verify_api_key)
):
    # ...
```

---

### Phase 2: Client SDK Development (1 week)

**Goal:** Create a lightweight Python SDK that mirrors the original API but makes HTTP calls.

#### 2.1 SDK Structure

```
ryumem_client/
├── pyproject.toml
├── README.md
├── src/
│   └── ryumem_client/
│       ├── __init__.py
│       ├── client.py       # Main RyumemClient class
│       ├── exceptions.py   # Custom exceptions
│       ├── models.py       # Pydantic response models
│       └── utils.py        # Retry logic, caching
└── tests/
    └── test_client.py
```

#### 2.2 Client Implementation

`src/ryumem_client/client.py`:

```python
import requests
from typing import Dict, List, Optional
from .exceptions import RyumemAPIError, QuotaExceededError, AuthenticationError
from .models import SearchResult, Episode

class RyumemClient:
    """
    Lightweight client for Ryumem hosted API.

    Example:
        from ryumem_client import RyumemClient

        client = RyumemClient(api_key="rym_live_...")

        # Add episode
        episode_id = client.add_episode(
            content="Alice works at Google",
            user_id="user_123"
        )

        # Search
        results = client.search(
            query="Where does Alice work?",
            user_id="user_123"
        )
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.ryumem.com",
        timeout: int = 30
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })

    def add_episode(
        self,
        content: str,
        user_id: str,
        session_id: Optional[str] = None,
        source: str = "text",
        metadata: Optional[Dict] = None,
        extract_entities: Optional[bool] = None,
    ) -> str:
        """
        Add a new episode to memory.

        Returns:
            Episode UUID
        """
        payload = {
            "content": content,
            "user_id": user_id,
            "source": source
        }

        if session_id:
            payload["session_id"] = session_id
        if metadata:
            payload["metadata"] = metadata
        if extract_entities is not None:
            payload["extract_entities"] = extract_entities

        response = self._post("/episodes", json=payload)
        return response["episode_id"]

    def search(
        self,
        query: str,
        user_id: str,
        limit: int = 10,
        strategy: str = "hybrid",
        min_rrf_score: Optional[float] = None,
        min_bm25_score: Optional[float] = None,
    ) -> SearchResult:
        """
        Search the knowledge graph.

        Returns:
            SearchResult with entities and edges
        """
        payload = {
            "query": query,
            "user_id": user_id,
            "limit": limit,
            "strategy": strategy
        }

        if min_rrf_score is not None:
            payload["min_rrf_score"] = min_rrf_score
        if min_bm25_score is not None:
            payload["min_bm25_score"] = min_bm25_score

        response = self._post("/search", json=payload)
        return SearchResult(**response)

    def get_entity_context(
        self,
        entity_name: str,
        user_id: str,
        max_depth: int = 2
    ) -> Dict:
        """Get context for an entity."""
        response = self._get(
            f"/entity/{entity_name}",
            params={"user_id": user_id, "max_depth": max_depth}
        )
        return response

    def _post(self, endpoint: str, **kwargs) -> Dict:
        """Make POST request with error handling."""
        try:
            response = self.session.post(
                f"{self.base_url}{endpoint}",
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            self._handle_http_error(e.response)
        except requests.exceptions.Timeout:
            raise RyumemAPIError("Request timed out")
        except requests.exceptions.RequestException as e:
            raise RyumemAPIError(f"Request failed: {str(e)}")

    def _get(self, endpoint: str, **kwargs) -> Dict:
        """Make GET request with error handling."""
        try:
            response = self.session.get(
                f"{self.base_url}{endpoint}",
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            self._handle_http_error(e.response)
        except requests.exceptions.Timeout:
            raise RyumemAPIError("Request timed out")
        except requests.exceptions.RequestException as e:
            raise RyumemAPIError(f"Request failed: {str(e)}")

    def _handle_http_error(self, response):
        """Handle HTTP errors with appropriate exceptions."""
        if response.status_code == 401:
            raise AuthenticationError("Invalid API key")
        elif response.status_code == 402:
            raise QuotaExceededError(response.json().get("detail", "Quota exceeded"))
        elif response.status_code == 429:
            raise RyumemAPIError("Rate limit exceeded")
        else:
            raise RyumemAPIError(f"API error: {response.text}")
```

#### 2.3 SDK Package Configuration

`pyproject.toml` for SDK:

```toml
[project]
name = "ryumem-client"
version = "0.1.0"
description = "Official Python client for Ryumem hosted API"
requires-python = ">=3.8"
dependencies = [
    "requests>=2.28.0",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-mock>=3.0.0",
]
```

**Key Point:** SDK has NO dependencies on:
- `ryugraph` (graph database)
- `openai` (LLM client)
- `networkx` (community detection)
- Any proprietary ryumem code

Total package size: **~100 KB** vs **~50 MB** for full library.

---

### Phase 3: Deployment & Infrastructure (1-2 weeks)

#### 3.1 Production Dockerfile

`docker/Dockerfile.production`:

```dockerfile
# Multi-stage build for smaller image
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY src/ryumem /app/ryumem
COPY server /app/server

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PATH=/root/.local/bin:$PATH

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD curl -f http://localhost:8000/health || exit 1

# Run server
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 3.2 Cloud Deployment Options

**Option A: AWS (Production-Ready)**

```yaml
# docker-compose.yml for AWS ECS
version: '3.8'

services:
  api:
    image: ryumem/api:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@rds-instance/ryumem
      - REDIS_URL=redis://redis-cluster:6379
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./data:/app/data
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - /etc/letsencrypt:/etc/letsencrypt
    depends_on:
      - api

volumes:
  redis-data:
```

**AWS Services:**
- **ECS Fargate:** Container hosting (auto-scaling)
- **RDS PostgreSQL:** Database (or S3 for file-based ryugraph)
- **ElastiCache Redis:** Rate limiting and caching
- **S3:** BM25 index storage
- **CloudFront:** CDN for dashboard
- **Route 53:** DNS management
- **ACM:** SSL certificates
- **CloudWatch:** Monitoring and logs

**Option B: Railway/Render (Simpler)**

```yaml
# railway.toml or render.yaml
services:
  - type: web
    name: ryumem-api
    env: docker
    dockerfilePath: ./docker/Dockerfile.production
    envVars:
      - key: OPENAI_API_KEY
        sync: false
    disk:
      name: ryumem-data
      mountPath: /app/data
      sizeGB: 10
```

**Cost Estimates:**
- **Railway/Render:** ~$20-50/month (hobby tier)
- **AWS:** ~$200-500/month (production tier with HA)

#### 3.3 CI/CD Pipeline

`.github/workflows/deploy.yml`:

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]
  release:
    types: [created]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run tests
        run: pytest tests/ -v --cov=ryumem

      - name: Check code quality
        run: |
          black --check src/
          ruff check src/

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Build Docker image
        run: |
          docker build -f docker/Dockerfile.production -t ryumem/api:latest .
          docker tag ryumem/api:latest ryumem/api:${{ github.sha }}

      - name: Push to registry
        run: |
          echo ${{ secrets.DOCKER_PASSWORD }} | docker login -u ${{ secrets.DOCKER_USERNAME }} --password-stdin
          docker push ryumem/api:latest
          docker push ryumem/api:${{ github.sha }}

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to AWS ECS
        uses: aws-actions/amazon-ecs-deploy-task-definition@v1
        with:
          task-definition: ecs-task-def.json
          service: ryumem-api
          cluster: production
          wait-for-service-stability: true
```

#### 3.4 Monitoring Setup

**Logging with Structured JSON:**

```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }

        # Add extra fields
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        if hasattr(record, 'api_key_id'):
            log_data['api_key_id'] = record.api_key_id

        return json.dumps(log_data)

# Configure in server/main.py
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.root.addHandler(handler)
```

**Integration with Sentry:**

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn="https://xxx@sentry.io/xxx",
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,  # 10% of requests
    environment="production"
)
```

---

### Phase 4: Subscription & Billing (1 week)

#### 4.1 Pricing Tiers

| Feature | Free | Pro ($29/mo) | Enterprise (Custom) |
|---------|------|--------------|---------------------|
| **Episodes/month** | 1,000 | 50,000 | Unlimited |
| **API Calls/month** | 10,000 | 500,000 | Unlimited |
| **Users** | 1 | 5 | Unlimited |
| **Search Strategies** | Semantic only | All (hybrid, BM25) | All + Custom |
| **Community Detection** | ❌ | ✅ | ✅ |
| **Memory Pruning** | ❌ | ✅ | ✅ |
| **Support** | Community | Email (24h) | Dedicated Slack |
| **SLA** | None | 99.5% uptime | 99.9% uptime + On-call |
| **Data Retention** | 30 days | 1 year | Forever |

#### 4.2 Stripe Integration

```python
import stripe
from fastapi import APIRouter

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

router = APIRouter(prefix="/billing", tags=["Billing"])

@router.post("/create-subscription")
async def create_subscription(
    email: str,
    tier: str,
    payment_method_id: str
):
    """Create new subscription for user."""

    # Create Stripe customer
    customer = stripe.Customer.create(
        email=email,
        payment_method=payment_method_id,
        invoice_settings={"default_payment_method": payment_method_id}
    )

    # Create subscription
    price_ids = {
        'pro': 'price_pro_monthly',
        'enterprise': 'price_enterprise_monthly'
    }

    subscription = stripe.Subscription.create(
        customer=customer.id,
        items=[{"price": price_ids[tier]}],
        expand=["latest_invoice.payment_intent"]
    )

    # Generate API key for user
    api_key = auth_service.generate_api_key(email, tier)

    return {
        "api_key": api_key,
        "subscription_id": subscription.id,
        "status": subscription.status
    }

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")

    # Handle events
    if event["type"] == "customer.subscription.deleted":
        # Deactivate API key
        subscription_id = event["data"]["object"]["id"]
        auth_service.deactivate_subscription(subscription_id)

    elif event["type"] == "invoice.payment_failed":
        # Send warning email
        customer_email = event["data"]["object"]["customer_email"]
        send_payment_failed_email(customer_email)

    return {"status": "success"}
```

#### 4.3 Usage Metering

Track usage for billing:

```python
def track_usage(api_key_id: str, metric: str, quantity: int = 1):
    """Track usage for billing purposes."""

    # Increment quota counter
    current_month = datetime.utcnow().strftime('%Y-%m')

    query = """
    MATCH (q:Quota {api_key_id: $api_key_id, month: $month})
    SET q.{metric}_count = q.{metric}_count + $quantity
    """

    db.execute(query, {
        "api_key_id": api_key_id,
        "month": current_month,
        "quantity": quantity
    })

    # Report to Stripe for usage-based billing (if applicable)
    stripe.SubscriptionItem.create_usage_record(
        subscription_item_id,
        quantity=quantity,
        timestamp=int(time.time())
    )
```

---

### Phase 5: Dashboard Migration (1 week, Optional)

#### 5.1 Host Dashboard as Web App

Deploy Next.js dashboard to Vercel:

```bash
# vercel.json
{
  "env": {
    "NEXT_PUBLIC_API_URL": "https://api.ryumem.com",
    "NEXT_PUBLIC_ENABLE_AUTH": "true"
  },
  "routes": [
    {
      "src": "/api/(.*)",
      "dest": "https://api.ryumem.com/api/$1"
    }
  ]
}
```

#### 5.2 Add User Authentication

Use NextAuth.js:

```typescript
// pages/api/auth/[...nextauth].ts
import NextAuth from 'next-auth'
import Providers from 'next-auth/providers'

export default NextAuth({
  providers: [
    Providers.Email({
      server: process.env.EMAIL_SERVER,
      from: process.env.EMAIL_FROM
    }),
    Providers.Google({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET
    })
  ],
  callbacks: {
    async session(session, user) {
      // Attach API key to session
      session.apiKey = await getApiKeyForUser(user.email)
      return session
    }
  }
})
```

#### 5.3 API Key Management UI

```typescript
// components/ApiKeyManager.tsx
import { useState } from 'react'

export function ApiKeyManager() {
  const [apiKey, setApiKey] = useState('')

  const generateKey = async () => {
    const response = await fetch('/api/keys/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tier: 'pro' })
    })

    const data = await response.json()
    setApiKey(data.api_key)
  }

  return (
    <div>
      <button onClick={generateKey}>Generate API Key</button>
      {apiKey && (
        <div>
          <code>{apiKey}</code>
          <p className="warning">Save this key - it won't be shown again!</p>
        </div>
      )}
    </div>
  )
}
```

---

## Technical Specifications

### API Endpoints

Complete list of endpoints with authentication:

```
# Authentication
POST   /auth/register              # Create account & get API key
POST   /auth/validate              # Validate API key
DELETE /auth/revoke                # Revoke API key

# Core Memory Operations
POST   /episodes                   # Add episode
GET    /episodes                   # List episodes (paginated)
GET    /episodes/{id}              # Get single episode

# Search & Retrieval
POST   /search                     # Hybrid search
GET    /entity/{name}              # Get entity context
GET    /graph/data                 # Get graph data for viz

# Management
POST   /communities/update         # Detect communities
POST   /prune                      # Prune memories
GET    /stats                      # Get statistics

# Billing
POST   /billing/create-subscription
POST   /billing/webhook            # Stripe webhooks
GET    /billing/usage              # Get current usage

# Health & Monitoring
GET    /health                     # Health check
GET    /metrics                    # Prometheus metrics
```

### Database Schema (Complete)

```sql
-- Existing ryugraph nodes (keep as-is)
-- Episode, Entity, Community nodes

-- New nodes for SaaS
CREATE NODE TABLE ApiKey (
    uuid STRING,
    key_hash STRING,
    user_email STRING,
    tier STRING,
    created_at TIMESTAMP,
    last_used TIMESTAMP,
    is_active BOOLEAN,
    stripe_customer_id STRING,
    stripe_subscription_id STRING,
    PRIMARY KEY (uuid)
);

CREATE NODE TABLE Quota (
    uuid STRING,
    api_key_id STRING,
    month STRING,
    episodes_count INT64,
    api_calls_count INT64,
    PRIMARY KEY (uuid)
);

CREATE NODE TABLE UsageLog (
    uuid STRING,
    api_key_id STRING,
    endpoint STRING,
    method STRING,
    timestamp TIMESTAMP,
    response_time_ms INT64,
    status_code INT64,
    PRIMARY KEY (uuid)
);
```

### Environment Variables

```bash
# Server (production)
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
SENTRY_DSN=https://...@sentry.io/...
JWT_SECRET=...
CORS_ORIGINS=https://app.ryumem.com

# Client SDK (user's .env)
RYUMEM_API_KEY=rym_live_...
RYUMEM_BASE_URL=https://api.ryumem.com  # Optional, defaults to production
```

---

## Security & Compliance

### API Security Measures

1. **Authentication:**
   - Bearer token authentication (API keys)
   - JWT tokens for dashboard sessions
   - API key rotation capability every 90 days

2. **Encryption:**
   - TLS 1.3 for all connections
   - API keys stored as SHA-256 hashes
   - Database encryption at rest (AWS RDS encryption)

3. **Rate Limiting:**
   - Per API key: 100 requests/minute (configurable by tier)
   - Per IP: 1000 requests/hour (prevent abuse)
   - Exponential backoff headers

4. **Input Validation:**
   - Pydantic models for all requests
   - SQL injection prevention (parameterized queries)
   - Max request size: 10 MB
   - Content-Type validation

5. **CORS Policy:**
   ```python
   CORS_ORIGINS = [
       "https://app.ryumem.com",
       "http://localhost:3000",  # Development only
   ]
   ```

### Data Privacy & Compliance

#### GDPR Compliance

1. **Data Subject Rights:**
   - Right to access: `GET /users/{user_id}/data`
   - Right to delete: `DELETE /users/{user_id}` (hard delete all data)
   - Right to portability: `GET /users/{user_id}/export` (JSON export)

2. **Privacy by Design:**
   - User data isolated by `user_id`
   - No cross-user data leakage
   - Audit logs for all data access
   - Retention policies per tier (30d/1yr/forever)

#### SOC 2 Type II (Enterprise)

1. **Security Controls:**
   - Annual penetration testing
   - Vulnerability scanning (weekly)
   - Access control reviews (quarterly)
   - Incident response plan

2. **Availability Controls:**
   - 99.9% SLA for enterprise
   - Automated failover
   - Regular backup testing

3. **Confidentiality Controls:**
   - Encryption in transit and at rest
   - Key rotation policies
   - Employee background checks

### Audit Logging

```python
def audit_log(
    action: str,
    api_key_id: str,
    resource_type: str,
    resource_id: str,
    details: dict
):
    """Log security-relevant actions."""

    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,  # 'read', 'write', 'delete'
        "api_key_id": api_key_id,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details,
        "ip_address": request.client.host
    }

    # Write to secure audit log (append-only)
    with open('/var/log/ryumem/audit.jsonl', 'a') as f:
        f.write(json.dumps(log_entry) + '\n')

    # Also send to SIEM (e.g., Splunk)
    siem_client.send(log_entry)
```

---

## Pricing & Business Model

### Revenue Projections

**Assumptions:**
- 1,000 free users
- 10% conversion to Pro ($29/mo)
- 1% conversion to Enterprise ($500/mo avg)

**Monthly Recurring Revenue:**
- Free: $0
- Pro: 100 users × $29 = $2,900
- Enterprise: 10 users × $500 = $5,000
- **Total MRR: $7,900**
- **Annual Revenue: ~$95,000**

### Cost Structure

**Monthly Costs:**
- AWS Infrastructure: $500
- OpenAI API: $200 (pass-through to users)
- Stripe fees: $200 (2.9% + 30¢)
- Support staff (part-time): $1,000
- Marketing: $500
- **Total Costs: $2,400**

**Profit Margin: $5,500/month (70%)**

### Growth Strategy

1. **Freemium Funnel:**
   - Free tier to drive adoption
   - Email drip campaign for conversion
   - In-app upgrade prompts

2. **Enterprise Sales:**
   - Direct outreach to large companies
   - Custom contracts with SLAs
   - White-label options

3. **Usage-Based Upsells:**
   - Charge $0.01 per additional episode after quota
   - Offer quota packs ($10 for 5,000 episodes)

4. **Referral Program:**
   - 20% commission for affiliates
   - Free month for both referrer and referee

---

## Migration Strategy

### For Existing Self-Hosted Users

#### Option 1: Gradual Migration (Recommended)

**Timeline: 6-12 months transition period**

1. **Month 1-3: Dual Support**
   - Announce SaaS launch
   - Keep self-hosted library maintained
   - Offer migration incentives (50% off first year)

2. **Month 4-6: Data Migration Tool**
   - Release migration script:
   ```bash
   # Export local data
   ryumem export --output data.json

   # Import to SaaS
   ryumem-client import --api-key rym_live_... --file data.json
   ```

3. **Month 7-12: Deprecation Warnings**
   - Add deprecation warnings to library
   - Limited support for self-hosted (security fixes only)
   - No new features for self-hosted

4. **Month 13+: End of Support**
   - Self-hosted library archived
   - Full focus on SaaS

#### Option 2: Hybrid Model (Long-term)

**Keep both options available:**

1. **SaaS** (default for most users):
   - Easy to use, managed service
   - Lower barrier to entry
   - $29-500/month

2. **Self-Hosted License** (enterprise only):
   - For companies with strict data residency requirements
   - Annual license: $10,000/year
   - Includes support and updates
   - No source code access (compiled binaries only)

### Migration Incentives

1. **Early Adopter Pricing:**
   - 50% off first year for early migrants
   - Lifetime discount (20% off)

2. **White Glove Migration:**
   - Free migration assistance for Enterprise tier
   - Dedicated engineer for data transfer

3. **Credit for Self-Hosted Users:**
   - GitHub sponsors get free Pro tier
   - Contributors get free Enterprise tier

---

## Timeline & Resources

### Development Timeline

| Phase | Duration | Dependencies | Output |
|-------|----------|--------------|--------|
| **Phase 1: API Auth** | 2 weeks | - | Secured FastAPI server |
| **Phase 2: Client SDK** | 1 week | Phase 1 | `ryumem-client` package |
| **Phase 3: Deployment** | 1-2 weeks | Phase 1, 2 | Production infrastructure |
| **Phase 4: Billing** | 1 week | Phase 3 | Stripe integration |
| **Phase 5: Dashboard** | 1 week | Phase 3 | Hosted web app |
| **Phase 6: Docs** | 1 week | Phase 2 | Developer portal |

**Total: 7-9 weeks (1.5-2 months)**

### Resource Requirements

**Team:**
- 1 Backend Engineer (FastAPI, auth, billing)
- 1 DevOps Engineer (AWS, Docker, CI/CD)
- 1 Frontend Engineer (Next.js dashboard) - optional
- 1 Technical Writer (docs, tutorials)

**Budget:**
- Development: $30,000 (assuming $75/hr × 400 hours)
- Infrastructure setup: $5,000
- Marketing/launch: $5,000
- **Total: $40,000**

**Ongoing:**
- Infrastructure: $500/month
- Support: $1,000/month
- Marketing: $500/month

---

## Files to Create/Modify

### New Files

```
# Authentication & Billing
src/ryumem/auth/
├── __init__.py
├── service.py              # AuthService class
├── models.py               # ApiKey, Quota models
└── middleware.py           # FastAPI middleware

src/ryumem/billing/
├── __init__.py
├── stripe_client.py        # Stripe integration
└── webhook_handlers.py     # Stripe webhook processing

# Client SDK (separate repo)
ryumem-client/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/ryumem_client/
│   ├── __init__.py
│   ├── client.py
│   ├── models.py
│   ├── exceptions.py
│   └── utils.py
└── tests/
    └── test_client.py

# Infrastructure
docker/
├── Dockerfile.production
└── docker-compose.yml

.github/workflows/
├── deploy.yml              # CI/CD pipeline
├── test.yml                # Automated tests
└── security-scan.yml       # Security scanning

# Documentation
docs/
├── api/
│   ├── authentication.md
│   ├── endpoints.md
│   └── rate-limits.md
├── sdk/
│   ├── python.md
│   ├── javascript.md (future)
│   └── examples.md
├── guides/
│   ├── quickstart.md
│   ├── migration.md
│   └── best-practices.md
└── legal/
    ├── privacy-policy.md
    ├── terms-of-service.md
    └── sla.md

# Landing page
website/
├── index.html
├── pricing.html
├── docs.html
└── signup.html
```

### Modified Files

```
# Add authentication to existing endpoints
server/main.py
- Add auth middleware
- Add billing endpoints
- Update all endpoints with Depends(verify_api_key)

# Database schema updates
src/ryumem/core/graph_db.py
- Add ApiKey, Quota, UsageLog tables
- Migration scripts

# Configuration
pyproject.toml
- Split into ryumem (server) and ryumem-client (SDK)

# Documentation
README.md
- Update to focus on SaaS model
- Add SDK installation instructions
- Link to migration guide

.env.example
- Add Stripe keys
- Add JWT secrets
- Add Redis URL
```

---

## Success Metrics

### Technical Metrics

- **Uptime:** 99.9% availability
- **Latency:** p95 < 500ms, p99 < 1s
- **Error Rate:** < 0.1% of requests
- **Deployment Frequency:** Weekly releases
- **Mean Time to Recovery:** < 1 hour

### Business Metrics

- **Monthly Recurring Revenue (MRR):** Target $10K in 6 months
- **Customer Acquisition Cost (CAC):** < $100
- **Lifetime Value (LTV):** > $500 (17 months retention)
- **LTV:CAC Ratio:** > 3:1
- **Churn Rate:** < 5% monthly

### Product Metrics

- **Activation Rate:** 50% of signups add first episode
- **Weekly Active Users (WAU):** 40% of customers
- **Net Promoter Score (NPS):** > 50
- **Time to First Value:** < 5 minutes
- **API Key Generation:** 80% within first session

---

## Risk Assessment & Mitigation

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Data Loss** | Low | Critical | Daily backups, point-in-time recovery |
| **Security Breach** | Medium | Critical | Penetration testing, bug bounty program |
| **API Downtime** | Medium | High | Load balancing, auto-scaling, failover |
| **Performance Issues** | Medium | Medium | Caching, DB optimization, monitoring |
| **Quota Abuse** | High | Low | Aggressive rate limiting, anomaly detection |

### Business Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Low Adoption** | Medium | High | Free tier, content marketing, referrals |
| **High Churn** | Medium | High | Customer success program, feature requests |
| **Competitor** | High | Medium | Unique features (bi-temporal, hybrid search) |
| **Pricing Issues** | Medium | Medium | A/B testing, customer surveys |
| **Support Burden** | High | Medium | Self-service docs, chatbot, community forum |

---

## Next Steps

When ready to implement this SaaS model:

1. **Validate Market Demand:**
   - Survey existing users about willingness to pay
   - Create landing page with email signup (gauge interest)
   - Run ads to target audience ($500 budget)

2. **Build MVP (4 weeks):**
   - Phase 1: Authentication
   - Phase 2: Client SDK
   - Deploy to Railway/Render (simple hosting)
   - Invite 10 beta users

3. **Iterate Based on Feedback:**
   - Adjust pricing based on usage patterns
   - Fix bugs reported by beta users
   - Add most-requested features

4. **Public Launch:**
   - Write launch blog post
   - Post to HackerNews, Reddit, ProductHunt
   - Email campaign to self-hosted users
   - Press release to tech media

5. **Scale:**
   - Migrate to AWS for better control
   - Hire support staff
   - Add enterprise features (SSO, audit logs)
   - Expand to more LLM providers

---

## Conclusion

Converting ryumem to a SaaS model provides the **best IP protection** while creating a sustainable business. Users get:
- Easy setup (no local installation)
- Always up-to-date features
- Professional support
- Scalable infrastructure

You retain:
- Full control over algorithms
- Recurring revenue stream
- Direct user relationships
- Ability to iterate quickly

The lightweight SDK approach (<100 KB) ensures users can still integrate ryumem into their applications with minimal overhead, while all proprietary code remains on your servers.

**Total Investment:** ~$40K and 2 months development
**Expected Return:** $95K/year revenue with 70% margins
**IP Protection:** 100% - users never see your code

Ready to ship when you are! 🚀
