"use client"

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Wrench, TrendingUp, User, Clock, CheckCircle, XCircle } from 'lucide-react';
import { api } from '@/lib/api';

interface Tool {
  uuid: string;
  tool_name: string;
  description: string;
  mentions: number;
  created_at: string;
}

interface ToolMetrics {
  tool_name: string;
  usage_count: number;
  success_rate: number;
  avg_duration_ms: number;
  recent_errors: string[];
}

interface ToolPreference {
  tool_name: string;
  usage_count: number;
  last_used: string;
}

interface ToolAnalyticsPanelProps {
  userId?: string;
  preselectedTool?: string | null;
}

export function ToolAnalyticsPanel({ userId, preselectedTool }: ToolAnalyticsPanelProps) {
  const [tools, setTools] = useState<Tool[]>([]);
  const [selectedTool, setSelectedTool] = useState<string>('');
  const [toolMetrics, setToolMetrics] = useState<ToolMetrics | null>(null);
  const [userPreferences, setUserPreferences] = useState<ToolPreference[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Load all tools
  useEffect(() => {
    const loadTools = async () => {
      setIsLoading(true);
      try {
        const allTools = await api.getAllTools();
        setTools(allTools);
      } catch (error) {
        console.error("Failed to load tools:", error);
        setTools([]);
      } finally {
        setIsLoading(false);
      }
    };

    loadTools();
  }, []);

  const handleLoadToolMetrics = async (toolName: string) => {
    setSelectedTool(toolName);
    setIsLoading(true);

    try {
      const metrics = await api.getToolMetrics(toolName, userId);
      setToolMetrics(metrics);
    } catch (error) {
      console.error("Failed to load tool metrics:", error);
      setToolMetrics(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLoadUserPreferences = async () => {
    if (!userId) return;

    setIsLoading(true);
    try {
      const prefs = await api.getUserToolPreferences(userId);
      setUserPreferences(prefs);
    } catch (error) {
      console.error("Failed to load user preferences:", error);
      setUserPreferences([]);
    } finally {
      setIsLoading(false);
    }
  };

  // Load user preferences on mount if userId is provided
  useEffect(() => {
    if (userId) {
      handleLoadUserPreferences();
    }
  }, [userId]);

  // Auto-load tool metrics when preselected tool changes
  useEffect(() => {
    if (preselectedTool && preselectedTool !== selectedTool) {
      handleLoadToolMetrics(preselectedTool);
    }
  }, [preselectedTool]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Wrench className="h-6 w-6" />
          Tool Analytics
        </h2>
        <p className="text-muted-foreground mt-1">
          View registered tools and their performance metrics
        </p>
      </div>

      {/* All Tools */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wrench className="h-5 w-5" />
            Registered Tools
          </CardTitle>
          <CardDescription>
            All tools available in the system
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {tools.length > 0 ? (
              tools.map((tool) => (
                <div
                  key={tool.uuid}
                  className="p-4 border rounded-lg hover:bg-accent cursor-pointer"
                  onClick={() => handleLoadToolMetrics(tool.tool_name)}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-semibold">{tool.tool_name}</h4>
                      <p className="text-sm text-muted-foreground">
                        {tool.description}
                      </p>
                    </div>
                    <Badge variant="outline">
                      {tool.mentions || 0} mentions
                    </Badge>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                <p>No tools registered yet</p>
                <p className="text-sm mt-2">Register tools at startup to see them here</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Tool Details */}
      {selectedTool && toolMetrics && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              {selectedTool} - Metrics
            </CardTitle>
            <CardDescription>
              Performance analysis and error tracking
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
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
                      <p className="text-sm text-red-800">{error}</p>
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
                        {pref.usage_count} uses • Last used: {new Date(pref.last_used).toLocaleDateString()}
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
    </div>
  );
}
