"use client";

import { MemoryPanel } from "@/components/memory-panel";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function MemoryStorePage() {
  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="border-b p-4 bg-card">
        <div className="flex items-center gap-4">
          <Link href="/">
            <Button variant="ghost" size="sm" className="gap-2">
              <ArrowLeft className="h-4 w-4" />
              Back to Chat
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold">Memory Store</h1>
            <p className="text-sm text-muted-foreground mt-1">
              View all cached queries and their execution times
            </p>
          </div>
        </div>
      </div>

      {/* Memory Panel */}
      <div className="flex-1 overflow-hidden">
        <MemoryPanel />
      </div>
    </div>
  );
}
