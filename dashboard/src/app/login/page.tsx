"use client";

import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Brain, Github, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import Meteors from "@/components/magicui/meteors";
import { exchangeGitHubCode, getGitHubAuthUrl } from "@/lib/api";

export default function LoginPage() {
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [showApiKeyLogin, setShowApiKeyLogin] = useState(false);
  const [isProcessingOAuth, setIsProcessingOAuth] = useState(false);
  const [isGitHubConfigured, setIsGitHubConfigured] = useState<boolean | null>(null);
  const router = useRouter();
  const searchParams = useSearchParams();

  // Check if GitHub OAuth is configured
  useEffect(() => {
    const checkGitHubConfig = async () => {
      try {
        const response = await getGitHubAuthUrl();
        setIsGitHubConfigured(response.configured);
      } catch {
        setIsGitHubConfigured(false);
      }
    };
    checkGitHubConfig();
  }, []);

  // Handle GitHub OAuth callback
  useEffect(() => {
    const code = searchParams.get("code");
    if (code && !isProcessingOAuth) {
      setIsProcessingOAuth(true);
      handleGitHubCallback(code);
    }
  }, [searchParams]);

  const handleGitHubCallback = async (code: string) => {
    setIsLoading(true);
    setError("");

    try {
      const redirectUri = process.env.NEXT_PUBLIC_GITHUB_REDIRECT_URI || `${window.location.origin}/login`;
      const result = await exchangeGitHubCode(code, redirectUri);

      // Store the API key
      localStorage.setItem("ryumem_api_key", result.api_key);

      // Clear the code from URL and redirect to dashboard
      window.history.replaceState({}, document.title, "/login");
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "GitHub authentication failed");
      // Clear the code from URL
      window.history.replaceState({}, document.title, "/login");
    } finally {
      setIsLoading(false);
      setIsProcessingOAuth(false);
    }
  };

  const handleGitHubLogin = async () => {
    try {
      setIsLoading(true);
      const response = await getGitHubAuthUrl();
      if (response.configured && response.auth_url) {
        window.location.href = response.auth_url;
      } else {
        setError("GitHub OAuth not configured");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to initiate GitHub login");
    } finally {
      setIsLoading(false);
    }
  };

  const handleApiKeyLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!apiKey.trim()) {
      setError("API Key is required");
      return;
    }

    try {
      if (!apiKey.startsWith("ryu_")) {
        setError("Invalid API Key format (should start with 'ryu_')");
        return;
      }

      localStorage.setItem("ryumem_api_key", apiKey);
      router.push("/");
    } catch (err) {
      setError("Failed to login");
    }
  };

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-background p-4 md:p-8">
      <Meteors number={60} />
      <div className="z-10 w-full max-w-md">
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="mb-4 rounded-xl bg-primary/10 p-3">
            <Brain className="h-10 w-10 text-primary" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight">Welcome back</h1>
          <p className="mt-2 text-muted-foreground">
            Sign in to access your dashboard
          </p>
        </div>

        <Card className="border-border/50 bg-card/50 backdrop-blur-xl">
          <CardHeader>
            <CardTitle>Sign In</CardTitle>
            <CardDescription>
              {isProcessingOAuth ? "Completing GitHub authentication..." : "Choose your preferred sign-in method"}
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4">
            {/* GitHub OAuth Button */}
            {isGitHubConfigured === true && (
              <Button
                type="button"
                variant="outline"
                className="w-full"
                onClick={handleGitHubLogin}
                disabled={isLoading || isProcessingOAuth}
              >
                <Github className="mr-2 h-4 w-4" />
                {isLoading && isProcessingOAuth ? "Authenticating..." : "Continue with GitHub"}
              </Button>
            )}

            {/* Divider */}
            {isGitHubConfigured === true && (
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <span className="w-full border-t border-border" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-card px-2 text-muted-foreground">Or</span>
                </div>
              </div>
            )}

            {/* API Key Login Toggle */}
            <Button
              type="button"
              variant="ghost"
              className="w-full justify-between"
              onClick={() => setShowApiKeyLogin(!showApiKeyLogin)}
            >
              <span>Sign in with API Key</span>
              {showApiKeyLogin ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </Button>

            {/* API Key Form (collapsible) */}
            {(showApiKeyLogin || isGitHubConfigured === false) && (
              <form onSubmit={handleApiKeyLogin} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="api-key">API Key</Label>
                  <Input
                    id="api-key"
                    name="apiKey"
                    type="password"
                    placeholder="ryu_..."
                    required
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    disabled={isLoading}
                  />
                </div>
                <Button type="submit" className="w-full" disabled={isLoading}>
                  Sign in with API Key
                </Button>
              </form>
            )}

            {/* Error Message */}
            {error && (
              <div className="text-sm font-medium text-destructive text-center">
                {error}
              </div>
            )}
          </CardContent>

          {isGitHubConfigured === false && (
            <CardFooter className="text-xs text-muted-foreground text-center">
              <p className="w-full">
                GitHub login not configured. Contact admin to enable OAuth.
              </p>
            </CardFooter>
          )}
        </Card>
      </div>
    </div>
  );
}
