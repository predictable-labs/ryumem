"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, type EpisodeInfo } from "@/lib/api";
import { Search, Calendar, ArrowUpDown, Loader2, Plus, Clock } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";

interface EpisodesListProps {
  userId?: string;
  onAddEpisodeClick: () => void;
}

export function EpisodesList({ userId, onAddEpisodeClick }: EpisodesListProps) {
  const [episodes, setEpisodes] = useState<EpisodeInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [search, setSearch] = useState("");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

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
  }, [userId, search, sortOrder, startDate, endDate, isLoading, hasMore, toast]);

  // Initial load and filters change
  useEffect(() => {
    offset.current = 0;
    setHasMore(true);
    loadEpisodes(true);
  }, [search, sortOrder, startDate, endDate, userId]);

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
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
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
        {episodes.length === 0 && !isLoading ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Clock className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">No episodes found</h3>
              <p className="text-sm text-muted-foreground text-center mb-4">
                {search || startDate || endDate
                  ? "Try adjusting your filters"
                  : "Get started by adding your first episode"}
              </p>
              <Button onClick={onAddEpisodeClick} className="gap-2">
                <Plus className="h-4 w-4" />
                Add Episode
              </Button>
            </CardContent>
          </Card>
        ) : (
          episodes.map((episode) => (
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
                      {episode.session_id && (
                        <Badge variant="outline" className="text-xs">
                          Session: {episode.session_id.slice(0, 8)}...
                        </Badge>
                      )}
                    </div>
                  </div>
                  <Badge className={`${getSourceColor(episode.source)} shrink-0`}>
                    {episode.source}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm whitespace-pre-wrap break-words">
                  {episode.content}
                </p>
                {episode.source_description && (
                  <p className="text-xs text-muted-foreground mt-2">
                    {episode.source_description}
                  </p>
                )}
              </CardContent>
            </Card>
          ))
        )}

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
            You've reached the end
          </div>
        )}
      </div>
    </div>
  );
}
