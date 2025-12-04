export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  toolCalls?: ToolCall[];
  executionTime?: number;
  usedMemory?: boolean;
  similarQueries?: string[];
  generatedWorkflow?: Workflow;
  appliedWorkflow?: Workflow;
}

export interface ToolCall {
  id: string;
  name: string;
  status: "pending" | "running" | "completed" | "error";
  input?: Record<string, any>;
  output?: Record<string, any>;
  timestamp: Date;
}

export interface MemoryEntry {
  id: string;
  query: string;
  context: string;
  timestamp: Date;
  similarity?: number;
  executionTime: number;
}

export interface ToolStats {
  name: string;
  calls: number;
  lastUsed: Date;
}

export interface PerformanceMetric {
  queryId: string;
  query: string;
  executionTime: number;
  usedMemory: boolean;
  timeSaved: number;
  timestamp: Date;
}

export interface WorkflowTool {
  name: string;
  enabled: boolean;
  category: "exploratory" | "core";
  order: number;
  description: string;
}

export interface WorkflowNode {
  id: string;
  toolName: string;
  enabled: boolean;
  category: "exploratory" | "core";
  description: string;
  position: { x: number; y: number };
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  type: "default" | "parallel";
}

export interface Workflow {
  id: string;
  name: string;
  queryPattern: string;
  tools: WorkflowTool[];
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  createdFrom: string[];
  timestamp: Date;
  isCustom: boolean;
  matchCount: number;
  avgExecutionTime?: number;
}

export interface WorkflowMatch {
  workflow: Workflow;
  similarity: number;
  reason: string;
}
