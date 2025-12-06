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

1. **Automatic Memory Saving**: Periodically save important context from conversations using add_episode:
   - Save key decisions, facts learned, and important exchanges
   - Include user_id and session_id for proper context isolation
   - Use kind='memory' for facts, kind='query' for questions/requests

2. **Memory Retrieval**: Use search_memory to recall relevant past context:
   - Search before answering questions that might benefit from history
   - Use strategy='hybrid' for best results (combines semantic + keyword + graph)
   - Set appropriate similarity_threshold (0.3-0.5 for broader recall, 0.6+ for precise matches)

3. **Best Practices**:
   - Save conversations in logical chunks (per topic or decision point, not every message)
   - Always provide meaningful content in episodes (avoid saving empty or trivial exchanges)
   - Use metadata to enrich episodes with tags, topics, or sentiment
   - Check entity_context to understand relationships between people/concepts

4. **Multi-step Workflows**:
   - For bulk operations: use batch_add_episodes instead of multiple add_episode calls
   - For entity exploration: get_entity_context before searching memories about that entity
   - For cleanup: periodically use prune_memories to remove low-value data`;

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
