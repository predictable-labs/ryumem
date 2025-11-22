"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import { api } from "@/lib/api";
import { Loader2, Plus, CheckCircle2 } from "lucide-react";

interface EpisodeFormProps {
  userId?: string;
  onEpisodeAdded?: () => void;
}

export function EpisodeForm({ userId, onEpisodeAdded }: EpisodeFormProps) {
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
      const response = await api.addEpisode({
        content: content.trim(),
        user_id: userId || "",
        source,
      });

      toast({
        title: "Success!",
        description: "Episode added successfully",
      });

      setContent("");
      onEpisodeAdded?.();
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

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="content">Episode Content</Label>
        <Textarea
          id="content"
          placeholder="Enter information to remember... e.g., 'Alice works at Google as a Software Engineer in Mountain View.'"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          className="min-h-[120px] resize-y"
          disabled={isLoading}
        />
        <p className="text-sm text-muted-foreground">
          Enter any information you want to store. Entities and relationships will be automatically extracted.
        </p>
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
        <p className="text-sm text-muted-foreground">
          Select the type of content you&apos;re adding
        </p>
      </div>

      <div className="flex gap-2">
        <Button type="submit" disabled={isLoading} className="flex-1">
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
      </div>

      {/* Example episodes */}
      <div className="mt-6 space-y-3 rounded-lg border bg-muted/50 p-4">
        <h4 className="text-sm font-semibold">Example Episodes:</h4>
        <div className="space-y-2 text-sm">
          <button
            type="button"
            onClick={() => setContent("Alice works at Google as a Software Engineer in Mountain View.")}
            className="block w-full rounded-md bg-background px-3 py-2 text-left hover:bg-accent transition-colors"
            disabled={isLoading}
          >
            &quot;Alice works at Google as a Software Engineer in Mountain View.&quot;
          </button>
          <button
            type="button"
            onClick={() => setContent("Bob graduated from Stanford University in 2020 with a degree in Computer Science.")}
            className="block w-full rounded-md bg-background px-3 py-2 text-left hover:bg-accent transition-colors"
            disabled={isLoading}
          >
            &quot;Bob graduated from Stanford University in 2020...&quot;
          </button>
          <button
            type="button"
            onClick={() => setContent("Alice and Bob are colleagues and often collaborate on machine learning projects.")}
            className="block w-full rounded-md bg-background px-3 py-2 text-left hover:bg-accent transition-colors"
            disabled={isLoading}
          >
            &quot;Alice and Bob are colleagues and collaborate on ML projects.&quot;
          </button>
        </div>
      </div>
    </form>
  );
}

