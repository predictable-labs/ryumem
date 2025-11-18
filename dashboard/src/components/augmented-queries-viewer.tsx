"use client"

import { useState, useEffect } from 'react'
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
  const [selectedQuery, setSelectedQuery] = useState<AugmentedQuery | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedUser, setSelectedUser] = useState<string>('')
  const [availableUsers, setAvailableUsers] = useState<string[]>([])
  const [onlyAugmented, setOnlyAugmented] = useState(false)
  const [isDetailOpen, setIsDetailOpen] = useState(false)

  useEffect(() => {
    loadUsers()
    loadQueries()
  }, [])

  useEffect(() => {
    loadQueries()
  }, [selectedUser, onlyAugmented])

  const loadUsers = async () => {
    try {
      const users = await api.getUsers()
      setAvailableUsers(users)
    } catch (err) {
      console.error('Error loading users:', err)
    }
  }

  const loadQueries = async () => {
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
  }

  const handleViewDetails = (query: AugmentedQuery) => {
    setSelectedQuery(query)
    setIsDetailOpen(true)
  }

  const formatTimestamp = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleString()
    } catch {
      return timestamp
    }
  }

  const getAugmentationBadge = (query: AugmentedQuery) => {
    if (!query.augmented) {
      return <Badge variant="secondary">Not Augmented</Badge>
    }
    return <Badge variant="default">Augmented</Badge>
  }

  const getToolsUsedSummary = (query: AugmentedQuery) => {
    if (!query.tools_used || query.tools_used.length === 0) {
      return <span className="text-muted-foreground text-sm">No tools used</span>
    }

    const successCount = query.tools_used.filter(t => t.success).length
    const failCount = query.tools_used.length - successCount

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
          ) : queries.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No queries found
            </div>
          ) : (
            <div className="border rounded-lg">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Query</TableHead>
                    <TableHead>User ID</TableHead>
                    <TableHead>Augmented</TableHead>
                    <TableHead>Tools Used</TableHead>
                    <TableHead>Created At</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {queries.map((query) => (
                    <TableRow key={query.episode_id}>
                      <TableCell className="max-w-md">
                        <div className="truncate font-mono text-sm">
                          {query.original_query}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{query.user_id}</Badge>
                      </TableCell>
                      <TableCell>{getAugmentationBadge(query)}</TableCell>
                      <TableCell>{getToolsUsedSummary(query)}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatTimestamp(query.created_at)}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleViewDetails(query)}
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

          {selectedQuery && (
            <div className="space-y-6">
              {/* Query Info */}
              <div>
                <h3 className="text-sm font-semibold mb-2">Original Query</h3>
                <div className="p-3 bg-muted rounded-md font-mono text-sm">
                  {selectedQuery.original_query}
                </div>
              </div>

              {/* Augmented Query */}
              {selectedQuery.augmented && selectedQuery.augmented_query && (
                <div>
                  <h3 className="text-sm font-semibold mb-2">Augmented Query (with context)</h3>
                  <div className="p-3 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-md font-mono text-sm whitespace-pre-wrap">
                    {selectedQuery.augmented_query}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    This is what was actually sent to the agent (original query + historical context)
                  </p>
                </div>
              )}

              {/* Metadata */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h3 className="text-sm font-semibold mb-2">Episode ID</h3>
                  <div className="text-sm text-muted-foreground font-mono">
                    {selectedQuery.episode_id}
                  </div>
                </div>
                <div>
                  <h3 className="text-sm font-semibold mb-2">User ID</h3>
                  <Badge variant="outline">{selectedQuery.user_id}</Badge>
                </div>
                {selectedQuery.session_id && (
                  <div>
                    <h3 className="text-sm font-semibold mb-2">Session ID</h3>
                    <div className="text-sm text-muted-foreground font-mono">
                      {selectedQuery.session_id}
                    </div>
                  </div>
                )}
                <div>
                  <h3 className="text-sm font-semibold mb-2">Created At</h3>
                  <div className="text-sm text-muted-foreground">
                    {formatTimestamp(selectedQuery.created_at)}
                  </div>
                </div>
              </div>

              {/* Augmentation Config */}
              {selectedQuery.augmented && selectedQuery.augmentation_config && (
                <div>
                  <h3 className="text-sm font-semibold mb-2">Augmentation Configuration</h3>
                  <div className="p-3 bg-muted rounded-md space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Similarity Threshold:</span>
                      <span className="font-mono">
                        {selectedQuery.augmentation_config.similarity_threshold}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Top K Similar:</span>
                      <span className="font-mono">
                        {selectedQuery.augmentation_config.top_k_similar}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Tools Used */}
              {selectedQuery.tools_used && selectedQuery.tools_used.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold mb-2">Tools Executed</h3>
                  <div className="space-y-2">
                    {selectedQuery.tools_used.map((tool, idx) => (
                      <Card key={idx}>
                        <CardContent className="p-4">
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-sm font-semibold">
                                {tool.tool_name}
                              </span>
                              {tool.success ? (
                                <Badge variant="outline" className="flex items-center gap-1">
                                  <CheckCircle2 className="h-3 w-3 text-green-500" />
                                  Success
                                </Badge>
                              ) : (
                                <Badge variant="outline" className="flex items-center gap-1">
                                  <XCircle className="h-3 w-3 text-red-500" />
                                  Failed
                                </Badge>
                              )}
                            </div>
                            <div className="flex items-center gap-1 text-xs text-muted-foreground">
                              <Clock className="h-3 w-3" />
                              {tool.duration_ms}ms
                            </div>
                          </div>

                          <div className="text-xs text-muted-foreground mb-2">
                            {formatTimestamp(tool.timestamp)}
                          </div>

                          {tool.error && (
                            <div className="mt-2 p-2 bg-red-50 dark:bg-red-950 rounded text-xs text-red-600 dark:text-red-400">
                              <strong>Error:</strong> {tool.error}
                            </div>
                          )}

                          {tool.input && (
                            <details className="mt-2">
                              <summary className="text-xs font-semibold cursor-pointer">
                                Input
                              </summary>
                              <pre className="mt-1 p-2 bg-muted rounded text-xs overflow-x-auto">
                                {JSON.stringify(tool.input, null, 2)}
                              </pre>
                            </details>
                          )}

                          {tool.output && (
                            <details className="mt-2">
                              <summary className="text-xs font-semibold cursor-pointer">
                                Output
                              </summary>
                              <pre className="mt-1 p-2 bg-muted rounded text-xs overflow-x-auto">
                                {JSON.stringify(tool.output, null, 2)}
                              </pre>
                            </details>
                          )}
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
