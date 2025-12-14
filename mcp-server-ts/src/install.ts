#!/usr/bin/env node

/**
 * Ryumem MCP Server Installer
 * Sets up the MCP server configuration for Claude Code
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { RyumemAuth } from './auth.js';

const DEFAULT_API_URL = 'https://api.ryumem.io';

interface McpServerConfig {
  type: string;
  command: string;
  args: string[];
  env?: Record<string, string>;
}

interface ClaudeConfig {
  mcpServers?: Record<string, McpServerConfig>;
  [key: string]: unknown;
}

function getClaudeConfigPath(client: string): string {
  const home = os.homedir();

  switch (client) {
    case 'claude-code':
    case 'claude':
      // Claude Code uses ~/.claude.json
      return path.join(home, '.claude.json');
    case 'claude-desktop':
      // Claude Desktop uses different paths per OS
      if (process.platform === 'darwin') {
        return path.join(home, 'Library', 'Application Support', 'Claude', 'claude_desktop_config.json');
      } else if (process.platform === 'win32') {
        return path.join(process.env.APPDATA || '', 'Claude', 'claude_desktop_config.json');
      } else {
        return path.join(home, '.config', 'claude', 'claude_desktop_config.json');
      }
    default:
      throw new Error(`Unknown client: ${client}. Supported: claude-code, claude-desktop`);
  }
}

function loadConfig(configPath: string): ClaudeConfig {
  try {
    if (fs.existsSync(configPath)) {
      const content = fs.readFileSync(configPath, 'utf-8');
      return JSON.parse(content);
    }
  } catch (error) {
    console.error(`Warning: Could not read existing config: ${error}`);
  }
  return {};
}

function saveConfig(configPath: string, config: ClaudeConfig): void {
  const dir = path.dirname(configPath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
}

async function uninstall(client: string): Promise<void> {
  console.log('\n🧠 Ryumem MCP Server Uninstaller\n');

  const configPath = getClaudeConfigPath(client);
  console.log(`📁 Config path: ${configPath}`);

  // Load existing config
  const config = loadConfig(configPath);

  if (config.mcpServers && config.mcpServers.ryumem) {
    delete config.mcpServers.ryumem;
    saveConfig(configPath, config);
    console.log('\n✅ Removed ryumem from Claude config');
  } else {
    console.log('\n⚠️  ryumem not found in config');
  }

  // Clear cached credentials
  const credentialsPath = path.join(os.homedir(), '.ryumem', 'credentials.json');
  try {
    if (fs.existsSync(credentialsPath)) {
      fs.unlinkSync(credentialsPath);
      console.log('✅ Cleared cached credentials');
    }
  } catch {
    // Ignore errors
  }

  console.log('\n🔄 Restart Claude Code to apply changes.\n');
}

async function install(options: {
  client: string;
  apiUrl: string;
  oauth: boolean;
  apiKey?: string;
}): Promise<void> {
  console.log('\n🧠 Ryumem MCP Server Installer\n');

  const configPath = getClaudeConfigPath(options.client);
  console.log(`📁 Config path: ${configPath}`);

  let apiKey = options.apiKey || process.env.RYUMEM_API_KEY;

  // If OAuth enabled and no API key, run device flow
  if (options.oauth && !apiKey) {
    console.log('\n🔐 Starting GitHub authentication...\n');
    const auth = new RyumemAuth({ apiUrl: options.apiUrl });
    apiKey = await auth.getApiKey();
  }

  if (!apiKey) {
    console.error('\n❌ No API key provided. Use --oauth or --api-key=<key> or set RYUMEM_API_KEY');
    process.exit(1);
  }

  // Load existing config
  const config = loadConfig(configPath);

  // Initialize mcpServers if not exists
  if (!config.mcpServers) {
    config.mcpServers = {};
  }

  // Add ryumem server config
  config.mcpServers.ryumem = {
    type: 'stdio',
    command: 'npx',
    args: ['-y', '@ryumem/mcp-server'],
    env: {
      RYUMEM_API_URL: options.apiUrl,
      RYUMEM_API_KEY: apiKey,
    },
  };

  // Save config
  saveConfig(configPath, config);

  console.log('\n✅ Ryumem MCP server configured successfully!');
  console.log(`\n📝 Added to: ${configPath}`);
  console.log('\n🔄 Restart Claude Code to activate the server.\n');
}

function printHelp(): void {
  console.log(`
🧠 Ryumem MCP Server Installer

Usage:
  npx @ryumem/mcp-server install [options]
  npx @ryumem/mcp-server uninstall [options]

Commands:
  install             Install and configure ryumem MCP server
  uninstall           Remove ryumem from Claude config and clear credentials

Options:
  --client <name>     Claude client to configure (default: claude-code)
                      Supported: claude-code, claude-desktop
  --oauth             Authenticate via GitHub OAuth (recommended)
  --api-key <key>     Use a specific API key
  --api-url <url>     API URL (default: https://api.ryumem.io)
  --help              Show this help message

Examples:
  npx @ryumem/mcp-server install --oauth
  npx @ryumem/mcp-server install --api-key ryu_xxxxx
  npx @ryumem/mcp-server install --api-url http://localhost:8000 --oauth
  npx @ryumem/mcp-server uninstall
`);
}

export async function runInstaller(args: string[]): Promise<void> {
  const options = {
    client: 'claude-code',
    apiUrl: process.env.RYUMEM_API_URL || DEFAULT_API_URL,
    oauth: false,
    apiKey: undefined as string | undefined,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];

    if (arg === '--help' || arg === '-h') {
      printHelp();
      process.exit(0);
    } else if (arg === '--oauth') {
      options.oauth = true;
    } else if (arg.startsWith('--client=')) {
      options.client = arg.split('=')[1];
    } else if (arg === '--client') {
      options.client = args[++i];
    } else if (arg.startsWith('--api-key=')) {
      options.apiKey = arg.split('=')[1];
    } else if (arg === '--api-key') {
      options.apiKey = args[++i];
    } else if (arg.startsWith('--api-url=')) {
      options.apiUrl = arg.split('=')[1];
    } else if (arg === '--api-url') {
      options.apiUrl = args[++i];
    }
  }

  await install(options);
}

export async function runUninstaller(args: string[]): Promise<void> {
  let client = 'claude-code';

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];

    if (arg === '--help' || arg === '-h') {
      printHelp();
      process.exit(0);
    } else if (arg.startsWith('--client=')) {
      client = arg.split('=')[1];
    } else if (arg === '--client') {
      client = args[++i];
    }
  }

  await uninstall(client);
}

// Run if called directly
if (process.argv[1]?.endsWith('install.js')) {
  runInstaller(process.argv.slice(2)).catch((error) => {
    console.error('Installation failed:', error);
    process.exit(1);
  });
}
