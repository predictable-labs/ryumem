"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const router = useRouter();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!apiKey.trim()) {
      setError("API Key is required");
      return;
    }

    try {
      // Basic validation - just store it for now. 
      // Real validation happens when making API calls.
      // You could optionally call a lightweight endpoint like /health or /me here if available.
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
    <div className="flex min-h-screen flex-col items-center justify-center bg-black text-white">
      <div className="w-full max-w-md space-y-8 p-8 border border-zinc-800 rounded-xl bg-zinc-900/50">
        <div className="text-center">
          <h2 className="mt-6 text-3xl font-bold tracking-tight">
            Ryumem Dashboard
          </h2>
          <p className="mt-2 text-sm text-zinc-400">
            Enter your API Key to continue
          </p>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleLogin}>
          <div className="-space-y-px rounded-md shadow-sm">
            <div>
              <label htmlFor="api-key" className="sr-only">
                API Key
              </label>
              <input
                id="api-key"
                name="apiKey"
                type="password"
                required
                className="relative block w-full rounded-md border-0 bg-zinc-800 py-1.5 text-white ring-1 ring-inset ring-zinc-700 placeholder:text-zinc-400 focus:z-10 focus:ring-2 focus:ring-inset focus:ring-indigo-500 sm:text-sm sm:leading-6 px-3"
                placeholder="ryu_..."
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />
            </div>
          </div>

          {error && (
            <div className="text-red-500 text-sm text-center">{error}</div>
          )}

          <div>
            <button
              type="submit"
              className="group relative flex w-full justify-center rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
            >
              Sign in
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
