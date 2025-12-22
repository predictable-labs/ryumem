/**
 * Ryumem API Client
 * Thin wrapper around the Ryumem HTTP API
 */

export interface RyumemConfig {
  apiUrl: string;
  apiKey?: string;        // Legacy API key (X-API-Key header)
  accessToken?: string;   // OAuth access token (Bearer token)
}

export interface SearchMemoryParams {
  query: string;
  user_id: string;
  session_id?: string;
  strategy?: 'semantic' | 'traversal' | 'bm25' | 'hybrid';
  limit?: number;
  similarity_threshold?: number;
  max_depth?: number;
  kinds?: ('query' | 'memory')[];
  tags?: string[];
  tag_match_mode?: 'any' | 'all';
}

export interface AddEpisodeParams {
  content: string;
  user_id: string;
  session_id: string;
  kind?: 'query' | 'memory';
  source?: 'text' | 'message' | 'json';
  metadata?: Record<string, any>;
  agent_id?: string;
}


export interface GetEntityContextParams {
  entity_name: string;
  user_id: string;
  session_id?: string;
  max_depth?: number;
}

export interface ListEpisodesParams {
  user_id: string;
  session_id?: string;
  kind?: 'query' | 'memory';
  limit?: number;
  offset?: number;
}

export interface GetEpisodeParams {
  episode_uuid: string;
  user_id: string;
}

export interface UpdateEpisodeMetadataParams {
  episode_uuid: string;
  user_id: string;
  metadata: Record<string, any>;
}

export interface PruneMemoriesParams {
  user_id: string;
  min_age_days?: number;
  min_mentions?: number;
  expired_cutoff_days?: number;
  compact_redundant?: boolean;
}

export interface ListAgentInstructionsParams {
  current_instruction?: string;
  agent_type?: string;
  enhance?: boolean;
  memory_enabled?: boolean;
  tool_tracking_enabled?: boolean;
  limit?: number;
}

export interface AgentInstruction {
  instruction_id: string;
  base_instruction: string;
  enhanced_instruction?: string;
  query_augmentation_template?: string;
  agent_type: string;
  memory_enabled?: boolean;
  tool_tracking_enabled?: boolean;
  created_at: string;
  updated_at: string;
}

export class RyumemClient {
  private config: RyumemConfig;

  constructor(config: RyumemConfig) {
    this.config = config;
  }

  /**
   * Update the API key (used by auth module after device flow completes)
   */
  setApiKey(apiKey: string): void {
    this.config.apiKey = apiKey;
  }

  private async request<T>(
    endpoint: string,
    method: string = 'POST',
    body?: any
  ): Promise<T> {
    const url = `${this.config.apiUrl}${endpoint}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    // Support both API key and Bearer token authentication
    if (this.config.accessToken) {
      headers['Authorization'] = `Bearer ${this.config.accessToken}`;
    } else if (this.config.apiKey) {
      headers['X-API-Key'] = this.config.apiKey;
    }

    const response = await fetch(url, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(
        `Ryumem API error (${response.status}): ${errorText}`
      );
    }

    return response.json();
  }

  async searchMemory(params: SearchMemoryParams): Promise<any> {
    return this.request('/search', 'POST', params);
  }

  async addEpisode(params: AddEpisodeParams): Promise<any> {
    return this.request('/episodes', 'POST', params);
  }

  async getEntityContext(params: GetEntityContextParams): Promise<any> {
    const { entity_name, user_id, max_depth } = params;
    const queryParams = new URLSearchParams();
    queryParams.append('user_id', user_id);
    if (max_depth !== undefined) {
      queryParams.append('max_depth', String(max_depth));
    }

    return this.request(
      `/entity/${encodeURIComponent(entity_name)}?${queryParams.toString()}`,
      'GET'
    );
  }

  async listEpisodes(params: ListEpisodesParams): Promise<any> {
    const queryParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        queryParams.append(key, String(value));
      }
    });

    return this.request(
      `/episodes?${queryParams.toString()}`,
      'GET'
    );
  }

  async getEpisode(params: GetEpisodeParams): Promise<any> {
    const { episode_uuid, user_id } = params;
    return this.request(
      `/episodes/${episode_uuid}?user_id=${user_id}`,
      'GET'
    );
  }

  async updateEpisodeMetadata(params: UpdateEpisodeMetadataParams): Promise<any> {
    const { episode_uuid, user_id, metadata } = params;
    return this.request(
      `/episodes/${episode_uuid}/metadata`,
      'PATCH',
      { user_id, metadata }
    );
  }

  async pruneMemories(params: PruneMemoriesParams): Promise<any> {
    return this.request('/prune', 'POST', params);
  }

  async listAgentInstructions(params: ListAgentInstructionsParams = {}): Promise<AgentInstruction[]> {
    const queryParams = new URLSearchParams();
    if (params.current_instruction) {
      queryParams.append('current_instruction', params.current_instruction);
    }
    if (params.agent_type) {
      queryParams.append('agent_type', params.agent_type);
    }
    if (params.enhance !== undefined) {
      queryParams.append('enhance', String(params.enhance));
    }
    if (params.memory_enabled !== undefined) {
      queryParams.append('memory_enabled', String(params.memory_enabled));
    }
    if (params.tool_tracking_enabled !== undefined) {
      queryParams.append('tool_tracking_enabled', String(params.tool_tracking_enabled));
    }
    if (params.limit !== undefined) {
      queryParams.append('limit', String(params.limit));
    }

    const query = queryParams.toString();
    const endpoint = query ? `/agent-instructions?${query}` : '/agent-instructions';
    return this.request<AgentInstruction[]>(endpoint, 'GET');
  }

  async saveAgentInstruction(params: {
    base_instruction: string;
    agent_type?: string;
    enhanced_instruction?: string;
    query_augmentation_template?: string;
    memory_enabled?: boolean;
    tool_tracking_enabled?: boolean;
  }): Promise<AgentInstruction> {
    return this.request<AgentInstruction>('/agent-instructions', 'POST', params);
  }
}
