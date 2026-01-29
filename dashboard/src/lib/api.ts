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
  kind?: string;
  created_at: string;
  valid_at: string;
  user_id?: string;
  session_id?: string;
  metadata?: Record<string, any>;
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

export interface SearchResultEpisode {
  uuid: string;
  name: string;
  content: string;
  source: string;
  source_description: string;
  kind?: string;
  created_at: string;
  score: number;
}

export interface SearchResult {
  entities: Entity[];
  edges: Edge[];
  episodes: SearchResultEpisode[];
  query: string;
  strategy: string;
  count: number;
}

export interface Stats {
  total_episodes: number;
  total_entities: number;
  total_relationships: number;
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
  base_instruction: string;
  enhanced_instruction?: string;
  query_augmentation_template?: string;
  agent_type: string;
  memory_enabled?: boolean;
  tool_tracking_enabled?: boolean;
  instruction_text?: string; // Kept for backward compatibility if needed
  description?: string;
  user_id?: string;
  original_user_request?: string;
}

export interface AgentInstructionResponse {
  instruction_id: string;
  base_instruction: string;
  enhanced_instruction: string;
  query_augmentation_template: string;
  agent_type: string;
  memory_enabled: boolean;
  tool_tracking_enabled: boolean;
  created_at: string;
  updated_at: string;
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
  workflow_execution?: {
    workflow_id: string;
    workflow_name: string;
    status: 'completed' | 'paused' | 'error';
    node_results?: Array<{
      node_id: string;
      node_type: string;
      status: string;
      output: any;
      error?: string;
      duration_ms: number;
    }>;
    final_context?: Record<string, any>;
    paused_at_node?: string;
    pause_reason?: string;
  };
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

    // Get API Key from storage
    const apiKey = typeof window !== 'undefined' ? localStorage.getItem('ryumem_api_key') : null;

    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (apiKey) {
      (headers as any)['X-API-Key'] = apiKey;
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      if (typeof window !== 'undefined') {
        // Clear invalid key and redirect if not already on login
        localStorage.removeItem('ryumem_api_key');
        if (!window.location.pathname.startsWith('/login')) {
          window.location.href = '/login';
        }
      }
      throw new Error('Unauthorized');
    }

    if (!response.ok) {
      const error = await response.json();
      throw new Error(`${error.detail.message}: ${error.detail.errors.join(',')}` || `HTTP ${response.status}: ${response.statusText}`);
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

  async updateEpisodeMetadata(episodeUuid: string, metadata: Record<string, any>) {
    return this.request(`/episodes/${episodeUuid}/metadata`, {
      method: 'PATCH',
      body: JSON.stringify({ metadata }),
    });
  }

  async deleteEpisode(episodeUuid: string) {
    return this.request(`/episodes/${episodeUuid}`, {
      method: 'DELETE',
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

  async getCustomerMe(): Promise<{ customer_id: string; display_name?: string; github_username?: string }> {
    return this.request('/customer/me');
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
    limit: number = 50
  ): Promise<AgentInstructionResponse[]> {
    const params = new URLSearchParams({
      ...(agentType && { agent_type: agentType }),
      limit: limit.toString(),
    });
    return this.request(`/agent-instructions?${params}`);
  }

  async deleteAgentInstruction(instructionId: string): Promise<{ message: string; success: boolean }> {
    return this.request(`/agent-instructions/${instructionId}`, {
      method: 'DELETE',
    });
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

  // ============================================================================
  // Settings Management
  // ============================================================================

  async getSettings(maskSensitive: boolean = true): Promise<SettingsResponse> {
    const params = new URLSearchParams({
      mask_sensitive: maskSensitive.toString(),
    });
    return this.request(`/api/settings?${params}`);
  }

  async getSettingsByCategory(
    category: string,
    maskSensitive: boolean = true
  ): Promise<ConfigValue[]> {
    const params = new URLSearchParams({
      mask_sensitive: maskSensitive.toString(),
    });
    return this.request(`/api/settings/${encodeURIComponent(category)}?${params}`);
  }

  async updateSettings(updates: Record<string, any>): Promise<UpdateSettingsResponse> {
    return this.request('/api/settings', {
      method: 'PUT',
      body: JSON.stringify({ updates }),
    });
  }

  async validateSettings(updates: Record<string, any>): Promise<ValidateSettingsResponse> {
    return this.request('/api/settings/validate', {
      method: 'POST',
      body: JSON.stringify({ updates }),
    });
  }

  async resetSettingsToDefaults(): Promise<ResetSettingsResponse> {
    return this.request('/api/settings/reset-defaults', {
      method: 'POST',
    });
  }

  // ============================================================================
  // Database Management
  // ============================================================================

  async deleteDatabase(): Promise<DeleteDatabaseResponse> {
    return this.request('/database/reset', {
      method: 'DELETE',
    });
  }

  // ========================= Workflow Methods =========================

  async listWorkflows(userId?: string, limit: number = 100): Promise<WorkflowDefinition[]> {
    const params = new URLSearchParams();
    if (userId) params.append('user_id', userId);
    params.append('limit', limit.toString());
    return this.request(`/workflows?${params.toString()}`);
  }

  async getWorkflow(workflowId: string): Promise<WorkflowDefinition> {
    return this.request(`/workflows/${workflowId}`);
  }

  async createWorkflow(workflow: Omit<WorkflowDefinition, 'workflow_id' | 'created_at' | 'updated_at' | 'success_count' | 'failure_count'>): Promise<{ workflow_id: string }> {
    return this.request('/workflows', {
      method: 'POST',
      body: JSON.stringify(workflow),
    });
  }

  async updateWorkflow(workflowId: string, workflow: Omit<WorkflowDefinition, 'workflow_id' | 'created_at' | 'updated_at' | 'success_count' | 'failure_count'>): Promise<{ workflow_id: string }> {
    return this.request(`/workflows/${workflowId}`, {
      method: 'PUT',
      body: JSON.stringify(workflow),
    });
  }

  async searchWorkflows(query: string, userId: string, threshold: number = 0.7): Promise<WorkflowDefinition[]> {
    return this.request('/workflows/search', {
      method: 'POST',
      body: JSON.stringify({ query, user_id: userId, threshold }),
    });
  }

  async deleteWorkflow(workflowId: string): Promise<{ message: string; workflow_id: string }> {
    return this.request(`/workflows/${workflowId}`, {
      method: 'DELETE',
    });
  }

  async deleteEpisode(episodeUuid: string): Promise<{ message: string; uuid: string }> {
    return this.request(`/episodes/${episodeUuid}`, {
      method: 'DELETE',
    });
  }
}

export interface ConfigValue {
  key: string;
  value: any;
  category: string;
  data_type: string;
  is_sensitive: boolean;
  updated_at: string;
  description: string;
}

export interface SettingsResponse {
  settings: Record<string, ConfigValue[]>;
  total: number;
}

export interface UpdateSettingsResponse {
  message: string;
  success_count: number;
  failed_keys: string[];
  updated_keys: string[];
}

export interface ValidateSettingsResponse {
  valid: boolean;
  results: Record<string, {
    valid: boolean;
    error?: string;
  }>;
}

export interface ResetSettingsResponse {
  message: string;
  success_count: number;
  failed_keys: string[];
}

export interface DeleteDatabaseResponse {
  message: string;
  customer_id: string;
  timestamp: string;
}

// ============================================================================
// GitHub OAuth Types
// ============================================================================

export interface GitHubAuthResponse {
  customer_id: string;
  api_key: string;
  github_username: string;
  message: string;
}

export interface AuthApiKeyResponse {
  api_key: string;
  customer_id: string;
  github_username?: string;
}

// ============================================================================
// GitHub OAuth Functions (standalone, not part of RyumemAPI class)
// ============================================================================

/**
 * Exchange GitHub OAuth code for API key
 * This is used after the OAuth redirect from GitHub
 */
export async function exchangeGitHubCode(
  code: string,
  redirectUri?: string
): Promise<GitHubAuthResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/github/callback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, redirect_uri: redirectUri }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'GitHub authentication failed');
  }

  return response.json();
}

export interface GitHubAuthUrlResponse {
  auth_url: string;
  configured: boolean;
}

/**
 * Get the GitHub OAuth authorization URL from the server
 */
export async function getGitHubAuthUrl(): Promise<GitHubAuthUrlResponse> {
  const redirectUri = typeof window !== 'undefined'
    ? `${window.location.origin}/login`
    : '/login';

  const response = await fetch(
    `${API_BASE_URL}/auth/github/url?redirect_uri=${encodeURIComponent(redirectUri)}`
  );

  if (!response.ok) {
    throw new Error('Failed to get GitHub auth URL');
  }

  return response.json();
}

/**
 * Get full API key for authenticated user (requires existing auth)
 */
export async function getFullApiKey(): Promise<AuthApiKeyResponse> {
  const apiKey = typeof window !== 'undefined' ? localStorage.getItem('ryumem_api_key') : null;

  if (!apiKey) {
    throw new Error('Not authenticated');
  }

  const response = await fetch(`${API_BASE_URL}/auth/api-key`, {
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey,
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get API key');
  }

  return response.json();
}

// ============================================================================
// Workflow Types
// ============================================================================

export type NodeType = "tool" | "mcp" | "llm_trigger" | "user_trigger" | "condition";

export interface RetryConfig {
  enabled: boolean;
  max_attempts: number;
  backoff_strategy: "fixed" | "exponential";
  initial_delay_ms: number;
  max_delay_ms: number;
}

export interface ConditionBranch {
  branch_id: string;
  condition_expr: string;
  next_nodes: string[];
}

export interface WorkflowNode {
  node_id: string;
  node_type?: NodeType;

  // Tool/MCP specific
  tool_name?: string;
  mcp_server?: string;

  // LLM Trigger specific
  llm_prompt?: string;
  llm_output_variable?: string;

  // User Trigger specific
  user_prompt?: string;
  user_input_variable?: string;

  // Condition specific
  branches?: ConditionBranch[];
  default_branch?: string;

  // Common fields
  input_params: Record<string, any>;
  dependencies: string[];
  retry_config?: RetryConfig;
  timeout_ms?: number;
}

export interface Tool {
  tool_name: string;
  description: string;
  mentions?: number;
  created_at?: string;
}

export interface WorkflowDefinition {
  workflow_id: string;
  name: string;
  description: string;
  query_templates: string[];
  nodes: WorkflowNode[];
  created_at: string;
  updated_at: string;
  success_count: number;
  failure_count: number;
  user_id?: string;
}

export const api = new RyumemAPI();

