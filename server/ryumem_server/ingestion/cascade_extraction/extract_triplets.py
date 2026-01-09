"""
Stage 3: Multi-round triplet extraction.

Extracts complete knowledge graph with nodes and edges through multiple rounds.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Set

from .models import KnowledgeGraph, ExtractedNode, ExtractedEdge

logger = logging.getLogger(__name__)

# Load prompt templates
PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(filename: str) -> str:
    """Load a prompt template from file."""
    with open(PROMPTS_DIR / filename, "r") as f:
        return f.read()


def _render_template(template: str, **kwargs) -> str:
    """Simple Jinja2-style template rendering."""
    result = template
    for key, value in kwargs.items():
        # Handle simple variable replacement
        result = result.replace("{{ " + key + " }}", str(value) if value else "")
        result = result.replace("{{" + key + "}}", str(value) if value else "")

    # Handle conditional blocks {% if var %}...{% endif %}
    import re
    for key, value in kwargs.items():
        if_pattern = rf'{{% if {key} %}}(.*?){{% endif %}}'
        if value:
            # Keep the content inside the if block
            result = re.sub(if_pattern, r'\1', result, flags=re.DOTALL)
        else:
            # Remove the entire if block
            result = re.sub(if_pattern, '', result, flags=re.DOTALL)

    return result.strip()


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
        if edge.source_node_id in valid_node_ids
        and edge.target_node_id in valid_node_ids
    ]

    if len(valid_edges) < len(graph.edges):
        removed = len(graph.edges) - len(valid_edges)
        logger.warning(f"Removed {removed} edges with invalid node references")

    return KnowledgeGraph(nodes=graph.nodes, edges=valid_edges)


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
    system_template = _load_prompt("extract_triplets_system.txt")
    input_template = _load_prompt("extract_triplets_input.txt")

    # Render system prompt with user_id
    system_prompt = _render_template(system_template, user_id=user_id)

    accumulated_graph = KnowledgeGraph(nodes=[], edges=[])

    for round_num in range(n_rounds):
        logger.debug(f"Triplet extraction round {round_num + 1}/{n_rounds}")

        # Prepare existing graph summary for prompt
        existing_graph_str = None
        if accumulated_graph.nodes or accumulated_graph.edges:
            existing_graph_str = {
                "nodes": [f"{n.id} ({n.type}): {n.name}" for n in accumulated_graph.nodes],
                "edges": [f"{e.source_node_id} --{e.relationship_name}--> {e.target_node_id}" for e in accumulated_graph.edges]
            }

        # Render input prompt
        input_prompt = _render_template(
            input_template,
            text=text,
            nodes=", ".join(nodes),
            relationships=", ".join(relationships),
            existing_graph=existing_graph_str,
            context=context,
        )

        # Call LLM with structured output
        response: KnowledgeGraph = await llm_client.acreate_structured_output(
            text_input=input_prompt,
            system_prompt=system_prompt,
            response_model=KnowledgeGraph,
            temperature=0.0,
        )

        # Merge with accumulated graph
        accumulated_graph = _merge_graphs(accumulated_graph, response)

        logger.debug(
            f"Round {round_num + 1}: {len(response.nodes)} nodes, {len(response.edges)} edges, "
            f"total: {len(accumulated_graph.nodes)} nodes, {len(accumulated_graph.edges)} edges"
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
    system_template = _load_prompt("extract_triplets_system.txt")
    input_template = _load_prompt("extract_triplets_input.txt")

    # Render system prompt with user_id
    system_prompt = _render_template(system_template, user_id=user_id)

    accumulated_graph = KnowledgeGraph(nodes=[], edges=[])

    for round_num in range(n_rounds):
        logger.debug(f"Triplet extraction round {round_num + 1}/{n_rounds}")

        # Prepare existing graph summary for prompt
        existing_graph_str = None
        if accumulated_graph.nodes or accumulated_graph.edges:
            existing_graph_str = {
                "nodes": [f"{n.id} ({n.type}): {n.name}" for n in accumulated_graph.nodes],
                "edges": [f"{e.source_node_id} --{e.relationship_name}--> {e.target_node_id}" for e in accumulated_graph.edges]
            }

        # Render input prompt
        input_prompt = _render_template(
            input_template,
            text=text,
            nodes=", ".join(nodes),
            relationships=", ".join(relationships),
            existing_graph=existing_graph_str,
            context=context,
        )

        # Call LLM with structured output
        response: KnowledgeGraph = llm_client.create_structured_output(
            text_input=input_prompt,
            system_prompt=system_prompt,
            response_model=KnowledgeGraph,
            temperature=0.0,
        )

        # Merge with accumulated graph
        accumulated_graph = _merge_graphs(accumulated_graph, response)

        logger.debug(
            f"Round {round_num + 1}: {len(response.nodes)} nodes, {len(response.edges)} edges, "
            f"total: {len(accumulated_graph.nodes)} nodes, {len(accumulated_graph.edges)} edges"
        )

    # Validate final graph
    final_graph = _validate_graph(accumulated_graph)

    logger.info(
        f"Extracted knowledge graph with {len(final_graph.nodes)} nodes "
        f"and {len(final_graph.edges)} edges after {n_rounds} rounds"
    )
    return final_graph
