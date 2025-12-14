/**
 * Ryumem Authentication Module
 * Handles API key management and GitHub Device Code Flow for CLI authentication
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export interface AuthConfig {
  apiUrl: string;
  tokenCachePath?: string;
}

export interface CachedCredentials {
  api_key: string;
  github_username?: string;
  customer_id?: string;
  cached_at: string;
}

export interface DeviceCodeResponse {
  device_code: string;
  user_code: string;
  verification_uri: string;
  expires_in: number;
  interval: number;
}

export interface DevicePollResponse {
  status: 'pending' | 'complete' | 'error';
  customer_id?: string;
  api_key?: string;
  github_username?: string;
  error?: string;
}

const DEFAULT_CACHE_PATH = path.join(os.homedir(), '.ryumem', 'credentials.json');

export class RyumemAuth {
  private apiUrl: string;
  private cachePath: string;

  constructor(config: AuthConfig) {
    this.apiUrl = config.apiUrl;
    this.cachePath = config.tokenCachePath || DEFAULT_CACHE_PATH;
  }

  /**
   * Get API key, using cached credentials or initiating device flow if needed
   */
  async getApiKey(): Promise<string> {
    // 1. Check environment variable first (highest priority)
    const envKey = process.env.RYUMEM_API_KEY;
    if (envKey) {
      console.error('Using API key from RYUMEM_API_KEY environment variable');
      return envKey;
    }

    // 2. Check cached credentials
    const cached = this.loadCachedCredentials();
    if (cached) {
      console.error(`Using cached API key (GitHub: @${cached.github_username || 'unknown'})`);
      return cached.api_key;
    }

    // 3. No credentials found, initiate device flow
    console.error('No API key found. Starting GitHub device code authentication...');
    return this.deviceCodeFlow();
  }

  /**
   * Load cached credentials from disk
   */
  private loadCachedCredentials(): CachedCredentials | null {
    try {
      if (fs.existsSync(this.cachePath)) {
        const data = fs.readFileSync(this.cachePath, 'utf-8');
        const credentials = JSON.parse(data) as CachedCredentials;

        // Check if api_key exists
        if (credentials.api_key) {
          return credentials;
        }
      }
    } catch (error) {
      console.error('Could not load cached credentials:', error instanceof Error ? error.message : String(error));
    }
    return null;
  }

  /**
   * Save credentials to disk
   */
  private saveCredentials(credentials: CachedCredentials): void {
    try {
      // Ensure directory exists
      const dir = path.dirname(this.cachePath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }

      fs.writeFileSync(this.cachePath, JSON.stringify(credentials, null, 2));
      console.error(`Credentials cached to ${this.cachePath}`);
    } catch (error) {
      console.error('Could not cache credentials:', error instanceof Error ? error.message : String(error));
    }
  }

  /**
   * Perform GitHub Device Code Flow
   */
  private async deviceCodeFlow(): Promise<string> {
    // Step 1: Request device code
    const deviceCodeResponse = await this.requestDeviceCode();

    // Step 2: Display instructions to user
    console.error('\n=================================================');
    console.error('GitHub Authentication Required');
    console.error('=================================================');
    console.error(`\n  1. Open: ${deviceCodeResponse.verification_uri}`);
    console.error(`  2. Enter code: ${deviceCodeResponse.user_code}`);
    console.error(`\n  Waiting for authorization...`);
    console.error('=================================================\n');

    // Step 3: Poll for completion
    const result = await this.pollForToken(
      deviceCodeResponse.device_code,
      deviceCodeResponse.interval,
      deviceCodeResponse.expires_in
    );

    if (result.status === 'complete' && result.api_key) {
      // Save credentials
      this.saveCredentials({
        api_key: result.api_key,
        github_username: result.github_username,
        customer_id: result.customer_id,
        cached_at: new Date().toISOString(),
      });

      console.error(`\nAuthenticated as @${result.github_username || 'unknown'}`);
      return result.api_key;
    }

    throw new Error(result.error || 'Authentication failed');
  }

  /**
   * Request a device code from the backend
   */
  private async requestDeviceCode(): Promise<DeviceCodeResponse> {
    const response = await fetch(`${this.apiUrl}/auth/github/device`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Failed to start device flow: ${error}`);
    }

    return response.json();
  }

  /**
   * Poll for token after user authorizes
   */
  private async pollForToken(
    deviceCode: string,
    interval: number,
    expiresIn: number
  ): Promise<DevicePollResponse> {
    const startTime = Date.now();
    const expiryTime = startTime + (expiresIn * 1000);

    while (Date.now() < expiryTime) {
      // Wait for the specified interval
      await this.sleep(interval * 1000);

      try {
        const response = await fetch(`${this.apiUrl}/auth/github/device/poll`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ device_code: deviceCode }),
        });

        if (!response.ok) {
          throw new Error(`Poll request failed: ${response.status}`);
        }

        const result: DevicePollResponse = await response.json();

        if (result.status === 'complete') {
          return result;
        }

        if (result.status === 'error') {
          throw new Error(result.error || 'Authentication error');
        }

        // Still pending, continue polling
        process.stderr.write('.');
      } catch (error) {
        // Network error, continue polling
        console.error('Poll error:', error instanceof Error ? error.message : String(error));
      }
    }

    throw new Error('Device code expired. Please try again.');
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Clear cached credentials (logout)
   */
  clearCredentials(): void {
    try {
      if (fs.existsSync(this.cachePath)) {
        fs.unlinkSync(this.cachePath);
        console.error('Cached credentials cleared');
      }
    } catch (error) {
      console.error('Could not clear credentials:', error instanceof Error ? error.message : String(error));
    }
  }
}
