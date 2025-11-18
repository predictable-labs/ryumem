/**
 * API client for Ryumem backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface Episode {
  content: string;
  user_id: string;
  session_id?: string;
  source?: string;
  metadata?: Record<string, any>;
}

export interface EpisodeInfo {
  uuid: string;
  name: string;
  content: string;
  source: string;
  source_description: string;
  created_at: string;
  valid_at: string;
  user_id?: string;
  session_id?: string;
  metadata?: string;
}

export interface GetEpisodesResponse {
  episodes: EpisodeInfo[];
  total: number;
  offset: number;
  limit: number;
}

export interface SearchQuery {
  query: string;
  user_id: string;
  limit?: number;
  strategy?: 'semantic' | 'bm25' | 'traversal' | 'hybrid';
  min_rrf_score?: number;
  min_bm25_score?: number;
}

export interface Entity {
  uuid: string;
  name: string;
  entity_type: string;
  summary: string;
  mentions: number;
  score: number;
}

export interface Edge {
  uuid: string;
  source_uuid: string;  // Added for graph visualization
  target_uuid: string;  // Added for graph visualization
  source_name: string;
  target_name: string;
  relation_type: string;
  fact: string;
  mentions: number;
  score: number;
}

export interface SearchResult {
  entities: Entity[];
  edges: Edge[];
  query: string;
  strategy: string;
  count: number;
}

export interface Stats {
  total_episodes: number;
  total_entities: number;
  total_relationships: number;
  total_communities: number;
  db_path: string;
}

export interface GraphNode {
  uuid: string;
  name: string;
  type: string;
  summary: string;
  mentions: number;
  user_id?: string;
}

export interface GraphEdge {
  uuid: string;
  source: string;  // Source node UUID
  target: string;  // Target node UUID
  label: string;   // Relation type
  fact: string;
  mentions: number;
}

export interface GraphDataResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  count: {
    nodes: number;
    edges: number;
  };
}

export interface EntitiesListResponse {
  entities: Entity[];
  total: number;
  offset: number;
  limit: number;
}

export interface RelationshipsListResponse {
  relationships: Edge[];
  total: number;
  offset: number;
  limit: number;
}

export interface EntityTypesResponse {
  entity_types: string[];
}

export interface AgentInstruction {
  instruction_text: string;
  agent_type?: string;
  instruction_type?: string;
  description?: string;
  user_id?: string;
  original_user_request?: string;
}

export interface AgentInstructionResponse {
  instruction_id: string;
  instruction_text: string;
  name: string;
  agent_type: string;
  instruction_type: string;
  version: number;
  description: string;
  original_user_request: string;
  converted_instruction: string;
  created_at: string;
}

export interface ToolForTask {
  tool_name: string;
  usage_count: number;
  success_rate: number;
  avg_duration_ms: number;
}

export interface ToolMetrics {
  tool_name: string;
  usage_count: number;
  success_rate: number;
  avg_duration_ms: number;
  recent_errors: string[];
}

export interface ToolPreference {
  tool_name: string;
  usage_count: number;
  last_used: string;
}

export interface QueryRun {
  run_id: string;
  timestamp: string;
  query: string;
  augmented_query?: string | null;
  tools_used: Array<{
    tool_name: string;
    success: boolean;
    duration_ms: number;
    timestamp: string;
    input_params?: any;
    output_summary?: any;
    error?: string;
  }>;
  agent_response?: string;
}

export interface AugmentedQuery {
  episode_id: string;
  query: string;
  user_id: string;
  session_id?: string;
  created_at: string;
  runs: QueryRun[];
}

class RyumemAPI {
  private baseURL: string;

  constructor(baseURL: string = API_BASE_URL) {
    this.baseURL = baseURL;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  async addEpisode(episode: Episode) {
    return this.request('/episodes', {
      method: 'POST',
      body: JSON.stringify(episode),
    });
  }

  async getEpisodes(
    userId?: string,
    limit: number = 20,
    offset: number = 0,
    startDate?: string,
    endDate?: string,
    search?: string,
    sortOrder: 'asc' | 'desc' = 'desc'
  ): Promise<GetEpisodesResponse> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
      sort_order: sortOrder,
      ...(userId && { user_id: userId }),
      ...(startDate && { start_date: startDate }),
      ...(endDate && { end_date: endDate }),
      ...(search && { search }),
    });
    return this.request(`/episodes?${params}`);
  }

  async search(query: SearchQuery): Promise<SearchResult> {
    return this.request('/search', {
      method: 'POST',
      body: JSON.stringify(query),
    });
  }

  async getEntityContext(
    entityName: string,
    userId?: string
  ) {
    const params = new URLSearchParams({
      ...(userId && { user_id: userId }),
    });

    return this.request(`/entity/${encodeURIComponent(entityName)}?${params}`);
  }

  async getStats(): Promise<Stats> {
    return this.request('/stats');
  }

  async updateCommunities(
    resolution: number = 1.0,
    minCommunitySize: number = 2
  ) {
    return this.request('/communities/update', {
      method: 'POST',
      body: JSON.stringify({
        resolution,
        min_community_size: minCommunitySize,
      }),
    });
  }

  async pruneMemories(
    userId: string,
    expiredCutoffDays: number = 90,
    minMentions: number = 2,
    minAgeDays: number = 30,
    compactRedundant: boolean = true
  ) {
    return this.request('/prune', {
      method: 'POST',
      body: JSON.stringify({
        user_id: userId,
        expired_cutoff_days: expiredCutoffDays,
        min_mentions: minMentions,
        min_age_days: minAgeDays,
        compact_redundant: compactRedundant,
      }),
    });
  }

  async getGraphData(
    userId?: string,
    limit: number = 1000
  ): Promise<GraphDataResponse> {
    const params = new URLSearchParams({
      ...(userId && { user_id: userId }),
      limit: limit.toString(),
    });
    return this.request(`/graph/data?${params}`);
  }

  async getEntitiesList(
    userId?: string,
    entityType?: string,
    offset: number = 0,
    limit: number = 50
  ): Promise<EntitiesListResponse> {
    const params = new URLSearchParams({
      ...(userId && { user_id: userId }),
      ...(entityType && { entity_type: entityType }),
      offset: offset.toString(),
      limit: limit.toString(),
    });
    return this.request(`/entities/list?${params}`);
  }

  async getEntityTypes(userId?: string): Promise<EntityTypesResponse> {
    const params = new URLSearchParams({
      ...(userId && { user_id: userId }),
    });
    return this.request(`/entities/types?${params}`);
  }

  async getRelationshipsList(
    userId?: string,
    relationType?: string,
    offset: number = 0,
    limit: number = 50
  ): Promise<RelationshipsListResponse> {
    const params = new URLSearchParams({
      ...(userId && { user_id: userId }),
      ...(relationType && { relation_type: relationType }),
      offset: offset.toString(),
      limit: limit.toString(),
    });
    return this.request(`/relationships/list?${params}`);
  }

  async health() {
    return this.request('/health');
  }

  async getUsers(): Promise<string[]> {
    const response = await this.request<{ users: string[] }>('/users');
    return response.users;
  }

  // ============================================================================
  // Agent Instruction Management
  // ============================================================================

  async createAgentInstruction(instruction: AgentInstruction): Promise<AgentInstructionResponse> {
    return this.request('/agent-instructions', {
      method: 'POST',
      body: JSON.stringify(instruction),
    });
  }

  async listAgentInstructions(
    agentType?: string,
    instructionType?: string,
    limit: number = 50
  ): Promise<AgentInstructionResponse[]> {
    const params = new URLSearchParams({
      ...(agentType && { agent_type: agentType }),
      ...(instructionType && { instruction_type: instructionType }),
      limit: limit.toString(),
    });
    return this.request(`/agent-instructions?${params}`);
  }

  // ============================================================================
  // Tool Analytics
  // ============================================================================

  async getAllTools(): Promise<any[]> {
    return this.request('/tools');
  }

  async getToolMetrics(
    toolName: string,
    userId?: string,
    minExecutions: number = 1
  ): Promise<ToolMetrics> {
    const params = new URLSearchParams({
      ...(userId && { user_id: userId }),
      min_executions: minExecutions.toString(),
    });
    return this.request(`/tools/${encodeURIComponent(toolName)}/metrics?${params}`);
  }

  async getUserToolPreferences(
    userId: string,
    limit: number = 10
  ): Promise<ToolPreference[]> {
    const params = new URLSearchParams({
      limit: limit.toString(),
    });
    return this.request(`/users/${encodeURIComponent(userId)}/tool-preferences?${params}`);
  }

  // ============================================================================
  // Query Augmentation
  // ============================================================================

  async getAugmentedQueries(
    userId?: string,
    limit: number = 50,
    offset: number = 0,
    onlyAugmented: boolean = false
  ): Promise<AugmentedQuery[]> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
      only_augmented: onlyAugmented.toString(),
      ...(userId && { user_id: userId }),
    });
    return this.request(`/augmented-queries?${params}`);
  }
}

export const api = new RyumemAPI();

