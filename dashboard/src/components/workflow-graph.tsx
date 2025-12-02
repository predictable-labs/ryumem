"use client";

import React, { useCallback, useEffect, useState } from 'react';
import ReactFlow, {
  Node,
  Edge,
  addEdge,
  Background,
  Controls,
  MiniMap,
  Connection,
  useNodesState,
  useEdgesState,
  MarkerType,
  Panel,
  Handle,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { WorkflowNode, NodeType, Tool, api } from '@/lib/api';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Plus, Trash2, X, Wrench, GitBranch, Brain, MessageSquare, Server } from 'lucide-react';

interface WorkflowGraphProps {
  workflowNodes: WorkflowNode[];
  onNodesChange: (nodes: WorkflowNode[]) => void;
}

// Custom node components for different node types
const ToolNode = ({ data }: { data: any }) => {
  return (
    <div className="px-4 py-2 shadow-md rounded-md bg-blue-50 border-2 border-blue-400 min-w-[150px]">
      <Handle type="target" position={Position.Top} />
      <div className="flex items-center gap-2">
        <Wrench className="h-4 w-4 text-blue-600" />
        <div className="font-bold text-sm">{data.tool_name || 'Tool'}</div>
      </div>
      <div className="text-xs text-gray-500 mt-1">ID: {data.node_id}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
};

const MCPNode = ({ data }: { data: any }) => {
  return (
    <div className="px-4 py-2 shadow-md rounded-md bg-indigo-50 border-2 border-indigo-400 min-w-[150px]">
      <Handle type="target" position={Position.Top} />
      <div className="flex items-center gap-2">
        <Server className="h-4 w-4 text-indigo-600" />
        <div className="font-bold text-sm">MCP</div>
      </div>
      <div className="text-xs text-gray-500 mt-1">{data.mcp_server || 'Server'}</div>
      <div className="text-xs text-gray-600">{data.tool_name}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
};

const LLMTriggerNode = ({ data }: { data: any }) => {
  return (
    <div className="px-4 py-2 shadow-md rounded-md bg-purple-50 border-2 border-purple-400 min-w-[150px]">
      <Handle type="target" position={Position.Top} />
      <div className="flex items-center gap-2">
        <Brain className="h-4 w-4 text-purple-600" />
        <div className="font-bold text-sm">LLM Trigger</div>
      </div>
      <div className="text-xs text-gray-500 mt-1">ID: {data.node_id}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
};

const UserTriggerNode = ({ data }: { data: any }) => {
  return (
    <div className="px-4 py-2 shadow-md rounded-md bg-green-50 border-2 border-green-400 min-w-[150px]">
      <Handle type="target" position={Position.Top} />
      <div className="flex items-center gap-2">
        <MessageSquare className="h-4 w-4 text-green-600" />
        <div className="font-bold text-sm">User Input</div>
      </div>
      <div className="text-xs text-gray-500 mt-1">ID: {data.node_id}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
};

const ConditionNode = ({ data }: { data: any }) => {
  return (
    <div className="px-4 py-2 shadow-md rounded-md bg-yellow-50 border-2 border-yellow-400 min-w-[150px]">
      <Handle type="target" position={Position.Top} />
      <div className="flex items-center gap-2">
        <GitBranch className="h-4 w-4 text-yellow-600" />
        <div className="font-bold text-sm">Condition</div>
      </div>
      <div className="text-xs text-gray-500 mt-1">
        {data.branches?.length || 0} branches
      </div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
};

const nodeTypes = {
  tool: ToolNode,
  mcp: MCPNode,
  llm_trigger: LLMTriggerNode,
  user_trigger: UserTriggerNode,
  condition: ConditionNode,
};

export function WorkflowGraph({ workflowNodes, onNodesChange }: WorkflowGraphProps) {
  const [nodes, setNodes, onNodesChangeInternal] = useNodesState([]);
  const [edges, setEdges, onEdgesChangeInternal] = useEdgesState([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [availableTools, setAvailableTools] = useState<Tool[]>([]);
  const selectedNode = workflowNodes.find(n => n.node_id === selectedNodeId);

  // Fetch available tools on mount
  useEffect(() => {
    const fetchTools = async () => {
      try {
        const tools = await api.getAllTools();
        setAvailableTools(tools);
      } catch (error) {
        console.error("Failed to fetch tools:", error);
      }
    };
    fetchTools();
  }, []);

  // Convert WorkflowNode[] to ReactFlow Node[]
  useEffect(() => {
    const flowNodes: Node[] = workflowNodes.map((wn, index) => ({
      id: wn.node_id,
      type: wn.node_type || 'tool',
      position: { x: 250 * (index % 3), y: 100 * Math.floor(index / 3) },
      data: wn,
    }));

    setNodes(flowNodes);

    // Create edges based on dependencies
    const flowEdges: Edge[] = [];
    workflowNodes.forEach((wn) => {
      wn.dependencies.forEach((depId) => {
        flowEdges.push({
          id: `${depId}-${wn.node_id}`,
          source: depId,
          target: wn.node_id,
          type: 'smoothstep',
          animated: true,
          markerEnd: {
            type: MarkerType.ArrowClosed,
          },
        });
      });
    });

    // Add edges for condition node branches
    const branchColors = ['#ef4444', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6'];
    workflowNodes.forEach((wn) => {
      if (wn.node_type === 'condition' && wn.branches && wn.branches.length > 0) {
        wn.branches.forEach((branch, branchIndex) => {
          branch.next_nodes.forEach((targetNodeId) => {
            flowEdges.push({
              id: `${wn.node_id}-${targetNodeId}-${branch.branch_id}`,
              source: wn.node_id,
              target: targetNodeId,
              label: branch.condition_expr || branch.branch_id,
              type: 'smoothstep',
              animated: true,
              style: {
                stroke: branchColors[branchIndex % branchColors.length],
                strokeWidth: 2,
              },
              labelStyle: {
                fill: branchColors[branchIndex % branchColors.length],
                fontWeight: 600,
                fontSize: 10,
              },
              markerEnd: {
                type: MarkerType.ArrowClosed,
                color: branchColors[branchIndex % branchColors.length],
              },
            });
          });
        });

        // Add edge for default branch if specified
        if (wn.default_branch) {
          flowEdges.push({
            id: `${wn.node_id}-${wn.default_branch}-default`,
            source: wn.node_id,
            target: wn.default_branch,
            label: 'default',
            type: 'smoothstep',
            animated: false,
            style: {
              stroke: '#6b7280',
              strokeWidth: 2,
              strokeDasharray: '5,5',
            },
            labelStyle: {
              fill: '#6b7280',
              fontWeight: 600,
              fontSize: 10,
            },
            markerEnd: {
              type: MarkerType.ArrowClosed,
              color: '#6b7280',
            },
          });
        }
      }
    });

    setEdges(flowEdges);
  }, [workflowNodes, setNodes, setEdges]);

  // Handle new connections (dependencies or condition branches)
  const onConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;

      // Update edges
      setEdges((eds) => addEdge(connection, eds));

      const sourceNode = workflowNodes.find(n => n.node_id === connection.source);

      // If source is a condition node, create a branch
      if (sourceNode?.node_type === 'condition') {
        const updatedNodes = workflowNodes.map((wn) => {
          if (wn.node_id === connection.source) {
            // Create a new branch for this connection
            const newBranch = {
              branch_id: `branch_${Date.now()}`,
              condition_expr: '', // Empty - user will fill this in
              next_nodes: [connection.target!],
            };
            const newBranches = [...(wn.branches || []), newBranch];
            return { ...wn, branches: newBranches };
          }
          return wn;
        });
        onNodesChange(updatedNodes);
      } else {
        // Otherwise, treat as regular dependency
        const updatedNodes = workflowNodes.map((wn) => {
          if (wn.node_id === connection.target) {
            const newDeps = [...wn.dependencies];
            if (!newDeps.includes(connection.source!)) {
              newDeps.push(connection.source!);
            }
            return { ...wn, dependencies: newDeps };
          }
          return wn;
        });
        onNodesChange(updatedNodes);
      }
    },
    [workflowNodes, onNodesChange, setEdges]
  );

  // Handle edge deletion
  const onEdgesDelete = useCallback(
    (edgesToDelete: Edge[]) => {
      edgesToDelete.forEach((edge) => {
        const sourceNode = workflowNodes.find(n => n.node_id === edge.source);

        // If source is a condition node, remove the branch
        if (sourceNode?.node_type === 'condition') {
          const updatedNodes = workflowNodes.map((wn) => {
            if (wn.node_id === edge.source) {
              // Remove branch that points to this target
              const newBranches = (wn.branches || []).filter(
                branch => !branch.next_nodes.includes(edge.target as string)
              );
              return { ...wn, branches: newBranches };
            }
            return wn;
          });
          onNodesChange(updatedNodes);
        } else {
          // Otherwise, remove as regular dependency
          const updatedNodes = workflowNodes.map((wn) => {
            if (wn.node_id === edge.target) {
              const newDeps = wn.dependencies.filter((dep) => dep !== edge.source);
              return { ...wn, dependencies: newDeps };
            }
            return wn;
          });
          onNodesChange(updatedNodes);
        }
      });
    },
    [workflowNodes, onNodesChange]
  );

  // Handle node position changes
  const handleNodesChange = useCallback(
    (changes: any) => {
      onNodesChangeInternal(changes);
    },
    [onNodesChangeInternal]
  );

  // Handle node selection
  const onNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    setSelectedNodeId(node.id);
  }, []);

  // Update selected node
  const updateSelectedNode = useCallback(
    (field: keyof WorkflowNode, value: any) => {
      if (!selectedNodeId) return;

      const updatedNodes = workflowNodes.map((wn) => {
        if (wn.node_id === selectedNodeId) {
          return { ...wn, [field]: value };
        }
        return wn;
      });

      onNodesChange(updatedNodes);
    },
    [selectedNodeId, workflowNodes, onNodesChange]
  );

  // Delete selected node
  const deleteSelectedNode = useCallback(() => {
    if (!selectedNodeId) return;

    const updatedNodes = workflowNodes.filter((wn) => wn.node_id !== selectedNodeId);
    onNodesChange(updatedNodes);
    setSelectedNodeId(null);
  }, [selectedNodeId, workflowNodes, onNodesChange]);

  // Add new node
  const addNewNode = useCallback(() => {
    const newNodeId = `node_${Date.now()}`;
    const newWorkflowNode: WorkflowNode = {
      node_id: newNodeId,
      node_type: 'tool',
      tool_name: '',
      input_params: {},
      dependencies: [],
    };

    onNodesChange([...workflowNodes, newWorkflowNode]);
  }, [workflowNodes, onNodesChange]);

  // Remove a branch from condition node
  const removeBranch = useCallback((branchId: string) => {
    if (!selectedNode || selectedNode.node_type !== 'condition') return;

    const updatedBranches = (selectedNode.branches || []).filter(
      (b) => b.branch_id !== branchId
    );
    updateSelectedNode('branches', updatedBranches);
  }, [selectedNode, updateSelectedNode]);

  // Update a branch
  const updateBranch = useCallback((branchId: string, field: string, value: any) => {
    if (!selectedNode || selectedNode.node_type !== 'condition') return;

    const updatedBranches = (selectedNode.branches || []).map((b) =>
      b.branch_id === branchId ? { ...b, [field]: value } : b
    );
    updateSelectedNode('branches', updatedBranches);
  }, [selectedNode, updateSelectedNode]);

  return (
    <div className="flex gap-4">
      <div className="flex-1 h-[600px] border rounded-lg">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={handleNodesChange}
          onEdgesChange={onEdgesChangeInternal}
          onEdgesDelete={onEdgesDelete}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          fitView
          className="bg-gray-50"
        >
          <Background />
          <Controls />
          <MiniMap />
          <Panel position="top-right" className="bg-white p-2 rounded-md shadow-md">
            <Button onClick={addNewNode} size="sm" className="gap-2">
              <Plus className="h-4 w-4" />
              Add Node
            </Button>
          </Panel>
        </ReactFlow>
      </div>

      {selectedNode && (
        <Card className="w-80 h-[600px] overflow-y-auto">
          <CardHeader>
            <div className="flex justify-between items-start">
              <CardTitle className="text-lg">Edit Node</CardTitle>
              <div className="flex gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={deleteSelectedNode}
                >
                  <Trash2 className="h-4 w-4 text-red-600" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedNodeId(null)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Node ID */}
            <div>
              <Label htmlFor="edit-node-id">Node ID *</Label>
              <Input
                id="edit-node-id"
                value={selectedNode.node_id}
                onChange={(e) => updateSelectedNode('node_id', e.target.value)}
                placeholder="e.g., fetch_weather"
              />
            </div>

            {/* Node Type Selector */}
            <div>
              <Label htmlFor="edit-node-type">Node Type *</Label>
              <Select
                value={selectedNode.node_type || 'tool'}
                onValueChange={(value) => updateSelectedNode('node_type', value as NodeType)}
              >
                <SelectTrigger id="edit-node-type">
                  <SelectValue placeholder="Select node type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="tool">Tool Execution</SelectItem>
                  <SelectItem value="mcp">MCP Server</SelectItem>
                  <SelectItem value="llm_trigger">LLM Trigger</SelectItem>
                  <SelectItem value="user_trigger">User Input</SelectItem>
                  <SelectItem value="condition">Conditional Branch</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Tool-specific fields */}
            {(selectedNode.node_type === 'tool' || !selectedNode.node_type) && (
              <div>
                <Label htmlFor="edit-tool-name">Tool Name *</Label>
                <Select
                  value={selectedNode.tool_name || ''}
                  onValueChange={(value) => updateSelectedNode('tool_name', value)}
                >
                  <SelectTrigger id="edit-tool-name">
                    <SelectValue placeholder="Select tool" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableTools.map((tool) => (
                      <SelectItem key={tool.tool_name} value={tool.tool_name}>
                        {tool.tool_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* MCP-specific fields */}
            {selectedNode.node_type === 'mcp' && (
              <>
                <div>
                  <Label htmlFor="edit-mcp-server">MCP Server *</Label>
                  <Input
                    id="edit-mcp-server"
                    value={selectedNode.mcp_server || ''}
                    onChange={(e) => updateSelectedNode('mcp_server', e.target.value)}
                    placeholder="e.g., mcp://localhost:8080"
                  />
                </div>
                <div>
                  <Label htmlFor="edit-mcp-tool">Tool Name *</Label>
                  <Input
                    id="edit-mcp-tool"
                    value={selectedNode.tool_name || ''}
                    onChange={(e) => updateSelectedNode('tool_name', e.target.value)}
                    placeholder="e.g., get_weather"
                  />
                </div>
              </>
            )}

            {/* LLM Trigger fields */}
            {selectedNode.node_type === 'llm_trigger' && (
              <>
                <div>
                  <Label htmlFor="edit-llm-prompt">LLM Prompt *</Label>
                  <Textarea
                    id="edit-llm-prompt"
                    value={selectedNode.llm_prompt || ''}
                    onChange={(e) => updateSelectedNode('llm_prompt', e.target.value)}
                    placeholder="Enter prompt for LLM"
                    rows={3}
                  />
                </div>
                <div>
                  <Label htmlFor="edit-llm-output">Output Variable</Label>
                  <Input
                    id="edit-llm-output"
                    value={selectedNode.llm_output_variable || ''}
                    onChange={(e) => updateSelectedNode('llm_output_variable', e.target.value)}
                    placeholder="e.g., llm_result"
                  />
                </div>
              </>
            )}

            {/* User Trigger fields */}
            {selectedNode.node_type === 'user_trigger' && (
              <>
                <div>
                  <Label htmlFor="edit-user-prompt">User Prompt *</Label>
                  <Textarea
                    id="edit-user-prompt"
                    value={selectedNode.user_prompt || ''}
                    onChange={(e) => updateSelectedNode('user_prompt', e.target.value)}
                    placeholder="Enter prompt for user"
                    rows={2}
                  />
                </div>
                <div>
                  <Label htmlFor="edit-user-input">Input Variable</Label>
                  <Input
                    id="edit-user-input"
                    value={selectedNode.user_input_variable || ''}
                    onChange={(e) => updateSelectedNode('user_input_variable', e.target.value)}
                    placeholder="e.g., user_response"
                  />
                </div>
              </>
            )}

            {/* Condition branches editor */}
            {selectedNode.node_type === 'condition' && (
              <div className="space-y-3">
                <div className="p-3 bg-blue-50 border border-blue-200 rounded-md">
                  <p className="text-xs font-semibold text-blue-900 mb-1">How to create IF/ELSE conditions:</p>
                  <ol className="text-xs text-blue-800 space-y-1 list-decimal ml-4">
                    <li><strong>Draw a connection</strong> from this condition node to a target node</li>
                    <li>A new branch will be created automatically</li>
                    <li>Enter the condition expression below (e.g., <code className="bg-blue-100 px-1">status == 'success'</code>)</li>
                    <li>Draw more connections for additional IF conditions</li>
                    <li>Optionally set a "Default Branch" for ELSE fallback</li>
                  </ol>
                </div>

                <Label className="text-sm font-semibold">Condition Branches (IF statements)</Label>

                {(selectedNode.branches || []).length === 0 && (
                  <div className="p-4 border-2 border-dashed rounded-md text-center text-sm text-gray-500">
                    No branches yet. Draw a connection from this condition node to create your first IF branch.
                  </div>
                )}

                {(selectedNode.branches || []).map((branch, idx) => (
                  <Card key={branch.branch_id} className="p-3 bg-gradient-to-r from-blue-50 to-purple-50 border-2 border-blue-300">
                    <div className="space-y-2">
                      <div className="flex justify-between items-start">
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-0.5 bg-blue-500 text-white text-xs font-bold rounded">
                            IF #{idx + 1}
                          </span>
                          <span className="text-xs text-gray-600">→ {branch.next_nodes.join(', ')}</span>
                        </div>
                        <Button
                          onClick={() => removeBranch(branch.branch_id)}
                          size="sm"
                          variant="ghost"
                          className="h-6 w-6 p-0"
                          title="Delete this branch (or delete the edge on the graph)"
                        >
                          <Trash2 className="h-3 w-3 text-red-600" />
                        </Button>
                      </div>

                      <div>
                        <Label className="text-xs font-semibold">IF Condition Expression *</Label>
                        <Input
                          value={branch.condition_expr}
                          onChange={(e) =>
                            updateBranch(branch.branch_id, 'condition_expr', e.target.value)
                          }
                          placeholder="status == 'success' OR count > 10 OR result == 'approved'"
                          className="text-xs font-mono"
                        />
                        <p className="text-xs text-gray-500 mt-0.5">
                          Examples: <code className="bg-gray-100 px-1">error == null</code>, <code className="bg-gray-100 px-1">score {'>'} 50</code>
                        </p>
                      </div>
                    </div>
                  </Card>
                ))}

                <div className="p-3 bg-gray-50 border-2 border-gray-300 rounded-md">
                  <Label className="text-xs font-semibold flex items-center gap-2">
                    <span className="px-2 py-0.5 bg-gray-500 text-white text-xs font-bold rounded">ELSE</span>
                    Default Branch (optional)
                  </Label>
                  <Input
                    value={selectedNode.default_branch || ''}
                    onChange={(e) => updateSelectedNode('default_branch', e.target.value)}
                    placeholder="error_handler, fallback_node"
                    className="text-xs font-mono mt-2"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Node ID to execute if <strong>NONE</strong> of the above conditions match (ELSE case)
                  </p>
                </div>

                {(selectedNode.branches || []).length > 0 && (
                  <div className="p-3 bg-green-50 border border-green-200 rounded-md">
                    <p className="text-xs font-semibold text-green-900 mb-1">Flow Summary:</p>
                    <div className="text-xs text-green-800 space-y-1">
                      {(selectedNode.branches || []).map((branch, idx) => (
                        <div key={branch.branch_id} className="font-mono">
                          <strong>IF</strong> {branch.condition_expr || '(no condition)'} <strong>→</strong> {branch.next_nodes.join(', ')}
                        </div>
                      ))}
                      {selectedNode.default_branch && (
                        <div className="font-mono">
                          <strong>ELSE</strong> → {selectedNode.default_branch}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Input Parameters - common for all types */}
            {selectedNode.node_type !== 'condition' && (
              <div>
                <Label htmlFor="edit-input-params">Input Parameters (JSON)</Label>
                <Textarea
                  id="edit-input-params"
                  value={JSON.stringify(selectedNode.input_params, null, 2)}
                  onChange={(e) => {
                    try {
                      const params = JSON.parse(e.target.value);
                      updateSelectedNode('input_params', params);
                    } catch (error) {
                      // Invalid JSON, don't update
                    }
                  }}
                  placeholder='{"key": "${value}"}'
                  rows={4}
                  className="font-mono text-xs"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Use ${"{variable}"} for session variables
                </p>
              </div>
            )}

            {/* Dependencies */}
            <div>
              <Label htmlFor="edit-dependencies">Dependencies</Label>
              <Input
                id="edit-dependencies"
                value={selectedNode.dependencies?.join(', ') || ''}
                onChange={(e) =>
                  updateSelectedNode(
                    'dependencies',
                    e.target.value
                      .split(',')
                      .map((d) => d.trim())
                      .filter((d) => d)
                  )
                }
                placeholder="e.g., fetch_weather"
                className="text-xs"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Or draw connections on the graph
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
