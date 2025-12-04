"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ToolCall } from "@/lib/types";
import { CheckCircle2, Loader2, XCircle, ChevronDown, ChevronRight } from "lucide-react";

interface ToolCallCardProps {
  toolCall: ToolCall;
  defaultExpanded?: boolean;
}

export function ToolCallCard({ toolCall, defaultExpanded = false }: ToolCallCardProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const getStatusIcon = () => {
    switch (toolCall.status) {
      case "completed":
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case "running":
        return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
      case "error":
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return null;
    }
  };

  const getStatusColor = () => {
    switch (toolCall.status) {
      case "completed":
        return "border-green-500/50";
      case "running":
        return "border-blue-500/50";
      case "error":
        return "border-red-500/50";
      default:
        return "";
    }
  };

  return (
    <Card className={`text-xs ${getStatusColor()}`}>
      <CardHeader
        className="p-3 pb-2 cursor-pointer hover:bg-muted/50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <CardTitle className="text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            {getStatusIcon()}
            <span className="font-mono">{toolCall.name}</span>
          </div>
          {isExpanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </CardTitle>
      </CardHeader>
      {isExpanded && (
        <CardContent className="p-3 pt-0 space-y-2">
          {toolCall.input && (
            <div>
              <div className="font-semibold text-muted-foreground mb-1">
                Input:
              </div>
              <pre className="bg-muted p-2 rounded text-xs overflow-x-auto">
                {JSON.stringify(toolCall.input, null, 2)}
              </pre>
            </div>
          )}
          {toolCall.output && (
            <div>
              <div className="font-semibold text-muted-foreground mb-1">
                Output:
              </div>
              <pre className="bg-muted p-2 rounded text-xs overflow-x-auto">
                {JSON.stringify(toolCall.output, null, 2)}
              </pre>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
