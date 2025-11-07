"use client";

import { useState, useEffect } from "react";
import { Brain, Database, Network, BookOpen } from "lucide-react";
import { EpisodeForm } from "@/components/episode-form";
import { ChatInterface } from "@/components/chat-interface";
import { StatsPanel } from "@/components/stats-panel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function Home() {
  const [groupId, setGroupId] = useState("demo_user");
  const [userId, setUserId] = useState("demo_user");
  const [refreshStats, setRefreshStats] = useState(0);

  const handleEpisodeAdded = () => {
    // Trigger stats refresh
    setRefreshStats(prev => prev + 1);
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
      <div className="container mx-auto p-6 max-w-7xl">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-primary/10 rounded-lg">
              <Brain className="h-8 w-8 text-primary" />
            </div>
            <div>
              <h1 className="text-4xl font-bold tracking-tight">Ryumem Dashboard</h1>
              <p className="text-muted-foreground">
                Bi-temporal Knowledge Graph Memory System
              </p>
            </div>
          </div>
        </div>

        {/* Stats Panel */}
        <div className="mb-6">
          <StatsPanel groupId={groupId} refreshKey={refreshStats} />
        </div>

        {/* Main Content */}
        <Tabs defaultValue="chat" className="space-y-6">
          <TabsList className="grid w-full grid-cols-2 lg:w-[400px]">
            <TabsTrigger value="chat" className="flex items-center gap-2">
              <BookOpen className="h-4 w-4" />
              Chat & Query
            </TabsTrigger>
            <TabsTrigger value="episodes" className="flex items-center gap-2">
              <Database className="h-4 w-4" />
              Add Episodes
            </TabsTrigger>
          </TabsList>

          <TabsContent value="chat" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Brain className="h-5 w-5" />
                  Query Knowledge Graph
                </CardTitle>
                <CardDescription>
                  Ask questions and explore your knowledge graph using hybrid search
                  (semantic + BM25 + graph traversal)
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ChatInterface groupId={groupId} userId={userId} />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="episodes" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Network className="h-5 w-5" />
                  Add New Episode
                </CardTitle>
                <CardDescription>
                  Add memories to the knowledge graph. Entities and relationships
                  will be automatically extracted and resolved.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <EpisodeForm
                  groupId={groupId}
                  userId={userId}
                  onEpisodeAdded={handleEpisodeAdded}
                />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Footer Info */}
        <div className="mt-12 text-center text-sm text-muted-foreground">
          <p>
            Powered by{" "}
            <a
              href="https://github.com/yourusername/ryumem"
              className="underline hover:text-primary"
              target="_blank"
              rel="noopener noreferrer"
            >
              Ryumem
            </a>{" "}
            - A bi-temporal knowledge graph memory system inspired by Zep
          </p>
        </div>
      </div>
    </main>
  );
}

