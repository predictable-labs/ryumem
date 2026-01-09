"""
Stage 1: Multi-round node extraction.

Extracts potential graph nodes from text through multiple refinement rounds.
"""

import logging
from pathlib import Path
from typing import List, Optional, Union

from .models import PotentialNodes

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
    system_template = _load_prompt("extract_nodes_system.txt")
    input_template = _load_prompt("extract_nodes_input.txt")

    # Render system prompt with user_id
    system_prompt = _render_template(system_template, user_id=user_id)

    accumulated_nodes: List[str] = []

    for round_num in range(n_rounds):
        logger.debug(f"Node extraction round {round_num + 1}/{n_rounds}")

        # Render input prompt
        existing_nodes_str = ", ".join(accumulated_nodes) if accumulated_nodes else None
        input_prompt = _render_template(
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
    system_template = _load_prompt("extract_nodes_system.txt")
    input_template = _load_prompt("extract_nodes_input.txt")

    # Render system prompt with user_id
    system_prompt = _render_template(system_template, user_id=user_id)

    accumulated_nodes: List[str] = []

    for round_num in range(n_rounds):
        logger.debug(f"Node extraction round {round_num + 1}/{n_rounds}")

        # Render input prompt
        existing_nodes_str = ", ".join(accumulated_nodes) if accumulated_nodes else None
        input_prompt = _render_template(
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
