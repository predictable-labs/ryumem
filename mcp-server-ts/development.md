# Development Guide

## Building from Source

```bash
cd mcp-server-ts
npm install
npm run build
```

## Local Development Setup

### Using npm link

After building, you can create a global symlink:

```bash
npm link
```

This makes the `ryumem-mcp` command available globally on your system.

### Using Local Build with Claude

```json
{
  "mcpServers": {
    "ryumem": {
      "command": "node",
      "args": ["/path/to/ryumem/mcp-server-ts/build/index.js"],
      "env": {
        "RYUMEM_API_URL": "https://api.ryumem.io"
      }
    }
  }
}
```

### Using npm link with Claude

```json
{
  "mcpServers": {
    "ryumem": {
      "command": "ryumem-mcp",
      "env": {
        "RYUMEM_API_URL": "https://api.ryumem.io"
      }
    }
  }
}
```

## Build Commands

### Build

```bash
npm run build
```

### Watch Mode

```bash
npm run watch
```

## Project Structure

```
mcp-server-ts/
├── src/
│   ├── index.ts       # MCP server entry point
│   ├── client.ts      # Ryumem API client
│   ├── auth.ts        # Authentication (device flow, API keys)
│   ├── tools.ts       # MCP tool definitions
│   └── install.ts     # CLI installer
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

## Troubleshooting

**"Connection refused"**
- Ensure the Ryumem API server is running
- Check `RYUMEM_API_URL` is correct

**"Unauthorized"**
- Verify your API key is correct
- Check authentication via `ryumem-mcp install`

**MCP server not appearing in Claude**
- Check JSON syntax in config file
- Restart Claude Desktop
- Check Claude logs for errors
