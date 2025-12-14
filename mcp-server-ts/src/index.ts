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
1. search_memory("project summary", {user_id, tags: ["project"], limit: 1})
2. search_memory("user preferences", {user_id, tags: ["preferences"], limit: 3})
3. search_memory("recent decisions", {user_id, tags: ["decision"], limit: 2})

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
2. WHEN TO SEARCH MEMORY - Use Aggressively
═══════════════════════════════════════════════════════════

Search memory BEFORE:
✓ Reading any file
✓ Making implementation decisions
✓ Answering questions about the codebase
✓ Updating user preferences
✓ Starting any multi-step task
✓ Exploring unfamiliar code areas

Search limits:
- Code summaries: limit: 1
- Preferences: limit: 3
- Decisions: limit: 2
- General queries: limit: 5

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
🎯 GOLDEN RULE: Memory first, files last. Always.
═══════════════════════════════════════════════════════════`;

class RyumemMCPServer {
  private server: Server;
  private client: RyumemClient;
  private auth: RyumemAuth;
  private apiUrl: string;
  private instructions: string;

  constructor() {
    this.apiUrl = process.env.RYUMEM_API_URL || DEFAULT_API_URL;

    // Initialize auth module (will handle API key or device flow)
    this.auth = new RyumemAuth({ apiUrl: this.apiUrl });

    // Initialize client without API key (will be set after auth)
    this.client = new RyumemClient({ apiUrl: this.apiUrl });
    this.instructions = INSTRUCTIONS; // Default instructions

    this.server = new Server(
      {
        name: 'ryumem',
        version: '0.1.0',
      },
      {
        capabilities: {
          tools: {},
        },
        instructions: this.instructions,
      }
    );

    this.setupHandlers();
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
   * Fetch agent instructions from the database.
   * Fallback hierarchy: API -> Memory -> Default instructions
   */
  private async fetchInstructions(): Promise<void> {
    try {
      console.error('Fetching MCP agent instructions...');

      // Step 1: Try to get instructions from the API
      const instructions = await this.client.listAgentInstructions({
        agent_type: 'mcp',
        limit: 1,
      });

      if (instructions && instructions.length > 0) {
        const instruction = instructions[0];
        // Use enhanced_instruction if available, otherwise use base_instruction
        this.instructions = instruction.enhanced_instruction || instruction.base_instruction;
        console.error(`✓ Loaded MCP instructions from database (ID: ${instruction.instruction_id})`);
        return;
      }

      console.error('No MCP instructions found in database');

      // Step 2: Try to get instructions from memory (stored summaries)
      try {
        const memoryResults = await this.client.searchMemory({
          query: 'mcp server instructions agent behavior',
          user_id: 'ryumem-system',
          strategy: 'bm25',
          limit: 1,
          tags: ['project', 'preferences'],
        });

        if (memoryResults && memoryResults.episodes && memoryResults.episodes.length > 0) {
          this.instructions = memoryResults.episodes[0].content;
          console.error('✓ Loaded MCP instructions from memory');
          return;
        }
      } catch (memError) {
        console.error('Failed to fetch from memory:', memError instanceof Error ? memError.message : String(memError));
      }

      console.error('✓ Using default MCP instructions');
    } catch (error) {
      console.error('Failed to fetch instructions, using defaults:', error instanceof Error ? error.message : String(error));
    }
  }

  /**
   * Save default instructions to the database for future use.
   * This creates a persistent configuration that can be customized later.
   */
  private async saveDefaultInstructions(): Promise<void> {
    // Only save if we're using default instructions (not loaded from database or memory)
    if (this.instructions !== INSTRUCTIONS) {
      return;
    }

    try {
      // Check if instructions already exist
      const existing = await this.client.listAgentInstructions({
        agent_type: 'mcp',
        limit: 1,
      });

      if (existing && existing.length > 0) {
        // Instructions already exist, don't overwrite
        return;
      }

      // Save default instructions to database
      console.error('Saving default MCP instructions to database...');
      await this.client.saveAgentInstruction({
        base_instruction: INSTRUCTIONS,
        agent_type: 'mcp',
        enhanced_instruction: INSTRUCTIONS,
        memory_enabled: true,
        tool_tracking_enabled: false,
      });

      console.error('✓ Default MCP instructions saved to database');

      // Also save to memory as a backup
      await this.saveInstructionsToMemory();
    } catch (error) {
      // This is not critical - we can still run with default instructions
      console.error('Note: Could not save default instructions (write access may be required):',
        error instanceof Error ? error.message : String(error));
    }
  }

  /**
   * Store instructions in memory for faster retrieval and redundancy.
   */
  private async saveInstructionsToMemory(): Promise<void> {
    try {
      await this.client.addEpisode({
        content: this.instructions,
        user_id: 'ryumem-system',
        session_id: 'mcp-server-instructions',
        kind: 'memory',
        source: 'text',
        metadata: {
          type: 'agent_instruction',
          agent_type: 'mcp',
          tags: ['project', 'preferences'],
        },
      });
      console.error('✓ MCP instructions backed up to memory');
    } catch (error) {
      console.error('Note: Could not save instructions to memory:',
        error instanceof Error ? error.message : String(error));
    }
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

    // Fetch instructions before starting the server
    await this.fetchInstructions();
    await this.saveDefaultInstructions();

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
