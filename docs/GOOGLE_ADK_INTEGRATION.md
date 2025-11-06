# Google ADK Integration Guide

## Overview

Ryumem provides **zero-boilerplate** memory integration with Google's Agent Developer Kit (ADK). Unlike other solutions that require you to write custom functions, Ryumem automatically generates and registers memory tools for your agents.

## Why Ryumem > mem0 for Google ADK?

| Feature | mem0 | Ryumem |
|---------|------|--------|
| **Setup Code** | ~20 lines of boilerplate | **1 line** |
| **Custom Functions** | Must write search_memory() and save_memory() | **Auto-generated** |
| **Tool Registration** | Manual | **Automatic** |
| **Memory Structure** | Flat key-value | **Knowledge Graph** |
| **Local LLM Support** | Limited | **Full Ollama support** |
| **Offline Mode** | No | **Yes (with local embeddings)** |

## Quick Start

### Installation

```bash
# Install dependencies
pip install google-genai ryumem python-dotenv

# Set your Google API key
export GOOGLE_API_KEY="your-google-api-key"
```

### Basic Usage (1 Line!)

```python
from google import genai
from ryumem.integrations import enable_memory

# Create your agent
agent = genai.Agent(
    name="assistant",
    model="gemini-2.0-flash-exp",
    instruction="You are a helpful assistant with memory."
)

# Enable memory - that's it!
enable_memory(agent, user_id="user_123")
```

## What Gets Auto-Generated?

When you call `enable_memory()`, Ryumem automatically creates and registers **3 tools** with your agent:

### 1. `search_memory(query: str, limit: int = 5)`
Searches the knowledge graph for relevant memories.

**Returns:**
```python
{
    "status": "success",
    "count": 3,
    "memories": [
        {
            "fact": "Alice works at Google",
            "score": 0.95,
            "source": "alice",
            "target": "google"
        },
        # ...
    ]
}
```

### 2. `save_memory(content: str, source: str = "google_adk")`
Saves information to the knowledge graph.

**Returns:**
```python
{
    "status": "success",
    "episode_id": "abc123...",
    "message": "Memory saved successfully"
}
```

### 3. `get_entity_context(entity_name: str)`
Retrieves full context about a specific entity.

**Returns:**
```python
{
    "status": "success",
    "entity": "alice",
    "context": "Alice is a person who works at Google..."
}
```

## Advanced Usage

### Multi-Agent Memory Sharing

Multiple agents can share the same memory by using the same `user_id`:

```python
from google import genai
from ryumem.integrations import enable_memory

# Agent 1: Personal Assistant
personal_agent = genai.Agent(name="assistant", model="gemini-2.0-flash-exp")
enable_memory(personal_agent, user_id="user_123", db_path="./shared_memory.db")

# Agent 2: Travel Planner (shares memory!)
travel_agent = genai.Agent(name="travel_planner", model="gemini-2.0-flash-exp")
enable_memory(travel_agent, user_id="user_123", db_path="./shared_memory.db")

# Both agents access the same knowledge graph
```

### Using Local LLMs (Ollama)

For privacy and cost savings, use Ollama for LLM operations:

```python
enable_memory(
    agent,
    user_id="user_123",
    db_path="./memory.db",
    llm_provider="ollama",
    llm_model="qwen2.5:7b",
    ollama_base_url="http://localhost:11434"
)
```

### Direct Memory Access

The `enable_memory()` function returns a `RyumemGoogleADK` instance for advanced usage:

```python
memory = enable_memory(agent, user_id="user_123")

# Direct search
results = memory.search_memory("What's Alice's job?", limit=5)
print(results)

# Direct save
memory.save_memory("Bob likes pizza", source="manual")

# Get entity context
context = memory.get_entity_context("alice")
print(context)
```

### Using Pre-configured Ryumem Instance

If you need fine-grained control over Ryumem configuration:

```python
from ryumem import Ryumem
from ryumem.integrations import enable_memory

# Create custom Ryumem instance
ryumem = Ryumem(
    db_path="./memory.db",
    llm_provider="ollama",
    llm_model="qwen2.5:7b",
    embedding_model="text-embedding-3-small",
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

# Use it with your agent
enable_memory(agent, user_id="user_123", ryumem_instance=ryumem)
```

## Complete Example

See [examples/google_adk_usage.py](../examples/google_adk_usage.py) for a full working example that demonstrates:
- Creating agents with memory
- Multi-agent memory sharing
- Direct memory access
- Conversation with memory recall

## Agent Instructions Best Practices

Help your agent use memory effectively with clear instructions:

```python
agent = genai.Agent(
    name="assistant",
    model="gemini-2.0-flash-exp",
    instruction="""You are a helpful assistant with long-term memory.

MEMORY GUIDELINES:
1. When users share personal information, use save_memory() to remember it
2. Before answering questions, use search_memory() to check what you know
3. Use get_entity_context() to learn more about specific people/places/things
4. Always personalize responses based on remembered information
5. If you're unsure, search your memory first

Examples:
- User: "My name is Alice" → save_memory("User's name is Alice")
- User: "What's my name?" → search_memory("user's name")
- User: "Tell me about Alice" → get_entity_context("alice")
"""
)
```

## Comparison: mem0 vs Ryumem

### mem0 Approach (Boilerplate Required)

```python
from mem0 import MemoryClient

mem0 = MemoryClient(api_key="...")

# User must write these functions manually
def search_memory(query: str, user_id: str):
    results = mem0.search(query, filters={"user_id": user_id})
    if results:
        return {"memories": results}
    return {"no_memories": True}

def save_memory(content: str, user_id: str):
    mem0.add([{"role": "user", "content": content}], user_id=user_id)
    return {"status": "success"}

# Manual tool registration
agent = Agent(
    name="assistant",
    model="gemini-2.0-flash",
    tools=[search_memory, save_memory]  # Must pass manually
)
```

### Ryumem Approach (Zero Boilerplate)

```python
from ryumem.integrations import enable_memory

agent = Agent(name="assistant", model="gemini-2.0-flash")

# One line - done!
enable_memory(agent, user_id="user_123")
```

**Result:** Ryumem eliminates ~20 lines of boilerplate and reduces setup time from minutes to seconds.

## Troubleshooting

### Agent doesn't use memory tools

**Solution:** Update your agent's instruction to explicitly mention memory usage:

```python
instruction="""Use search_memory() to recall information and
save_memory() to remember new information."""
```

### "Agent doesn't have 'tools' attribute"

This warning means your agent object doesn't have a `tools` attribute. Ryumem will create it automatically, but verify your Google ADK version is up to date:

```bash
pip install --upgrade google-genai
```

### Memory not persisting between runs

Make sure you're using the same `db_path` across runs:

```python
# Always use the same path
enable_memory(agent, user_id="user_123", db_path="./persistent_memory.db")
```

## Next Steps

- **Multi-language support**: We're adding TypeScript/JavaScript support next
- **More integrations**: LangChain, LlamaIndex, and Vercel AI SDK coming soon
- **Local embeddings**: Eliminate OpenAI dependency completely

## Feedback & Contributions

Found a bug or have a feature request? Open an issue on [GitHub](https://github.com/yourusername/ryumem).

Want to contribute? PRs welcome! See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.
