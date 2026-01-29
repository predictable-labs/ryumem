"""
Token counting utilities for chunking and LLM operations.
Uses tiktoken for accurate OpenAI model token counting.
"""

import logging
from functools import lru_cache
from typing import List, Optional

logger = logging.getLogger(__name__)

# Lazy import tiktoken to handle missing dependency gracefully
_tiktoken = None


def _get_tiktoken():
    """Lazy load tiktoken module."""
    global _tiktoken
    if _tiktoken is None:
        try:
            import tiktoken
            _tiktoken = tiktoken
        except ImportError:
            logger.warning(
                "tiktoken not installed. Token counting will use character-based estimation. "
                "Install with: pip install tiktoken"
            )
            _tiktoken = False
    return _tiktoken


@lru_cache(maxsize=8)
def get_encoding(model: str = "text-embedding-3-large"):
    """
    Get the tiktoken encoding for a specific model.

    Args:
        model: Model name (e.g., 'text-embedding-3-large', 'gpt-4', 'gpt-3.5-turbo')

    Returns:
        Tiktoken encoding object or None if tiktoken not available
    """
    tiktoken = _get_tiktoken()
    if not tiktoken:
        return None

    try:
        # Try to get encoding for the specific model
        return tiktoken.encoding_for_model(model)
    except KeyError:
        # Fall back to cl100k_base for unknown models (used by GPT-4, embeddings)
        logger.debug(f"No specific encoding for {model}, using cl100k_base")
        return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str, model: str = "text-embedding-3-large") -> int:
    """
    Count the number of tokens in a text string.

    Args:
        text: The text to count tokens for
        model: Model name for encoding selection

    Returns:
        Number of tokens in the text
    """
    if not text:
        return 0

    encoding = get_encoding(model)

    if encoding is None:
        # Fallback: estimate ~4 characters per token (rough average)
        return len(text) // 4

    try:
        return len(encoding.encode(text))
    except Exception as e:
        logger.warning(f"Error counting tokens: {e}, using character estimation")
        return len(text) // 4


def count_tokens_batch(texts: List[str], model: str = "text-embedding-3-large") -> List[int]:
    """
    Count tokens for multiple texts efficiently.

    Args:
        texts: List of text strings
        model: Model name for encoding selection

    Returns:
        List of token counts corresponding to each text
    """
    if not texts:
        return []

    encoding = get_encoding(model)

    if encoding is None:
        # Fallback estimation
        return [len(text) // 4 for text in texts]

    try:
        return [len(encoding.encode(text)) for text in texts]
    except Exception as e:
        logger.warning(f"Error batch counting tokens: {e}, using character estimation")
        return [len(text) // 4 for text in texts]


def truncate_to_tokens(
    text: str,
    max_tokens: int,
    model: str = "text-embedding-3-large",
    suffix: str = "..."
) -> str:
    """
    Truncate text to a maximum number of tokens.

    Args:
        text: Text to truncate
        max_tokens: Maximum tokens to keep
        model: Model name for encoding selection
        suffix: Suffix to append if truncated (counted in max_tokens)

    Returns:
        Truncated text
    """
    if not text:
        return text

    encoding = get_encoding(model)

    if encoding is None:
        # Fallback: estimate ~4 characters per token
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text
        suffix_chars = len(suffix) if suffix else 0
        return text[:max_chars - suffix_chars] + (suffix or "")

    try:
        tokens = encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text

        # Account for suffix tokens
        suffix_tokens = len(encoding.encode(suffix)) if suffix else 0
        truncated_tokens = tokens[:max_tokens - suffix_tokens]

        return encoding.decode(truncated_tokens) + (suffix or "")
    except Exception as e:
        logger.warning(f"Error truncating to tokens: {e}")
        return text


def split_by_tokens(
    text: str,
    chunk_size: int,
    overlap: int = 0,
    model: str = "text-embedding-3-large"
) -> List[str]:
    """
    Split text into chunks of approximately chunk_size tokens with optional overlap.

    This is a low-level token-based splitter. For smarter chunking that respects
    sentence boundaries, use the chunking module.

    Args:
        text: Text to split
        chunk_size: Target number of tokens per chunk
        overlap: Number of overlapping tokens between chunks
        model: Model name for encoding selection

    Returns:
        List of text chunks
    """
    if not text or chunk_size <= 0:
        return [text] if text else []

    if overlap >= chunk_size:
        raise ValueError(f"Overlap ({overlap}) must be less than chunk_size ({chunk_size})")

    encoding = get_encoding(model)

    if encoding is None:
        # Fallback: character-based splitting
        char_size = chunk_size * 4
        char_overlap = overlap * 4
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + char_size, len(text))
            chunks.append(text[start:end])
            start += char_size - char_overlap
        return chunks

    try:
        tokens = encoding.encode(text)
        if len(tokens) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        step = chunk_size - overlap

        while start < len(tokens):
            end = min(start + chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = encoding.decode(chunk_tokens)
            chunks.append(chunk_text)
            start += step

        return chunks
    except Exception as e:
        logger.warning(f"Error splitting by tokens: {e}")
        return [text]


def estimate_embedding_cost(
    token_count: int,
    model: str = "text-embedding-3-large"
) -> float:
    """
    Estimate the cost of embedding a given number of tokens.

    Prices are approximate and may change. Check OpenAI pricing for current rates.

    Args:
        token_count: Number of tokens to embed
        model: Embedding model name

    Returns:
        Estimated cost in USD
    """
    # Prices per 1M tokens (as of early 2024, may be outdated)
    prices_per_million = {
        "text-embedding-3-large": 0.13,
        "text-embedding-3-small": 0.02,
        "text-embedding-ada-002": 0.10,
    }

    price = prices_per_million.get(model, 0.13)  # Default to large model price
    return (token_count / 1_000_000) * price
