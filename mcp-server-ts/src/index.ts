#!/usr/bin/env node

/**
 * Ryumem MCP Server
 * TypeScript implementation using MCP SDK
 *
 * Usage:
 *   npx @ryumem/mcp-server              - Run the MCP server (for Claude)
 *   npx @ryumem/mcp-server install      - Install/configure for Claude Code
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { RyumemClient } from './client.js';
import { RyumemAuth } from './auth.js';
import { TOOLS } from './tools.js';
import { runInstaller, runUninstaller } from './install.js';

// Check for install/uninstall command before anything else
const args = process.argv.slice(2);
if (args[0] === 'install') {
  runInstaller(args.slice(1)).catch((error) => {
    console.error('Installation failed:', error);
    process.exit(1);
  });
} else if (args[0] === 'uninstall') {
  runUninstaller(args.slice(1)).catch((error) => {
    console.error('Uninstallation failed:', error);
    process.exit(1);
  });
} else {
  // Continue with normal MCP server startup (handled at bottom of file)
}

const DEFAULT_API_URL = 'https://api.ryumem.io';

const INSTRUCTIONS = `⚠️ MEMORY FIRST - NON-NEGOTIABLE ⚠️

EVERY conversation MUST start with the 3 required searches. NO EXCEPTIONS.
EVERY file access MUST search memory first. Reading files directly wastes context.

═══════════════════════════════════════════════════════════
0. STARTUP - REQUIRED (Run these 3 searches IMMEDIATELY)
═══════════════════════════════════════════════════════════

Determine project name from working directory (e.g., "myapp", "ryumem").
Use user_id = project_name.

🚨 REQUIRED - Run these 3 searches at the START of EVERY conversation:
1. search_memory({user_id, tags: ["project"], limit: 1})        // NO query parameter
2. search_memory({user_id, tags: ["preferences"], limit: 1})    // NO query parameter
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
═══════════════════════════════════════════════════════════`;

class RyumemMCPServer {
  private server!: Server;
  private client: RyumemClient;
  private auth: RyumemAuth;
  private apiUrl: string;

  constructor() {
    this.apiUrl = process.env.RYUMEM_API_URL || DEFAULT_API_URL;

    // Initialize auth module (will handle API key or device flow)
    this.auth = new RyumemAuth({ apiUrl: this.apiUrl });

    // Initialize client without API key (will be set after auth)
    this.client = new RyumemClient({ apiUrl: this.apiUrl });

    // Server will be created after fetching instructions
  }

  /**
   * Initialize authentication (get API key via env var, cache, or device flow)
   */
  private async initAuth(): Promise<void> {
    try {
      const apiKey = await this.auth.getApiKey();
      this.client.setApiKey(apiKey);
      console.error('Authentication successful');
    } catch (error) {
      console.error('Authentication failed:', error instanceof Error ? error.message : String(error));
      throw error;
    }
  }

  /**
   * Fetch agent instructions from the database using current_instruction pattern.
   * Server handles resolution and returns matching instruction or saves if not found.
   * Returns the enhanced_instruction to use (or defaults to INSTRUCTIONS).
   */
  private async fetchInstructions(): Promise<string> {
    try {
      console.error('Fetching MCP agent instructions...');

      // Fetch using current_instruction pattern - server handles everything
      const instructions = await this.client.listAgentInstructions({
        current_instruction: INSTRUCTIONS,
        agent_type: "mcp",
        enhance: false,  // No enhancement for MCP
        memory_enabled: false,  // No memory blocks
        tool_tracking_enabled: false,  // No tool tracking
        limit: 1,
      });

      if (instructions && instructions.length > 0) {
        const instruction = instructions[0];
        const instructionText = instruction.enhanced_instruction || instruction.base_instruction;
        console.error(`✓ Loaded MCP instructions from database (ID: ${instruction.instruction_id})`);
        return instructionText;
      }

      console.error('✓ Using default MCP instructions');
      return INSTRUCTIONS;
    } catch (error) {
      console.error('Failed to fetch instructions, using defaults:', error instanceof Error ? error.message : String(error));
      return INSTRUCTIONS;
    }
  }

  /**
   * Initialize the MCP server with the given instructions
   */
  private initializeServer(instructions: string): void {
    this.server = new Server(
      {
        name: 'ryumem',
        version: '0.1.0',
      },
      {
        capabilities: {
          tools: {},
        },
        instructions,
      }
    );

    this.setupHandlers();
  }

  private setupHandlers(): void {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: TOOLS,
    }));

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;

      try {
        let result: any;

        switch (name) {
          case 'search_memory':
            result = await this.client.searchMemory(args as any);
            break;
          case 'add_episode':
            result = await this.client.addEpisode(args as any);
            break;
          case 'get_entity_context':
            result = await this.client.getEntityContext(args as any);
            break;
          case 'list_episodes':
            result = await this.client.listEpisodes(args as any);
            break;
          case 'get_episode':
            result = await this.client.getEpisode(args as any);
            break;
          case 'update_episode_metadata':
            result = await this.client.updateEpisodeMetadata(args as any);
            break;
          case 'prune_memories':
            result = await this.client.pruneMemories(args as any);
            break;
          default:
            throw new Error(`Unknown tool: ${name}`);
        }

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : String(error);
        return {
          content: [
            {
              type: 'text',
              text: `Error: ${errorMessage}`,
            },
          ],
          isError: true,
        };
      }
    });
  }

  async run(): Promise<void> {
    // Initialize authentication first
    await this.initAuth();

    // Fetch instructions from database (or use defaults)
    const instructions = await this.fetchInstructions();

    // Initialize server with the fetched/default instructions
    this.initializeServer(instructions);

    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error('Ryumem MCP server running on stdio');
  }
}

// Only start the MCP server if not running install/uninstall command
if (args[0] !== 'install' && args[0] !== 'uninstall') {
  const server = new RyumemMCPServer();
  server.run().catch((error) => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}
