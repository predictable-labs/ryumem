"""
Stage 2: Multi-round relationship extraction.

Extracts relationship types and refines nodes through multiple rounds.
"""

import logging
from typing import List, Optional, Tuple

from .base import multi_round_extraction, multi_round_extraction_sync
from .models import NodesAndRelationships

logger = logging.getLogger(__name__)


def _prepare_relationships_input_kwargs(
    state: Tuple[List[str], List[str]], round_num: int
) -> dict:
    """Prepare input template kwargs for relationship extraction round."""
    current_nodes, accumulated_relationships = state
    nodes_str = ", ".join(current_nodes)
    existing_rels_str = ", ".join(accumulated_relationships) if accumulated_relationships else None
    return {"nodes": nodes_str, "existing_relationships": existing_rels_str}


def _accumulate_relationships(
    state: Tuple[List[str], List[str]], response: NodesAndRelationships
) -> Tuple[List[str], List[str]]:
    """Accumulate relationships and refine nodes from round response."""
    current_nodes, accumulated_relationships = state

    # Update nodes with refined list
    if response.nodes:
        current_nodes = [n.strip() for n in response.nodes if n.strip()]

    # Merge new relationships with existing (deduplicate)
    for rel in response.relationships:
        rel_normalized = rel.strip().upper()
        if rel_normalized and rel_normalized not in accumulated_relationships:
            accumulated_relationships.append(rel_normalized)

    logger.debug(
        f"Round complete: {len(response.relationships)} new relationships, "
        f"total: {len(accumulated_relationships)}, nodes: {len(current_nodes)}"
    )

    return current_nodes, accumulated_relationships


async def extract_relationships(
    text: str,
    nodes: List[str],
    user_id: str,
    llm_client,
    n_rounds: int = 2,
    context: Optional[str] = None,
) -> Tuple[List[str], List[str]]:
    """
    Extract relationship types and refine nodes through multiple rounds.

    Each round builds on the previous, adding missed relationships.

    Args:
        text: Input text to analyze
        nodes: List of potential node names from Stage 1
        user_id: User ID for context
        llm_client: LLM client with acreate_structured_output method
        n_rounds: Number of extraction rounds (default: 2)
        context: Optional conversation context

    Returns:
        Tuple of (refined_nodes, relationship_names)
    """
    current_nodes, accumulated_relationships = await multi_round_extraction(
        llm_client=llm_client,
        text=text,
        user_id=user_id,
        system_prompt_file="extract_relationships_system.txt",
        input_prompt_file="extract_relationships_input.txt",
        response_model=NodesAndRelationships,
        n_rounds=n_rounds,
        context=context,
        prepare_input_kwargs=_prepare_relationships_input_kwargs,
        accumulate_results=_accumulate_relationships,
        initial_state=(list(nodes), []),
        stage_name="Relationship extraction",
    )

    logger.info(
        f"Extracted {len(accumulated_relationships)} relationship types "
        f"and refined to {len(current_nodes)} nodes after {n_rounds} rounds"
    )
    return current_nodes, accumulated_relationships


def extract_relationships_sync(
    text: str,
    nodes: List[str],
    user_id: str,
    llm_client,
    n_rounds: int = 2,
    context: Optional[str] = None,
) -> Tuple[List[str], List[str]]:
    """
    Synchronous version of extract_relationships.

    Args:
        text: Input text to analyze
        nodes: List of potential node names from Stage 1
        user_id: User ID for context
        llm_client: LLM client with create_structured_output method
        n_rounds: Number of extraction rounds (default: 2)
        context: Optional conversation context

    Returns:
        Tuple of (refined_nodes, relationship_names)
    """
    current_nodes, accumulated_relationships = multi_round_extraction_sync(
        llm_client=llm_client,
        text=text,
        user_id=user_id,
        system_prompt_file="extract_relationships_system.txt",
        input_prompt_file="extract_relationships_input.txt",
        response_model=NodesAndRelationships,
        n_rounds=n_rounds,
        context=context,
        prepare_input_kwargs=_prepare_relationships_input_kwargs,
        accumulate_results=_accumulate_relationships,
        initial_state=(list(nodes), []),
        stage_name="Relationship extraction",
    )

    logger.info(
        f"Extracted {len(accumulated_relationships)} relationship types "
        f"and refined to {len(current_nodes)} nodes after {n_rounds} rounds"
    )
    return current_nodes, accumulated_relationships
