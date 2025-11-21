"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Brain, Database, Network, BookOpen, GitBranch, List, Wrench, Settings, User, History, Cog, LogOut } from "lucide-react";
import { EpisodesList } from "@/components/episodes-list";
import { EpisodeFormModal } from "@/components/episode-form-modal";
import { ChatInterface } from "@/components/chat-interface";
import { StatsPanel } from "@/components/stats-panel";
import { GraphVisualization } from "@/components/graph-visualization";
import { EntityBrowser } from "@/components/entity-browser";
import { EntityDetailPanel } from "@/components/entity-detail-panel";
import { ToolAnalyticsPanel } from "@/components/tool-analytics-panel";
import { AgentInstructionEditor } from "@/components/agent-instruction-editor";
import AugmentedQueriesViewer from "@/components/augmented-queries-viewer";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { api, Entity, GraphDataResponse, EntitiesListResponse, Edge } from "@/lib/api";

export default function Home() {
  const [users, setUsers] = useState<string[]>([]);
  const [userId, setUserId] = useState<string>("");
  const [isLoadingUsers, setIsLoadingUsers] = useState(true);
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

  // Episode modal state
  const [isEpisodeModalOpen, setIsEpisodeModalOpen] = useState(false);
  const [episodeListRefresh, setEpisodeListRefresh] = useState(0);

  // Tool analytics state - shared between tabs
  const [activeTab, setActiveTab] = useState("chat");
  const [selectedToolForAnalytics, setSelectedToolForAnalytics] = useState<string | null>(null);

  // Load users on mount
  useEffect(() => {
    const loadData = async () => {
      setIsLoadingUsers(true);
      try {
        const usersList = await api.getUsers();

        setUsers(usersList);
        if (usersList.length > 0) {
          setUserId(usersList[0]); // Set first user as default
        }
      } catch (error) {
        console.error("Failed to load initial data:", error);
      } finally {
        setIsLoadingUsers(false);
      }
    };

    loadData();
  }, []);

  const handleEpisodeAdded = () => {
    // Trigger stats refresh
    setRefreshStats(prev => prev + 1);
    // Trigger episode list refresh
    setEpisodeListRefresh(prev => prev + 1);
  };

  const handleToolClick = (toolName: string) => {
    // Set the tool to be selected in analytics
    setSelectedToolForAnalytics(toolName);
    // Switch to analytics tab
    setActiveTab("analytics");
  };

  // Load graph data
  const loadGraphData = async () => {
    setIsLoadingGraph(true);
    try {
      const data = await api.getGraphData(userId, 1000);
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
      const data = await api.getEntitiesList(userId, type, offset, 50);
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
      const allRelationships = await api.getRelationshipsList(userId, undefined, 0, 1000);
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
    <div className="min-h-0">
      <div className="container mx-auto p-6 max-w-7xl">

        {/* User Selector */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-4 flex-1">
                <User className="h-5 w-5 text-muted-foreground" />
                <div className="flex-1">
                  <Label htmlFor="user-select" className="text-sm font-medium">
                    Select User
                  </Label>
                  <p className="text-xs text-muted-foreground mb-2">
                    Choose a user to filter episodes, entities, and graph data
                  </p>
                  {isLoadingUsers ? (
                    <div className="text-sm text-muted-foreground">Loading users...</div>
                  ) : users.length > 0 ? (
                    <Select value={userId} onValueChange={setUserId}>
                      <SelectTrigger id="user-select" className="w-full max-w-md">
                        <SelectValue placeholder="Select a user" />
                      </SelectTrigger>
                      <SelectContent>
                        {users.map((user) => (
                          <SelectItem key={user} value={user}>
                            {user}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <div className="text-sm text-muted-foreground">
                      No users found. Add some episodes first.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Stats Panel */}
        <div className="mb-6">
          <StatsPanel refreshKey={refreshStats} />
        </div>

        {/* Main Content */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-3 lg:grid-cols-7 lg:w-full">
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
              Episodes
            </TabsTrigger>
            <TabsTrigger value="queries" className="flex items-center gap-2">
              <History className="h-4 w-4" />
              Queries
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
                <ChatInterface userId={userId} />
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
                    userId={userId}
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
            <EpisodesList
              userId={userId}
              onAddEpisodeClick={() => setIsEpisodeModalOpen(true)}
              onToolClick={handleToolClick}
            />
            <EpisodeFormModal
              userId={userId}
              open={isEpisodeModalOpen}
              onOpenChange={setIsEpisodeModalOpen}
              onEpisodeAdded={handleEpisodeAdded}
            />
          </TabsContent>

          <TabsContent value="queries" className="space-y-4">
            <AugmentedQueriesViewer />
          </TabsContent>

          <TabsContent value="analytics" className="space-y-4">
            <ToolAnalyticsPanel userId={userId} preselectedTool={selectedToolForAnalytics} />
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
      </div>
    </div>
  );
}

