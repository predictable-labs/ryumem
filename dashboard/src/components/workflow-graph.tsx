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
} from 'reactflow';
import 'reactflow/dist/style.css';
import { WorkflowNode } from '@/lib/api';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Plus, Trash2, X } from 'lucide-react';

interface WorkflowGraphProps {
  workflowNodes: WorkflowNode[];
  onNodesChange: (nodes: WorkflowNode[]) => void;
}

// Custom node component for workflow tools
const ToolNode = ({ data }: { data: any }) => {
  return (
    <div className="px-4 py-2 shadow-md rounded-md bg-white border-2 border-gray-300 min-w-[150px]">
      <div className="font-bold text-sm">{data.tool_name || 'New Tool'}</div>
      <div className="text-xs text-gray-500 mt-1">ID: {data.node_id}</div>
      {data.input_params && Object.keys(data.input_params).length > 0 && (
        <div className="text-xs text-gray-600 mt-1">
          {Object.keys(data.input_params).length} params
        </div>
      )}
    </div>
  );
};

const nodeTypes = {
  tool: ToolNode,
};

export function WorkflowGraph({ workflowNodes, onNodesChange }: WorkflowGraphProps) {
  const [nodes, setNodes, onNodesChangeInternal] = useNodesState([]);
  const [edges, setEdges, onEdgesChangeInternal] = useEdgesState([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const selectedNode = workflowNodes.find(n => n.node_id === selectedNodeId);

  // Convert WorkflowNode[] to ReactFlow Node[]
  useEffect(() => {
    const flowNodes: Node[] = workflowNodes.map((wn, index) => ({
      id: wn.node_id,
      type: 'tool',
      position: { x: 250 * (index % 3), y: 100 * Math.floor(index / 3) },
      data: {
        node_id: wn.node_id,
        tool_name: wn.tool_name,
        input_params: wn.input_params,
        dependencies: wn.dependencies,
      },
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

    setEdges(flowEdges);
  }, [workflowNodes, setNodes, setEdges]);

  // Handle new connections (dependencies)
  const onConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;

      // Update edges
      setEdges((eds) => addEdge(connection, eds));

      // Update workflow nodes with new dependency
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
    },
    [workflowNodes, onNodesChange, setEdges]
  );

  // Handle edge deletion
  const onEdgesDelete = useCallback(
    (edgesToDelete: Edge[]) => {
      edgesToDelete.forEach((edge) => {
        // Update workflow nodes to remove dependency
        const updatedNodes = workflowNodes.map((wn) => {
          if (wn.node_id === edge.target) {
            const newDeps = wn.dependencies.filter((dep) => dep !== edge.source);
            return { ...wn, dependencies: newDeps };
          }
          return wn;
        });

        onNodesChange(updatedNodes);
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
      tool_name: '',
      input_params: {},
      dependencies: [],
    };

    onNodesChange([...workflowNodes, newWorkflowNode]);
  }, [workflowNodes, onNodesChange]);

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
            <div>
              <Label htmlFor="edit-node-id">Node ID *</Label>
              <Input
                id="edit-node-id"
                value={selectedNode.node_id}
                onChange={(e) => updateSelectedNode('node_id', e.target.value)}
                placeholder="e.g., fetch_weather"
              />
            </div>

            <div>
              <Label htmlFor="edit-tool-name">Tool Name *</Label>
              <Input
                id="edit-tool-name"
                value={selectedNode.tool_name}
                onChange={(e) => updateSelectedNode('tool_name', e.target.value)}
                placeholder="e.g., get_weather"
              />
            </div>

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
                placeholder='{"location": "${user_location}"}'
                rows={5}
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Use ${"{variable}"} to reference session variables or outputs
              </p>
            </div>

            <div>
              <Label htmlFor="edit-dependencies">Dependencies</Label>
              <Input
                id="edit-dependencies"
                value={selectedNode.dependencies.join(', ')}
                onChange={(e) =>
                  updateSelectedNode(
                    'dependencies',
                    e.target.value
                      .split(',')
                      .map((d) => d.trim())
                      .filter((d) => d)
                  )
                }
                placeholder="e.g., fetch_weather, process_data"
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
