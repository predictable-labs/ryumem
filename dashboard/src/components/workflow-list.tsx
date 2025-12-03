"use client";

import { useState, useEffect } from "react";
import { Plus, Play, Trash2, Edit, CheckCircle, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, WorkflowDefinition } from "@/lib/api";

interface WorkflowListProps {
  userId?: string;
  onCreateClick: () => void;
  onEditClick: (workflow: WorkflowDefinition) => void;
  refreshKey?: number;
}

export function WorkflowList({ userId, onCreateClick, onEditClick, refreshKey }: WorkflowListProps) {
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    loadWorkflows();
  }, [userId, refreshKey]);

  const loadWorkflows = async () => {
    setIsLoading(true);
    try {
      const data = await api.listWorkflows(userId);
      setWorkflows(data);
    } catch (error) {
      console.error("Failed to load workflows:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (workflowId: string, workflowName: string) => {
    if (!confirm(`Are you sure you want to delete "${workflowName}"? This action cannot be undone.`)) {
      return;
    }

    setDeletingId(workflowId);
    try {
      await api.deleteWorkflow(workflowId);
      setWorkflows(workflows.filter(w => w.workflow_id !== workflowId));
    } catch (error) {
      console.error("Failed to delete workflow:", error);
      alert("Failed to delete workflow. Please try again.");
    } finally {
      setDeletingId(null);
    }
  };

  if (isLoading) {
    return <div>Loading workflows...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Workflows</h2>
        <Button onClick={onCreateClick} className="flex items-center gap-2">
          <Plus className="h-4 w-4" />
          Create Workflow
        </Button>
      </div>

      {workflows.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground mb-4">No workflows yet</p>
            <Button onClick={onCreateClick}>Create your first workflow</Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {workflows.map((workflow) => (
            <Card key={workflow.workflow_id} className="hover:shadow-md transition-shadow">
              <CardHeader>
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <CardTitle className="flex items-center gap-2">
                      {workflow.name}
                      <Badge variant="outline" className="ml-2">
                        {workflow.nodes.length} nodes
                      </Badge>
                    </CardTitle>
                    <CardDescription className="mt-1">
                      {workflow.description}
                    </CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onEditClick(workflow)}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDelete(workflow.workflow_id, workflow.name)}
                      disabled={deletingId === workflow.workflow_id}
                    >
                      <Trash2 className="h-4 w-4 text-red-600" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 text-sm">
                  <div>
                    <span className="font-semibold">Trigger: </span>
                    <code className="bg-muted px-2 py-1 rounded">
                      {workflow.query_template}
                    </code>
                  </div>
                  <div className="flex gap-4">
                    <div className="flex items-center gap-1">
                      <CheckCircle className="h-4 w-4 text-green-600" />
                      <span>{workflow.success_count} successes</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <XCircle className="h-4 w-4 text-red-600" />
                      <span>{workflow.failure_count} failures</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
