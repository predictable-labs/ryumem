# Ryumem Examples

This directory contains examples demonstrating various features and integrations of Ryumem.

## Prerequisites

### 1. Running Server

All examples require a running Ryumem API server:

```bash
# Start the server
cd server
cp .env.example .env
# Edit .env and add your LLM API key
uvicorn main:app --reload
```

### 2. Get an API Key

Register a customer to get an API key:

```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "my_company"}'
```

### 3. Install SDK

```bash
# From PyPI
pip install ryumem

# Or from source (project root)
pip install -e .
```

### 4. Configure Environment

```bash
cd examples
cp .env.example .env
# Edit .env with your configuration
```

**Required environment variables:**

| Variable | Description |
|----------|-------------|
| `RYUMEM_API_URL` | API server URL (e.g., `http://localhost:8000`) |
| `RYUMEM_API_KEY` | Your API key (starts with `ryu_`) |
| `GOOGLE_API_KEY` | Google Gemini API key (for ADK examples) |

## Getting Started

Start with these examples to learn the basics:

| Example | Description |
|---------|-------------|
| [basic_usage.py](getting-started/basic_usage.py) | Standalone local usage with in-memory graph |
| [client_usage.py](getting-started/client_usage.py) | Connect to a Ryumem server via API |
| [advanced_usage.py](getting-started/advanced_usage.py) | Advanced SDK features and configurations |

## Framework Integrations

### Google ADK

Zero-boilerplate memory integration for Google ADK agents:

| Example | Description |
|---------|-------------|
| [google_adk_usage.py](integrations/google-adk/google_adk_usage.py) | Complete integration with multi-user isolation |
| [simple_tool_tracking_demo.py](integrations/google-adk/simple_tool_tracking_demo.py) | Automatic tool tracking and query augmentation |
| [async_tool_tracking_demo.py](integrations/google-adk/async_tool_tracking_demo.py) | Async tool tracking with concurrent operations |
| [password_guessing_game.py](integrations/google-adk/password_guessing_game.py) | Advanced query augmentation demo |

**Additional setup:**
```bash
pip install ryumem[google-adk]
export GOOGLE_API_KEY="your-google-api-key"
```

### LiteLLM

Use any LLM provider (100+ providers supported):

| Example | Description |
|---------|-------------|
| [litellm_usage.py](integrations/litellm/litellm_usage.py) | Basic LiteLLM integration |
| [litellm_simple_tool_tracking.py](integrations/litellm/litellm_simple_tool_tracking.py) | Tool tracking with LiteLLM |

### Ollama

Local LLM usage with Ollama:

| Example | Description |
|---------|-------------|
| [ollama_usage.py](integrations/ollama/ollama_usage.py) | Run Ryumem with local Ollama models |

**Additional setup:**
```bash
# Install Ollama from https://ollama.ai
ollama pull llama2  # or your preferred model
```

## Running Examples

Each example is self-contained:

```bash
cd examples
python getting-started/basic_usage.py
```

For client examples, ensure the server is running:

```bash
# Terminal 1 - Start server
cd server
uvicorn main:app --reload

# Terminal 2 - Run example
cd examples
python getting-started/client_usage.py
```

## Directory Structure

```
examples/
├── README.md                      # This file
├── .env.example                   # Environment template
├── getting-started/               # Basic SDK usage
│   ├── basic_usage.py
│   ├── client_usage.py
│   └── advanced_usage.py
├── integrations/                  # Framework integrations
│   ├── google-adk/
│   │   ├── google_adk_usage.py
│   │   ├── simple_tool_tracking_demo.py
│   │   ├── async_tool_tracking_demo.py
│   │   └── password_guessing_game.py
│   ├── litellm/
│   │   ├── litellm_usage.py
│   │   └── litellm_simple_tool_tracking.py
│   └── ollama/
│       └── ollama_usage.py
└── tests/                         # Testing examples
    ├── test_async_wrapper.py
    └── test_deduplication.py
```

## License

Apache License 2.0 - See [LICENSE](../LICENSE) for details.
