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

### Install for Cursor

```bash
npx @predictable/ryumem-mcp-server install --oauth --client cursor
```

### Install for Claude Desktop

```bash
npx @predictable/ryumem-mcp-server install --oauth --client claude-desktop
```

### Uninstall

```bash
npx @predictable/ryumem-mcp-server uninstall
```

## Manual Configuration

If you prefer manual setup, add to your configuration file:

**Claude Code:** `~/.claude.json`
**Cursor:** `~/.cursor/mcp.json`
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
| `--client <name>` | Target client: `claude-code` (default), `cursor`, or `claude-desktop` |

### Examples

```bash
# OAuth authentication (recommended)
npx @predictable/ryumem-mcp-server install --oauth

# Configure for Cursor
npx @predictable/ryumem-mcp-server install --oauth --client cursor

# Configure for Claude Desktop
npx @predictable/ryumem-mcp-server install --oauth --client claude-desktop

# Use custom API server
npx @predictable/ryumem-mcp-server install --api-key ryu_api_key --api-url http://localhost:8000
```

## Cursor Configuration

Cursor's MCP implementation doesn't automatically load server instructions. To enable Ryumem's memory-first behavior, add the following to your project's `.cursorrules` file:

<details>
<summary>📋 Click to expand .cursorrules content</summary>

```
# Ryumem Memory Instructions

⚠️ MEMORY FIRST - NON-NEGOTIABLE ⚠️

EVERY conversation MUST start with the 3 required searches. NO EXCEPTIONS.
EVERY file access MUST search memory first. Reading files directly wastes context.

═══════════════════════════════════════════════════════════
0. STARTUP - REQUIRED (Run these 3 searches IMMEDIATELY)
═══════════════════════════════════════════════════════════

Determine project name from working directory (e.g., "myapp", "ryumem").
Use user_id = project_name.

🚨 REQUIRED - Run these 3 searches at the START of EVERY conversation:
1. search_memory({user_id, tags: ["project"], limit: 1})        // NO query parameter
2. search_memory({user_id, tags: ["preferences"], limit: 3})    // NO query parameter
3. search_memory({user_id, tags: ["decision"], limit: 2})       // NO query parameter

IMPORTANT: Use ONLY tags for startup searches - do NOT include query parameter.

If you skip these searches, you will:
- Miss critical user preferences and waste their time
- Repeat past mistakes and decisions
- Provide solutions that don't match their coding style
- Force them to re-explain context

═══════════════════════════════════════════════════════════
1. CODE FILES - ALWAYS Search Before Reading
═══════════════════════════════════════════════════════════

🚨 MANDATORY workflow for ANY file access:

Step 1: search_memory("path/to/file.ext", {tags: ["code"], limit: 1})

Step 2:
  → Summary found? → Use it, SKIP reading the file
  → No summary? → Read file, IMMEDIATELY store summary (< 200 words)

After reading ANY file, you MUST run:
add_episode({
  content: "path/to/file.ext: {purpose}. Key: {exports/classes}. Notable: {details}",
  user_id, session_id,
  kind: "memory",
  metadata: {type: "code_summary", tags: ["code", "backend"|"frontend", domain], file_path: "path/to/file.ext"}
})

WHY: Re-reading files bloats context. Summaries are 10x more efficient.

═══════════════════════════════════════════════════════════
2. WHEN TO SEARCH & SEARCH VOLUME CONTROL
═══════════════════════════════════════════════════════════

Search memory BEFORE:
✓ Reading files (check for code summaries)
✓ Exploring unfamiliar code areas
✓ Starting multi-step tasks

Search volume limits:
- Code summaries: limit: 1
- Preferences: limit: 3
- Decisions: limit: 2
- General queries: limit: 5
- Max 5 search results before starting work

🚨 STOP if search returns too much data:
- If search returns >5 results, query is too broad
- Refine with more specific tags or query
- Don't search repeatedly if you keep finding data
- If need more context, read files instead

Strategy: "bm25" (default) | "hybrid" | "semantic"

═══════════════════════════════════════════════════════════
3. WHAT TO STORE - Be Proactive
═══════════════════════════════════════════════════════════

Keep ALL content under 200 words. Store liberally.

A. Code Summaries (AFTER every file read)
   Tags: ["code", "backend"|"frontend", domain]
   Format: "{file}: {purpose}. Key: {exports}. Notable: {details}"

B. User Preferences (Update frequently as you learn)
   Tags: ["preferences", category]
   Examples: coding style, testing, security, tools, development

   🚨 CRITICAL - Updating Preferences:
   1. ALWAYS search for existing preferences first
   2. Get COMPLETE existing content
   3. Merge ALL previous + new info
   4. NEVER create partial preferences

C. Decisions (Store architecture choices, trade-offs)
   Tags: ["decision", domain]
   Why choices were made, affected files, alternatives considered

D. Project Context (Store project structure, patterns)
   Tags: ["project"]
   Stack, architecture, key patterns, folder structure

═══════════════════════════════════════════════════════════
4. METADATA - Required Fields
═══════════════════════════════════════════════════════════

REQUIRED:
- type: "code_summary" | "preferences" | "decision" | "project" | "issue"
- tags: 2-3 tags (lowercase)

OPTIONAL:
- file_path: for code summaries
- relates_to: related files

session_id: "feature-name" or "context-name"

═══════════════════════════════════════════════════════════
5. PREVENT DUPLICATES - Always Merge
═══════════════════════════════════════════════════════════

WORKFLOW for updates:
1. Search for existing content (limit: 1)
2. If exists → Get full episode → Merge with new info → Create new episode
3. If not exists → Create new

NEVER:
- Create duplicate partial content
- Update without searching first
- Lose information when updating

═══════════════════════════════════════════════════════════
6. LIMITS - Stay Within Budget
═══════════════════════════════════════════════════════════

- Searches per conversation: < 8
- Results per search: ≤ 5
- Episodes created: < 15
- Episode content: < 200 words

═══════════════════════════════════════════════════════════
7. LOW CONTEXT - Save State and Ask User
═══════════════════════════════════════════════════════════

🚨 When context is running low (< 20% remaining):

1. IMMEDIATELY store current state as a decision:
   add_episode({
     content: "Current task: {what you're working on}. Progress: {what's done}. Next steps: {what remains}. Files modified: {list}.",
     user_id, session_id,
     kind: "memory",
     metadata: {type: "decision", tags: ["decision", "checkpoint", domain], status: "in_progress"}
   })

2. Ask user to take action:
   "⚠️ Context is running low. I've saved our progress as a decision.

   Please either:
   - Clear context (/clear) and I'll resume from the saved state
   - Ask me to compact by summarizing our work

   What would you like to do?"

3. NEVER continue working if context is critically low
4. NEVER lose progress - always save state first

═══════════════════════════════════════════════════════════
🎯 GOLDEN RULE: Memory first, files last. Always.
═══════════════════════════════════════════════════════════
```

</details>

**Alternative:** You can also add these instructions to Cursor's global "Rules for AI" in Settings → General → Rules for AI.

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
