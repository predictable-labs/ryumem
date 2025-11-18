"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import { api } from "@/lib/api";
import { Loader2, Plus } from "lucide-react";

interface EpisodeFormModalProps {
  userId?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onEpisodeAdded?: () => void;
}

export function EpisodeFormModal({
  userId,
  open,
  onOpenChange,
  onEpisodeAdded,
}: EpisodeFormModalProps) {
  const [content, setContent] = useState("");
  const [source, setSource] = useState("text");
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!content.trim()) {
      toast({
        title: "Error",
        description: "Please enter some content",
        variant: "destructive",
      });
      return;
    }

    setIsLoading(true);

    try {
      await api.addEpisode({
        content: content.trim(),
        user_id: userId!,
        source,
      });

      toast({
        title: "Success!",
        description: "Episode added successfully",
      });

      // Reset form
      setContent("");
      setSource("text");

      // Close modal
      onOpenChange(false);

      // Notify parent
      if (onEpisodeAdded) {
        onEpisodeAdded();
      }
    } catch (error) {
      console.error("Error adding episode:", error);
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to add episode",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const fillExample = (exampleContent: string) => {
    setContent(exampleContent);
  };

  const exampleEpisodes = [
    "Alice works at Google as a Software Engineer in Mountain View.",
    "Bob met Carol at Stanford University in 2015 where they both studied Computer Science.",
    "David founded a startup called TechCorp in San Francisco in 2020.",
  ];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Add New Episode</DialogTitle>
          <DialogDescription>
            Add a new memory episode. Entities and relationships will be automatically extracted.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="content">Episode Content</Label>
            <Textarea
              id="content"
              placeholder="Enter episode content (text, message, or JSON)..."
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={8}
              className="resize-none"
              disabled={isLoading}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="source">Source Type</Label>
            <Select value={source} onValueChange={setSource} disabled={isLoading}>
              <SelectTrigger id="source">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="text">Text</SelectItem>
                <SelectItem value="message">Message/Conversation</SelectItem>
                <SelectItem value="json">JSON</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Example Episodes */}
          <div className="space-y-2">
            <Label>Example Episodes</Label>
            <div className="space-y-2">
              {exampleEpisodes.map((example, index) => (
                <button
                  key={index}
                  type="button"
                  onClick={() => fillExample(example)}
                  disabled={isLoading}
                  className="w-full text-left p-3 rounded-md border border-border bg-muted/50 hover:bg-muted transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading || !content.trim()}>
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Adding...
                </>
              ) : (
                <>
                  <Plus className="mr-2 h-4 w-4" />
                  Add Episode
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
