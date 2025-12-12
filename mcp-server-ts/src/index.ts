#!/usr/bin/env node

/**
 * Ryumem MCP Server
 * TypeScript implementation using MCP SDK
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { RyumemClient } from './client.js';
import { TOOLS } from './tools.js';

const DEFAULT_API_URL = 'https://api.ryumem.io';

const INSTRUCTIONS = `Ryumem is a bi-temporal knowledge graph memory system. To provide persistent memory across conversations:

0. **Session Initialization**: At the start of EVERY conversation (even if user just says "hi"):
   - Determine the project name from the working directory or context (e.g., "myapp", "company-platform")
   - IMMEDIATELY use search_memory to find relevant context:
     - Search for "user preferences coding standards recent work" with strategy='bm25'
     - Use the project name as user_id (NEVER use personal names, always use project/workspace identifier)
     - Set similarity_threshold=0.3 for broad recall
   - ALSO use list_episodes with the project name as user_id to read recent episodes
   - Look for user preferences, coding standards, past decisions, and context
   - Episodes may contain important information about:
     - User's coding preferences and standards
     - Project-specific conventions and patterns
     - Past decisions and their rationale
     - Important technical context from previous sessions
   - Apply learned preferences throughout the conversation

1. **Automatic Memory Saving with Rich Metadata**: Periodically save important context using add_episode:
   - Save key decisions, facts learned, and important exchanges
   - Use project/workspace name as user_id for project-scoped memories
   - Use descriptive session_id for conversation context (e.g., "bug_fix_2025_12_12", "feature_planning")
   - Use kind='memory' for facts, kind='query' for questions/requests
   - **CRITICAL - Always include comprehensive metadata tagging**:
     - type: Category like "user_preferences", "bug_fix", "api_documentation", "infrastructure", "technical_investigation"
     - tags: Array of specific, searchable keywords (e.g., ["authentication", "api", "database", "performance"])
     - category: Broad category like "system_architecture", "methodology", "resolution"
     - importance: "high", "medium", or "low" to prioritize critical information
     - status: Current state like "resolved", "investigating", "pending" for tracking
     - relates_to: Array of related components for connecting information
   - **Example good metadata**:
     {
       "type": "bug_fix",
       "tags": ["search", "performance", "configuration"],
       "category": "resolution",
       "importance": "high",
       "status": "resolved",
       "relates_to": ["search_system", "api"]
     }
   - **Save user preferences**: When user expresses preferences about code style, tools, or workflows, save with type="user_preferences" and relevant tags

2. **Memory Retrieval with Fallback Strategies**: Use search_memory to recall relevant past context:
   - Always use the project/workspace name as user_id when searching
   - Search before answering questions that might benefit from history
   - **Search Strategy Selection**:
     - strategy='bm25': Use for keyword/text matching (reliable for most queries, works with or without embeddings)
     - strategy='hybrid': Combines semantic + keyword + graph (best results when embeddings enabled, but may need threshold adjustments)
     - strategy='semantic': Requires embeddings enabled on server (check if results are empty)
   - **Handling Empty Results**:
     - If search returns no results, try these in order:
       1. Switch to strategy='bm25' (more reliable)
       2. Lower similarity_threshold to 0.1 or 0.0
       3. Try different/broader search keywords
       4. Use list_episodes to browse recent memories
       5. Search by tags in metadata if you know them
   - Set appropriate similarity_threshold:
     - 0.1-0.3 for very broad exploration
     - 0.3-0.5 for standard recall
     - 0.6+ for precise matches when you know exactly what to find

3. **Best Practices**:
   - Save conversations in logical chunks (per topic or decision point, not every message)
   - Always provide meaningful content in episodes (avoid saving empty or trivial exchanges)
   - **Use rich, specific metadata tags** - this is the most important factor for future searchability
   - Tag by multiple dimensions: type, component, status, priority, technology, problem area
   - Be specific with tags: use "database_migration" not just "database", "jwt_authentication" not just "auth"
   - Check entity_context to understand relationships between people/concepts
   - Store user preferences separately with clear metadata for easy retrieval
   - When documenting technical details, include file paths, configuration keys, and specific values

4. **Multi-step Workflows**:
   - For bulk operations: use batch_add_episodes instead of multiple add_episode calls
   - For entity exploration: get_entity_context before searching memories about that entity
   - For cleanup: periodically use prune_memories to remove low-value data

5. **Troubleshooting Search Issues**:
   - If search consistently returns empty, the server may have embeddings disabled - use strategy='bm25'
   - Only recently created episodes may be indexed - older memories might not be searchable
   - Check that you're using the correct user_id (should match project/workspace name)
   - Verify metadata tags are being saved - use list_episodes to check recent episode structure`;

class RyumemMCPServer {
  private server: Server;
  private client: RyumemClient;

  constructor() {
    const apiUrl = process.env.RYUMEM_API_URL || DEFAULT_API_URL;
    const apiKey = process.env.RYUMEM_API_KEY;

    if (!apiKey) {
      throw new Error('RYUMEM_API_KEY environment variable is required');
    }

    this.client = new RyumemClient({ apiUrl, apiKey });

    this.server = new Server(
      {
        name: 'ryumem',
        version: '0.1.0',
      },
      {
        capabilities: {
          tools: {},
        },
        instructions: INSTRUCTIONS,
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
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error('Ryumem MCP server running on stdio');
  }
}

const server = new RyumemMCPServer();
server.run().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
