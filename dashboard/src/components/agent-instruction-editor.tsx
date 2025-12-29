"use client"

import { useState, useEffect, useCallback, useMemo } from "react"
import { api, type AgentInstructionResponse } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Loader2, Database, Edit2, X, Save, Trash2, AlertCircle, Info } from "lucide-react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
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

// Valid template variables for query augmentation templates
// Based on src/ryumem/integrations/google_adk.py:705-712
const VALID_TEMPLATE_VARIABLES = [
  'agent_response',
  'tool_summary',
  'simplified_tool_summary',
  'custom_tool_summary',
  'last_session',
  'query_text'
] as const

// Extract template variables from a string (e.g., "{var1} text {var2}" -> ["var1", "var2"])
function extractTemplateVariables(template: string): string[] {
  const matches = template.match(/\{([^}]+)\}/g)
  if (!matches) return []
  return matches.map(m => m.slice(1, -1)) // Remove { and }
}

// Validate template variables
function validateTemplateVariables(template: string): { valid: boolean; invalidVars: string[] } {
  const usedVars = extractTemplateVariables(template)
  const invalidVars = usedVars.filter(v => !VALID_TEMPLATE_VARIABLES.includes(v as any))
  return { valid: invalidVars.length === 0, invalidVars }
}

export function AgentInstructionEditor({ userId }: AgentInstructionEditorProps) {
  const [agentType, setAgentType] = useState<string>("all")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [instructions, setInstructions] = useState<AgentInstructionResponse[]>([])

  // View/Edit dialog state (unified)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [selectedInstruction, setSelectedInstruction] = useState<AgentInstructionResponse | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [editedBaseInstruction, setEditedBaseInstruction] = useState("")
  const [editedEnhancedInstruction, setEditedEnhancedInstruction] = useState("")
  const [editedQueryTemplate, setEditedQueryTemplate] = useState("")
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState(false)

  // Validate template variables
  const templateValidation = useMemo(() => {
    if (!editedQueryTemplate) return { valid: true, invalidVars: [], usedVars: [] }
    const validation = validateTemplateVariables(editedQueryTemplate)
    const usedVars = extractTemplateVariables(editedQueryTemplate)
    return { ...validation, usedVars }
  }, [editedQueryTemplate])

  const loadInstructions = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      // Load instructions with optional filters
      const allInstructions = await api.listAgentInstructions(
        agentType === "all" ? undefined : agentType,
        100
      )

      setInstructions(allInstructions)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load instructions")
      console.error("Error loading instructions:", err)
    } finally {
      setLoading(false)
    }
  }, [agentType])

  // Load all cached instructions
  useEffect(() => {
    loadInstructions()
  }, [loadInstructions])

  const handleOpenDialog = (instruction: AgentInstructionResponse) => {
    setSelectedInstruction(instruction)
    setEditedBaseInstruction(instruction.base_instruction)
    setEditedEnhancedInstruction(instruction.enhanced_instruction)
    setEditedQueryTemplate(instruction.query_augmentation_template || "")
    setIsEditing(true)  // Start in edit mode
    setDialogOpen(true)
  }

  const handleSave = async () => {
    if (!selectedInstruction) return

    setSaving(true)
    setError(null)
    setSuccess(null)

    try {
      await api.createAgentInstruction({
        base_instruction: editedBaseInstruction,
        enhanced_instruction: editedEnhancedInstruction,
        query_augmentation_template: editedQueryTemplate,
        agent_type: selectedInstruction.agent_type,
        memory_enabled: selectedInstruction.memory_enabled,
        tool_tracking_enabled: selectedInstruction.tool_tracking_enabled,
      })

      setSuccess("Agent configuration updated successfully!")
      setIsEditing(false)

      // Reload instructions
      await loadInstructions()

      // Update the selected instruction with new values
      const updated = instructions.find(i => i.agent_type === selectedInstruction.agent_type)
      if (updated) {
        setSelectedInstruction(updated)
      }

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save configuration")
      console.error("Error saving configuration:", err)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!selectedInstruction) return

    // First click: ask for confirmation
    if (!deleteConfirm) {
      setDeleteConfirm(true)
      setTimeout(() => setDeleteConfirm(false), 3000)
      return
    }

    setDeleting(true)
    setError(null)
    setSuccess(null)

    try {
      await api.deleteAgentInstruction(selectedInstruction.instruction_id)
      setSuccess("Agent instruction deleted successfully!")
      setDialogOpen(false)

      // Reload instructions
      await loadInstructions()

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete instruction")
      console.error("Error deleting instruction:", err)
    } finally {
      setDeleting(false)
      setDeleteConfirm(false)
    }
  }

  // Group instructions by agent_type (should be one per agent_type now)
  const groupedInstructions = instructions.reduce((acc, instr) => {
    const key = instr.agent_type
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
                        <TableHead className="w-32">Agent Type</TableHead>
                        <TableHead className="w-48">Base Instruction</TableHead>
                        <TableHead className="w-40">Features</TableHead>
                        <TableHead className="w-64">Enhanced Instruction</TableHead>
                        <TableHead className="w-64">Query Template</TableHead>
                        <TableHead className="w-40">Last Updated</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {instrs.map((instr) => (
                        <TableRow
                          key={instr.instruction_id}
                          className="cursor-pointer hover:bg-muted/50"
                          onClick={() => handleOpenDialog(instr)}
                        >
                          <TableCell className="font-medium">{instr.agent_type}</TableCell>
                          <TableCell>
                            <div className="max-w-xs">
                              <pre className="text-xs whitespace-pre-wrap break-words font-mono bg-slate-50 p-2 rounded line-clamp-2">
                                {instr.base_instruction.substring(0, 80)}
                                {instr.base_instruction.length > 80 && '...'}
                              </pre>
                            </div>
                          </TableCell>
                          <TableCell className="text-sm">
                            <div className="flex gap-1 flex-wrap">
                              {instr.memory_enabled && <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">Memory</span>}
                              {instr.tool_tracking_enabled && <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded">Tracking</span>}
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="max-w-xs">
                              <pre className="text-xs whitespace-pre-wrap break-words font-mono bg-muted p-2 rounded line-clamp-2">
                                {instr.enhanced_instruction.substring(0, 100)}
                                {instr.enhanced_instruction.length > 100 && '...'}
                              </pre>
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="max-w-xs">
                              {instr.query_augmentation_template ? (
                                <pre className="text-xs whitespace-pre-wrap break-words font-mono bg-amber-50 p-2 rounded line-clamp-2">
                                  {instr.query_augmentation_template.substring(0, 100)}
                                  {instr.query_augmentation_template.length > 100 && '...'}
                                </pre>
                              ) : (
                                <span className="text-xs text-muted-foreground italic">No template</span>
                              )}
                            </div>
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {new Date(instr.updated_at || instr.created_at).toLocaleString()}
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

      {/* Unified View/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              Agent Configuration - {selectedInstruction?.agent_type}
            </DialogTitle>
            <DialogDescription>
              <div className="flex gap-2 mt-2">
                {selectedInstruction?.memory_enabled && <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">Memory Enabled</span>}
                {selectedInstruction?.tool_tracking_enabled && <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded">Tool Tracking Enabled</span>}
              </div>
            </DialogDescription>
          </DialogHeader>
          {selectedInstruction && (
            <div className="space-y-4">
              <div>
                <Label className="text-sm font-medium">Base Instruction</Label>
                <pre className="text-sm bg-slate-50 p-3 rounded mt-1 whitespace-pre-wrap font-mono border border-slate-200">
                  {selectedInstruction.base_instruction}
                </pre>
              </div>

              <div>
                <Label className="text-sm font-medium">Enhanced Instruction</Label>
                <Textarea
                  value={editedEnhancedInstruction}
                  onChange={(e) => setEditedEnhancedInstruction(e.target.value)}
                  rows={8}
                  className="font-mono text-sm mt-1"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <Label className="text-sm font-medium">Query Augmentation Template</Label>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Info className="h-3 w-3" />
                    <span>Available template variables</span>
                  </div>
                </div>

                {/* Available template variables */}
                <div className="mb-2 flex flex-wrap gap-1">
                  {VALID_TEMPLATE_VARIABLES.map((varName) => {
                    const isUsed = templateValidation.usedVars.includes(varName)
                    return (
                      <Badge
                        key={varName}
                        variant={isUsed ? "default" : "outline"}
                        className="text-xs font-mono cursor-pointer"
                        onClick={() => {
                          // Insert variable at cursor position
                          const textarea = document.querySelector('textarea[placeholder="Optional query augmentation template..."]') as HTMLTextAreaElement
                          if (textarea) {
                            const cursorPos = textarea.selectionStart
                            const textBefore = editedQueryTemplate.substring(0, cursorPos)
                            const textAfter = editedQueryTemplate.substring(cursorPos)
                            setEditedQueryTemplate(textBefore + `{${varName}}` + textAfter)
                          }
                        }}
                      >
                        {`{${varName}}`}
                      </Badge>
                    )
                  })}
                </div>

                <Textarea
                  value={editedQueryTemplate}
                  onChange={(e) => setEditedQueryTemplate(e.target.value)}
                  rows={8}
                  className="font-mono text-sm mt-1"
                  placeholder="Optional query augmentation template..."
                />

                {/* Validation errors */}
                {!templateValidation.valid && (
                  <Alert variant="destructive" className="mt-2">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>
                      Invalid template variables found: {templateValidation.invalidVars.map(v => `{${v}}`).join(', ')}
                      <br />
                      <span className="text-xs">Only the variables shown above are supported.</span>
                    </AlertDescription>
                  </Alert>
                )}
              </div>

              <div className="text-xs text-muted-foreground border-t pt-3">
                Created: {new Date(selectedInstruction.created_at).toLocaleString()}
                {selectedInstruction.updated_at && ` • Updated: ${new Date(selectedInstruction.updated_at).toLocaleString()}`}
              </div>

              <div className="flex justify-between gap-2 pt-2">
                <Button
                  variant={deleteConfirm ? "destructive" : "outline"}
                  onClick={handleDelete}
                  disabled={deleting || saving}
                >
                  {deleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {!deleting && <Trash2 className="mr-2 h-4 w-4" />}
                  {deleteConfirm ? "Click again to confirm" : "Delete"}
                </Button>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() => setDialogOpen(false)}
                    disabled={saving || deleting}
                  >
                    Cancel
                  </Button>
                  <Button onClick={handleSave} disabled={saving || deleting || !templateValidation.valid}>
                    {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Save Changes
                  </Button>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
