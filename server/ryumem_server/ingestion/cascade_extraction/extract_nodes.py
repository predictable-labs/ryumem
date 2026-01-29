"""
Stage 1: Multi-round node extraction.

Extracts potential graph nodes from text through multiple refinement rounds.
"""

import logging
from typing import List, Optional

from .base import multi_round_extraction, multi_round_extraction_sync
from .models import PotentialNodes

logger = logging.getLogger(__name__)


def _prepare_nodes_input_kwargs(accumulated_nodes: List[str], round_num: int) -> dict:
    """Prepare input template kwargs for node extraction round."""
    existing_nodes_str = ", ".join(accumulated_nodes) if accumulated_nodes else None
    return {"existing_nodes": existing_nodes_str}


def _accumulate_nodes(accumulated_nodes: List[str], response: PotentialNodes) -> List[str]:
    """Accumulate nodes from round response, deduplicating."""
    for node in response.nodes:
        node_normalized = node.strip()
        if node_normalized and node_normalized not in accumulated_nodes:
            accumulated_nodes.append(node_normalized)

    logger.debug(f"Round complete: {len(response.nodes)} new nodes, total: {len(accumulated_nodes)}")
    return accumulated_nodes


async def extract_nodes(
    text: str,
    user_id: str,
    llm_client,
    n_rounds: int = 2,
    context: Optional[str] = None,
) -> List[str]:
    """
    Extract potential nodes from text through multiple rounds.

    Each round builds on the previous, adding missed entities.

    Args:
        text: Input text to extract nodes from
        user_id: User ID for self-reference resolution
        llm_client: LLM client with acreate_structured_output method
        n_rounds: Number of extraction rounds (default: 2)
        context: Optional conversation context

    Returns:
        List of unique node name strings
    """
    accumulated_nodes = await multi_round_extraction(
        llm_client=llm_client,
        text=text,
        user_id=user_id,
        system_prompt_file="extract_nodes_system.txt",
        input_prompt_file="extract_nodes_input.txt",
        response_model=PotentialNodes,
        n_rounds=n_rounds,
        context=context,
        prepare_input_kwargs=_prepare_nodes_input_kwargs,
        accumulate_results=_accumulate_nodes,
        initial_state=[],
        stage_name="Node extraction",
    )

    logger.info(f"Extracted {len(accumulated_nodes)} unique nodes after {n_rounds} rounds")
    return accumulated_nodes


def extract_nodes_sync(
    text: str,
    user_id: str,
    llm_client,
    n_rounds: int = 2,
    context: Optional[str] = None,
) -> List[str]:
    """
    Synchronous version of extract_nodes.

    Args:
        text: Input text to extract nodes from
        user_id: User ID for self-reference resolution
        llm_client: LLM client with create_structured_output method
        n_rounds: Number of extraction rounds (default: 2)
        context: Optional conversation context

    Returns:
        List of unique node name strings
    """
    accumulated_nodes = multi_round_extraction_sync(
        llm_client=llm_client,
        text=text,
        user_id=user_id,
        system_prompt_file="extract_nodes_system.txt",
        input_prompt_file="extract_nodes_input.txt",
        response_model=PotentialNodes,
        n_rounds=n_rounds,
        context=context,
        prepare_input_kwargs=_prepare_nodes_input_kwargs,
        accumulate_results=_accumulate_nodes,
        initial_state=[],
        stage_name="Node extraction",
    )

    logger.info(f"Extracted {len(accumulated_nodes)} unique nodes after {n_rounds} rounds")
    return accumulated_nodes
