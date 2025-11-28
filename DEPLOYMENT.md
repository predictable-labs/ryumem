# Ryumem Production Deployment with PM2

This guide covers deploying the Ryumem server and dashboard to production using PM2 process manager.

## Prerequisites

- Node.js and npm installed
- Python 3.8+ installed
- PM2 installed globally: `npm install -g pm2`

## Server Deployment

### 1. Setup Server Environment

```bash
cd server

# Create virtual environment
python3.12 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your production values:
# - RYUMEM_DB_FOLDER: Path to database folder
# - ADMIN_API_KEY: Secure random string for admin access
```

**Note**: The PM2 configuration is set to use `.venv/bin/python`, so the virtual environment must exist in the server folder.

### 2. Create Logs Directory

```bash
mkdir -p logs
```

### 3. Start Server with PM2

```bash
# Start the server
pm2 start ecosystem.config.js

# Save PM2 process list
pm2 save

# Setup PM2 to start on system boot
pm2 startup
```

### 4. Monitor Server

```bash
# View server status
pm2 status

# View logs
pm2 logs ryumem-server

# Monitor resources
pm2 monit
```

## Dashboard Deployment

### 1. Setup Dashboard Environment

```bash
cd dashboard

# Install dependencies
npm install

# Build the Next.js application
npm run build

# Create environment file (optional, or use env variables)
cp env.template .env.local
# Edit .env.local with:
# - NEXT_PUBLIC_API_URL: URL of your Ryumem server
```

### 2. Create Logs Directory

```bash
mkdir -p logs
```

### 3. Start Dashboard with PM2

```bash
# Start the dashboard
pm2 start ecosystem.config.js

# Save PM2 process list
pm2 save

# Setup PM2 to start on system boot (if not done already)
pm2 startup
```

### 4. Monitor Dashboard

```bash
# View dashboard status
pm2 status

# View logs
pm2 logs ryumem-dashboard

# Monitor resources
pm2 monit
```

## PM2 Management Commands

### Process Control

```bash
# Start all processes
pm2 start all

# Stop specific process
pm2 stop ryumem-server
pm2 stop ryumem-dashboard

# Restart specific process
pm2 restart ryumem-server
pm2 restart ryumem-dashboard

# Delete process from PM2
pm2 delete ryumem-server
pm2 delete ryumem-dashboard

# Reload (zero-downtime restart)
pm2 reload ryumem-dashboard
```

### Monitoring

```bash
# View all process status
pm2 status

# View real-time logs
pm2 logs

# View logs for specific process
pm2 logs ryumem-server
pm2 logs ryumem-dashboard

# Clear logs
pm2 flush

# Monitor CPU/Memory
pm2 monit
```

### Environment Variables

You can override environment variables when starting PM2:

```bash
# Server
cd server
PORT=8080 pm2 start ecosystem.config.js

# Dashboard
cd dashboard
PORT=3001 NEXT_PUBLIC_API_URL=http://your-server:8080 pm2 start ecosystem.config.js
```

## Production Configuration

### Server Configuration (server/ecosystem.config.js)

- **Python**: Uses `.venv/bin/python` from virtual environment
- **Port**: Default 8000 (configurable via --port in args)
- **Memory**: Auto-restart if exceeds 1GB
- **Instances**: 1 (FastAPI handles async)
- **Logs**: `server/logs/error.log` and `server/logs/out.log`

### Dashboard Configuration (dashboard/ecosystem.config.js)

- **Port**: Default 3000 (set via PORT env variable)
- **Memory**: Auto-restart if exceeds 512MB
- **Instances**: 1
- **Logs**: `dashboard/logs/error.log` and `dashboard/logs/out.log`

## Reverse Proxy Setup (Optional)

For production, use nginx as a reverse proxy:

```nginx
# Server API
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}

# Dashboard
server {
    listen 80;
    server_name dashboard.yourdomain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

## Troubleshooting

### Server Not Starting

1. Ensure virtual environment exists: `cd server && python3.12 -m venv .venv`
2. Check Python dependencies: `source .venv/bin/activate && pip install -r requirements.txt`
3. Verify .env file exists and has correct values
4. Check logs: `pm2 logs ryumem-server`
5. Check port availability: `lsof -i :8000`
6. Verify Python path in ecosystem.config.js points to `.venv/bin/python`

### Dashboard Not Starting

1. Ensure Next.js build completed: `cd dashboard && npm run build`
2. Verify node_modules installed: `npm install`
3. Check logs: `pm2 logs ryumem-dashboard`
4. Check port availability: `lsof -i :3000`

### High Memory Usage

- Adjust `max_memory_restart` in ecosystem.config.js
- Monitor with: `pm2 monit`

### Process Keeps Restarting

- Check logs for errors: `pm2 logs`
- Increase `min_uptime` in ecosystem.config.js if process crashes immediately
- Check `max_restarts` setting

## Security Recommendations

1. **Environment Variables**: Never commit `.env` files
2. **API Keys**: Use strong, random strings for `ADMIN_API_KEY`
3. **Firewall**: Only expose necessary ports (80, 443)
4. **HTTPS**: Use SSL certificates (Let's Encrypt)
5. **User Permissions**: Run PM2 as non-root user
6. **Updates**: Keep dependencies updated regularly

## Backup

Regularly backup:
- Database files: `server/data/*.db`
- Environment configurations: `.env` files
- PM2 process list: `pm2 save`

## Monitoring & Logs

Set up log rotation to prevent disk space issues:

```bash
pm2 install pm2-logrotate
pm2 set pm2-logrotate:max_size 10M
pm2 set pm2-logrotate:retain 7
```


## Extra
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

## PyPI Account Setup (One-Time)

### 1. Create PyPI Accounts

**TestPyPI (for testing):**
- URL: https://test.pypi.org/account/register/
- Enable 2FA (recommended)

**Production PyPI:**
- URL: https://pypi.org/account/register/
- Enable 2FA (REQUIRED for new projects)

### 2. Generate API Tokens

**TestPyPI Token:**
1. Login to https://test.pypi.org
2. Account Settings → API tokens → "Add API token"
3. Name: `ryumem-test-upload`
4. Scope: "Entire account" (for first upload, can scope to project after)
5. **Save token immediately** (shown only once)

**Production PyPI Token:**
1. Login to https://pypi.org
2. Account Settings → API tokens → "Add API token"
3. Name: `ryumem-production-upload`
4. Scope: "Entire account" (for first upload, can scope to project after)
5. **Save token** (shown only once)

### 3. Configure ~/.pypirc

Create `~/.pypirc` with tokens:

```bash
cat > ~/.pypirc << 'EOF'
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-YOUR-PRODUCTION-TOKEN-HERE

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-YOUR-TEST-TOKEN-HERE
EOF

chmod 600 ~/.pypirc
```

## Build Process

### 1. Install Build Tools

```bash
cd /Users/saksham115/Projects/Predictable/ryumem
source .venv/bin/activate  # Or create new venv

pip install --upgrade pip build twine
```

### 2. Clean Previous Builds

```bash
rm -rf build/ dist/ *.egg-info src/*.egg-info
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete
```

### 3. Build Distributions

```bash
python -m build
```

This creates:
- `dist/ryumem-0.1.0-py3-none-any.whl` (wheel)
- `dist/ryumem-0.1.0.tar.gz` (source distribution)

### 4. Verify Build

```bash
# Check package compliance
twine check dist/*

# List wheel contents
unzip -l dist/ryumem-0.1.0-py3-none-any.whl

# Test local installation
python -m venv test_venv
source test_venv/bin/activate
pip install dist/ryumem-0.1.0-py3-none-any.whl
python -c "from ryumem import Ryumem; print('✅ Import successful')"
deactivate
rm -rf test_venv
```

## Upload Process

### 1. Upload to TestPyPI (RECOMMENDED FIRST)

```bash
twine upload --repository testpypi dist/*
```

### 2. Verify TestPyPI Upload

```bash
# View package page
open https://test.pypi.org/project/ryumem/

# Test installation
python -m venv testpypi_venv
source testpypi_venv/bin/activate

# Install from TestPyPI with production PyPI as fallback for dependencies
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            ryumem

python -c "from ryumem import Ryumem; print('✅ TestPyPI install successful')"
deactivate
rm -rf testpypi_venv
```

### 3. Upload to Production PyPI

**⚠️ WARNING: This is permanent - versions cannot be deleted or modified**

```bash
twine upload dist/*
```

### 4. Verify Production Upload

```bash
# View package page
open https://pypi.org/project/ryumem/

# Test installation
python -m venv pypi_venv
source pypi_venv/bin/activate
pip install ryumem
python -c "from ryumem import Ryumem; print('✅ PyPI install successful')"

# Test optional dependencies
pip install ryumem[google-adk]
python -c "from ryumem.integrations import add_memory_to_agent; print('✅ Google ADK integration available')"

deactivate
rm -rf pypi_venv
```

## Post-Release Tasks

### 1. Git Tagging

```bash
cd /Users/saksham115/Projects/Predictable/ryumem

git add LICENSE MANIFEST.in pyproject.toml examples/
git commit -m "Prepare for v0.1.0 PyPI release

- Add LICENSE file
- Reorganize examples into categories
- Fix repository URLs
- Add missing dependencies (requests, google-genai)
- Create optional google-adk dependency group
- Add MANIFEST.in for package distribution
"

git push origin main

git tag -a v0.1.0 -m "Release v0.1.0 - First PyPI release

Features:
- Bi-temporal knowledge graph memory system
- Google ADK integration with zero-boilerplate setup
- Automatic tool tracking and query augmentation
- Hybrid search (semantic, BM25, graph traversal)
- Multi-tenancy support
- Client/server architecture
"

git push origin v0.1.0
```

### 2. Create GitHub Release

```bash
gh release create v0.1.0 \
  --title "v0.1.0 - First PyPI Release" \
  --notes "# Ryumem v0.1.0

🎉 First release on PyPI!

## Installation

\`\`\`bash
pip install ryumem
\`\`\`

For Google ADK integration:
\`\`\`bash
pip install ryumem[google-adk]
\`\`\`

## Key Features

- **Bi-temporal Knowledge Graph**: Episode-first ingestion with automatic entity extraction
- **Zero-Boilerplate Integrations**: Add memory to Google ADK agents with one line
- **Query Augmentation**: Automatically enrich queries with relevant historical context
- **Tool Tracking**: Automatic tracking of all tool executions
- **Hybrid Search**: Semantic, BM25, and graph traversal combined
- **Multi-tenancy**: Isolated memory graphs per user/customer

## Documentation

- [README](https://github.com/predictable-labs/ryumem#readme)
- [Examples](https://github.com/predictable-labs/ryumem/tree/main/examples)
- [PyPI Package](https://pypi.org/project/ryumem/)

## What's Included

- Python SDK (\`src/ryumem/\`)
- Google ADK integration
- Tool tracking and query augmentation
- 12 example scripts organized by use case
- Comprehensive documentation
"
```

### 3. Update README (Optional Enhancements)

Add PyPI badges at the top of README.md:

```markdown
# Ryumem

[![PyPI version](https://badge.fury.io/py/ryumem.svg)](https://badge.fury.io/py/ryumem)
[![Python versions](https://img.shields.io/pypi/pyversions/ryumem.svg)](https://pypi.org/project/ryumem/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[Rest of README...]
```

## Summary of Files Modified

1. **pyproject.toml** - Add missing dependencies, fix URLs, add optional dependencies
2. **LICENSE** - Create MIT license file
3. **MANIFEST.in** - Create package manifest
4. **examples/** - Reorganize into subdirectories with README
5. **README.md** - Add PyPI badges (optional)

## Verification Checklist

Before uploading to PyPI, verify:

- [ ] All dependencies in `pyproject.toml` are available on PyPI
- [ ] `ryugraph` version updated to `>=25.9.0` (not `>=0.1.0`)
- [ ] LICENSE file exists and is correct
- [ ] Repository URLs point to correct GitHub repo (predictable-labs, not ryumem)
- [ ] README displays correctly on PyPI (check with `twine check`)
- [ ] Examples are properly organized and documented
- [ ] Version number is correct (0.1.0)
- [ ] Build succeeds without warnings
- [ ] Local installation test passes
- [ ] TestPyPI upload successful
- [ ] TestPyPI installation test passes

## Quick Command Reference

```bash
# Complete release workflow
cd /Users/saksham115/Projects/Predictable/ryumem

# 1. Make pre-release changes
# (Update files as described above)

# 2. Clean and build
rm -rf build/ dist/ *.egg-info src/*.egg-info
python -m build
twine check dist/*

# 3. Test upload
twine upload --repository testpypi dist/*

# 4. Production upload (after verification)
twine upload dist/*

# 5. Post-release
git add LICENSE MANIFEST.in pyproject.toml examples/
git commit -m "Prepare for v0.1.0 PyPI release"
git push origin main
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
gh release create v0.1.0 --title "v0.1.0 - First PyPI Release"
```

## Critical Dependency Check

**✅ VERIFIED:** `ryugraph` exists on PyPI with versions 25.9.0 and 25.9.1

**⚠️ ACTION REQUIRED:** Update `pyproject.toml` to specify correct version:
- Change `ryugraph>=0.1.0` to `ryugraph>=25.9.0`
- The version `0.1.0` doesn't exist on PyPI and will cause installation failures

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