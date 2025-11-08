"use client"

import React, { useState, useEffect } from 'react';
import { Entity, Edge } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { X, ArrowRight, ArrowLeft } from 'lucide-react';

interface EntityDetailPanelProps {
  entity: Entity | null;
  relationships: Edge[];
  onClose?: () => void;
  onEntityClick?: (entityName: string) => void;
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

export function EntityDetailPanel({
  entity,
  relationships,
  onClose,
  onEntityClick,
}: EntityDetailPanelProps) {
  const [groupedRelationships, setGroupedRelationships] = useState<{
    outgoing: Edge[];
    incoming: Edge[];
  }>({ outgoing: [], incoming: [] });

  useEffect(() => {
    if (!entity || !relationships) {
      setGroupedRelationships({ outgoing: [], incoming: [] });
      return;
    }

    const outgoing = relationships.filter(
      (rel) => rel.source_name === entity.name
    );
    const incoming = relationships.filter(
      (rel) => rel.target_name === entity.name
    );

    setGroupedRelationships({ outgoing, incoming });
  }, [entity, relationships]);

  if (!entity) {
    return (
      <Card className="w-full">
        <CardContent className="p-8 text-center text-gray-500">
          Select an entity to view details
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="space-y-2 flex-1">
            <CardTitle className="text-2xl">{entity.name}</CardTitle>
            <CardDescription>
              <Badge
                variant="outline"
                className={getEntityColor(entity.entity_type)}
              >
                {entity.entity_type}
              </Badge>
            </CardDescription>
          </div>
          {onClose && (
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Summary */}
        <div>
          <h3 className="font-semibold text-sm text-gray-600 mb-2">Summary</h3>
          <p className="text-sm">{entity.summary}</p>
        </div>

        <Separator />

        {/* Metadata */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <h3 className="font-semibold text-sm text-gray-600 mb-1">Mentions</h3>
            <p className="text-2xl font-bold">{entity.mentions}</p>
          </div>
          <div>
            <h3 className="font-semibold text-sm text-gray-600 mb-1">Score</h3>
            <p className="text-2xl font-bold">{entity.score.toFixed(3)}</p>
          </div>
        </div>

        <div>
          <h3 className="font-semibold text-sm text-gray-600 mb-1">UUID</h3>
          <p className="text-xs font-mono bg-gray-100 p-2 rounded break-all">
            {entity.uuid}
          </p>
        </div>

        <Separator />

        {/* Outgoing Relationships */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <h3 className="font-semibold text-sm text-gray-600">
              Outgoing Relationships
            </h3>
            <Badge variant="secondary">{groupedRelationships.outgoing.length}</Badge>
          </div>

          {groupedRelationships.outgoing.length > 0 ? (
            <div className="space-y-2">
              {groupedRelationships.outgoing.map((rel) => (
                <Card key={rel.uuid} className="bg-gray-50">
                  <CardContent className="p-3">
                    <div className="flex items-start gap-2">
                      <ArrowRight className="h-4 w-4 mt-1 text-gray-400 flex-shrink-0" />
                      <div className="flex-1 space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge variant="outline" className="text-xs">
                            {rel.relation_type}
                          </Badge>
                          <button
                            className="text-sm font-medium text-blue-600 hover:underline"
                            onClick={() => onEntityClick?.(rel.target_name)}
                          >
                            {rel.target_name}
                          </button>
                        </div>
                        <p className="text-xs text-gray-600">{rel.fact}</p>
                        <div className="text-xs text-gray-500">
                          Mentions: {rel.mentions} • Score: {rel.score.toFixed(3)}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500 italic">
              No outgoing relationships found
            </p>
          )}
        </div>

        <Separator />

        {/* Incoming Relationships */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <h3 className="font-semibold text-sm text-gray-600">
              Incoming Relationships
            </h3>
            <Badge variant="secondary">{groupedRelationships.incoming.length}</Badge>
          </div>

          {groupedRelationships.incoming.length > 0 ? (
            <div className="space-y-2">
              {groupedRelationships.incoming.map((rel) => (
                <Card key={rel.uuid} className="bg-gray-50">
                  <CardContent className="p-3">
                    <div className="flex items-start gap-2">
                      <ArrowLeft className="h-4 w-4 mt-1 text-gray-400 flex-shrink-0" />
                      <div className="flex-1 space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <button
                            className="text-sm font-medium text-blue-600 hover:underline"
                            onClick={() => onEntityClick?.(rel.source_name)}
                          >
                            {rel.source_name}
                          </button>
                          <Badge variant="outline" className="text-xs">
                            {rel.relation_type}
                          </Badge>
                        </div>
                        <p className="text-xs text-gray-600">{rel.fact}</p>
                        <div className="text-xs text-gray-500">
                          Mentions: {rel.mentions} • Score: {rel.score.toFixed(3)}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500 italic">
              No incoming relationships found
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
