"use client"

import { useState, useEffect, useCallback } from 'react'
import { api, AugmentedQuery } from '@/lib/api'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2, Eye, CheckCircle2, XCircle, Clock, Filter } from 'lucide-react'

export default function AugmentedQueriesViewer() {
  const [queries, setQueries] = useState<AugmentedQuery[]>([])
  const [selectedRun, setSelectedRun] = useState<{ query: AugmentedQuery; run: any } | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedUser, setSelectedUser] = useState<string>('')
  const [availableUsers, setAvailableUsers] = useState<string[]>([])
  const [onlyAugmented, setOnlyAugmented] = useState(false)
  const [isDetailOpen, setIsDetailOpen] = useState(false)

  const loadUsers = useCallback(async () => {
    try {
      const users = await api.getUsers()
      setAvailableUsers(users)
    } catch (err) {
      console.error('Error loading users:', err)
    }
  }, [])

  const loadQueries = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await api.getAugmentedQueries(
        selectedUser || undefined,
        50,
        0,
        onlyAugmented
      )
      setQueries(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load queries')
    } finally {
      setIsLoading(false)
    }
  }, [selectedUser, onlyAugmented])

  useEffect(() => {
    loadUsers()
    loadQueries()
  }, [loadUsers, loadQueries])

  useEffect(() => {
    loadQueries()
  }, [loadQueries])

  const handleViewDetails = (query: AugmentedQuery, run: any) => {
    setSelectedRun({ query, run })
    setIsDetailOpen(true)
  }

  const formatTimestamp = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleString()
    } catch {
      return timestamp
    }
  }

  // Flatten queries into individual runs for display
  const flattenedRuns = queries.flatMap(query =>
    query.runs.map(run => ({
      episode_id: query.episode_id,
      user_id: query.user_id,
      session_id: query.session_id,
      query: query.query,
      created_at: query.created_at,
      run: run,
    }))
  )

  const getRunAugmentationBadge = (run: any) => {
    const isAugmented = run.augmented_query && run.augmented_query !== run.query
    if (!isAugmented) {
      return <Badge variant="secondary">Not Augmented</Badge>
    }
    return <Badge variant="default">Augmented</Badge>
  }

  const getRunToolsSummary = (run: any) => {
    const tools = run.tools_used || []

    if (tools.length === 0) {
      return <span className="text-muted-foreground text-sm">No tools</span>
    }

    const successCount = tools.filter((t: any) => t.success).length
    const failCount = tools.length - successCount

    return (
      <div className="flex gap-2 items-center">
        <Badge variant="outline" className="flex items-center gap-1">
          <CheckCircle2 className="h-3 w-3 text-green-500" />
          {successCount}
        </Badge>
        {failCount > 0 && (
          <Badge variant="outline" className="flex items-center gap-1">
            <XCircle className="h-3 w-3 text-red-500" />
            {failCount}
          </Badge>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Augmented Queries</CardTitle>
              <CardDescription>
                View user queries with augmentation metadata (read-only)
              </CardDescription>
            </div>
            <Button onClick={loadQueries} variant="outline" size="sm">
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {/* Filters */}
          <div className="flex gap-4 mb-4">
            <div className="flex-1">
              <Select value={selectedUser || "all"} onValueChange={(val) => setSelectedUser(val === "all" ? "" : val)}>
                <SelectTrigger>
                  <SelectValue placeholder="All Users" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Users</SelectItem>
                  {availableUsers.map((user) => (
                    <SelectItem key={user} value={user}>
                      {user}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <Button
                variant={onlyAugmented ? "default" : "outline"}
                size="sm"
                onClick={() => setOnlyAugmented(!onlyAugmented)}
              >
                Only Augmented
              </Button>
            </div>
          </div>

          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : flattenedRuns.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No query runs found
            </div>
          ) : (
            <div className="border rounded-lg">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Query</TableHead>
                    <TableHead>User ID</TableHead>
                    <TableHead>Run ID</TableHead>
                    <TableHead>Augmented</TableHead>
                    <TableHead>Tools Used</TableHead>
                    <TableHead>Run Time</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {flattenedRuns.map((item, idx) => (
                    <TableRow key={`${item.episode_id}-${item.run.run_id}-${idx}`}>
                      <TableCell className="max-w-md">
                        <div className="truncate font-mono text-sm">
                          {item.query}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{item.user_id}</Badge>
                      </TableCell>
                      <TableCell>
                        <div className="font-mono text-xs text-muted-foreground">
                          {item.run.run_id.substring(0, 8)}...
                        </div>
                      </TableCell>
                      <TableCell>{getRunAugmentationBadge(item.run)}</TableCell>
                      <TableCell>{getRunToolsSummary(item.run)}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatTimestamp(item.run.timestamp)}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            // Find the original query to pass to the detail view
                            const query = queries.find(q => q.episode_id === item.episode_id)
                            if (query) handleViewDetails(query, item.run)
                          }}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Details Dialog */}
      <Dialog open={isDetailOpen} onOpenChange={setIsDetailOpen}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Query Details</DialogTitle>
            <DialogDescription>
              Augmentation metadata and tool execution details (read-only)
            </DialogDescription>
          </DialogHeader>

          {selectedRun && (
            <div className="space-y-6">
              {/* Query Info */}
              <div>
                <h3 className="text-sm font-semibold mb-2">Query</h3>
                <div className="p-3 bg-muted rounded-md font-mono text-sm">
                  {selectedRun.query.query}
                </div>
              </div>

              {selectedRun.run.augmented_query && selectedRun.run.augmented_query !== selectedRun.run.query && (
                <div>
                  <h3 className="text-sm font-semibold mb-2">Augmented Query</h3>
                  <div className="p-3 bg-muted rounded-md font-mono text-sm whitespace-pre-wrap">
                    {selectedRun.run.augmented_query}
                  </div>
                </div>
              )}

              {/* Metadata */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h3 className="text-sm font-semibold mb-2">Episode ID</h3>
                  <div className="text-sm text-muted-foreground font-mono">
                    {selectedRun.query.episode_id}
                  </div>
                </div>
                <div>
                  <h3 className="text-sm font-semibold mb-2">User ID</h3>
                  <Badge variant="outline">{selectedRun.query.user_id}</Badge>
                </div>
                {selectedRun.query.session_id && (
                  <div>
                    <h3 className="text-sm font-semibold mb-2">Session ID</h3>
                    <div className="text-sm text-muted-foreground font-mono">
                      {selectedRun.query.session_id}
                    </div>
                  </div>
                )}
                <div>
                  <h3 className="text-sm font-semibold mb-2">Run ID</h3>
                  <div className="text-sm text-muted-foreground font-mono">
                    {selectedRun.run.run_id}
                  </div>
                </div>
              </div>

              {/* Run Details */}
              <div>
                <h3 className="text-sm font-semibold mb-3">Run Details</h3>
                <Card className="border-2">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground font-mono">
                          {selectedRun.run.run_id.substring(0, 8)}...
                        </span>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {formatTimestamp(selectedRun.run.timestamp)}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {/* Augmented Query for this run */}
                    {selectedRun.run.augmented_query && selectedRun.run.augmented_query !== selectedRun.run.query && (
                      <div>
                        <h4 className="text-xs font-semibold mb-1">Augmented Query</h4>
                        <div className="p-2 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded text-xs font-mono whitespace-pre-wrap max-h-40 overflow-y-auto">
                          {selectedRun.run.augmented_query}
                        </div>
                      </div>
                    )}

                    {/* Agent Response */}
                    {selectedRun.run.agent_response && (
                      <div>
                        <h4 className="text-xs font-semibold mb-1">Agent Response</h4>
                        <div className="p-2 bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 rounded text-xs max-h-40 overflow-y-auto">
                          {selectedRun.run.agent_response}
                        </div>
                      </div>
                    )}

                    {/* Tools Used in this run */}
                    {selectedRun.run.tools_used && selectedRun.run.tools_used.length > 0 && (
                      <div>
                        <h4 className="text-xs font-semibold mb-2">Tools Used ({selectedRun.run.tools_used.length})</h4>
                        <div className="space-y-2">
                          {selectedRun.run.tools_used.map((tool: any, toolIdx: number) => (
                            <div key={toolIdx} className="p-2 bg-muted rounded text-xs">
                              <div className="flex items-center justify-between mb-1">
                                <div className="flex items-center gap-2">
                                  <span className="font-mono font-semibold">{tool.tool_name}</span>
                                  {tool.success ? (
                                    <Badge variant="outline" className="flex items-center gap-1 text-xs h-5">
                                      <CheckCircle2 className="h-3 w-3 text-green-500" />
                                      Success
                                    </Badge>
                                  ) : (
                                    <Badge variant="outline" className="flex items-center gap-1 text-xs h-5">
                                      <XCircle className="h-3 w-3 text-red-500" />
                                      Failed
                                    </Badge>
                                  )}
                                </div>
                                <div className="flex items-center gap-1 text-muted-foreground">
                                  <Clock className="h-3 w-3" />
                                  {tool.duration_ms}ms
                                </div>
                              </div>
                              {tool.error && (
                                <div className="mt-1 p-1 bg-red-50 dark:bg-red-950 rounded text-red-600 dark:text-red-400">
                                  <strong>Error:</strong> {tool.error}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                  </CardContent>
                </Card>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
