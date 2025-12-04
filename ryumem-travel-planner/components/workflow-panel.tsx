"use client";

import { useState, useEffect } from "react";
import { Settings, Sparkles, Check, X, List, Network } from "lucide-react";
import { MockMemoryStore } from "@/lib/mock-workflow";
import { Workflow, WorkflowTool } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { WorkflowGraphView } from "./workflow-graph-view";
import { cn } from "@/lib/utils";

interface WorkflowPanelProps {
  memoryStore: MockMemoryStore;
  currentWorkflow?: Workflow;
  onWorkflowUpdate: (workflow: Workflow) => void;
}

type ViewMode = "list" | "graph";

export function WorkflowPanel({ memoryStore, currentWorkflow, onWorkflowUpdate }: WorkflowPanelProps) {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [editingWorkflowId, setEditingWorkflowId] = useState<string | null>(null);
  const [editedTools, setEditedTools] = useState<WorkflowTool[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [selectedWorkflowForGraph, setSelectedWorkflowForGraph] = useState<Workflow | null>(null);

  // Poll for workflow updates
  useEffect(() => {
    const updateWorkflows = () => {
      setWorkflows(memoryStore.getAllWorkflows());
    };

    updateWorkflows();
    const interval = setInterval(updateWorkflows, 1000);

    return () => clearInterval(interval);
  }, [memoryStore]);

  const handleEditWorkflow = (workflow: Workflow) => {
    setEditingWorkflowId(workflow.id);
    setEditedTools([...workflow.tools]);
  };

  const handleToggleTool = (toolName: string) => {
    setEditedTools(prev =>
      prev.map(tool =>
        tool.name === toolName && tool.category === "exploratory"
          ? { ...tool, enabled: !tool.enabled }
          : tool
      )
    );
  };

  const handleSaveWorkflow = () => {
    if (editingWorkflowId) {
      memoryStore.updateWorkflow(editingWorkflowId, editedTools);
      const updatedWorkflow = workflows.find(w => w.id === editingWorkflowId);
      if (updatedWorkflow) {
        onWorkflowUpdate({ ...updatedWorkflow, tools: editedTools, isCustom: true });
      }
      setEditingWorkflowId(null);
      setEditedTools([]);
    }
  };

  const handleCancelEdit = () => {
    setEditingWorkflowId(null);
    setEditedTools([]);
  };

  // Auto-select first workflow for graph view when workflows exist
  useEffect(() => {
    if (workflows.length > 0 && !selectedWorkflowForGraph) {
      setSelectedWorkflowForGraph(workflows[0]);
    }
  }, [workflows, selectedWorkflowForGraph]);

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-purple-600" />
            Workflows
          </h2>
          <div className="flex items-center gap-1 bg-muted p-1 rounded-md">
            <Button
              variant={viewMode === "list" ? "secondary" : "ghost"}
              size="sm"
              onClick={() => setViewMode("list")}
              className="h-6 px-2"
            >
              <List className="h-3 w-3 mr-1" />
              <span className="text-xs">List</span>
            </Button>
            <Button
              variant={viewMode === "graph" ? "secondary" : "ghost"}
              size="sm"
              onClick={() => setViewMode("graph")}
              className="h-6 px-2"
            >
              <Network className="h-3 w-3 mr-1" />
              <span className="text-xs">Graph</span>
            </Button>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          {workflows.length === 0 ? "No workflows yet" : `${workflows.length} workflow${workflows.length > 1 ? 's' : ''}`}
        </p>
      </div>

      {/* List View */}
      {viewMode === "list" && (
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {workflows.length === 0 && (
          <div className="text-center py-8">
            <div className="bg-purple-50 dark:bg-purple-950 rounded-lg p-4 mb-3">
              <Sparkles className="h-8 w-8 text-purple-600 mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">
                Workflows will appear here after your first query
              </p>
            </div>
            <div className="text-xs text-muted-foreground space-y-2 text-left">
              <p className="font-semibold">How workflows work:</p>
              <ul className="space-y-1 list-disc list-inside">
                <li>Auto-generated after each query</li>
                <li>Edit to enable/disable exploratory tools</li>
                <li>Auto-applied to similar queries</li>
                <li>Optimizes execution time (76-77%)</li>
              </ul>
            </div>
          </div>
        )}

        {workflows.map((workflow, index) => {
          const isEditing = editingWorkflowId === workflow.id;
          const toolsToDisplay = isEditing ? editedTools : workflow.tools;
          const enabledCount = toolsToDisplay.filter(t => t.enabled).length;
          const isActive = currentWorkflow?.id === workflow.id;

          return (
            <div
              key={workflow.id}
              className={cn(
                "rounded-lg border p-3 space-y-2 transition-colors",
                isActive && "bg-purple-50 dark:bg-purple-950 border-purple-200 dark:border-purple-800"
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <p className="text-xs font-medium truncate">
                      {workflow.name}
                    </p>
                    {workflow.isCustom && (
                      <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                        Custom
                      </Badge>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                    <span>{enabledCount}/10 tools</span>
                    {workflow.matchCount > 0 && (
                      <span>• {workflow.matchCount} match{workflow.matchCount > 1 ? 'es' : ''}</span>
                    )}
                  </div>
                </div>
                {!isEditing && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleEditWorkflow(workflow)}
                    className="h-7 w-7 p-0"
                  >
                    <Settings className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>

              {isEditing && (
                <div className="space-y-2 pt-2 border-t">
                  <p className="text-xs font-semibold">Configure Tools</p>
                  <div className="space-y-1.5 max-h-40 overflow-y-auto">
                    {toolsToDisplay
                      .sort((a, b) => a.order - b.order)
                      .map((tool) => (
                        <div
                          key={tool.name}
                          className="flex items-center justify-between gap-2 py-1"
                        >
                          <div className="flex-1 min-w-0">
                            <p className={cn(
                              "text-xs truncate",
                              tool.category === "core" && "font-semibold"
                            )}>
                              {tool.description}
                            </p>
                            {tool.category === "core" && (
                              <p className="text-[10px] text-muted-foreground">
                                Core tool (always enabled)
                              </p>
                            )}
                          </div>
                          <Switch
                            checked={tool.enabled}
                            onCheckedChange={() => handleToggleTool(tool.name)}
                            disabled={tool.category === "core"}
                            className="scale-75"
                          />
                        </div>
                      ))}
                  </div>
                  <div className="flex gap-2 pt-2">
                    <Button
                      size="sm"
                      onClick={handleSaveWorkflow}
                      className="flex-1 h-7 text-xs"
                    >
                      <Check className="h-3 w-3 mr-1" />
                      Save
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={handleCancelEdit}
                      className="flex-1 h-7 text-xs"
                    >
                      <X className="h-3 w-3 mr-1" />
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
        </div>
      )}

      {/* Graph View */}
      {viewMode === "graph" && (
        <div className="flex-1 flex flex-col">
          {workflows.length === 0 ? (
            <div className="text-center py-8 px-4">
              <div className="bg-purple-50 dark:bg-purple-950 rounded-lg p-4 mb-3">
                <Network className="h-8 w-8 text-purple-600 mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">
                  No workflows to visualize yet
                </p>
              </div>
              <p className="text-xs text-muted-foreground">
                Execute a query to generate your first workflow graph
              </p>
            </div>
          ) : (
            <>
              {/* Workflow selector for graph view */}
              <div className="p-3 border-b bg-muted/30">
                <select
                  value={selectedWorkflowForGraph?.id || ""}
                  onChange={(e) => {
                    const workflow = workflows.find(w => w.id === e.target.value);
                    if (workflow) setSelectedWorkflowForGraph(workflow);
                  }}
                  className="w-full text-xs bg-background border rounded px-2 py-1"
                >
                  {workflows.map((workflow) => (
                    <option key={workflow.id} value={workflow.id}>
                      {workflow.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Graph visualization */}
              <div className="flex-1 relative">
                {selectedWorkflowForGraph && (
                  <WorkflowGraphView workflow={selectedWorkflowForGraph} />
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
