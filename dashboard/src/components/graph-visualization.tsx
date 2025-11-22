"use client"

import React, { useCallback, useEffect, useState } from 'react';
import {
  ReactFlow,
  Node,
  Edge,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Panel,
  BackgroundVariant,
  MiniMap,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { GraphDataResponse, GraphNode as APIGraphNode } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface GraphVisualizationProps {
  data: GraphDataResponse;
  onNodeClick?: (node: APIGraphNode) => void;
  onEdgeClick?: (edge: any) => void;
}

const nodeTypes = {
  PERSON: { color: '#60a5fa', label: 'Person' },
  ORGANIZATION: { color: '#34d399', label: 'Organization' },
  LOCATION: { color: '#fbbf24', label: 'Location' },
  EVENT: { color: '#f472b6', label: 'Event' },
  CONCEPT: { color: '#a78bfa', label: 'Concept' },
  OBJECT: { color: '#fb923c', label: 'Object' },
  default: { color: '#94a3b8', label: 'Unknown' },
};

const getNodeStyle = (type: string) => {
  const nodeType = nodeTypes[type as keyof typeof nodeTypes] || nodeTypes.default;
  return {
    background: nodeType.color,
    color: 'white',
    border: '2px solid white',
    borderRadius: '8px',
    padding: '10px',
    fontSize: '12px',
    fontWeight: 500,
    boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
  };
};

export function GraphVisualization({ data, onNodeClick, onEdgeClick }: GraphVisualizationProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedNode, setSelectedNode] = useState<APIGraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<any | null>(null);

  // Convert API data to React Flow format
  useEffect(() => {
    if (!data) return;

    // Calculate layout positions using force-directed approach (simplified)
    const nodeMap = new Map<string, { x: number; y: number }>();
    const angleStep = (2 * Math.PI) / data.nodes.length;
    const radius = Math.max(300, data.nodes.length * 20);

    // Create nodes with circular layout
    const flowNodes: Node[] = data.nodes.map((node, index) => {
      const angle = index * angleStep;
      const x = Math.cos(angle) * radius;
      const y = Math.sin(angle) * radius;
      nodeMap.set(node.uuid, { x, y });

      return {
        id: node.uuid,
        type: 'default',
        position: { x, y },
        data: {
          label: (
            <div className="text-center">
              <div className="font-semibold">{node.name}</div>
              <div className="text-xs opacity-75">{node.type}</div>
              <div className="text-xs opacity-60">({node.mentions} mentions)</div>
            </div>
          ),
          node: node,
        },
        style: getNodeStyle(node.type),
      };
    });

    // Create edges
    const flowEdges: Edge[] = data.edges.map((edge, index) => ({
      id: edge.uuid,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      type: 'smoothstep',
      animated: edge.mentions > 5,
      style: {
        strokeWidth: Math.min(2 + edge.mentions * 0.5, 8),
        stroke: edge.mentions > 5 ? '#3b82f6' : '#94a3b8',
      },
      labelStyle: {
        fontSize: 10,
        fill: '#64748b',
        fontWeight: 500,
      },
      data: edge as unknown as Record<string, unknown>,
    }));

    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [data, setNodes, setEdges]);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      const apiNode = node.data.node as APIGraphNode;
      setSelectedNode(apiNode);
      setSelectedEdge(null);
      if (onNodeClick) {
        onNodeClick(apiNode);
      }
    },
    [onNodeClick]
  );

  const handleEdgeClick = useCallback(
    (_event: React.MouseEvent, edge: Edge) => {
      setSelectedEdge(edge.data);
      setSelectedNode(null);
      if (onEdgeClick) {
        onEdgeClick(edge.data);
      }
    },
    [onEdgeClick]
  );

  return (
    <div className="w-full h-full flex gap-4">
      <div className="flex-1 h-[700px] border rounded-lg overflow-hidden">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={handleNodeClick}
          onEdgeClick={handleEdgeClick}
          fitView
          attributionPosition="bottom-left"
        >
          <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
          <Controls />
          <MiniMap
            nodeColor={(node) => {
              const apiNode = node.data.node as APIGraphNode;
              const type = nodeTypes[apiNode.type as keyof typeof nodeTypes] || nodeTypes.default;
              return type.color;
            }}
            maskColor="rgba(0, 0, 0, 0.1)"
          />

          <Panel position="top-left" className="bg-white p-4 rounded-lg shadow-md space-y-2">
            <div className="font-semibold text-sm">Knowledge Graph</div>
            <div className="text-xs text-gray-600">
              {data?.count?.nodes || 0} entities • {data?.count?.edges || 0} relationships
            </div>
            <div className="space-y-1">
              {Object.entries(nodeTypes).map(([type, config]) => (
                type !== 'default' && (
                  <div key={type} className="flex items-center gap-2 text-xs">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: config.color }}
                    />
                    <span>{config.label}</span>
                  </div>
                )
              ))}
            </div>
          </Panel>
        </ReactFlow>
      </div>

      {/* Info Panel */}
      <div className="w-80 space-y-4">
        {selectedNode && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">{selectedNode.name}</CardTitle>
              <CardDescription>
                <Badge variant="outline">{selectedNode.type}</Badge>
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <div className="text-sm font-medium text-gray-600">Summary</div>
                <div className="text-sm mt-1">{selectedNode.summary}</div>
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <div className="font-medium text-gray-600">Mentions</div>
                  <div>{selectedNode.mentions}</div>
                </div>
                <div>
                  <div className="font-medium text-gray-600">UUID</div>
                  <div className="text-xs font-mono truncate">{selectedNode.uuid.slice(0, 8)}...</div>
                </div>
              </div>
              {selectedNode.user_id && (
                <div>
                  <div className="text-sm font-medium text-gray-600">User ID</div>
                  <div className="text-sm">{selectedNode.user_id}</div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {selectedEdge && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Relationship</CardTitle>
              <CardDescription>
                <Badge variant="outline">{selectedEdge.label}</Badge>
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <div className="text-sm font-medium text-gray-600">Fact</div>
                <div className="text-sm mt-1">{selectedEdge.fact}</div>
              </div>
              <div>
                <div className="text-sm font-medium text-gray-600">Mentions</div>
                <div className="text-sm">{selectedEdge.mentions}</div>
              </div>
            </CardContent>
          </Card>
        )}

        {!selectedNode && !selectedEdge && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Selection</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-gray-600">
                Click on a node or edge to see details
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
