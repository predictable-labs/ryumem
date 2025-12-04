"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { TrendingDown, Zap, Clock, Award } from "lucide-react";
import { PerformanceMetric } from "@/lib/types";

interface PerformancePanelProps {
  metrics: PerformanceMetric[];
}

export function PerformancePanel({ metrics }: PerformancePanelProps) {
  const memoryAssistedQueries = metrics.filter((m) => m.usedMemory).length;
  const totalTimeSaved = metrics
    .filter((m) => m.usedMemory)
    .reduce((sum, m) => sum + m.timeSaved, 0);
  const avgTimeSaved =
    memoryAssistedQueries > 0 ? totalTimeSaved / memoryAssistedQueries : 0;
  const avgSpeedImprovement =
    memoryAssistedQueries > 0
      ? metrics
          .filter((m) => m.usedMemory)
          .reduce(
            (sum, m) =>
              sum + (m.timeSaved / (m.executionTime + m.timeSaved)) * 100,
            0
          ) / memoryAssistedQueries
      : 0;

  return (
    <div className="space-y-3">
      {/* Performance Stats Grid */}
      <div className="grid grid-cols-2 gap-3">
        <Card className="bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-950 dark:to-emerald-950 border-green-200 dark:border-green-800">
          <CardHeader className="p-3 pb-2">
            <CardTitle className="text-xs flex items-center gap-1.5 text-green-700 dark:text-green-300">
              <Zap className="h-3.5 w-3.5" />
              Memory Hits
            </CardTitle>
          </CardHeader>
          <CardContent className="p-3 pt-0">
            <div className="text-2xl font-bold text-green-700 dark:text-green-300">
              {memoryAssistedQueries}
            </div>
            <div className="text-xs text-green-600 dark:text-green-400">
              out of {metrics.length} queries
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-blue-50 to-cyan-50 dark:from-blue-950 dark:to-cyan-950 border-blue-200 dark:border-blue-800">
          <CardHeader className="p-3 pb-2">
            <CardTitle className="text-xs flex items-center gap-1.5 text-blue-700 dark:text-blue-300">
              <TrendingDown className="h-3.5 w-3.5" />
              Avg Speed Up
            </CardTitle>
          </CardHeader>
          <CardContent className="p-3 pt-0">
            <div className="text-2xl font-bold text-blue-700 dark:text-blue-300">
              {avgSpeedImprovement.toFixed(0)}%
            </div>
            <div className="text-xs text-blue-600 dark:text-blue-400">
              faster with memory
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-purple-50 to-violet-50 dark:from-purple-950 dark:to-violet-950 border-purple-200 dark:border-purple-800">
          <CardHeader className="p-3 pb-2">
            <CardTitle className="text-xs flex items-center gap-1.5 text-purple-700 dark:text-purple-300">
              <Clock className="h-3.5 w-3.5" />
              Time Saved
            </CardTitle>
          </CardHeader>
          <CardContent className="p-3 pt-0">
            <div className="text-2xl font-bold text-purple-700 dark:text-purple-300">
              {(totalTimeSaved / 1000).toFixed(1)}s
            </div>
            <div className="text-xs text-purple-600 dark:text-purple-400">
              total time saved
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-orange-50 to-amber-50 dark:from-orange-950 dark:to-amber-950 border-orange-200 dark:border-orange-800">
          <CardHeader className="p-3 pb-2">
            <CardTitle className="text-xs flex items-center gap-1.5 text-orange-700 dark:text-orange-300">
              <Award className="h-3.5 w-3.5" />
              Avg Saved
            </CardTitle>
          </CardHeader>
          <CardContent className="p-3 pt-0">
            <div className="text-2xl font-bold text-orange-700 dark:text-orange-300">
              {(avgTimeSaved / 1000).toFixed(2)}s
            </div>
            <div className="text-xs text-orange-600 dark:text-orange-400">
              per cached query
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Query Timeline */}
      {metrics.length > 0 && (
        <Card>
          <CardHeader className="p-3 pb-2">
            <CardTitle className="text-xs">Query Performance Timeline</CardTitle>
          </CardHeader>
          <CardContent className="p-3 pt-0">
            <div className="space-y-2">
              {metrics.slice(-5).reverse().map((metric, idx) => {
                const speedup = metric.usedMemory
                  ? ((metric.timeSaved / (metric.executionTime + metric.timeSaved)) * 100).toFixed(0)
                  : 0;
                return (
                  <div key={metric.queryId} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        {metric.usedMemory && (
                          <Zap className="h-3 w-3 text-green-500" />
                        )}
                        <span className="truncate max-w-[150px]">
                          {metric.query.slice(0, 30)}...
                        </span>
                      </div>
                      <span className="font-semibold">
                        {(metric.executionTime / 1000).toFixed(1)}s
                      </span>
                    </div>
                    <div className="flex gap-1 items-center">
                      <div className="flex-1 bg-muted rounded-full h-2 overflow-hidden">
                        <div
                          className={`h-full ${
                            metric.usedMemory
                              ? "bg-gradient-to-r from-green-500 to-emerald-500"
                              : "bg-gradient-to-r from-blue-500 to-cyan-500"
                          }`}
                          style={{
                            width: `${(metric.executionTime / 2600) * 100}%`,
                          }}
                        />
                      </div>
                      {metric.usedMemory && (
                        <span className="text-xs text-green-600 dark:text-green-400 font-semibold whitespace-nowrap">
                          ↓{speedup}%
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
            {metrics.length > 5 && (
              <div className="text-xs text-muted-foreground text-center mt-2">
                Showing last 5 queries
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Explanation */}
      <Card className="bg-muted/50">
        <CardContent className="p-3">
          <div className="text-xs space-y-2">
            <div className="font-semibold">How It Works:</div>
            <ul className="space-y-1 text-muted-foreground">
              <li className="flex gap-2">
                <span className="text-green-500">✓</span>
                <span>First query: ~2.6s (full tool execution)</span>
              </li>
              <li className="flex gap-2">
                <span className="text-green-500">✓</span>
                <span>Similar query: ~0.65s (memory-assisted)</span>
              </li>
              <li className="flex gap-2">
                <span className="text-green-500">✓</span>
                <span>Up to 75% faster with cached context</span>
              </li>
            </ul>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
