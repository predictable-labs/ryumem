"use client"

import { useState, useEffect } from "react"
import { api, type AgentInstructionResponse } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Loader2, Save, RotateCcw, History, CheckCircle2, XCircle } from "lucide-react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"

interface AgentInstructionEditorProps {
  userId?: string
}

const DEFAULT_INSTRUCTION = `TOOL SELECTION GUIDANCE (IMPORTANT):
Before selecting which tool to use for a user's request, you MUST first call search_memory to check for past tool usage patterns.

REQUIRED WORKFLOW:
1. FIRST: Call search_memory with a query like "tool execution for [task type]" or "which tools were used for [similar query]?"
2. THEN: Review the tool usage history and success rates from memory
3. FINALLY: Select the most appropriate tool based on past performance

Example queries for search_memory:
- "Which tools were used for weather queries?"
- "Tool execution for information retrieval tasks"
- "What tools successfully handled external API calls?"

This historical context will help you make better tool selections based on proven success rates.`

export function AgentInstructionEditor({ userId }: AgentInstructionEditorProps) {
  const [agentType, setAgentType] = useState("google_adk")
  const [instructionType, setInstructionType] = useState("tool_tracking")
  const [originalUserRequest, setOriginalUserRequest] = useState("")
  const [instructionText, setInstructionText] = useState("")
  const [description, setDescription] = useState("")
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [activeInstruction, setActiveInstruction] = useState<AgentInstructionResponse | null>(null)
  const [history, setHistory] = useState<AgentInstructionResponse[]>([])
  const [showHistory, setShowHistory] = useState(false)

  // Load active instruction and history
  useEffect(() => {
    loadInstructions()
  }, [agentType, instructionType])

  const loadInstructions = async () => {
    setLoading(true)
    setError(null)

    try {
      // Load active instruction
      const active = await api.getActiveAgentInstruction(
        agentType,
        instructionType,
        userId
      )

      setActiveInstruction(active)

      if (active) {
        setOriginalUserRequest(active.original_user_request)
        setInstructionText(active.converted_instruction)
        setDescription(active.description)
      } else {
        // No custom instruction - show default
        setOriginalUserRequest("")
        setInstructionText("")
        setDescription("")
      }

      // Load history
      const allInstructions = await api.listAgentInstructions(
        agentType,
        instructionType,
        false,
        20
      )

      setHistory(allInstructions)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load instructions")
      console.error("Error loading instructions:", err)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!instructionText.trim()) {
      setError("Instruction text cannot be empty")
      return
    }

    setSaving(true)
    setError(null)
    setSuccess(null)

    try {
      await api.createAgentInstruction({
        original_user_request: originalUserRequest,
        instruction_text: instructionText,
        agent_type: agentType,
        instruction_type: instructionType,
        description: description,
        user_id: userId,
        active: true,
      })

      setSuccess("Instruction saved successfully!")

      // Reload to show new version
      await loadInstructions()

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save instruction")
      console.error("Error saving instruction:", err)
    } finally {
      setSaving(false)
    }
  }

  const handleResetToDefault = () => {
    setOriginalUserRequest("")
    setInstructionText(DEFAULT_INSTRUCTION)
    setDescription("Default tool tracking instruction")
  }

  const handleLoadVersion = (instruction: AgentInstructionResponse) => {
    setOriginalUserRequest(instruction.original_user_request)
    setInstructionText(instruction.converted_instruction)
    setDescription(instruction.description)
    setShowHistory(false)
  }

  return (
    <div className="space-y-6">
      {/* Configuration Section */}
      <Card>
        <CardHeader>
          <CardTitle>Agent Instruction Configuration</CardTitle>
          <CardDescription>
            Customize the instructions that are added to your agent's prompt
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
                  <SelectItem value="tool_tracking">Tool Tracking</SelectItem>
                  <SelectItem value="memory_guidance">Memory Guidance</SelectItem>
                  <SelectItem value="general">General Guidance</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {activeInstruction && (
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>
                Currently using custom instruction (v{activeInstruction.version})
              </AlertDescription>
            </Alert>
          )}

          {!activeInstruction && !loading && (
            <Alert>
              <AlertDescription>
                No custom instruction set - agent will use default hardcoded instruction
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Editor Section */}
      <Card>
        <CardHeader>
          <CardTitle>Instruction Text</CardTitle>
          <CardDescription>
            This text will be appended to the agent's system prompt
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="description">Description (Optional)</Label>
            <Input
              id="description"
              placeholder="Brief description of what this instruction does"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="original-request">Original User Request</Label>
            <Textarea
              id="original-request"
              placeholder="What you originally asked for (e.g., 'Make the agent check past tool usage')..."
              value={originalUserRequest}
              onChange={(e) => setOriginalUserRequest(e.target.value)}
              rows={3}
              className="text-sm"
            />
            <p className="text-xs text-muted-foreground">
              This tracks what you requested before it was converted into the instruction below
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="instruction-text">Converted Instruction (What Gets Added to Agent)</Label>
            <Textarea
              id="instruction-text"
              placeholder="The actual instruction text that will be added to the agent's prompt..."
              value={instructionText}
              onChange={(e) => setInstructionText(e.target.value)}
              rows={15}
              className="font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground">
              This is the formatted instruction that will actually be appended to the agent
            </p>
          </div>

          {error && (
            <Alert variant="destructive">
              <XCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {success && (
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>{success}</AlertDescription>
            </Alert>
          )}

          <div className="flex gap-2">
            <Button onClick={handleSave} disabled={saving || loading}>
              {saving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="mr-2 h-4 w-4" />
                  Save Instruction
                </>
              )}
            </Button>

            <Button variant="outline" onClick={handleResetToDefault} disabled={loading}>
              <RotateCcw className="mr-2 h-4 w-4" />
              Reset to Default
            </Button>

            <Button
              variant="outline"
              onClick={() => setShowHistory(!showHistory)}
              disabled={loading}
            >
              <History className="mr-2 h-4 w-4" />
              {showHistory ? "Hide" : "Show"} Version History
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Version History Section */}
      {showHistory && (
        <Card>
          <CardHeader>
            <CardTitle>Version History</CardTitle>
            <CardDescription>
              Previous versions of instructions for this agent
            </CardDescription>
          </CardHeader>
          <CardContent>
            {history.length === 0 ? (
              <p className="text-sm text-muted-foreground">No version history available</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Version</TableHead>
                    <TableHead>Original Request</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.map((instr) => (
                    <TableRow key={instr.instruction_id}>
                      <TableCell className="font-medium">v{instr.version}</TableCell>
                      <TableCell className="max-w-md truncate">
                        {instr.original_user_request || <span className="text-muted-foreground italic">No original request</span>}
                      </TableCell>
                      <TableCell className="max-w-md truncate">
                        {instr.description || instr.name}
                      </TableCell>
                      <TableCell>
                        {instr.active ? (
                          <Badge variant="default">Active</Badge>
                        ) : (
                          <Badge variant="outline">Inactive</Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {new Date(instr.created_at).toLocaleString()}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleLoadVersion(instr)}
                        >
                          Load
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
