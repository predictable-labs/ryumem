"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { api, Entity, Edge, SearchResultEpisode } from "@/lib/api";
import { Search, Loader2, User, Link as LinkIcon, TrendingUp, Sparkles, FileText, Plus, Zap } from "lucide-react";
import { Label } from "@/components/ui/label";

interface PlaygroundProps {
  userId?: string;
  onEpisodeAdded?: () => void;
  entityExtractionEnabled?: boolean;
}

interface QueryResult {
  query: string;
  entities: Entity[];
  edges: Edge[];
  episodes: SearchResultEpisode[];
  strategy: string;
  count: number;
}

export function Playground({ userId, onEpisodeAdded, entityExtractionEnabled = false }: PlaygroundProps) {
  // Search state
  const [query, setQuery] = useState("");
  const [strategy, setStrategy] = useState<"hybrid" | "semantic" | "bm25" | "traversal">("hybrid");
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState<QueryResult | null>(null);

  // Episode form state
  const [content, setContent] = useState("");
  const [source, setSource] = useState("text");
  const [tags, setTags] = useState("");
  const [isAddingEpisode, setIsAddingEpisode] = useState(false);

  const { toast } = useToast();

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!query.trim()) {
      toast({
        title: "Error",
        description: "Please enter a query",
        variant: "destructive",
      });
      return;
    }

    setIsSearching(true);

    try {
      const searchResult = await api.search({
        query: query.trim(),
        user_id: userId || "",
        limit: 10,
        strategy,
      });

      setResults({
        ...searchResult,
        query: query.trim(),
      });

      if (searchResult.count === 0) {
        toast({
          title: "No results",
          description: "Try a different query or add more episodes first",
        });
      }
    } catch (error) {
      console.error("Error searching:", error);
      toast({
        title: "Search Error",
        description: error instanceof Error ? error.message : "Failed to search",
        variant: "destructive",
      });
      setResults(null);
    } finally {
      setIsSearching(false);
    }
  };

  const handleAddEpisode = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!content.trim()) {
      toast({
        title: "Error",
        description: "Please enter some content",
        variant: "destructive",
      });
      return;
    }

    setIsAddingEpisode(true);

    try {
      const tagArray = tags
        .split(",")
        .map(t => t.trim())
        .filter(t => t.length > 0);

      const metadata: Record<string, unknown> = {};
      if (tagArray.length > 0) {
        metadata.tags = tagArray;
      }

      await api.addEpisode({
        content: content.trim(),
        user_id: userId || "",
        source,
        ...(Object.keys(metadata).length > 0 && { metadata }),
      });

      toast({
        title: "Success!",
        description: "Episode added successfully. Try searching for it!",
      });

      setContent("");
      setTags("");
      onEpisodeAdded?.();
    } catch (error) {
      console.error("Error adding episode:", error);
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to add episode",
        variant: "destructive",
      });
    } finally {
      setIsAddingEpisode(false);
    }
  };

  const exampleQueries = [
    "Where does Alice work?",
    "What did Bob study?",
    "Who works at Google?",
    "Tell me about machine learning projects",
  ];

  const exampleEpisodes = [
    "Alice works at Google as a Software Engineer in Mountain View.",
    "Bob graduated from Stanford University in 2020 with a degree in Computer Science.",
    "Alice and Bob are colleagues and often collaborate on machine learning projects.",
  ];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Left Panel - Search */}
      <Card className="flex flex-col">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search className="h-5 w-5" />
            Explore Memories
          </CardTitle>
          <CardDescription>
            Search your knowledge graph using hybrid search (semantic + BM25 + graph traversal)
          </CardDescription>
        </CardHeader>
        <CardContent className="flex-1 space-y-4">
          {/* Search Form */}
          <form onSubmit={handleSearch} className="space-y-4">
            <div className="flex gap-2">
              <Input
                placeholder="Ask anything... e.g., 'Where does Alice work?'"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                disabled={isSearching}
                className="flex-1"
              />
              <Button type="submit" disabled={isSearching}>
                {isSearching ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Search className="h-4 w-4" />
                )}
              </Button>
            </div>

            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Label htmlFor="strategy" className="text-sm">Strategy:</Label>
                <Select value={strategy} onValueChange={(v: "hybrid" | "semantic" | "bm25" | "traversal") => setStrategy(v)} disabled={isSearching}>
                  <SelectTrigger id="strategy" className="w-[140px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="hybrid">
                      <span className="flex items-center gap-2">
                        <Sparkles className="h-3 w-3" />
                        Hybrid
                      </span>
                    </SelectItem>
                    <SelectItem value="semantic">Semantic</SelectItem>
                    <SelectItem value="bm25">BM25</SelectItem>
                    <SelectItem value="traversal">Graph</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </form>

          {/* Example Queries */}
          {!results && (
            <div className="space-y-3 rounded-lg border bg-muted/50 p-4">
              <h4 className="text-sm font-semibold">Example Queries:</h4>
              <div className="grid grid-cols-1 gap-2">
                {exampleQueries.map((exampleQuery, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setQuery(exampleQuery)}
                    className="rounded-md bg-background px-3 py-2 text-left text-sm hover:bg-accent transition-colors"
                    disabled={isSearching}
                  >
                    {exampleQuery}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Results */}
          {results && (
            <div className="space-y-4">
              {/* Header */}
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-semibold">Results for: &quot;{results.query}&quot;</h3>
                  <p className="text-sm text-muted-foreground">
                    Found {results.count} results using {results.strategy} search
                  </p>
                </div>
                <Button variant="outline" size="sm" onClick={() => setResults(null)}>
                  Clear
                </Button>
              </div>

              {/* Entities */}
              {results.entities.length > 0 && (
                <div className="space-y-2">
                  <h4 className="flex items-center gap-2 text-sm font-semibold">
                    <User className="h-4 w-4" />
                    Entities ({results.entities.length})
                  </h4>
                  <div className="space-y-2 max-h-[200px] overflow-y-auto">
                    {results.entities.map((entity) => (
                      <div
                        key={entity.uuid}
                        className="flex items-start justify-between gap-2 rounded-lg border p-3 hover:bg-accent/50 transition-colors"
                      >
                        <div className="flex-1 space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-sm">{entity.name}</span>
                            <Badge variant="secondary" className="text-xs">{entity.entity_type}</Badge>
                          </div>
                          {entity.summary && (
                            <p className="text-xs text-muted-foreground line-clamp-2">{entity.summary}</p>
                          )}
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <span>{entity.mentions} mentions</span>
                            <span>•</span>
                            <span className="flex items-center gap-1">
                              <TrendingUp className="h-3 w-3" />
                              {entity.score.toFixed(3)}
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Relationships/Facts */}
              {results.edges.length > 0 && (
                <div className="space-y-2">
                  <h4 className="flex items-center gap-2 text-sm font-semibold">
                    <LinkIcon className="h-4 w-4" />
                    Facts ({results.edges.length})
                  </h4>
                  <div className="space-y-2 max-h-[200px] overflow-y-auto">
                    {results.edges.map((edge) => (
                      <div
                        key={edge.uuid}
                        className="rounded-lg border p-3 space-y-1 hover:bg-accent/50 transition-colors"
                      >
                        <div className="flex items-center gap-1 flex-wrap text-xs">
                          {edge.source_name && edge.target_name && (
                            <>
                              <Badge variant="outline" className="font-mono text-xs">
                                {edge.source_name}
                              </Badge>
                              <span className="text-muted-foreground">→</span>
                              <Badge variant="outline" className="text-xs">
                                {edge.relation_type}
                              </Badge>
                              <span className="text-muted-foreground">→</span>
                              <Badge variant="outline" className="font-mono text-xs">
                                {edge.target_name}
                              </Badge>
                            </>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground">{edge.fact}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Episodes */}
              {results.episodes && results.episodes.length > 0 && (
                <div className="space-y-2">
                  <h4 className="flex items-center gap-2 text-sm font-semibold">
                    <FileText className="h-4 w-4" />
                    Episodes ({results.episodes.length})
                  </h4>
                  <div className="space-y-2 max-h-[200px] overflow-y-auto">
                    {results.episodes.map((episode) => (
                      <div
                        key={episode.uuid}
                        className="rounded-lg border p-3 space-y-1 hover:bg-accent/50 transition-colors"
                      >
                        <div className="flex items-center gap-2">
                          {episode.kind && (
                            <Badge variant="secondary" className="text-xs">{episode.kind}</Badge>
                          )}
                          {episode.source && (
                            <Badge variant="outline" className="text-xs">{episode.source}</Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground line-clamp-2">
                          {episode.content}
                        </p>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <span>{new Date(episode.created_at).toLocaleDateString()}</span>
                          <span>•</span>
                          <span className="flex items-center gap-1">
                            <TrendingUp className="h-3 w-3" />
                            {episode.score.toFixed(3)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* No results */}
              {results.count === 0 && (
                <div className="text-center py-8">
                  <p className="text-sm text-muted-foreground">
                    No results found. Try a different query or add more episodes.
                  </p>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Right Panel - Add Episode */}
      <Card className="flex flex-col">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plus className="h-5 w-5" />
            Add New Memory
          </CardTitle>
          <CardDescription className="flex items-center gap-2">
            Store new information.
            {entityExtractionEnabled ? (
              <Badge variant="secondary" className="text-xs flex items-center gap-1">
                <Zap className="h-3 w-3" />
                Entity extraction enabled
              </Badge>
            ) : (
              <span className="text-muted-foreground">(Entity extraction disabled)</span>
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex-1 space-y-4">
          <form onSubmit={handleAddEpisode} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="content">Content</Label>
              <Textarea
                id="content"
                placeholder="Enter information to remember..."
                value={content}
                onChange={(e) => setContent(e.target.value)}
                className="min-h-[120px] resize-y"
                disabled={isAddingEpisode}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="source">Source Type</Label>
              <Select value={source} onValueChange={setSource} disabled={isAddingEpisode}>
                <SelectTrigger id="source">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="text">Text (plain facts, notes, descriptions)</SelectItem>
                  <SelectItem value="message">Message (chat logs, conversations)</SelectItem>
                  <SelectItem value="json">JSON (structured data objects)</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                {source === "text" && "Free-form text like \"Alice works at Google\" or meeting notes"}
                {source === "message" && "Conversation format like \"User: Hi\" / \"Assistant: Hello\""}
                {source === "json" && "Structured data like {\"name\": \"Alice\", \"company\": \"Google\"}"}
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="tags">Tags (optional)</Label>
              <Input
                id="tags"
                placeholder="e.g., project, api, backend"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                disabled={isAddingEpisode}
              />
              <p className="text-xs text-muted-foreground">
                Comma-separated tags to organize this episode
              </p>
            </div>

            <Button type="submit" disabled={isAddingEpisode} className="w-full">
              {isAddingEpisode ? (
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
          </form>

          {/* Example Episodes */}
          <div className="space-y-3 rounded-lg border bg-muted/50 p-4">
            <h4 className="text-sm font-semibold">Example Episodes:</h4>
            <div className="space-y-2">
              {exampleEpisodes.map((example, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setContent(example)}
                  className="block w-full rounded-md bg-background px-3 py-2 text-left text-xs hover:bg-accent transition-colors"
                  disabled={isAddingEpisode}
                >
                  &quot;{example.length > 60 ? example.substring(0, 60) + "..." : example}&quot;
                </button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
