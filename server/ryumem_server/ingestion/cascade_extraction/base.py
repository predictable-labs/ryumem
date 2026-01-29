"""
Base framework for multi-round cascade extraction.

Provides generic multi-round extraction engine to eliminate duplication
across nodes, relationships, and triplets extraction stages.
"""

import logging
from typing import Any, Callable, Optional, TypeVar

from pydantic import BaseModel

from .utils import load_prompt, render_template

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


async def multi_round_extraction(
    llm_client,
    text: str,
    user_id: str,
    system_prompt_file: str,
    input_prompt_file: str,
    response_model: type[T],
    n_rounds: int,
    context: Optional[str],
    prepare_input_kwargs: Callable[[Any, int], dict],
    accumulate_results: Callable[[Any, T], Any],
    initial_state: Any,
    stage_name: str = "Extraction",
) -> Any:
    """
    Generic multi-round extraction with template rendering and accumulation.

    Args:
        llm_client: LLM client with acreate_structured_output method
        text: Input text to process
        user_id: User ID for self-reference resolution
        system_prompt_file: Filename of system prompt template
        input_prompt_file: Filename of input prompt template
        response_model: Pydantic model for structured output
        n_rounds: Number of extraction rounds
        context: Optional conversation context
        prepare_input_kwargs: Function to prepare input template kwargs per round
            Signature: (accumulated_state, round_num) -> dict of template kwargs
        accumulate_results: Function to merge round results into accumulated state
            Signature: (accumulated_state, round_response) -> new_accumulated_state
        initial_state: Initial accumulated state (e.g., [], {}, KnowledgeGraph())
        stage_name: Name of extraction stage for logging (e.g., "Node extraction")

    Returns:
        Final accumulated state after all rounds
    """
    # Load and render system prompt (static across all rounds)
    system_template = load_prompt(system_prompt_file)
    system_prompt = render_template(system_template, user_id=user_id)

    # Load input template (will be rendered per-round)
    input_template = load_prompt(input_prompt_file)

    accumulated_state = initial_state

    for round_num in range(n_rounds):
        logger.debug(f"{stage_name} round {round_num + 1}/{n_rounds}")

        # Prepare input template kwargs for this round
        input_kwargs = prepare_input_kwargs(accumulated_state, round_num)

        # Add text and context to kwargs
        input_kwargs['text'] = text
        input_kwargs['context'] = context

        # Render input prompt with accumulated state
        input_prompt = render_template(input_template, **input_kwargs)

        # Call LLM with structured output
        response: T = await llm_client.acreate_structured_output(
            text_input=input_prompt,
            system_prompt=system_prompt,
            response_model=response_model,
            temperature=0.0,
        )

        # Accumulate results
        accumulated_state = accumulate_results(accumulated_state, response)

        logger.debug(f"{stage_name} round {round_num + 1} completed")

    logger.info(f"{stage_name} completed after {n_rounds} rounds")
    return accumulated_state


def multi_round_extraction_sync(
    llm_client,
    text: str,
    user_id: str,
    system_prompt_file: str,
    input_prompt_file: str,
    response_model: type[T],
    n_rounds: int,
    context: Optional[str],
    prepare_input_kwargs: Callable[[Any, int], dict],
    accumulate_results: Callable[[Any, T], Any],
    initial_state: Any,
    stage_name: str = "Extraction",
) -> Any:
    """
    Synchronous version of multi_round_extraction.

    Args:
        llm_client: LLM client with create_structured_output method
        text: Input text to process
        user_id: User ID for self-reference resolution
        system_prompt_file: Filename of system prompt template
        input_prompt_file: Filename of input prompt template
        response_model: Pydantic model for structured output
        n_rounds: Number of extraction rounds
        context: Optional conversation context
        prepare_input_kwargs: Function to prepare input template kwargs per round
            Signature: (accumulated_state, round_num) -> dict of template kwargs
        accumulate_results: Function to merge round results into accumulated state
            Signature: (accumulated_state, round_response) -> new_accumulated_state
        initial_state: Initial accumulated state (e.g., [], {}, KnowledgeGraph())
        stage_name: Name of extraction stage for logging (e.g., "Node extraction")

    Returns:
        Final accumulated state after all rounds
    """
    # Load and render system prompt (static across all rounds)
    system_template = load_prompt(system_prompt_file)
    system_prompt = render_template(system_template, user_id=user_id)

    # Load input template (will be rendered per-round)
    input_template = load_prompt(input_prompt_file)

    accumulated_state = initial_state

    for round_num in range(n_rounds):
        logger.debug(f"{stage_name} round {round_num + 1}/{n_rounds}")

        # Prepare input template kwargs for this round
        input_kwargs = prepare_input_kwargs(accumulated_state, round_num)

        # Add text and context to kwargs
        input_kwargs['text'] = text
        input_kwargs['context'] = context

        # Render input prompt with accumulated state
        input_prompt = render_template(input_template, **input_kwargs)

        # Call LLM with structured output
        response: T = llm_client.create_structured_output(
            text_input=input_prompt,
            system_prompt=system_prompt,
            response_model=response_model,
            temperature=0.0,
        )

        # Accumulate results
        accumulated_state = accumulate_results(accumulated_state, response)

        logger.debug(f"{stage_name} round {round_num + 1} completed")

    logger.info(f"{stage_name} completed after {n_rounds} rounds")
    return accumulated_state
