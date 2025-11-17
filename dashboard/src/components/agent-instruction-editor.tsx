"use client"

import { useState, useEffect } from "react"
import { api, type AgentInstructionResponse } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Loader2, Database, Edit2, X, Save } from "lucide-react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

interface AgentInstructionEditorProps {
  userId?: string
}

export function AgentInstructionEditor({ userId }: AgentInstructionEditorProps) {
  const [agentType, setAgentType] = useState<string>("all")
  const [instructionType, setInstructionType] = useState<string>("all")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [instructions, setInstructions] = useState<AgentInstructionResponse[]>([])

  // Edit dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [editingInstruction, setEditingInstruction] = useState<AgentInstructionResponse | null>(null)
  const [editInstructionText, setEditInstructionText] = useState("")
  const [editDescription, setEditDescription] = useState("")
  const [editOriginalRequest, setEditOriginalRequest] = useState("")
  const [saving, setSaving] = useState(false)

  // View dialog state
  const [viewDialogOpen, setViewDialogOpen] = useState(false)
  const [viewingInstruction, setViewingInstruction] = useState<AgentInstructionResponse | null>(null)

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

  const handleViewInstruction = (instruction: AgentInstructionResponse) => {
    setViewingInstruction(instruction)
    setViewDialogOpen(true)
  }

  const handleEditInstruction = (instruction: AgentInstructionResponse) => {
    setEditingInstruction(instruction)
    setEditInstructionText(instruction.instruction_text)
    setEditDescription(instruction.description)
    setEditOriginalRequest(instruction.original_user_request)
    setEditDialogOpen(true)
  }

  const handleSaveEdit = async () => {
    if (!editInstructionText.trim() || !editingInstruction) {
      setError("Instruction text cannot be empty")
      return
    }

    setSaving(true)
    setError(null)
    setSuccess(null)

    try {
      await api.createAgentInstruction({
        instruction_text: editInstructionText,
        agent_type: editingInstruction.agent_type,
        instruction_type: editingInstruction.instruction_type,
        description: editDescription,
        original_user_request: editOriginalRequest,
      })

      setSuccess("Instruction updated successfully!")
      setEditDialogOpen(false)

      // Reload instructions
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

  // Group instructions by agent_type and instruction_type
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
            View and manage all instructions cached in the database for different agent types
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

          {success && (
            <Alert>
              <AlertDescription>{success}</AlertDescription>
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
                        <TableHead>Instruction Preview</TableHead>
                        <TableHead className="w-40">Created</TableHead>
                        <TableHead className="w-32">Actions</TableHead>
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
                            <div className="max-w-md">
                              <pre className="text-xs whitespace-pre-wrap break-words font-mono bg-muted p-2 rounded line-clamp-3">
                                {instr.instruction_text.substring(0, 150)}
                                {instr.instruction_text.length > 150 && '...'}
                              </pre>
                            </div>
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {new Date(instr.created_at).toLocaleString()}
                          </TableCell>
                          <TableCell>
                            <div className="flex gap-2">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleViewInstruction(instr)}
                              >
                                View
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleEditInstruction(instr)}
                              >
                                <Edit2 className="h-4 w-4" />
                              </Button>
                            </div>
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

      {/* View Dialog */}
      <Dialog open={viewDialogOpen} onOpenChange={setViewDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              Instruction Details - v{viewingInstruction?.version}
            </DialogTitle>
            <DialogDescription>
              {viewingInstruction?.agent_type} - {viewingInstruction?.instruction_type}
            </DialogDescription>
          </DialogHeader>
          {viewingInstruction && (
            <div className="space-y-4">
              <div>
                <Label className="text-sm font-medium">Description</Label>
                <p className="text-sm text-muted-foreground mt-1">
                  {viewingInstruction.description || "No description"}
                </p>
              </div>

              <div>
                <Label className="text-sm font-medium">Original User Request</Label>
                <pre className="text-sm bg-muted p-3 rounded mt-1 whitespace-pre-wrap">
                  {viewingInstruction.original_user_request || "No original request"}
                </pre>
              </div>

              <div>
                <Label className="text-sm font-medium">Full Instruction Text</Label>
                <pre className="text-sm bg-muted p-3 rounded mt-1 whitespace-pre-wrap font-mono">
                  {viewingInstruction.instruction_text}
                </pre>
              </div>

              <div className="text-xs text-muted-foreground">
                Created: {new Date(viewingInstruction.created_at).toLocaleString()}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              Edit Instruction - v{editingInstruction?.version}
            </DialogTitle>
            <DialogDescription>
              Create a new version by modifying the instruction below
            </DialogDescription>
          </DialogHeader>
          {editingInstruction && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="edit-description">Description</Label>
                <Input
                  id="edit-description"
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  placeholder="Brief description of this instruction"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="edit-original-request">Original User Request</Label>
                <Textarea
                  id="edit-original-request"
                  value={editOriginalRequest}
                  onChange={(e) => setEditOriginalRequest(e.target.value)}
                  placeholder="What was originally requested"
                  rows={3}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="edit-instruction-text">Instruction Text</Label>
                <Textarea
                  id="edit-instruction-text"
                  value={editInstructionText}
                  onChange={(e) => setEditInstructionText(e.target.value)}
                  placeholder="The actual instruction text that will be added to the agent"
                  rows={12}
                  className="font-mono text-sm"
                />
              </div>

              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => setEditDialogOpen(false)}
                  disabled={saving}
                >
                  <X className="h-4 w-4 mr-2" />
                  Cancel
                </Button>
                <Button
                  onClick={handleSaveEdit}
                  disabled={saving}
                >
                  {saving ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4 mr-2" />
                      Save as New Version
                    </>
                  )}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
