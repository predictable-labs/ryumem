"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, type EpisodeInfo } from "@/lib/api";
import { Search, Calendar, ArrowUpDown, Loader2, Plus, Clock, Wrench, CheckCircle2, XCircle, Trash2, X, Tag as TagIcon } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";

interface EpisodesListProps {
  userId?: string;
  onAddEpisodeClick: () => void;
  onToolClick?: (toolName: string) => void;
}

export function EpisodesList({ userId, onAddEpisodeClick, onToolClick }: EpisodesListProps) {
  const [episodes, setEpisodes] = useState<EpisodeInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [search, setSearch] = useState("");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [editingTags, setEditingTags] = useState<string | null>(null);
  const [newTag, setNewTag] = useState("");
  const [deletingEpisode, setDeletingEpisode] = useState<string | null>(null);
  const [tagFilter, setTagFilter] = useState("");

  const { toast } = useToast();
  const observerTarget = useRef<HTMLDivElement>(null);
  const offset = useRef(0);

  const loadEpisodes = useCallback(async (reset = false) => {
    if (isLoading || (!hasMore && !reset)) return;

    setIsLoading(true);

    try {
      const currentOffset = reset ? 0 : offset.current;
      const response = await api.getEpisodes(
        userId,
        20, // limit
        currentOffset,
        startDate || undefined,
        endDate || undefined,
        search || undefined,
        sortOrder
      );

      if (reset) {
        setEpisodes(response.episodes);
        offset.current = response.episodes.length;
      } else {
        setEpisodes(prev => [...prev, ...response.episodes]);
        offset.current += response.episodes.length;
      }

      setTotal(response.total);
      setHasMore(offset.current < response.total);
    } catch (error) {
      console.error("Error loading episodes:", error);
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to load episodes",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  }, [userId, search, sortOrder, startDate, endDate, toast]);

  // Initial load and filters change
  useEffect(() => {
    offset.current = 0;
    setHasMore(true);
    loadEpisodes(true);
  }, [search, sortOrder, startDate, endDate, userId, loadEpisodes]);

  // Infinite scroll observer
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !isLoading) {
          loadEpisodes();
        }
      },
      { threshold: 0.1 }
    );

    const currentTarget = observerTarget.current;
    if (currentTarget) {
      observer.observe(currentTarget);
    }

    return () => {
      if (currentTarget) {
        observer.unobserve(currentTarget);
      }
    };
  }, [hasMore, isLoading, loadEpisodes]);

  const toggleSortOrder = () => {
    setSortOrder(prev => prev === "desc" ? "asc" : "desc");
  };

  const handleDeleteEpisode = async (episodeUuid: string) => {
    if (deletingEpisode === episodeUuid) {
      // Confirmed - proceed with deletion
      try {
        await api.deleteEpisode(episodeUuid);
        setEpisodes(prev => prev.filter(ep => ep.uuid !== episodeUuid));
        setTotal(prev => prev - 1);
        toast({
          title: "Success",
          description: "Episode deleted successfully",
        });
      } catch (error) {
        console.error("Error deleting episode:", error);
        toast({
          title: "Error",
          description: error instanceof Error ? error.message : "Failed to delete episode",
          variant: "destructive",
        });
      } finally {
        setDeletingEpisode(null);
      }
    } else {
      // First click - ask for confirmation
      setDeletingEpisode(episodeUuid);
      setTimeout(() => setDeletingEpisode(null), 3000); // Reset after 3 seconds
    }
  };

  const handleRemoveTag = async (episode: EpisodeInfo, tagToRemove: string) => {
    const currentTags = getTags(episode);
    const updatedTags = currentTags.filter(tag => tag !== tagToRemove);

    try {
      const updatedMetadata = {
        ...(episode.metadata || {}),
        tags: updatedTags,
      };

      await api.updateEpisodeMetadata(episode.uuid, updatedMetadata);

      // Update local state
      setEpisodes(prev => prev.map(ep =>
        ep.uuid === episode.uuid
          ? { ...ep, metadata: updatedMetadata }
          : ep
      ));

      toast({
        title: "Success",
        description: "Tag removed successfully",
      });
    } catch (error) {
      console.error("Error removing tag:", error);
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to remove tag",
        variant: "destructive",
      });
    }
  };

  const handleAddTag = async (episode: EpisodeInfo) => {
    if (!newTag.trim()) return;

    const currentTags = getTags(episode);
    if (currentTags.includes(newTag.trim())) {
      toast({
        title: "Info",
        description: "Tag already exists",
      });
      return;
    }

    const updatedTags = [...currentTags, newTag.trim()];

    try {
      const updatedMetadata = {
        ...(episode.metadata || {}),
        tags: updatedTags,
      };

      await api.updateEpisodeMetadata(episode.uuid, updatedMetadata);

      // Update local state
      setEpisodes(prev => prev.map(ep =>
        ep.uuid === episode.uuid
          ? { ...ep, metadata: updatedMetadata }
          : ep
      ));

      setNewTag("");
      setEditingTags(null);

      toast({
        title: "Success",
        description: "Tag added successfully",
      });
    } catch (error) {
      console.error("Error adding tag:", error);
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to add tag",
        variant: "destructive",
      });
    }
  };

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
      });
    } catch {
      return dateString;
    }
  };

  const getSourceColor = (source: string) => {
    switch (source.toLowerCase()) {
      case "message":
        return "bg-blue-500/10 text-blue-500 border-blue-500/20";
      case "json":
        return "bg-purple-500/10 text-purple-500 border-purple-500/20";
      case "text":
      default:
        return "bg-green-500/10 text-green-500 border-green-500/20";
    }
  };

  const getKindColor = (kind?: string) => {
    switch (kind?.toLowerCase()) {
      case "memory":
        return "bg-amber-500/10 text-amber-600 border-amber-500/20";
      case "query":
      default:
        return "bg-indigo-500/10 text-indigo-600 border-indigo-500/20";
    }
  };

  const getTags = (episode: EpisodeInfo): string[] => {
    const metadata = episode.metadata;
    if (!metadata?.tags) return [];
    return Array.isArray(metadata.tags) ? metadata.tags : [];
  };

  const filterEpisodesByTag = (episodes: EpisodeInfo[]): EpisodeInfo[] => {
    if (!tagFilter.trim()) return episodes;

    const filterText = tagFilter.toLowerCase().trim();
    return episodes.filter(episode => {
      const tags = getTags(episode);
      return tags.some(tag => tag.toLowerCase().includes(filterText));
    });
  };

  const getToolsUsed = (episode: EpisodeInfo) => {
    const metadata = episode.metadata;
    if (!metadata) return [];

    // New structure: metadata.sessions[session_id][].tools_used[]
    if (metadata.sessions) {
      const allTools: any[] = [];
      Object.values(metadata.sessions).forEach((runs: any) => {
        if (Array.isArray(runs)) {
          runs.forEach((run: any) => {
            if (run.tools_used && Array.isArray(run.tools_used)) {
              allTools.push(...run.tools_used);
            }
          });
        }
      });
      return allTools;
    }

    // Old structure (backward compatibility): metadata.tools_used[]
    return metadata.tools_used || [];
  };

  const getQueryRuns = (episode: EpisodeInfo) => {
    const metadata = episode.metadata;
    if (!metadata?.sessions) return [];

    const allRuns: any[] = [];
    Object.entries(metadata.sessions).forEach(([sessionId, runs]: [string, any]) => {
      if (Array.isArray(runs)) {
        runs.forEach((run: any) => {
          allRuns.push({ ...run, session_id: sessionId });
        });
      }
    });
    return allRuns;
  };

  return (
    <div className="space-y-4">
      {/* Header with Add Button */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Episodes</h2>
          <p className="text-sm text-muted-foreground">
            {total} total episode{total !== 1 ? "s" : ""}
          </p>
        </div>
        <Button onClick={onAddEpisodeClick} className="gap-2">
          <Plus className="h-4 w-4" />
          Add Episode
        </Button>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        {/* Search */}
        <div className="md:col-span-2 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search episodes..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>

        {/* Tag Filter */}
        <div className="relative">
          <TagIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Filter by tags..."
            value={tagFilter}
            onChange={(e) => setTagFilter(e.target.value)}
            className="pl-10"
          />
        </div>

        {/* Start Date */}
        <div className="relative">
          <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="date"
            placeholder="Start date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="pl-10"
          />
        </div>

        {/* End Date */}
        <div className="relative">
          <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="date"
            placeholder="End date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="pl-10"
          />
        </div>
      </div>

      {/* Sort Toggle */}
      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          size="sm"
          onClick={toggleSortOrder}
          className="gap-2"
        >
          <ArrowUpDown className="h-4 w-4" />
          {sortOrder === "desc" ? "Newest First" : "Oldest First"}
        </Button>
      </div>

      {/* Episodes Timeline */}
      <div className="space-y-4">
        {(() => {
          const filteredEpisodes = filterEpisodesByTag(episodes);

          if (filteredEpisodes.length === 0 && !isLoading) {
            return (
              <Card>
                <CardContent className="flex flex-col items-center justify-center py-12">
                  <Clock className="h-12 w-12 text-muted-foreground mb-4" />
                  <h3 className="text-lg font-semibold mb-2">No episodes found</h3>
                  <p className="text-sm text-muted-foreground text-center mb-4">
                    {search || startDate || endDate || tagFilter
                      ? "Try adjusting your filters"
                      : "Get started by adding your first episode"}
                  </p>
                  <Button onClick={onAddEpisodeClick} className="gap-2">
                    <Plus className="h-4 w-4" />
                    Add Episode
                  </Button>
                </CardContent>
              </Card>
            );
          }

          return filteredEpisodes.map((episode) => (
            <Card key={episode.uuid} className="transition-all hover:shadow-md">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <CardTitle className="text-base font-semibold mb-2 truncate">
                      {episode.name || "Untitled Episode"}
                    </CardTitle>
                    <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        <span>{formatDate(episode.created_at)}</span>
                      </div>
                      {episode.user_id && (
                        <Badge variant="outline" className="text-xs">
                          User: {episode.user_id}
                        </Badge>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-2 shrink-0 items-start">
                    <Badge className={getKindColor(episode.kind)}>
                      {episode.kind || 'query'}
                    </Badge>
                    <Badge className={getSourceColor(episode.source)}>
                      {episode.source}
                    </Badge>
                    <Button
                      variant={deletingEpisode === episode.uuid ? "destructive" : "ghost"}
                      size="sm"
                      onClick={() => handleDeleteEpisode(episode.uuid)}
                      className="h-7 px-2"
                      title={deletingEpisode === episode.uuid ? "Click again to confirm" : "Delete episode"}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {/* Tags Section */}
                {(() => {
                  const tags = getTags(episode);
                  const isEditing = editingTags === episode.uuid;

                  return (
                    <div className="mb-3">
                      <div className="flex items-center gap-2 mb-2">
                        <TagIcon className="h-3.5 w-3.5 text-muted-foreground" />
                        <span className="text-xs font-medium text-muted-foreground">Tags</span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setEditingTags(isEditing ? null : episode.uuid);
                            setNewTag("");
                          }}
                          className="h-6 px-2 text-xs"
                        >
                          {isEditing ? "Done" : "Edit"}
                        </Button>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {tags.length === 0 && !isEditing ? (
                          <span className="text-xs text-muted-foreground italic">No tags</span>
                        ) : (
                          tags.map((tag, idx) => (
                            <Badge
                              key={idx}
                              variant="outline"
                              className="text-xs bg-slate-500/10 text-slate-600 border-slate-500/20 gap-1.5"
                            >
                              {tag}
                              {isEditing && (
                                <button
                                  onClick={() => handleRemoveTag(episode, tag)}
                                  className="ml-1 hover:bg-slate-500/20 rounded-sm"
                                >
                                  <X className="h-3 w-3" />
                                </button>
                              )}
                            </Badge>
                          ))
                        )}
                        {isEditing && (
                          <div className="flex items-center gap-1">
                            <Input
                              placeholder="New tag..."
                              value={newTag}
                              onChange={(e) => setNewTag(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") {
                                  e.preventDefault();
                                  handleAddTag(episode);
                                }
                              }}
                              className="h-6 w-24 text-xs px-2"
                            />
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleAddTag(episode)}
                              className="h-6 px-2"
                              disabled={!newTag.trim()}
                            >
                              <Plus className="h-3 w-3" />
                            </Button>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })()}

                <p className="text-sm whitespace-pre-wrap break-words">
                  {episode.content}
                </p>
                {episode.source_description && (
                  <p className="text-xs text-muted-foreground mt-2">
                    {episode.source_description}
                  </p>
                )}

                {/* Query Runs Section */}
                {(() => {
                  const queryRuns = getQueryRuns(episode);
                  if (queryRuns.length === 0) return null;

                  return (
                    <div className="mt-4 pt-4 border-t">
                      <div className="flex items-center gap-2 mb-3">
                        <Search className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium text-muted-foreground">
                          Query Runs ({queryRuns.length})
                        </span>
                      </div>
                      <div className="space-y-4">
                        {queryRuns.map((run: any, idx: number) => (
                          <div
                            key={idx}
                            className="p-3 rounded-md bg-muted/30 border border-muted text-xs space-y-2"
                          >
                            <div className="flex items-center gap-2">
                              <span className="text-muted-foreground">
                                {formatDate(run.timestamp)}
                              </span>
                            </div>

                            {run.query && (
                              <div>
                                <p className="font-medium text-muted-foreground mb-1">Query:</p>
                                <p className="text-foreground/90">{run.query}</p>
                              </div>
                            )}

                            {run.augmented_query && (
                              <div>
                                <p className="font-medium text-purple-500 mb-1">
                                  Augmented Query:
                                  {run.augmented_query === run.query && (
                                    <Badge variant="outline" className="ml-2 text-[10px]">
                                      Same as query
                                    </Badge>
                                  )}
                                </p>
                                <p className="text-foreground/70 text-[11px] max-h-40 overflow-y-auto whitespace-pre-wrap">
                                  {run.augmented_query}
                                </p>
                              </div>
                            )}

                            {run.agent_response && (
                              <div>
                                <p className="font-medium text-blue-500 mb-1">Agent Response:</p>
                                <p className="text-foreground/80">{run.agent_response}</p>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })()}

                {/* Tool Usage Section */}
                {(() => {
                  const toolsUsed = getToolsUsed(episode);
                  if (toolsUsed.length === 0) return null;

                  return (
                    <div className="mt-4 pt-4 border-t">
                      <div className="flex items-center gap-2 mb-3">
                        <Wrench className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium text-muted-foreground">
                          Tools Used ({toolsUsed.length})
                        </span>
                      </div>
                      <div className="space-y-2">
                        {toolsUsed.map((tool: any, idx: number) => (
                          <div
                            key={idx}
                            className="flex items-start gap-2 p-2 rounded-md bg-muted/50 text-xs"
                          >
                            <div className="mt-0.5">
                              {tool.success ? (
                                <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                              ) : (
                                <XCircle className="h-3.5 w-3.5 text-red-500" />
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <button
                                  onClick={() => onToolClick?.(tool.tool_name)}
                                  className="font-medium hover:underline hover:text-primary cursor-pointer transition-colors"
                                >
                                  {tool.tool_name}
                                </button>
                                <Badge variant="outline" className="text-[10px] px-1 py-0">
                                  {tool.duration_ms}ms
                                </Badge>
                              </div>
                              {tool.context && (
                                <p className="text-muted-foreground line-clamp-2">
                                  {tool.context}
                                </p>
                              )}
                              {!tool.success && tool.error && (
                                <p className="text-red-500 mt-1 line-clamp-1">
                                  Error: {tool.error}
                                </p>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })()}
              </CardContent>
            </Card>
          ));
        })()}

        {/* Loading Indicator */}
        {isLoading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* Infinite Scroll Trigger */}
        <div ref={observerTarget} className="h-4" />

        {/* End Message */}
        {!hasMore && episodes.length > 0 && (
          <div className="text-center py-4 text-sm text-muted-foreground">
            You&apos;ve reached the end
          </div>
        )}
      </div>
    </div>
  );
}
