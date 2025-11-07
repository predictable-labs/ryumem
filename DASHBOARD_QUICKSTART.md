# Ryumem Dashboard & API Quick Start

This guide will help you set up and run the complete Ryumem dashboard and API server.

## Architecture Overview

```
┌─────────────────────┐
│  Next.js Dashboard  │  (Port 3000)
│  User Interface     │
└──────────┬──────────┘
           │ HTTP REST API
           ▼
┌─────────────────────┐
│  FastAPI Server     │  (Port 8000)
│  API Layer          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Ryumem Core        │
│  Knowledge Graph    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  SQLite Database    │
│  (Ryugraph)         │
└─────────────────────┘
```

## Prerequisites

- **Python 3.11+** with pip
- **Node.js 18+** with npm
- **OpenAI API Key** (for embeddings and LLM)
- **Optional**: Ollama for local LLM inference

## Quick Start (5 minutes)

### Step 1: Set up the API Server

```bash
# Navigate to server directory
cd server

# Install Python dependencies
pip install -r requirements.txt

# Install Ryumem core from parent directory
cd ..
pip install -e .
cd server

# Create environment file
cp env.template .env

# Edit .env and add your OpenAI API key
nano .env
```

Required `.env` configuration:
```bash
OPENAI_API_KEY=sk-your-key-here
RYUMEM_LLM_PROVIDER=openai
RYUMEM_LLM_MODEL=gpt-4o-mini
```

### Step 2: Start the API Server

```bash
# Start the FastAPI server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Starting Ryumem server...
INFO:     Ryumem initialized successfully
```

✅ API is now running at **http://localhost:8000**
- Interactive docs: http://localhost:8000/docs

### Step 3: Set up the Dashboard

Open a **new terminal** (keep the API server running):

```bash
# Navigate to dashboard directory
cd dashboard

# Install dependencies
npm install

# Create environment file
cp env.template .env.local

# No need to edit - default points to localhost:8000
```

### Step 4: Start the Dashboard

```bash
# Start the Next.js development server
npm run dev
```

You should see:
```
  ▲ Next.js 14.2.15
  - Local:        http://localhost:3000
  - Ready in 2.3s
```

✅ Dashboard is now running at **http://localhost:3000**

## First Time Usage

### 1. Open the Dashboard

Navigate to **http://localhost:3000** in your browser.

### 2. Add Your First Episode

1. Click on the **"Add Episodes"** tab
2. Try one of the example episodes or enter your own:
   ```
   Alice works at Google as a Software Engineer in Mountain View.
   ```
3. Click **"Add Episode"**
4. Wait a few seconds for processing

### 3. Query Your Knowledge

1. Click on the **"Chat & Query"** tab
2. Try a query:
   ```
   Where does Alice work?
   ```
3. Click search or press Enter
4. View the results!

### 4. Add More Data

Try adding more episodes to build your knowledge graph:

```
Bob graduated from Stanford University in 2020 with a degree in Computer Science.
Alice and Bob are colleagues and often collaborate on machine learning projects.
Google is headquartered in Mountain View, California.
```

Then search:
```
Who works at Google?
What did Bob study?
Tell me about machine learning projects
```

## Using Ollama (Local LLMs)

For cost savings and privacy, use local models via Ollama:

### Install Ollama

```bash
# macOS
brew install ollama

# Or download from https://ollama.ai
```

### Start Ollama and Pull a Model

```bash
# Start Ollama service
ollama serve

# In a new terminal, pull a recommended model
ollama pull qwen2.5:7b    # Best for structured output
# or
ollama pull llama3.2:3b   # Faster, still good
```

### Configure Server to Use Ollama

Edit `server/.env`:
```bash
OPENAI_API_KEY=sk-your-key-here  # Still needed for embeddings
RYUMEM_LLM_PROVIDER=ollama
RYUMEM_LLM_MODEL=qwen2.5:7b
RYUMEM_OLLAMA_BASE_URL=http://localhost:11434
```

Restart the server:
```bash
# Stop current server (Ctrl+C)
# Start again
uvicorn main:app --reload
```

Now LLM inference is **free** and **private**! 🎉

## Troubleshooting

### "Connection refused" error in dashboard

**Problem**: Dashboard can't connect to API server

**Solution**:
1. Make sure API server is running on port 8000
2. Check `dashboard/.env.local` has correct API URL
3. Verify CORS settings in `server/main.py`

```bash
# Test API manually
curl http://localhost:8000/health
```

### "OpenAI API error"

**Problem**: Invalid or missing API key

**Solution**:
1. Check `server/.env` has valid `OPENAI_API_KEY`
2. Verify key starts with `sk-`
3. Check your OpenAI account has credits

### "No results found" when searching

**Problem**: Knowledge graph is empty

**Solution**:
1. Add episodes first using "Add Episodes" tab
2. Wait a few seconds after adding
3. Check API server logs for errors

### Port already in use

**Problem**: Port 8000 or 3000 is busy

**Solution**:
```bash
# API Server - use different port
uvicorn main:app --reload --port 8001

# Update dashboard/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8001

# Dashboard - use different port
npm run dev -- -p 3001
```

## Production Deployment

### API Server

```bash
# Install production dependencies
pip install gunicorn

# Run with multiple workers
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Dashboard

```bash
# Build for production
cd dashboard
npm run build

# Start production server
npm start
```

Or deploy to:
- **Vercel** (recommended for Next.js)
- **Railway**
- **Fly.io**
- **Docker**

## API Endpoints Reference

Once the server is running, explore the API:

- **Interactive Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

Key endpoints:
- `POST /episodes` - Add new episode
- `POST /search` - Search knowledge graph
- `GET /entity/{name}` - Get entity context
- `GET /stats` - Get statistics
- `POST /communities/update` - Detect communities
- `POST /prune` - Prune memories

## Next Steps

1. **Explore the API**: http://localhost:8000/docs
2. **Read the Docs**:
   - [Server README](server/README.md)
   - [Dashboard README](dashboard/README.md)
   - [Main README](README.md)
3. **Customize**: Modify components and add features
4. **Deploy**: Take it to production!

## Development Tips

### Auto-reload

Both servers support auto-reload:
- **API**: Saves automatically reload the server
- **Dashboard**: File changes instantly reflect in browser

### View Logs

```bash
# API Server logs
# Displayed in terminal where you ran uvicorn

# Dashboard logs
# Check browser console (F12)
```

### Database Location

SQLite database is stored at:
```
server/data/ryumem_server.db
```

To reset:
```bash
rm server/data/ryumem_server.db
# Restart server to recreate
```

## Support & Resources

- **Main Docs**: [README.md](README.md)
- **API Docs**: [server/README.md](server/README.md)
- **Dashboard Docs**: [dashboard/README.md](dashboard/README.md)
- **API Reference**: http://localhost:8000/docs (when running)

## Common Workflows

### Workflow 1: Building a Knowledge Base

```bash
# 1. Add multiple episodes
curl -X POST http://localhost:8000/episodes \
  -H "Content-Type: application/json" \
  -d '{"content": "...", "group_id": "user_123"}'

# 2. Detect communities
curl -X POST http://localhost:8000/communities/update \
  -H "Content-Type: application/json" \
  -d '{"group_id": "user_123"}'

# 3. Search
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "...", "group_id": "user_123"}'
```

### Workflow 2: Maintenance

```bash
# Prune old memories
curl -X POST http://localhost:8000/prune \
  -H "Content-Type: application/json" \
  -d '{"group_id": "user_123", "expired_cutoff_days": 90}'

# Get stats
curl http://localhost:8000/stats?group_id=user_123
```

---

**Happy building with Ryumem! 🧠💾**

