# Ryumem MCP Server (TypeScript)

A thin TypeScript wrapper MCP server for the Ryumem API.

## Installation

```bash
npm install
npm run build
```

## Configuration

The server requires an API key to connect to the Ryumem API:

```bash
export RYUMEM_API_KEY="your-api-key-here"
```

By default, the server connects to `https://api.ryumem.io`. To use a different endpoint:

```bash
export RYUMEM_API_URL="http://localhost:8000"
```

## Usage with Claude Desktop

Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "ryumem": {
      "command": "node",
      "args": ["/path/to/ryumem/mcp-server-ts/build/index.js"],
      "env": {
        "RYUMEM_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

Or if you want to use a local API:

```json
{
  "mcpServers": {
    "ryumem": {
      "command": "node",
      "args": ["/path/to/ryumem/mcp-server-ts/build/index.js"],
      "env": {
        "RYUMEM_API_URL": "http://localhost:8000",
        "RYUMEM_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

## Available Tools

- `search_memory` - Multi-strategy semantic search across the knowledge graph
- `add_episode` - Save new episodic memory
- `get_entity_context` - Retrieve entity details and relationships
- `list_episodes` - Paginated episode listing with filters
- `get_episode` - Retrieve specific episode by UUID
- `update_episode_metadata` - Update metadata on existing episode
- `prune_memories` - Clean up expired and low-value memories

## Development

Watch mode for development:

```bash
npm run watch
```

## Architecture

This is a thin wrapper that makes HTTP API calls to the Ryumem backend. It does not contain any business logic - all memory operations are handled by the Ryumem API server.
