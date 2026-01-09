"""
Cascade Extraction Module

Multi-round cascade extraction pipeline for knowledge graph construction.

The pipeline has three stages:
1. Node Extraction - Extract potential entity nodes from text
2. Relationship Extraction - Identify relationship types and refine nodes
3. Triplet Extraction - Build complete knowledge graph with nodes and edges

Each stage runs multiple rounds for improved extraction quality.
"""

from .cascade_extractor import CascadeExtractor
from .models import (
    KnowledgeGraph,
    ExtractedNode,
    ExtractedEdge,
    PotentialNodes,
    NodesAndRelationships,
)
from .extract_nodes import extract_nodes, extract_nodes_sync
from .extract_relationships import extract_relationships, extract_relationships_sync
from .extract_triplets import extract_triplets, extract_triplets_sync

__all__ = [
    # Main orchestrator
    "CascadeExtractor",
    # Models
    "KnowledgeGraph",
    "ExtractedNode",
    "ExtractedEdge",
    "PotentialNodes",
    "NodesAndRelationships",
    # Stage functions (async)
    "extract_nodes",
    "extract_relationships",
    "extract_triplets",
    # Stage functions (sync)
    "extract_nodes_sync",
    "extract_relationships_sync",
    "extract_triplets_sync",
]
