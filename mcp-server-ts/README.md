# Ryumem MCP Server

MCP server for integrating Ryumem memory with Claude and AI coding agents.

## Quick Start

### Install for Claude Code

```bash
npx @predictable/ryumem-mcp-server install --oauth
```

This will:
1. Authenticate with your Ryumem account via GitHub (opens browser)
2. Configure Claude Code automatically

### Install for Claude Desktop

```bash
npx @predictable/ryumem-mcp-server install --oauth --client claude-desktop
```

### Uninstall

```bash
npx @predictable/ryumem-mcp-server uninstall
```

## Manual Configuration

If you prefer manual setup, add to your Claude configuration file:

**Claude Code:** `~/.claude/claude_code_config.json`
**Claude Desktop (macOS):** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Claude Desktop (Windows):** `%APPDATA%\Claude\claude_desktop_config.json`
**Claude Desktop (Linux):** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "ryumem": {
      "command": "npx",
      "args": ["@predictable/ryumem-mcp-server"],
      "env": {
        "RYUMEM_API_KEY": "ryu_your_api_key_here"
      }
    }
  }
}
```

## CLI Options

```bash
npx @predictable/ryumem-mcp-server install [options]
```

| Option | Description |
|--------|-------------|
| `--oauth` | Authenticate via GitHub OAuth (default, recommended) |
| `--api-key <key>` | Use a specific API key instead of OAuth |
| `--api-url <url>` | Custom API URL (default: `https://api.ryumem.io`) |
| `--client <name>` | Target client: `claude-code` (default) or `claude-desktop` |

### Examples

```bash
# OAuth authentication (recommended)
npx @predictable/ryumem-mcp-server install --oauth

# Use existing API key
npx @predictable/ryumem-mcp-server install --api-key ryu_xxxxx

# Configure for Claude Desktop
npx @predictable/ryumem-mcp-server install --oauth --client claude-desktop

# Use custom API server
npx @predictable/ryumem-mcp-server install --oauth --api-url http://localhost:8000
```

## Available Tools

| Tool | Description |
|------|-------------|
| `search_memory` | Multi-strategy semantic search across the knowledge graph |
| `add_episode` | Save new episodic memory |
| `get_entity_context` | Retrieve entity details and relationships |
| `list_episodes` | Paginated episode listing with filters |
| `get_episode` | Retrieve specific episode by UUID |
| `update_episode_metadata` | Update metadata on existing episode |
| `prune_memories` | Clean up old or redundant memories |

## License

Apache 2.0 - See [LICENSE](../LICENSE) for details.
