/**
 * MCP Tool Definitions for Ryumem
 */

export const TOOLS = [
  {
    name: 'search_memory',
    description: 'Multi-strategy semantic search across the knowledge graph',
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Natural language search query',
        },
        user_id: {
          type: 'string',
          description: 'User identifier for multi-tenant isolation',
        },
        session_id: {
          type: 'string',
          description: 'Optional session context',
        },
        strategy: {
          type: 'string',
          enum: ['semantic', 'traversal', 'bm25', 'hybrid'],
          description: 'Search strategy to use',
          default: 'hybrid',
        },
        limit: {
          type: 'number',
          description: 'Maximum number of results',
          minimum: 1,
          maximum: 100,
          default: 10,
        },
        similarity_threshold: {
          type: 'number',
          description: 'Minimum similarity score',
          minimum: 0,
          maximum: 1,
          default: 0.5,
        },
        max_depth: {
          type: 'number',
          description: 'Graph traversal depth',
          minimum: 1,
          maximum: 5,
          default: 2,
        },
        kinds: {
          type: 'array',
          items: {
            type: 'string',
            enum: ['query', 'memory'],
          },
          description: 'Filter by episode kinds',
        },
      },
      required: ['query', 'user_id'],
    },
  },
  {
    name: 'add_episode',
    description: 'Save new episodic memory (event, conversation, observation)',
    inputSchema: {
      type: 'object',
      properties: {
        content: {
          type: 'string',
          description: 'Memory content to save',
        },
        user_id: {
          type: 'string',
          description: 'User identifier',
        },
        session_id: {
          type: 'string',
          description: 'Session identifier',
        },
        kind: {
          type: 'string',
          enum: ['query', 'memory'],
          description: 'Episode kind',
          default: 'query',
        },
        source: {
          type: 'string',
          enum: ['text', 'message', 'json'],
          description: 'Episode source type',
          default: 'text',
        },
        metadata: {
          type: 'object',
          description: 'Additional structured metadata',
        },
        agent_id: {
          type: 'string',
          description: 'Agent identifier',
        },
      },
      required: ['content', 'user_id', 'session_id'],
    },
  },
  {
    name: 'get_entity_context',
    description: 'Retrieve entity details and relationship neighborhood',
    inputSchema: {
      type: 'object',
      properties: {
        entity_name: {
          type: 'string',
          description: 'Name of entity to look up',
        },
        user_id: {
          type: 'string',
          description: 'User identifier',
        },
        session_id: {
          type: 'string',
          description: 'Optional session context',
        },
        max_depth: {
          type: 'number',
          description: 'Graph traversal depth',
          minimum: 1,
          maximum: 5,
          default: 2,
        },
      },
      required: ['entity_name', 'user_id'],
    },
  },
  {
    name: 'list_episodes',
    description: 'Paginated episode listing with filters',
    inputSchema: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'User identifier',
        },
        session_id: {
          type: 'string',
          description: 'Filter by session',
        },
        kind: {
          type: 'string',
          enum: ['query', 'memory'],
          description: 'Filter by kind',
        },
        limit: {
          type: 'number',
          description: 'Results per page',
          minimum: 1,
          maximum: 100,
          default: 50,
        },
        offset: {
          type: 'number',
          description: 'Pagination offset',
          minimum: 0,
          default: 0,
        },
      },
      required: ['user_id'],
    },
  },
  {
    name: 'get_episode',
    description: 'Retrieve specific episode by UUID',
    inputSchema: {
      type: 'object',
      properties: {
        episode_uuid: {
          type: 'string',
          description: 'Episode UUID',
        },
        user_id: {
          type: 'string',
          description: 'User identifier for access control',
        },
      },
      required: ['episode_uuid', 'user_id'],
    },
  },
  {
    name: 'update_episode_metadata',
    description: 'Update metadata on existing episode',
    inputSchema: {
      type: 'object',
      properties: {
        episode_uuid: {
          type: 'string',
          description: 'Episode UUID',
        },
        user_id: {
          type: 'string',
          description: 'User identifier',
        },
        metadata: {
          type: 'object',
          description: 'New metadata dictionary (merged with existing)',
        },
      },
      required: ['episode_uuid', 'user_id', 'metadata'],
    },
  },
  {
    name: 'prune_memories',
    description: 'Clean up expired and low-value memories',
    inputSchema: {
      type: 'object',
      properties: {
        user_id: {
          type: 'string',
          description: 'User identifier',
        },
        min_age_days: {
          type: 'number',
          description: 'Minimum age before pruning',
          minimum: 1,
          default: 30,
        },
        min_mentions: {
          type: 'number',
          description: 'Minimum mentions to keep',
          minimum: 1,
          default: 2,
        },
        expired_cutoff_days: {
          type: 'number',
          description: 'Days for expiration cutoff',
          minimum: 1,
          default: 90,
        },
        compact_redundant: {
          type: 'boolean',
          description: 'Merge duplicate memories',
          default: true,
        },
      },
      required: ['user_id'],
    },
  },
];
