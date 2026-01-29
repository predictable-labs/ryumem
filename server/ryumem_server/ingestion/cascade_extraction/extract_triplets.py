"""
Stage 3: Multi-round triplet extraction.

Extracts complete knowledge graph with nodes and edges through multiple rounds.
"""

import logging
from typing import Dict, List, Optional, Set

from .base import multi_round_extraction, multi_round_extraction_sync
from .models import KnowledgeGraph, ExtractedNode, ExtractedEdge

logger = logging.getLogger(__name__)


def _merge_graphs(existing: KnowledgeGraph, new: KnowledgeGraph) -> KnowledgeGraph:
    """
    Merge two knowledge graphs, deduplicating nodes and edges.

    Args:
        existing: Existing knowledge graph
        new: New knowledge graph to merge

    Returns:
        Merged knowledge graph
    """
    # Track existing node IDs
    node_ids: Set[str] = {node.id for node in existing.nodes}
    merged_nodes: List[ExtractedNode] = list(existing.nodes)

    # Add new nodes
    for node in new.nodes:
        if node.id not in node_ids:
            merged_nodes.append(node)
            node_ids.add(node.id)

    # Track existing edges by (source, target, relationship)
    edge_keys: Set[tuple] = {
        (edge.source_node_id, edge.target_node_id, edge.relationship_name)
        for edge in existing.edges
    }
    merged_edges: List[ExtractedEdge] = list(existing.edges)

    # Add new edges
    for edge in new.edges:
        key = (edge.source_node_id, edge.target_node_id, edge.relationship_name)
        if key not in edge_keys:
            merged_edges.append(edge)
            edge_keys.add(key)

    return KnowledgeGraph(nodes=merged_nodes, edges=merged_edges)


def _validate_graph(graph: KnowledgeGraph) -> KnowledgeGraph:
    """
    Validate and clean a knowledge graph.

    Removes edges that reference non-existent nodes.

    Args:
        graph: Knowledge graph to validate

    Returns:
        Validated knowledge graph
    """
    valid_node_ids = {node.id for node in graph.nodes}

    valid_edges = [
        edge for edge in graph.edges
        if edge.source_node_id and edge.target_node_id
        and edge.source_node_id in valid_node_ids
        and edge.target_node_id in valid_node_ids
    ]

    if len(valid_edges) < len(graph.edges):
        removed = len(graph.edges) - len(valid_edges)
        logger.warning(f"Removed {removed} edges with invalid node references")

    return KnowledgeGraph(nodes=graph.nodes, edges=valid_edges)


def _prepare_triplets_input_kwargs(accumulated_graph: KnowledgeGraph, round_num: int) -> dict:
    """Prepare input template kwargs for triplet extraction round."""
    # Prepare existing graph summary for prompt
    existing_graph_str = None
    if accumulated_graph.nodes or accumulated_graph.edges:
        existing_graph_str = {
            "nodes": [f"{n.id} ({n.type}): {n.name}" for n in accumulated_graph.nodes],
            "edges": [f"{e.source_node_id} --{e.relationship_name}--> {e.target_node_id}" for e in accumulated_graph.edges]
        }

    # Note: nodes and relationships will be passed as closure from the main function
    # We can't access them here, so we'll use a different approach
    return {"existing_graph": existing_graph_str}


def _accumulate_triplets(accumulated_graph: KnowledgeGraph, response: KnowledgeGraph) -> KnowledgeGraph:
    """Accumulate triplets from round response, merging graphs."""
    merged_graph = _merge_graphs(accumulated_graph, response)

    logger.debug(
        f"Round complete: {len(response.nodes)} new nodes, {len(response.edges)} new edges, "
        f"total: {len(merged_graph.nodes)} nodes, {len(merged_graph.edges)} edges"
    )

    return merged_graph


async def extract_triplets(
    text: str,
    nodes: List[str],
    relationships: List[str],
    user_id: str,
    llm_client,
    n_rounds: int = 2,
    context: Optional[str] = None,
) -> KnowledgeGraph:
    """
    Extract complete knowledge graph through multiple rounds.

    Each round refines and adds to the graph.

    Args:
        text: Input text to analyze
        nodes: List of node names from Stage 2
        relationships: List of relationship type names from Stage 2
        user_id: User ID for context
        llm_client: LLM client with acreate_structured_output method
        n_rounds: Number of extraction rounds (default: 2)
        context: Optional conversation context

    Returns:
        Complete KnowledgeGraph with nodes and edges
    """
    # Create a closure to include nodes and relationships in the kwargs
    nodes_str = ", ".join(nodes)
    relationships_str = ", ".join(relationships)

    def prepare_input_kwargs_with_context(accumulated_graph: KnowledgeGraph, round_num: int) -> dict:
        kwargs = _prepare_triplets_input_kwargs(accumulated_graph, round_num)
        kwargs["nodes"] = nodes_str
        kwargs["relationships"] = relationships_str
        return kwargs

    accumulated_graph = await multi_round_extraction(
        llm_client=llm_client,
        text=text,
        user_id=user_id,
        system_prompt_file="extract_triplets_system.txt",
        input_prompt_file="extract_triplets_input.txt",
        response_model=KnowledgeGraph,
        n_rounds=n_rounds,
        context=context,
        prepare_input_kwargs=prepare_input_kwargs_with_context,
        accumulate_results=_accumulate_triplets,
        initial_state=KnowledgeGraph(nodes=[], edges=[]),
        stage_name="Triplet extraction",
    )

    # Validate final graph
    final_graph = _validate_graph(accumulated_graph)

    logger.info(
        f"Extracted knowledge graph with {len(final_graph.nodes)} nodes "
        f"and {len(final_graph.edges)} edges after {n_rounds} rounds"
    )
    return final_graph


def extract_triplets_sync(
    text: str,
    nodes: List[str],
    relationships: List[str],
    user_id: str,
    llm_client,
    n_rounds: int = 2,
    context: Optional[str] = None,
) -> KnowledgeGraph:
    """
    Synchronous version of extract_triplets.

    Args:
        text: Input text to analyze
        nodes: List of node names from Stage 2
        relationships: List of relationship type names from Stage 2
        user_id: User ID for context
        llm_client: LLM client with create_structured_output method
        n_rounds: Number of extraction rounds (default: 2)
        context: Optional conversation context

    Returns:
        Complete KnowledgeGraph with nodes and edges
    """
    # Create a closure to include nodes and relationships in the kwargs
    nodes_str = ", ".join(nodes)
    relationships_str = ", ".join(relationships)

    def prepare_input_kwargs_with_context(accumulated_graph: KnowledgeGraph, round_num: int) -> dict:
        kwargs = _prepare_triplets_input_kwargs(accumulated_graph, round_num)
        kwargs["nodes"] = nodes_str
        kwargs["relationships"] = relationships_str
        return kwargs

    accumulated_graph = multi_round_extraction_sync(
        llm_client=llm_client,
        text=text,
        user_id=user_id,
        system_prompt_file="extract_triplets_system.txt",
        input_prompt_file="extract_triplets_input.txt",
        response_model=KnowledgeGraph,
        n_rounds=n_rounds,
        context=context,
        prepare_input_kwargs=prepare_input_kwargs_with_context,
        accumulate_results=_accumulate_triplets,
        initial_state=KnowledgeGraph(nodes=[], edges=[]),
        stage_name="Triplet extraction",
    )

    # Validate final graph
    final_graph = _validate_graph(accumulated_graph)

    logger.info(
        f"Extracted knowledge graph with {len(final_graph.nodes)} nodes "
        f"and {len(final_graph.edges)} edges after {n_rounds} rounds"
    )
    return final_graph
