"""
Stage 1: Multi-round node extraction.

Extracts potential graph nodes from text through multiple refinement rounds.
"""

import logging
from typing import List, Optional

from .models import PotentialNodes
from .utils import load_prompt, render_template

logger = logging.getLogger(__name__)


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
    system_template = load_prompt("extract_nodes_system.txt")
    input_template = load_prompt("extract_nodes_input.txt")

    # Render system prompt with user_id
    system_prompt = render_template(system_template, user_id=user_id)

    accumulated_nodes: List[str] = []

    for round_num in range(n_rounds):
        logger.debug(f"Node extraction round {round_num + 1}/{n_rounds}")

        # Render input prompt
        existing_nodes_str = ", ".join(accumulated_nodes) if accumulated_nodes else None
        input_prompt = render_template(
            input_template,
            text=text,
            existing_nodes=existing_nodes_str,
            context=context,
        )

        # Call LLM with structured output
        response: PotentialNodes = await llm_client.acreate_structured_output(
            text_input=input_prompt,
            system_prompt=system_prompt,
            response_model=PotentialNodes,
            temperature=0.0,
        )

        # Merge new nodes with existing (deduplicate)
        for node in response.nodes:
            node_normalized = node.strip()
            if node_normalized and node_normalized not in accumulated_nodes:
                accumulated_nodes.append(node_normalized)

        logger.debug(f"Round {round_num + 1}: {len(response.nodes)} nodes, total: {len(accumulated_nodes)}")

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
    system_template = load_prompt("extract_nodes_system.txt")
    input_template = load_prompt("extract_nodes_input.txt")

    # Render system prompt with user_id
    system_prompt = render_template(system_template, user_id=user_id)

    accumulated_nodes: List[str] = []

    for round_num in range(n_rounds):
        logger.debug(f"Node extraction round {round_num + 1}/{n_rounds}")

        # Render input prompt
        existing_nodes_str = ", ".join(accumulated_nodes) if accumulated_nodes else None
        input_prompt = render_template(
            input_template,
            text=text,
            existing_nodes=existing_nodes_str,
            context=context,
        )

        # Call LLM with structured output
        response: PotentialNodes = llm_client.create_structured_output(
            text_input=input_prompt,
            system_prompt=system_prompt,
            response_model=PotentialNodes,
            temperature=0.0,
        )

        # Merge new nodes with existing (deduplicate)
        for node in response.nodes:
            node_normalized = node.strip()
            if node_normalized and node_normalized not in accumulated_nodes:
                accumulated_nodes.append(node_normalized)

        logger.debug(f"Round {round_num + 1}: {len(response.nodes)} nodes, total: {len(accumulated_nodes)}")

    logger.info(f"Extracted {len(accumulated_nodes)} unique nodes after {n_rounds} rounds")
    return accumulated_nodes
