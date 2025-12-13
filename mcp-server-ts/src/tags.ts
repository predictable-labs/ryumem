/**
 * Standard tags for memory organization in MCP.
 *
 * Use these to ensure consistent tagging across agent memory storage.
 */

export enum MemoryTag {
  // Memory types
  PROJECT = "project",
  PREFERENCES = "preferences",
  DECISION = "decision",
  ISSUE = "issue",

  // Technical topics
  API = "api",
  DATABASE = "database",
  CODE = "code",
  TESTING = "testing",

  // Domains
  BACKEND = "backend",
  FRONTEND = "frontend",
  SECURITY = "security",
  PERFORMANCE = "performance",
}

/**
 * Convert enum values to array of strings
 */
export function tagsToArray(...tags: MemoryTag[]): string[] {
  return tags.map(t => t.toString());
}

/**
 * All valid tag values
 */
export const ALL_TAGS = Object.values(MemoryTag);
