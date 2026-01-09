"""
Pydantic models for cascade extraction pipeline.

These models define the structured output formats for each stage
of the multi-round cascade extraction process.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# Stage 1: Node Extraction Models

class PotentialNodes(BaseModel):
    """Response model for Stage 1 - extracting potential node names."""

    nodes: List[str] = Field(
        default_factory=list,
        description="List of potential node names extracted from the text"
    )


# Stage 2: Relationship Extraction Models

class NodesAndRelationships(BaseModel):
    """Response model for Stage 2 - extracting nodes and relationship names."""

    nodes: List[str] = Field(
        default_factory=list,
        description="Refined list of node names"
    )
    relationships: List[str] = Field(
        default_factory=list,
        description="List of relationship type names (e.g., WORKS_AT, KNOWS)"
    )


# Stage 3: Triplet Extraction Models

class ExtractedNode(BaseModel):
    """A fully extracted node with all attributes."""

    id: str = Field(
        description="Unique identifier for the node (lowercase, underscores)"
    )
    name: str = Field(
        description="Human-readable name of the node"
    )
    type: str = Field(
        description="Entity type (e.g., PERSON, ORGANIZATION, CONCEPT)"
    )
    description: Optional[str] = Field(
        default=None,
        description="Brief description of the node based on context"
    )


class ExtractedEdge(BaseModel):
    """A fully extracted edge (relationship) between nodes."""

    source_node_id: str = Field(
        description="ID of the source node"
    )
    target_node_id: str = Field(
        description="ID of the target node"
    )
    relationship_name: str = Field(
        description="Type of relationship (e.g., WORKS_AT, KNOWS)"
    )
    fact: Optional[str] = Field(
        default=None,
        description="Natural language description of the relationship"
    )


class KnowledgeGraph(BaseModel):
    """Complete knowledge graph with nodes and edges."""

    nodes: List[ExtractedNode] = Field(
        default_factory=list,
        description="List of extracted nodes"
    )
    edges: List[ExtractedEdge] = Field(
        default_factory=list,
        description="List of extracted edges"
    )
