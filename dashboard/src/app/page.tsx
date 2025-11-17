"use client";

import { useState, useEffect } from "react";
import { Brain, Database, Network, BookOpen, GitBranch, List, Wrench, Settings } from "lucide-react";
import { EpisodeForm } from "@/components/episode-form";
import { ChatInterface } from "@/components/chat-interface";
import { StatsPanel } from "@/components/stats-panel";
import { GraphVisualization } from "@/components/graph-visualization";
import { EntityBrowser } from "@/components/entity-browser";
import { EntityDetailPanel } from "@/components/entity-detail-panel";
import { ToolAnalyticsPanel } from "@/components/tool-analytics-panel";
import { AgentInstructionEditor } from "@/components/agent-instruction-editor";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, Entity, GraphDataResponse, EntitiesListResponse, Edge } from "@/lib/api";

export default function Home() {
  const [groupId, setGroupId] = useState("user1234");
  const [userId, setUserId] = useState("");
  const [refreshStats, setRefreshStats] = useState(0);

  // Graph visualization state
  const [graphData, setGraphData] = useState<GraphDataResponse | null>(null);
  const [isLoadingGraph, setIsLoadingGraph] = useState(false);

  // Entity browser state
  const [entitiesData, setEntitiesData] = useState<EntitiesListResponse | null>(null);
  const [isLoadingEntities, setIsLoadingEntities] = useState(false);
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [entityRelationships, setEntityRelationships] = useState<Edge[]>([]);
  const [entityType, setEntityType] = useState<string | undefined>(undefined);
  const [entitiesOffset, setEntitiesOffset] = useState(0);

  const handleEpisodeAdded = () => {
    // Trigger stats refresh
    setRefreshStats(prev => prev + 1);
  };

  // Load graph data
  const loadGraphData = async () => {
    setIsLoadingGraph(true);
    try {
      const data = await api.getGraphData(groupId, userId, 1000);
      setGraphData(data);
    } catch (error) {
      console.error("Failed to load graph data:", error);
    } finally {
      setIsLoadingGraph(false);
    }
  };

  // Load entities list
  const loadEntities = async (offset: number = 0, type?: string) => {
    setIsLoadingEntities(true);
    try {
      const data = await api.getEntitiesList(groupId, userId, type, offset, 50);
      setEntitiesData(data);
    } catch (error) {
      console.error("Failed to load entities:", error);
    } finally {
      setIsLoadingEntities(false);
    }
  };

  // Handle entity selection
  const handleEntityClick = async (entity: Entity) => {
    setSelectedEntity(entity);

    // Load all relationships for this entity
    try {
      const allRelationships = await api.getRelationshipsList(groupId, userId, undefined, 0, 1000);
      const entityRels = allRelationships.relationships.filter(
        (rel) => rel.source_name === entity.name || rel.target_name === entity.name
      );
      setEntityRelationships(entityRels);
    } catch (error) {
      console.error("Failed to load entity relationships:", error);
    }
  };

  // Handle entity type filter change
  const handleEntityTypeChange = (type?: string) => {
    setEntityType(type);
    setEntitiesOffset(0);
    loadEntities(0, type);
  };

  // Handle entity pagination
  const handleEntitiesLoadMore = (offset: number) => {
    setEntitiesOffset(offset);
    loadEntities(offset, entityType);
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
          <TabsList className="grid w-full grid-cols-3 lg:grid-cols-6 lg:w-full">
            <TabsTrigger value="chat" className="flex items-center gap-2">
              <BookOpen className="h-4 w-4" />
              Chat & Query
            </TabsTrigger>
            <TabsTrigger
              value="graph"
              className="flex items-center gap-2"
              onClick={() => !graphData && loadGraphData()}
            >
              <GitBranch className="h-4 w-4" />
              Graph
            </TabsTrigger>
            <TabsTrigger
              value="entities"
              className="flex items-center gap-2"
              onClick={() => !entitiesData && loadEntities()}
            >
              <List className="h-4 w-4" />
              Entities
            </TabsTrigger>
            <TabsTrigger value="episodes" className="flex items-center gap-2">
              <Database className="h-4 w-4" />
              Add Episodes
            </TabsTrigger>
            <TabsTrigger value="analytics" className="flex items-center gap-2">
              <Wrench className="h-4 w-4" />
              Tool Analytics
            </TabsTrigger>
            <TabsTrigger value="settings" className="flex items-center gap-2">
              <Settings className="h-4 w-4" />
              Agent Settings
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

          <TabsContent value="graph" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <GitBranch className="h-5 w-5" />
                  Knowledge Graph Visualization
                </CardTitle>
                <CardDescription>
                  Interactive visualization of entities and relationships in your knowledge graph
                </CardDescription>
              </CardHeader>
              <CardContent>
                {isLoadingGraph ? (
                  <div className="flex items-center justify-center h-[700px]">
                    <div className="text-center">
                      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
                      <p className="text-muted-foreground">Loading graph...</p>
                    </div>
                  </div>
                ) : graphData ? (
                  <GraphVisualization data={graphData} />
                ) : (
                  <div className="flex items-center justify-center h-[700px]">
                    <p className="text-muted-foreground">No graph data available</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="entities" className="space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="lg:col-span-2">
                {isLoadingEntities ? (
                  <Card>
                    <CardContent className="p-8">
                      <div className="flex items-center justify-center">
                        <div className="text-center">
                          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
                          <p className="text-muted-foreground">Loading entities...</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ) : entitiesData ? (
                  <EntityBrowser
                    data={entitiesData}
                    onEntityClick={handleEntityClick}
                    onLoadMore={handleEntitiesLoadMore}
                    onFilterChange={handleEntityTypeChange}
                    groupId={groupId}
                  />
                ) : (
                  <Card>
                    <CardContent className="p-8">
                      <p className="text-center text-muted-foreground">No entities available</p>
                    </CardContent>
                  </Card>
                )}
              </div>
              <div>
                <EntityDetailPanel
                  entity={selectedEntity}
                  relationships={entityRelationships}
                  onClose={() => setSelectedEntity(null)}
                  onEntityClick={(entityName) => {
                    // Find and select entity by name
                    const entity = entitiesData?.entities.find(e => e.name === entityName);
                    if (entity) {
                      handleEntityClick(entity);
                    }
                  }}
                />
              </div>
            </div>
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

          <TabsContent value="analytics" className="space-y-4">
            <ToolAnalyticsPanel groupId={groupId} userId={userId} />
          </TabsContent>

          <TabsContent value="settings" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Settings className="h-5 w-5" />
                  Agent Instruction Management
                </CardTitle>
                <CardDescription>
                  Configure custom instructions for your agents
                </CardDescription>
              </CardHeader>
              <CardContent>
                <AgentInstructionEditor userId={userId} />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Footer Info */}
        <div className="mt-12 text-center text-sm text-muted-foreground">
          <p>
            Powered by{" "}
            <a
              href="https://github.com/predictable-labs/ryumem"
              className="underline hover:text-primary"
              target="_blank"
              rel="noopener noreferrer"
            >
              Ryumem
            </a>{" "}
            - Memory layer for your agentic workflow.
          </p>
        </div>
      </div>
    </main>
  );
}

