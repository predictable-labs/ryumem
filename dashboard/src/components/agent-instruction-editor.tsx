"use client"

import { useState, useEffect } from "react"
import { api, type AgentInstructionResponse } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Loader2, Database } from "lucide-react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

interface AgentInstructionEditorProps {
  userId?: string
}

export function AgentInstructionEditor({ userId }: AgentInstructionEditorProps) {
  const [agentType, setAgentType] = useState<string>("all")
  const [instructionType, setInstructionType] = useState<string>("all")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [instructions, setInstructions] = useState<AgentInstructionResponse[]>([])

  // Load all cached instructions
  useEffect(() => {
    loadInstructions()
  }, [agentType, instructionType])

  const loadInstructions = async () => {
    setLoading(true)
    setError(null)

    try {
      // Load instructions with optional filters
      const allInstructions = await api.listAgentInstructions(
        agentType === "all" ? undefined : agentType,
        instructionType === "all" ? undefined : instructionType,
        100
      )

      setInstructions(allInstructions)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load instructions")
      console.error("Error loading instructions:", err)
    } finally {
      setLoading(false)
    }
  }

  // Group instructions by agent_type
  const groupedInstructions = instructions.reduce((acc, instr) => {
    const key = `${instr.agent_type}-${instr.instruction_type}`
    if (!acc[key]) {
      acc[key] = []
    }
    acc[key].push(instr)
    return acc
  }, {} as Record<string, AgentInstructionResponse[]>)

  return (
    <div className="space-y-6">
      {/* Filter Section */}
      <Card>
        <CardHeader>
          <CardTitle>Cached Agent Instructions</CardTitle>
          <CardDescription>
            View all instructions cached in the database for different agent types
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="agent-type">Agent Type</Label>
              <Select value={agentType} onValueChange={setAgentType}>
                <SelectTrigger id="agent-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Agent Types</SelectItem>
                  <SelectItem value="google_adk">Google ADK</SelectItem>
                  <SelectItem value="custom_agent">Custom Agent</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="instruction-type">Instruction Type</Label>
              <Select value={instructionType} onValueChange={setInstructionType}>
                <SelectTrigger id="instruction-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Instruction Types</SelectItem>
                  <SelectItem value="memory_usage">Memory Usage</SelectItem>
                  <SelectItem value="tool_tracking">Tool Tracking</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <Alert>
            <Database className="h-4 w-4" />
            <AlertDescription>
              {loading ? "Loading..." : `${instructions.length} cached instruction${instructions.length !== 1 ? 's' : ''} found`}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>

      {/* Instructions List */}
      {loading ? (
        <Card>
          <CardContent className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </CardContent>
        </Card>
      ) : instructions.length === 0 ? (
        <Card>
          <CardContent className="py-12">
            <p className="text-center text-muted-foreground">
              No cached instructions found. Instructions are automatically created when you enable memory on agents.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {Object.entries(groupedInstructions).map(([key, instrs]) => {
            const [agent, instrType] = key.split('-')
            return (
              <Card key={key}>
                <CardHeader>
                  <CardTitle className="text-lg">
                    {agent} - {instrType}
                  </CardTitle>
                  <CardDescription>
                    {instrs.length} version{instrs.length !== 1 ? 's' : ''} cached
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-20">Version</TableHead>
                        <TableHead className="w-48">Description</TableHead>
                        <TableHead>Instruction Text</TableHead>
                        <TableHead className="w-40">Created</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {instrs.map((instr) => (
                        <TableRow key={instr.instruction_id}>
                          <TableCell className="font-medium">v{instr.version}</TableCell>
                          <TableCell className="text-sm">
                            {instr.description || <span className="text-muted-foreground italic">No description</span>}
                          </TableCell>
                          <TableCell>
                            <div className="max-w-2xl">
                              <pre className="text-xs whitespace-pre-wrap break-words font-mono bg-muted p-2 rounded">
                                {instr.instruction_text.substring(0, 200)}
                                {instr.instruction_text.length > 200 && '...'}
                              </pre>
                            </div>
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {new Date(instr.created_at).toLocaleString()}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
