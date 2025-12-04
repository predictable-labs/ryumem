"use client";

import { useCallback, useMemo } from "react";
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  BackgroundVariant,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
} from "reactflow";
import "reactflow/dist/style.css";
import { Workflow } from "@/lib/types";
import { cn } from "@/lib/utils";

interface WorkflowGraphViewProps {
  workflow: Workflow;
  onNodeToggle?: (nodeId: string) => void;
}

export function WorkflowGraphView({ workflow, onNodeToggle }: WorkflowGraphViewProps) {
  // Convert workflow nodes to React Flow nodes
  const initialNodes: Node[] = useMemo(() => {
    return workflow.nodes.map((node) => ({
      id: node.id,
      type: "default",
      position: node.position,
      data: {
        label: (
          <div className={cn(
            "px-3 py-2 rounded-lg text-xs font-medium transition-all",
            node.enabled
              ? node.category === "core"
                ? "bg-blue-100 dark:bg-blue-900 text-blue-900 dark:text-blue-100 border-2 border-blue-500"
                : "bg-purple-100 dark:bg-purple-900 text-purple-900 dark:text-purple-100 border-2 border-purple-400"
              : "bg-gray-100 dark:bg-gray-800 text-gray-400 border-2 border-gray-300 opacity-50"
          )}>
            <div className="font-bold">{node.description}</div>
            <div className="text-[10px] mt-1 opacity-70">
              {node.category === "core" ? "Core" : "Exploratory"}
            </div>
          </div>
        ),
      },
      draggable: false,
      style: {
        background: "transparent",
        border: "none",
        padding: 0,
      },
    }));
  }, [workflow.nodes]);

  // Convert workflow edges to React Flow edges
  const initialEdges: Edge[] = useMemo(() => {
    return workflow.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: "smoothstep",
      animated: edge.type === "parallel",
      style: {
        stroke: edge.type === "parallel" ? "#a78bfa" : "#60a5fa",
        strokeWidth: 2,
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: edge.type === "parallel" ? "#a78bfa" : "#60a5fa",
      },
    }));
  }, [workflow.edges]);

  const [nodes] = useNodesState(initialNodes);
  const [edges] = useEdgesState(initialEdges);

  return (
    <div className="h-full w-full bg-background">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        minZoom={0.5}
        maxZoom={1.5}
        defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
        <Controls showInteractive={false} />
        <MiniMap
          nodeColor={(node) => {
            const workflowNode = workflow.nodes.find(n => n.id === node.id);
            if (!workflowNode?.enabled) return "#9ca3af";
            return workflowNode.category === "core" ? "#3b82f6" : "#a78bfa";
          }}
          maskColor="rgba(0, 0, 0, 0.1)"
          style={{
            height: 80,
            width: 120,
          }}
        />
      </ReactFlow>
      <div className="absolute bottom-2 left-2 text-[10px] text-muted-foreground bg-background/80 backdrop-blur px-2 py-1 rounded border">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1">
            <div className="w-3 h-0.5 bg-blue-500"></div>
            <span>Sequential</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-0.5 bg-purple-400 animate-pulse"></div>
            <span>Parallel</span>
          </div>
        </div>
      </div>
    </div>
  );
}
