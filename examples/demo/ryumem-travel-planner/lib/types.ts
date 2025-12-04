export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  toolCalls?: ToolCall[];
  executionTime?: number;
  usedMemory?: boolean;
  similarQueries?: string[];
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
