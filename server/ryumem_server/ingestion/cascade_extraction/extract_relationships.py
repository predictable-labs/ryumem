"""
Stage 2: Multi-round relationship extraction.

Extracts relationship types and refines nodes through multiple rounds.
"""

import logging
from pathlib import Path
from typing import List, Optional, Tuple

from .models import NodesAndRelationships

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
    system_template = _load_prompt("extract_relationships_system.txt")
    input_template = _load_prompt("extract_relationships_input.txt")

    # Render system prompt with user_id
    system_prompt = _render_template(system_template, user_id=user_id)

    current_nodes = list(nodes)
    accumulated_relationships: List[str] = []

    for round_num in range(n_rounds):
        logger.debug(f"Relationship extraction round {round_num + 1}/{n_rounds}")

        # Render input prompt
        nodes_str = ", ".join(current_nodes)
        existing_rels_str = ", ".join(accumulated_relationships) if accumulated_relationships else None

        input_prompt = _render_template(
            input_template,
            text=text,
            nodes=nodes_str,
            existing_relationships=existing_rels_str,
            context=context,
        )

        # Call LLM with structured output
        response: NodesAndRelationships = await llm_client.acreate_structured_output(
            text_input=input_prompt,
            system_prompt=system_prompt,
            response_model=NodesAndRelationships,
            temperature=0.0,
        )

        # Update nodes with refined list
        if response.nodes:
            current_nodes = [n.strip() for n in response.nodes if n.strip()]

        # Merge new relationships with existing (deduplicate)
        for rel in response.relationships:
            rel_normalized = rel.strip().upper()
            if rel_normalized and rel_normalized not in accumulated_relationships:
                accumulated_relationships.append(rel_normalized)

        logger.debug(
            f"Round {round_num + 1}: {len(response.relationships)} relationships, "
            f"total: {len(accumulated_relationships)}, nodes: {len(current_nodes)}"
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
    system_template = _load_prompt("extract_relationships_system.txt")
    input_template = _load_prompt("extract_relationships_input.txt")

    # Render system prompt with user_id
    system_prompt = _render_template(system_template, user_id=user_id)

    current_nodes = list(nodes)
    accumulated_relationships: List[str] = []

    for round_num in range(n_rounds):
        logger.debug(f"Relationship extraction round {round_num + 1}/{n_rounds}")

        # Render input prompt
        nodes_str = ", ".join(current_nodes)
        existing_rels_str = ", ".join(accumulated_relationships) if accumulated_relationships else None

        input_prompt = _render_template(
            input_template,
            text=text,
            nodes=nodes_str,
            existing_relationships=existing_rels_str,
            context=context,
        )

        # Call LLM with structured output
        response: NodesAndRelationships = llm_client.create_structured_output(
            text_input=input_prompt,
            system_prompt=system_prompt,
            response_model=NodesAndRelationships,
            temperature=0.0,
        )

        # Update nodes with refined list
        if response.nodes:
            current_nodes = [n.strip() for n in response.nodes if n.strip()]

        # Merge new relationships with existing (deduplicate)
        for rel in response.relationships:
            rel_normalized = rel.strip().upper()
            if rel_normalized and rel_normalized not in accumulated_relationships:
                accumulated_relationships.append(rel_normalized)

        logger.debug(
            f"Round {round_num + 1}: {len(response.relationships)} relationships, "
            f"total: {len(accumulated_relationships)}, nodes: {len(current_nodes)}"
        )

    logger.info(
        f"Extracted {len(accumulated_relationships)} relationship types "
        f"and refined to {len(current_nodes)} nodes after {n_rounds} rounds"
    )
    return current_nodes, accumulated_relationships
