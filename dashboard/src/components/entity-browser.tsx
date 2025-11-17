"use client"

import React, { useState, useEffect } from 'react';
import { Entity, EntitiesListResponse, api } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ChevronLeft, ChevronRight, Search } from 'lucide-react';

interface EntityBrowserProps {
  data: EntitiesListResponse;
  onEntityClick?: (entity: Entity) => void;
  onLoadMore?: (offset: number) => void;
  onFilterChange?: (entityType?: string) => void;
  groupId: string;  // Add groupId to props
}

const getEntityColor = (type: string) => {
  const colors: Record<string, string> = {
    PERSON: 'bg-blue-100 text-blue-800 border-blue-200',
    ORGANIZATION: 'bg-green-100 text-green-800 border-green-200',
    LOCATION: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    EVENT: 'bg-pink-100 text-pink-800 border-pink-200',
    CONCEPT: 'bg-purple-100 text-purple-800 border-purple-200',
    OBJECT: 'bg-orange-100 text-orange-800 border-orange-200',
  };
  return colors[type] || 'bg-gray-100 text-gray-800 border-gray-200';
};

export function EntityBrowser({
  data,
  onEntityClick,
  onLoadMore,
  onFilterChange,
  groupId,
}: EntityBrowserProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState('all');
  const [filteredEntities, setFilteredEntities] = useState<Entity[]>(data.entities);
  const [entityTypes, setEntityTypes] = useState<Array<{value: string; label: string}>>([
    { value: 'all', label: 'All Types' }
  ]);

  // Fetch entity types when component mounts or groupId changes
  useEffect(() => {
    async function fetchEntityTypes() {
      try {
        const response = await api.getEntityTypes(groupId);
        const types = [
          { value: 'all', label: 'All Types' },
          ...response.entity_types.map(type => ({
            value: type,
            label: type.split('_').map(word =>
              word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
            ).join(' ')
          }))
        ];
        setEntityTypes(types);
      } catch (error) {
        console.error('Failed to fetch entity types:', error);
      }
    }

    if (groupId) {
      fetchEntityTypes();
    }
  }, [groupId]);

  useEffect(() => {
    let filtered = data.entities;

    // Filter by search query
    if (searchQuery) {
      filtered = filtered.filter((entity) =>
        entity.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        entity.summary.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    setFilteredEntities(filtered);
  }, [searchQuery, data.entities]);

  const handleTypeChange = (value: string) => {
    setSelectedType(value);
    if (onFilterChange) {
      onFilterChange(value === 'all' ? undefined : value);
    }
  };

  const currentPage = Math.floor(data.offset / data.limit) + 1;
  const totalPages = Math.ceil(data.total / data.limit);
  const canGoBack = data.offset > 0;
  const canGoForward = data.offset + data.limit < data.total;

  return (
    <div className="space-y-4">
      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Entity Browser</CardTitle>
          <CardDescription>
            Browse and filter entities in the knowledge graph
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                placeholder="Search entities..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={selectedType} onValueChange={handleTypeChange}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="Select type" />
              </SelectTrigger>
              <SelectContent>
                {entityTypes.map((type) => (
                  <SelectItem key={type.value} value={type.value}>
                    {type.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="text-sm text-gray-600">
            Showing {filteredEntities.length} of {data.total} entities
          </div>
        </CardContent>
      </Card>

      {/* Entity List */}
      <div className="grid gap-3">
        {filteredEntities.map((entity) => (
          <Card
            key={entity.uuid}
            className="cursor-pointer hover:shadow-md transition-shadow"
            onClick={() => onEntityClick?.(entity)}
          >
            <CardContent className="p-4">
              <div className="flex items-start justify-between">
                <div className="flex-1 space-y-2">
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-lg">{entity.name}</h3>
                    <Badge
                      variant="outline"
                      className={getEntityColor(entity.entity_type)}
                    >
                      {entity.entity_type}
                    </Badge>
                  </div>
                  <p className="text-sm text-gray-600 line-clamp-2">
                    {entity.summary}
                  </p>
                  <div className="flex items-center gap-4 text-xs text-gray-500">
                    <span>Mentions: {entity.mentions}</span>
                    <span>Score: {entity.score.toFixed(3)}</span>
                    <span className="font-mono">ID: {entity.uuid.slice(0, 8)}...</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Pagination */}
      {data.total > data.limit && (
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="text-sm text-gray-600">
                Page {currentPage} of {totalPages}
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onLoadMore?.(data.offset - data.limit)}
                  disabled={!canGoBack}
                >
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onLoadMore?.(data.offset + data.limit)}
                  disabled={!canGoForward}
                >
                  Next
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {filteredEntities.length === 0 && (
        <Card>
          <CardContent className="p-8 text-center text-gray-500">
            No entities found matching your criteria
          </CardContent>
        </Card>
      )}
    </div>
  );
}
