/**
 * API client for Ryumem backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface Episode {
  content: string;
  group_id: string;
  user_id?: string;
  agent_id?: string;
  session_id?: string;
  source?: string;
  metadata?: Record<string, any>;
}

export interface SearchQuery {
  query: string;
  group_id: string;
  user_id?: string;
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
  group_id: string;
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

  async search(query: SearchQuery): Promise<SearchResult> {
    return this.request('/search', {
      method: 'POST',
      body: JSON.stringify(query),
    });
  }

  async getEntityContext(
    entityName: string,
    groupId: string,
    userId?: string
  ) {
    const params = new URLSearchParams({
      group_id: groupId,
      ...(userId && { user_id: userId }),
    });
    
    return this.request(`/entity/${encodeURIComponent(entityName)}?${params}`);
  }

  async getStats(groupId?: string): Promise<Stats> {
    const params = groupId ? `?group_id=${groupId}` : '';
    return this.request(`/stats${params}`);
  }

  async updateCommunities(
    groupId: string,
    resolution: number = 1.0,
    minCommunitySize: number = 2
  ) {
    return this.request('/communities/update', {
      method: 'POST',
      body: JSON.stringify({
        group_id: groupId,
        resolution,
        min_community_size: minCommunitySize,
      }),
    });
  }

  async pruneMemories(
    groupId: string,
    expiredCutoffDays: number = 90,
    minMentions: number = 2,
    minAgeDays: number = 30,
    compactRedundant: boolean = true
  ) {
    return this.request('/prune', {
      method: 'POST',
      body: JSON.stringify({
        group_id: groupId,
        expired_cutoff_days: expiredCutoffDays,
        min_mentions: minMentions,
        min_age_days: minAgeDays,
        compact_redundant: compactRedundant,
      }),
    });
  }

  async getGraphData(
    groupId: string,
    userId?: string,
    limit: number = 1000
  ): Promise<GraphDataResponse> {
    const params = new URLSearchParams({
      group_id: groupId,
      ...(userId && { user_id: userId }),
      limit: limit.toString(),
    });
    return this.request(`/graph/data?${params}`);
  }

  async getEntitiesList(
    groupId: string,
    userId?: string,
    entityType?: string,
    offset: number = 0,
    limit: number = 50
  ): Promise<EntitiesListResponse> {
    const params = new URLSearchParams({
      group_id: groupId,
      ...(userId && { user_id: userId }),
      ...(entityType && { entity_type: entityType }),
      offset: offset.toString(),
      limit: limit.toString(),
    });
    return this.request(`/entities/list?${params}`);
  }

  async getEntityTypes(groupId: string): Promise<EntityTypesResponse> {
    const params = new URLSearchParams({ group_id: groupId });
    return this.request(`/entities/types?${params}`);
  }

  async getRelationshipsList(
    groupId: string,
    userId?: string,
    relationType?: string,
    offset: number = 0,
    limit: number = 50
  ): Promise<RelationshipsListResponse> {
    const params = new URLSearchParams({
      group_id: groupId,
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
}

export const api = new RyumemAPI();

