"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Send, Loader2, Zap, Clock, PlayCircle, RotateCcw, Settings, Sparkles } from "lucide-react";
import { Message, ToolCall, PerformanceMetric, Workflow } from "@/lib/types";
import {
  executeTravelWorkflow,
  MockMemoryStore,
  calculateTotalExecutionTime,
  generateWorkflowFromExecution,
} from "@/lib/mock-workflow";
import { ToolCallCard } from "./tool-call-card";
import { MemoryPanel } from "./memory-panel";
import { PerformancePanel } from "./performance-panel";
import { WorkflowPanel } from "./workflow-panel";

// Preset prompts for demo
const PRESET_PROMPTS = [
  "Plan a trip from Mumbai to Bangalore for 2 nights",
  "Plan a trip from Mumbai to Bangalore for 3 nights",
  "I want to visit Bangalore from Mumbai for 2 nights",
  "Plan a trip from Delhi to Mumbai for 3 nights",
  "Plan a trip from Delhi to Mumbai for 2 nights",
  "I need a 3-night trip to Mumbai from Delhi",
];

export function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "system",
      content:
        "Welcome to Ryumem Travel Planner Demo! Click any query below to see it execute. Watch how similar queries run faster using Ryumem's memory!",
      timestamp: new Date(),
    },
  ]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentToolCalls, setCurrentToolCalls] = useState<ToolCall[]>([]);
  const [currentExecutionTime, setCurrentExecutionTime] = useState<number>(0);
  const [performanceMetrics, setPerformanceMetrics] = useState<PerformanceMetric[]>([]);
  const [currentWorkflow, setCurrentWorkflow] = useState<Workflow | undefined>();
  const memoryStore = useRef(new MockMemoryStore());
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, currentToolCalls]);

  const resetDemo = () => {
    setMessages([
      {
        id: "welcome",
        role: "system",
        content:
          "Welcome to Ryumem Travel Planner Demo! Click any query below to see it execute. Watch how similar queries run faster using Ryumem's memory!",
        timestamp: new Date(),
      },
    ]);
    setPerformanceMetrics([]);
    setCurrentWorkflow(undefined);
    memoryStore.current = new MockMemoryStore();
  };

  const executeQuery = async (query: string) => {
    if (isProcessing) return;

    const startTime = Date.now();

    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      role: "user",
      content: query,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsProcessing(true);
    setCurrentToolCalls([]);
    setCurrentExecutionTime(0);

    // Find similar queries from memory
    const similarMemories = memoryStore.current.findSimilar(query, 0.4);
    const useMemory = similarMemories.length > 0;
    const similarQueries = similarMemories.map((m) => m.query);

    // Find matching workflow
    const matchedWorkflow = memoryStore.current.findMatchingWorkflow(query, 0.6);
    if (matchedWorkflow) {
      setCurrentWorkflow(matchedWorkflow);
      memoryStore.current.incrementWorkflowMatchCount(matchedWorkflow.id);
    }

    // Calculate expected time
    const baseTime = calculateTotalExecutionTime(false);
    const optimizedTime = calculateTotalExecutionTime(true);

    // Execute workflow
    const toolCalls: ToolCall[] = [];

    const onToolStart = (tool: ToolCall) => {
      toolCalls.push(tool);
      setCurrentToolCalls([...toolCalls]);
    };

    const onToolComplete = (tool: ToolCall) => {
      const index = toolCalls.findIndex((t) => t.id === tool.id);
      if (index !== -1) {
        toolCalls[index] = tool;
        setCurrentToolCalls([...toolCalls]);
      }
    };

    // Track execution time
    const executionInterval = setInterval(() => {
      setCurrentExecutionTime(Date.now() - startTime);
    }, 100);

    const response = await executeTravelWorkflow(
      query,
      onToolStart,
      onToolComplete,
      useMemory,
      matchedWorkflow
    );

    clearInterval(executionInterval);
    const totalExecutionTime = Date.now() - startTime;

    // Add to memory
    memoryStore.current.addMemory(query, response, totalExecutionTime);

    // Generate workflow if not using an existing one
    let generatedWorkflow: Workflow | undefined;
    if (!matchedWorkflow) {
      generatedWorkflow = generateWorkflowFromExecution(query, toolCalls, userMessage.id);
      memoryStore.current.addWorkflow(generatedWorkflow);
    }

    // Track performance metric
    const metric: PerformanceMetric = {
      queryId: userMessage.id,
      query: query,
      executionTime: totalExecutionTime,
      usedMemory: useMemory,
      timeSaved: useMemory ? baseTime - optimizedTime : 0,
      timestamp: new Date(),
    };

    memoryStore.current.addPerformanceMetric(metric);
    setPerformanceMetrics((prev) => [...prev, metric]);

    // Create assistant message
    const assistantMessage: Message = {
      id: `msg-${Date.now()}`,
      role: "assistant",
      content: response,
      timestamp: new Date(),
      toolCalls: toolCalls,
      executionTime: totalExecutionTime,
      usedMemory: useMemory,
      similarQueries: similarQueries,
      generatedWorkflow: generatedWorkflow,
      appliedWorkflow: matchedWorkflow,
    };

    setMessages((prev) => [...prev, assistantMessage]);
    setIsProcessing(false);
    setCurrentToolCalls([]);
    setCurrentExecutionTime(0);
  };

  return (
    <div className="h-screen flex">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="border-b p-4 bg-card">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold">Ryumem Travel Planner Demo</h1>
              <p className="text-sm text-muted-foreground mt-1">
                Watch query performance improve with memory-assisted execution
              </p>
            </div>
            <Button
              onClick={resetDemo}
              disabled={isProcessing}
              variant="outline"
              size="sm"
              className="flex items-center gap-2"
            >
              <RotateCcw className="h-4 w-4" />
              Reset Demo
            </Button>
          </div>
        </div>

        {/* Messages */}
        <ScrollArea className="flex-1 p-4">
          <div ref={scrollRef} className="space-y-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${
                  message.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-2 ${
                    message.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : message.role === "system"
                      ? "bg-muted text-muted-foreground"
                      : "bg-card border"
                  }`}
                >
                  {/* Applied Workflow Indicator */}
                  {message.role === "assistant" && message.appliedWorkflow && (
                    <div className="mb-2 flex items-center gap-2 text-xs bg-purple-50 dark:bg-purple-950 text-purple-700 dark:text-purple-300 px-2 py-1 rounded border border-purple-200 dark:border-purple-800">
                      <Settings className="h-3 w-3" />
                      <span className="font-semibold">Custom Workflow Applied</span>
                      <span>• {message.appliedWorkflow.tools.filter(t => t.enabled).length}/10 tools</span>
                    </div>
                  )}

                  {/* Generated Workflow Indicator */}
                  {message.role === "assistant" && message.generatedWorkflow && !message.appliedWorkflow && (
                    <div className="mb-2 flex items-center gap-2 text-xs bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-300 px-2 py-1 rounded border border-amber-200 dark:border-amber-800">
                      <Sparkles className="h-3 w-3" />
                      <span className="font-semibold">Workflow Generated</span>
                      <span>• View in sidebar to edit</span>
                    </div>
                  )}

                  {/* Memory indicator for assistant messages */}
                  {message.role === "assistant" && message.usedMemory && (
                    <div className="mb-2 flex items-center gap-2 text-xs bg-green-50 dark:bg-green-950 text-green-700 dark:text-green-300 px-2 py-1 rounded border border-green-200 dark:border-green-800">
                      <Zap className="h-3 w-3" />
                      <span className="font-semibold">
                        Memory-Assisted Query
                      </span>
                      {message.executionTime && (
                        <span className="text-green-600 dark:text-green-400">
                          • {(message.executionTime / 1000).toFixed(2)}s
                        </span>
                      )}
                    </div>
                  )}

                  {/* Execution time for non-memory queries */}
                  {message.role === "assistant" && !message.usedMemory && message.executionTime && (
                    <div className="mb-2 flex items-center gap-2 text-xs bg-blue-50 dark:bg-blue-950 text-blue-700 dark:text-blue-300 px-2 py-1 rounded border border-blue-200 dark:border-blue-800">
                      <Clock className="h-3 w-3" />
                      <span>
                        Executed in {(message.executionTime / 1000).toFixed(2)}s
                      </span>
                    </div>
                  )}

                  {/* Similar queries found */}
                  {message.role === "assistant" &&
                    message.similarQueries &&
                    message.similarQueries.length > 0 && (
                      <div className="mb-2 text-xs bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-300 px-2 py-1 rounded border border-amber-200 dark:border-amber-800">
                        <span className="font-semibold">Similar queries found:</span>{" "}
                        {message.similarQueries.length}
                      </div>
                    )}

                  <div className="whitespace-pre-wrap">{message.content}</div>
                  {message.toolCalls && message.toolCalls.length > 0 && (
                    <div className="mt-4 space-y-2">
                      <div className="text-xs font-semibold opacity-70">
                        Tool Executions:
                      </div>
                      {message.toolCalls.map((tool) => (
                        <ToolCallCard key={tool.id} toolCall={tool} defaultExpanded={false} />
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {/* Current tool calls being executed */}
            {currentToolCalls.length > 0 && (
              <div className="flex justify-start">
                <div className="max-w-[80%] rounded-lg px-4 py-2 bg-card border">
                  <div className="flex items-center gap-2 text-sm mb-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Processing...</span>
                    {currentExecutionTime > 0 && (
                      <span className="text-muted-foreground text-xs">
                        {(currentExecutionTime / 1000).toFixed(1)}s
                      </span>
                    )}
                  </div>
                  <div className="space-y-2">
                    {currentToolCalls.map((tool) => (
                      <ToolCallCard key={tool.id} toolCall={tool} defaultExpanded={true} />
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Preset Prompts Area */}
        <div className="border-t p-4 bg-card">
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              {PRESET_PROMPTS.map((prompt, idx) => (
                <Button
                  key={`prompt-${idx}`}
                  onClick={() => executeQuery(prompt)}
                  disabled={isProcessing}
                  variant="outline"
                  className="justify-start text-left h-auto py-2 px-3"
                >
                  <PlayCircle className="h-4 w-4 mr-2 flex-shrink-0" />
                  <span className="text-xs">{prompt}</span>
                </Button>
              ))}
            </div>
            <div className="text-xs text-muted-foreground text-center">
              Click any query to execute. Watch performance improve for similar queries!
            </div>
          </div>
        </div>
      </div>

      {/* Sidebar */}
      <div className="w-80 border-l bg-card flex flex-col">
        {/* Performance Panel */}
        <div className="p-4 border-b">
          <h2 className="font-semibold mb-3 flex items-center gap-2">
            <Zap className="h-4 w-4" />
            Performance Metrics
          </h2>
          <PerformancePanel metrics={performanceMetrics} />
        </div>

        {/* Workflow Panel */}
        <div className="border-b" style={{ height: '300px' }}>
          <WorkflowPanel
            memoryStore={memoryStore.current}
            currentWorkflow={currentWorkflow}
            onWorkflowUpdate={(workflow) => console.log("Workflow updated:", workflow)}
          />
        </div>

        {/* Memory Panel */}
        <div className="flex-1 overflow-hidden">
          <MemoryPanel memoryStore={memoryStore.current} />
        </div>
      </div>
    </div>
  );
}
