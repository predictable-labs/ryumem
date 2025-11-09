"use client"

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Wrench, TrendingUp, User, Target, Clock, CheckCircle, XCircle } from 'lucide-react';

interface ToolUsage {
  tool_name: string;
  usage_count: number;
  success_rate: number;
  avg_duration_ms: number;
  examples?: Array<{
    input: any;
    output: string;
    success: boolean;
  }>;
}

interface ToolMetrics {
  tool_name: string;
  usage_count: number;
  success_rate: number;
  failure_count: number;
  avg_duration_ms: number;
  task_types: Record<string, number>;
  recent_errors: Array<{
    error: string;
    timestamp: string;
  }>;
}

interface ToolAnalyticsPanelProps {
  groupId: string;
  userId?: string;
}

export function ToolAnalyticsPanel({ groupId, userId }: ToolAnalyticsPanelProps) {
  const [taskType, setTaskType] = useState('information_retrieval');
  const [toolsForTask, setToolsForTask] = useState<ToolUsage[]>([]);
  const [selectedTool, setSelectedTool] = useState<string>('');
  const [toolMetrics, setToolMetrics] = useState<ToolMetrics | null>(null);
  const [userPreferences, setUserPreferences] = useState<ToolUsage[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Note: In a real implementation, these would call the API
  // For now, showing the structure

  useEffect(() => {
    // Load initial data
    // This would call api.getToolsForTask(taskType, groupId, userId)
  }, [groupId, userId, taskType]);

  const handleLoadToolMetrics = async (toolName: string) => {
    setSelectedTool(toolName);
    // This would call api.getToolSuccessRate(toolName, groupId, userId)
  };

  const handleLoadUserPreferences = async () => {
    if (userId) {
      // This would call api.getUserToolPreferences(userId, groupId)
    }
  };

  const taskTypes = [
    'information_retrieval',
    'data_transformation',
    'calculation',
    'external_api',
    'file_operation',
    'database_operation',
    'communication',
    'automation',
    'analysis',
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Wrench className="h-6 w-6" />
          Tool Usage Analytics
        </h2>
        <p className="text-muted-foreground mt-1">
          Analyze tool performance, success rates, and usage patterns
        </p>
      </div>

      {/* Tools by Task Type */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="h-5 w-5" />
            Tools by Task Type
          </CardTitle>
          <CardDescription>
            Discover which tools work best for different types of tasks
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Task type selector */}
            <div>
              <label className="text-sm font-medium mb-2 block">Select Task Type:</label>
              <div className="flex flex-wrap gap-2">
                {taskTypes.map((type) => (
                  <Badge
                    key={type}
                    variant={taskType === type ? "default" : "outline"}
                    className="cursor-pointer"
                    onClick={() => setTaskType(type)}
                  >
                    {type.replace(/_/g, ' ')}
                  </Badge>
                ))}
              </div>
            </div>

            {/* Tools list */}
            <div className="space-y-2">
              {toolsForTask.length > 0 ? (
                toolsForTask.map((tool) => (
                  <div
                    key={tool.tool_name}
                    className="p-4 border rounded-lg hover:bg-accent cursor-pointer"
                    onClick={() => handleLoadToolMetrics(tool.tool_name)}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="font-semibold">{tool.tool_name}</h4>
                        <p className="text-sm text-muted-foreground">
                          {tool.usage_count} uses • {(tool.success_rate * 100).toFixed(1)}% success
                        </p>
                      </div>
                      <div className="text-right">
                        <Badge variant={tool.success_rate > 0.9 ? "default" : "secondary"}>
                          {tool.avg_duration_ms}ms avg
                        </Badge>
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <p>No tool usage data for "{taskType}"</p>
                  <p className="text-sm mt-2">Run some tools to see analytics here</p>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tool Details */}
      {selectedTool && toolMetrics && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              {selectedTool} - Detailed Metrics
            </CardTitle>
            <CardDescription>
              Performance analysis and error tracking
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="text-center p-4 border rounded-lg">
                <div className="text-2xl font-bold">{toolMetrics.usage_count}</div>
                <div className="text-sm text-muted-foreground">Total Uses</div>
              </div>
              <div className="text-center p-4 border rounded-lg">
                <div className="text-2xl font-bold text-green-600">
                  {(toolMetrics.success_rate * 100).toFixed(1)}%
                </div>
                <div className="text-sm text-muted-foreground">Success Rate</div>
              </div>
              <div className="text-center p-4 border rounded-lg">
                <div className="text-2xl font-bold">{toolMetrics.avg_duration_ms}ms</div>
                <div className="text-sm text-muted-foreground">Avg Duration</div>
              </div>
              <div className="text-center p-4 border rounded-lg">
                <div className="text-2xl font-bold text-red-600">{toolMetrics.failure_count}</div>
                <div className="text-sm text-muted-foreground">Failures</div>
              </div>
            </div>

            {/* Task Types Distribution */}
            <div className="mb-6">
              <h4 className="font-semibold mb-3">Task Types Distribution</h4>
              <div className="space-y-2">
                {Object.entries(toolMetrics.task_types).map(([task, count]) => (
                  <div key={task} className="flex items-center justify-between">
                    <span className="text-sm">{task.replace(/_/g, ' ')}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-32 h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary"
                          style={{
                            width: `${(count / toolMetrics.usage_count) * 100}%`,
                          }}
                        />
                      </div>
                      <span className="text-sm font-medium w-12 text-right">{count}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Recent Errors */}
            {toolMetrics.recent_errors.length > 0 && (
              <div>
                <h4 className="font-semibold mb-3 flex items-center gap-2">
                  <XCircle className="h-4 w-4 text-red-600" />
                  Recent Errors
                </h4>
                <div className="space-y-2">
                  {toolMetrics.recent_errors.map((error, idx) => (
                    <div key={idx} className="p-3 border border-red-200 rounded-lg bg-red-50">
                      <p className="text-sm text-red-800">{error.error}</p>
                      <p className="text-xs text-red-600 mt-1">{error.timestamp}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* User Tool Preferences */}
      {userId && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="h-5 w-5" />
              User Tool Preferences
            </CardTitle>
            <CardDescription>
              Most frequently used tools by this user
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={handleLoadUserPreferences} className="mb-4">
              Load Preferences
            </Button>
            <div className="space-y-2">
              {userPreferences.length > 0 ? (
                userPreferences.map((pref) => (
                  <div
                    key={pref.tool_name}
                    className="flex items-center justify-between p-3 border rounded-lg"
                  >
                    <div>
                      <h4 className="font-medium">{pref.tool_name}</h4>
                      <p className="text-sm text-muted-foreground">
                        {pref.usage_count} uses • {(pref.success_rate * 100).toFixed(1)}% success
                      </p>
                    </div>
                    <CheckCircle className="h-5 w-5 text-green-600" />
                  </div>
                ))
              ) : (
                <p className="text-center text-muted-foreground py-4">
                  No tool preferences loaded
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Implementation Note */}
      <Card className="border-dashed">
        <CardContent className="pt-6">
          <div className="text-center text-sm text-muted-foreground">
            <p className="font-medium mb-2">📝 Implementation Note</p>
            <p>
              Tool analytics API endpoints exist in the backend at:
            </p>
            <ul className="mt-2 space-y-1">
              <li>• <code className="text-xs bg-muted px-2 py-1 rounded">GET /tools/for-task</code></li>
              <li>• <code className="text-xs bg-muted px-2 py-1 rounded">GET /tools/{'{'}tool_name{'}'}/metrics</code></li>
              <li>• <code className="text-xs bg-muted px-2 py-1 rounded">GET /users/{'{'}user_id{'}'}/tool-preferences</code></li>
            </ul>
            <p className="mt-3 text-xs">
              These endpoints need to be added to the backend server to enable full analytics.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
