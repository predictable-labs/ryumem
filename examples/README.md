# Ryumem Examples

This directory contains examples demonstrating various features and integrations of Ryumem.

## Getting Started

Start with these examples to learn the basics:

- **[basic_usage.py](getting-started/basic_usage.py)** - Standalone local usage with in-memory graph
- **[client_usage.py](getting-started/client_usage.py)** - Connect to a Ryumem server via API
- **[advanced_usage.py](getting-started/advanced_usage.py)** - Advanced SDK features and configurations

## Framework Integrations

### Google ADK

Zero-boilerplate memory integration for Google ADK agents:

- **[google_adk_usage.py](integrations/google-adk/google_adk_usage.py)** - Complete integration example with multi-user isolation
- **[simple_tool_tracking_demo.py](integrations/google-adk/simple_tool_tracking_demo.py)** - Automatic tool tracking and query augmentation
- **[async_tool_tracking_demo.py](integrations/google-adk/async_tool_tracking_demo.py)** - Async tool tracking with concurrent operations
- **[password_guessing_game.py](integrations/google-adk/password_guessing_game.py)** - Advanced query augmentation demo

### LiteLLM

Use any LLM provider (100+ providers supported):

- **[litellm_usage.py](integrations/litellm/litellm_usage.py)** - Basic LiteLLM integration
- **[litellm_simple_tool_tracking.py](integrations/litellm/litellm_simple_tool_tracking.py)** - Tool tracking with LiteLLM

### Ollama

Local LLM usage with Ollama:

- **[ollama_usage.py](integrations/ollama/ollama_usage.py)** - Run Ryumem with local Ollama models

## Tests

Example test files demonstrating testing patterns:

- **[test_async_wrapper.py](tests/test_async_wrapper.py)** - Testing async operations
- **[test_deduplication.py](tests/test_deduplication.py)** - Testing duplicate detection

## Prerequisites

### Basic Installation

All examples require:

```bash
pip install ryumem
```

### Google ADK Examples

For Google ADK integration examples:

```bash
pip install ryumem[google-adk]
export GOOGLE_API_KEY="your-google-api-key"
```

Optional (for better embeddings):
```bash
export OPENAI_API_KEY="your-openai-api-key"
```

### LiteLLM Examples

```bash
export OPENAI_API_KEY="your-api-key"
# OR set credentials for your preferred provider
```

### Ollama Examples

Requires Ollama running locally:

```bash
# Install Ollama from https://ollama.ai
ollama pull llama2  # or your preferred model
```

## Running Examples

Each example is self-contained and can be run directly:

```bash
cd examples
python getting-started/basic_usage.py
```

For client examples, ensure a Ryumem server is running:

```bash
# In one terminal - start the server
cd server
python main.py

# In another terminal - run the client example
cd examples
python getting-started/client_usage.py
```

## Example Structure

```
examples/
├── README.md                          # This file
├── getting-started/                   # Basic SDK usage
├── integrations/                      # Framework-specific examples
│   ├── google-adk/                   # Google ADK integration
│   ├── litellm/                      # LiteLLM integration
│   └── ollama/                       # Ollama integration
└── tests/                             # Testing examples
```

## Need Help?

- [Main README](../README.md) - Full documentation
- [GitHub Issues](https://github.com/predictable-labs/ryumem/issues) - Report bugs or request features
- [PyPI Package](https://pypi.org/project/ryumem/) - Latest release information
