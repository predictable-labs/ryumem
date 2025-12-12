/**
 * Ryumem API Client
 * Thin wrapper around the Ryumem HTTP API
 */

export interface RyumemConfig {
  apiUrl: string;
  apiKey: string;
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

export class RyumemClient {
  private config: RyumemConfig;

  constructor(config: RyumemConfig) {
    this.config = config;
  }

  private async request<T>(
    endpoint: string,
    method: string = 'POST',
    body?: any
  ): Promise<T> {
    const url = `${this.config.apiUrl}${endpoint}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-API-Key': this.config.apiKey,
    };

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
}
