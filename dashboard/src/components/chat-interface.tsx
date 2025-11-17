"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { api, Entity, Edge } from "@/lib/api";
import { Search, Loader2, User, Link as LinkIcon, TrendingUp, Sparkles } from "lucide-react";
import { Label } from "@/components/ui/label";

interface ChatInterfaceProps {
  groupId: string;
  userId?: string;
}

interface QueryResult {
  query: string;
  entities: Entity[];
  edges: Edge[];
  strategy: string;
  count: number;
}

export function ChatInterface({ groupId, userId }: ChatInterfaceProps) {
  const [query, setQuery] = useState("");
  const [strategy, setStrategy] = useState<"hybrid" | "semantic" | "bm25" | "traversal">("hybrid");
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState<QueryResult | null>(null);
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
        group_id: groupId,
        user_id: userId,
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

  const exampleQueries = [
    "Where does Alice work?",
    "What did Bob study?",
    "Who works at Google?",
    "Tell me about machine learning projects",
  ];

  return (
    <div className="space-y-6">
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
            <Select value={strategy} onValueChange={(v: any) => setStrategy(v)} disabled={isSearching}>
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

          <div className="flex-1 text-sm text-muted-foreground">
            {strategy === "hybrid" && "Combines semantic, BM25, and graph search (recommended)"}
            {strategy === "semantic" && "Embedding-based similarity search"}
            {strategy === "bm25" && "Keyword-based lexical matching"}
            {strategy === "traversal" && "Graph relationship navigation"}
          </div>
        </div>
      </form>

      {/* Example Queries */}
      {!results && (
        <div className="space-y-3 rounded-lg border bg-muted/50 p-4">
          <h4 className="text-sm font-semibold">Example Queries:</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
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
              <h3 className="text-lg font-semibold">Results for: "{results.query}"</h3>
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
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <User className="h-5 w-5" />
                  Entities ({results.entities.length})
                </CardTitle>
                <CardDescription>
                  People, places, organizations, and concepts found
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {results.entities.map((entity) => (
                  <div
                    key={entity.uuid}
                    className="flex items-start justify-between gap-4 rounded-lg border p-4 hover:bg-accent/50 transition-colors"
                  >
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center gap-2">
                        <h4 className="font-semibold">{entity.name}</h4>
                        <Badge variant="secondary">{entity.entity_type}</Badge>
                      </div>
                      {entity.summary && (
                        <p className="text-sm text-muted-foreground">{entity.summary}</p>
                      )}
                      <div className="flex items-center gap-3 text-xs text-muted-foreground">
                        <span>{entity.mentions} mentions</span>
                        <span>•</span>
                        <span className="flex items-center gap-1">
                          <TrendingUp className="h-3 w-3" />
                          Score: {entity.score.toFixed(4)}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Relationships/Facts */}
          {results.edges.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <LinkIcon className="h-5 w-5" />
                  Facts & Relationships ({results.edges.length})
                </CardTitle>
                <CardDescription>
                  Extracted facts and connections between entities
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {results.edges.map((edge) => (
                  <div
                    key={edge.uuid}
                    className="rounded-lg border p-4 space-y-2 hover:bg-accent/50 transition-colors"
                  >
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      {edge.source_name && edge.target_name && (
                        <>
                          <Badge variant="outline" className="font-mono text-xs">
                            {edge.source_name}
                          </Badge>
                          <span>→</span>
                          <Badge variant="outline" className="text-xs">
                            {edge.relation_type}
                          </Badge>
                          <span>→</span>
                          <Badge variant="outline" className="font-mono text-xs">
                            {edge.target_name}
                          </Badge>
                        </>
                      )}
                    </div>
                    <p className="text-sm">{edge.fact}</p>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span>{edge.mentions} mentions</span>
                      <span>•</span>
                      <span className="flex items-center gap-1">
                        <TrendingUp className="h-3 w-3" />
                        Score: {edge.score.toFixed(4)}
                      </span>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* No results */}
          {results.count === 0 && (
            <Card>
              <CardContent className="py-12 text-center">
                <p className="text-muted-foreground">
                  No results found. Try a different query or add more episodes first.
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

