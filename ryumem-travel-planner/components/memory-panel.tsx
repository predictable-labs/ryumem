"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Brain, Database } from "lucide-react";
import { useMemoryStore } from "@/lib/memory-store-context";
import { MemoryEntry } from "@/lib/types";

export function MemoryPanel() {
  const memoryStore = useMemoryStore();
  const [memories, setMemories] = useState<MemoryEntry[]>([]);

  // Poll for memory updates
  useEffect(() => {
    const interval = setInterval(() => {
      setMemories(memoryStore.getAll());
    }, 1000);

    return () => clearInterval(interval);
  }, [memoryStore]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b">
        <div className="flex items-center gap-2">
          <Brain className="h-4 w-4" />
          <h2 className="font-semibold">Memory Store</h2>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          {memories.length} {memories.length === 1 ? 'query' : 'queries'} cached
        </p>
      </div>

      {/* Memory List */}
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-3">
          {memories.length === 0 ? (
            <div className="text-xs text-muted-foreground text-center py-8">
              No memories yet. Start a conversation!
            </div>
          ) : (
            memories.slice(0, 10).map((memory) => (
              <Card key={memory.id} className="text-xs">
                <CardHeader className="p-3 pb-2">
                  <CardTitle className="text-xs line-clamp-2">
                    {memory.query}
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-3 pt-0">
                  <div className="text-xs text-muted-foreground">
                    {(memory.executionTime / 1000).toFixed(2)}s • {memory.timestamp.toLocaleTimeString()}
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
