"use client";

import { useState } from "react";
import { Plus, Trash2, Save, X, Network } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, WorkflowDefinition, WorkflowNode } from "@/lib/api";
import { WorkflowGraph } from "./workflow-graph";

interface WorkflowEditorProps {
  workflow?: WorkflowDefinition;
  userId: string;
  onSave: () => void;
  onCancel: () => void;
}

export function WorkflowEditor({ workflow, userId, onSave, onCancel }: WorkflowEditorProps) {
  const [name, setName] = useState(workflow?.name || "");
  const [description, setDescription] = useState(workflow?.description || "");
  const [queryTemplates, setQueryTemplates] = useState<string[]>(
    workflow?.query_templates || [""]
  );
  const [nodes, setNodes] = useState<WorkflowNode[]>(
    workflow?.nodes || [
      {
        node_id: "node_1",
        tool_name: "",
        input_params: {},
        dependencies: [],
      },
    ]
  );
  const [isSaving, setIsSaving] = useState(false);
  const [viewMode, setViewMode] = useState<"graph" | "list">("graph");

  const addQueryTemplate = () => {
    setQueryTemplates([...queryTemplates, ""]);
  };

  const removeQueryTemplate = (index: number) => {
    if (queryTemplates.length > 1) {
      const newTemplates = queryTemplates.filter((_, i) => i !== index);
      setQueryTemplates(newTemplates);
    }
  };

  const updateQueryTemplate = (index: number, value: string) => {
    const newTemplates = [...queryTemplates];
    newTemplates[index] = value;
    setQueryTemplates(newTemplates);
  };

  const addNode = () => {
    const newNode: WorkflowNode = {
      node_id: `node_${nodes.length + 1}`,
      tool_name: "",
      input_params: {},
      dependencies: [],
    };
    setNodes([...nodes, newNode]);
  };

  const removeNode = (index: number) => {
    const newNodes = nodes.filter((_, i) => i !== index);
    setNodes(newNodes);
  };

  const updateNode = (index: number, field: keyof WorkflowNode, value: any) => {
    const newNodes = [...nodes];
    newNodes[index] = { ...newNodes[index], [field]: value };
    setNodes(newNodes);
  };

  const handleSave = async () => {
    const validTemplates = queryTemplates.filter(t => t.trim());

    if (!name || validTemplates.length === 0 || nodes.some((n) => !n.tool_name)) {
      alert("Please fill in all required fields (name, at least one trigger query, and tool names)");
      return;
    }

    setIsSaving(true);
    try {
      await api.createWorkflow({
        name,
        description,
        query_templates: validTemplates,
        nodes,
        user_id: userId,
      });
      onSave();
    } catch (error) {
      console.error("Failed to save workflow:", error);
      alert("Failed to save workflow");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">
          {workflow ? "Edit" : "Create"} Workflow
        </h2>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onCancel}>
            <X className="h-4 w-4 mr-2" />
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isSaving}>
            <Save className="h-4 w-4 mr-2" />
            {isSaving ? "Saving..." : "Save"}
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Basic Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="name">Workflow Name *</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Weather Workflow"
            />
          </div>

          <div>
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does this workflow do?"
              rows={3}
            />
          </div>

          <div className="space-y-2">
            <Label>Trigger Queries *</Label>
            {queryTemplates.map((template, index) => (
              <div key={index} className="flex gap-2">
                <Input
                  value={template}
                  onChange={(e) => updateQueryTemplate(index, e.target.value)}
                  placeholder="e.g., What's the weather like?"
                />
                {queryTemplates.length > 1 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeQueryTemplate(index)}
                  >
                    <Trash2 className="h-4 w-4 text-red-600" />
                  </Button>
                )}
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={addQueryTemplate}>
              <Plus className="h-4 w-4 mr-2" />
              Add Query Template
            </Button>
            <p className="text-sm text-muted-foreground">
              Similar queries will also trigger this workflow
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle>Workflow Nodes</CardTitle>
            <Button variant="outline" size="sm" onClick={addNode}>
              <Plus className="h-4 w-4 mr-2" />
              Add Node
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as "graph" | "list")}>
            <TabsList className="grid w-full grid-cols-2 mb-4">
              <TabsTrigger value="graph" className="flex items-center gap-2">
                <Network className="h-4 w-4" />
                Graph View
              </TabsTrigger>
              <TabsTrigger value="list">List View</TabsTrigger>
            </TabsList>

            <TabsContent value="graph" className="space-y-4">
              <WorkflowGraph workflowNodes={nodes} onNodesChange={setNodes} />
            </TabsContent>

            <TabsContent value="list" className="space-y-4">
              {nodes.map((node, index) => (
                <Card key={index} className="border-2">
                  <CardContent className="pt-6 space-y-4">
                    <div className="flex justify-between items-start">
                      <h4 className="font-semibold">Node {index + 1}</h4>
                      {nodes.length > 1 && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeNode(index)}
                        >
                          <Trash2 className="h-4 w-4 text-red-600" />
                        </Button>
                      )}
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label htmlFor={`node_id_${index}`}>Node ID *</Label>
                        <Input
                          id={`node_id_${index}`}
                          value={node.node_id}
                          onChange={(e) =>
                            updateNode(index, "node_id", e.target.value)
                          }
                          placeholder="e.g., fetch_weather"
                        />
                      </div>

                      <div>
                        <Label htmlFor={`tool_name_${index}`}>Tool Name *</Label>
                        <Input
                          id={`tool_name_${index}`}
                          value={node.tool_name}
                          onChange={(e) =>
                            updateNode(index, "tool_name", e.target.value)
                          }
                          placeholder="e.g., get_weather"
                        />
                      </div>
                    </div>

                    <div>
                      <Label htmlFor={`input_params_${index}`}>
                        Input Parameters (JSON)
                      </Label>
                      <Textarea
                        id={`input_params_${index}`}
                        value={JSON.stringify(node.input_params, null, 2)}
                        onChange={(e) => {
                          try {
                            const params = JSON.parse(e.target.value);
                            updateNode(index, "input_params", params);
                          } catch (error) {
                            // Invalid JSON, don't update
                          }
                        }}
                        placeholder='{"location": "${user_location}"}'
                        rows={3}
                        className="font-mono text-sm"
                      />
                      <p className="text-sm text-muted-foreground mt-1">
                        Use ${"{variable}"} to reference session variables or previous node outputs
                      </p>
                    </div>

                    <div>
                      <Label htmlFor={`dependencies_${index}`}>
                        Dependencies (comma-separated node IDs)
                      </Label>
                      <Input
                        id={`dependencies_${index}`}
                        value={node.dependencies.join(", ")}
                        onChange={(e) =>
                          updateNode(
                            index,
                            "dependencies",
                            e.target.value
                              .split(",")
                              .map((d) => d.trim())
                              .filter((d) => d)
                          )
                        }
                        placeholder="e.g., fetch_weather, process_data"
                      />
                      <p className="text-sm text-muted-foreground mt-1">
                        This node will wait for these nodes to complete first
                      </p>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}
