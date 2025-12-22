# Ryumem MCP Server

A TypeScript MCP (Model Context Protocol) server for integrating Ryumem with Claude Desktop and other AI coding agents.

## Installation

### From npm

```bash
npm install -g @predictable/ryumem-mcp-server
```

### From Source

```bash
cd mcp-server-ts
npm install
npm run build
```

## Configuration

The server requires environment variables to connect to your Ryumem API:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `RYUMEM_API_URL` | Yes | `http://localhost:8000` | Ryumem API server URL |
| `RYUMEM_API_KEY` | Yes | - | Your API key (starts with `ryu_`) |

## Claude Desktop Setup

Add to your Claude Desktop configuration:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**Linux:** `~/.config/Claude/claude_desktop_config.json`

### Using npm package

```json
{
  "mcpServers": {
    "ryumem": {
      "command": "npx",
      "args": ["@predictable/ryumem-mcp-server"],
      "env": {
        "RYUMEM_API_URL": "http://localhost:8000",
        "RYUMEM_API_KEY": "ryu_your_api_key_here"
      }
    }
  }
}
```

### Using local build

```json
{
  "mcpServers": {
    "ryumem": {
      "command": "node",
      "args": ["/path/to/ryumem/mcp-server-ts/build/index.js"],
      "env": {
        "RYUMEM_API_URL": "http://localhost:8000",
        "RYUMEM_API_KEY": "ryu_your_api_key_here"
      }
    }
  }
}
```

After updating the config, restart Claude Desktop.

## Claude Code Setup

For Claude Code (CLI), add to your configuration:

```json
{
  "mcpServers": {
    "ryumem": {
      "command": "node",
      "args": ["/path/to/ryumem/mcp-server-ts/build/index.js"],
      "env": {
        "RYUMEM_API_URL": "http://localhost:8000",
        "RYUMEM_API_KEY": "ryu_your_api_key_here"
      }
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `search_memory` | Multi-strategy semantic search across the knowledge graph |
| `add_episode` | Save new episodic memory |
| `get_entity_context` | Retrieve entity details and relationships |
| `batch_add_episodes` | Add multiple episodes at once |
| `list_episodes` | Paginated episode listing with filters |
| `get_episode` | Retrieve specific episode by UUID |
| `update_episode_metadata` | Update metadata on existing episode |
| `prune_memories` | Clean up expired and low-value memories |
| `execute_cypher` | Execute custom Cypher queries |

### Tool Examples

**Search Memory:**
```
Search for information about Alice's work history
```

**Add Episode:**
```
Remember that Alice joined Google as a software engineer in 2023
```

**Get Entity Context:**
```
Get all information about the entity "Alice"
```

## Development

### Build

```bash
npm run build
```

### Watch Mode

```bash
npm run watch
```

### Project Structure

```
mcp-server-ts/
├── src/
│   └── index.ts       # MCP server implementation
├── build/             # Compiled JavaScript
├── package.json
└── tsconfig.json
```

## Architecture

This is a thin wrapper that makes HTTP API calls to the Ryumem backend. It does not contain any business logic - all memory operations are handled by the Ryumem API server.

```
+------------------+     +------------------+     +------------------+
| Claude Desktop   | --> | MCP Server       | --> | Ryumem API       |
| or Claude Code   |     | (This package)   |     | (FastAPI)        |
+------------------+     +------------------+     +------------------+
```

## Getting an API Key

1. Start the Ryumem API server (see [server/README.md](../server/README.md))
2. Register a customer:
   ```bash
   curl -X POST http://localhost:8000/register \
     -H "Content-Type: application/json" \
     -d '{"customer_id": "my_company"}'
   ```
3. Use the returned API key in your configuration

## Troubleshooting

**"Connection refused"**
- Ensure the Ryumem API server is running
- Check `RYUMEM_API_URL` is correct

**"Unauthorized"**
- Verify your `RYUMEM_API_KEY` is correct
- Register a new customer if needed

**MCP server not appearing in Claude**
- Check JSON syntax in config file
- Restart Claude Desktop
- Check Claude logs for errors

## License

Apache License 2.0 - See [LICENSE](../LICENSE) for details.
