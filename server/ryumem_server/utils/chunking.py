"""
Text chunking strategies for episode content.
Provides multiple chunking approaches optimized for embeddings and search.
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Protocol, TYPE_CHECKING

from ryumem_server.utils.token_counter import count_tokens, split_by_tokens

if TYPE_CHECKING:
    from ryumem.core.config import ChunkingConfig

logger = logging.getLogger(__name__)


@dataclass
class ChunkResult:
    """Result of chunking a text."""
    text: str
    start_offset: int
    end_offset: int
    token_count: int
    chunk_index: int

    @property
    def char_count(self) -> int:
        """Number of characters in the chunk."""
        return len(self.text)


@dataclass
class ChunkingResult:
    """Complete result of chunking operation."""
    chunks: List[ChunkResult]
    original_length: int
    total_tokens: int
    strategy_used: str
    config_used: dict = field(default_factory=dict)

    @property
    def num_chunks(self) -> int:
        return len(self.chunks)

    def get_texts(self) -> List[str]:
        """Get just the text content of all chunks."""
        return [c.text for c in self.chunks]

    def get_offsets(self) -> List[tuple]:
        """Get (start, end) offset tuples for all chunks."""
        return [(c.start_offset, c.end_offset) for c in self.chunks]


class ChunkingStrategy(ABC):
    """Abstract base class for chunking strategies."""

    @abstractmethod
    def chunk(
        self,
        text: str,
        chunk_size: int,
        overlap: int,
        model: str = "text-embedding-3-large"
    ) -> ChunkingResult:
        """
        Chunk text according to the strategy.

        Args:
            text: Text to chunk
            chunk_size: Target size in tokens
            overlap: Overlap between chunks in tokens
            model: Model name for token counting

        Returns:
            ChunkingResult with all chunks and metadata
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name for logging and config."""
        pass


class OverlapChunker(ChunkingStrategy):
    """
    Simple fixed-size chunking with overlap.
    Splits strictly by token count without respecting boundaries.
    """

    @property
    def name(self) -> str:
        return "overlap"

    def chunk(
        self,
        text: str,
        chunk_size: int,
        overlap: int,
        model: str = "text-embedding-3-large"
    ) -> ChunkingResult:
        if not text:
            return ChunkingResult(
                chunks=[],
                original_length=0,
                total_tokens=0,
                strategy_used=self.name
            )

        total_tokens = count_tokens(text, model)

        # If text fits in one chunk, return as-is
        if total_tokens <= chunk_size:
            chunk = ChunkResult(
                text=text,
                start_offset=0,
                end_offset=len(text),
                token_count=total_tokens,
                chunk_index=0
            )
            return ChunkingResult(
                chunks=[chunk],
                original_length=len(text),
                total_tokens=total_tokens,
                strategy_used=self.name
            )

        # Split by tokens
        chunk_texts = split_by_tokens(text, chunk_size, overlap, model)

        # Build ChunkResult objects with offset tracking
        chunks = []
        current_offset = 0

        for i, chunk_text in enumerate(chunk_texts):
            # Find actual position in original text
            # This is approximate due to encoding/decoding
            start = text.find(chunk_text[:50], current_offset) if len(chunk_text) >= 50 else current_offset
            if start == -1:
                start = current_offset
            end = start + len(chunk_text)

            chunks.append(ChunkResult(
                text=chunk_text,
                start_offset=start,
                end_offset=end,
                token_count=count_tokens(chunk_text, model),
                chunk_index=i
            ))

            # Move forward, accounting for overlap
            current_offset = max(current_offset, end - (overlap * 4))  # Approximate char overlap

        return ChunkingResult(
            chunks=chunks,
            original_length=len(text),
            total_tokens=total_tokens,
            strategy_used=self.name
        )


class SentenceChunker(ChunkingStrategy):
    """
    Chunks text by sentence boundaries.
    Tries to keep chunks under the token limit while respecting sentence endings.
    """

    # Sentence-ending patterns
    SENTENCE_ENDINGS = re.compile(r'(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])\s*$')

    @property
    def name(self) -> str:
        return "sentence"

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting - could be enhanced with nltk/spacy
        sentences = self.SENTENCE_ENDINGS.split(text)
        return [s.strip() for s in sentences if s.strip()]

    def chunk(
        self,
        text: str,
        chunk_size: int,
        overlap: int,
        model: str = "text-embedding-3-large"
    ) -> ChunkingResult:
        if not text:
            return ChunkingResult(
                chunks=[],
                original_length=0,
                total_tokens=0,
                strategy_used=self.name
            )

        total_tokens = count_tokens(text, model)

        if total_tokens <= chunk_size:
            chunk = ChunkResult(
                text=text,
                start_offset=0,
                end_offset=len(text),
                token_count=total_tokens,
                chunk_index=0
            )
            return ChunkingResult(
                chunks=[chunk],
                original_length=len(text),
                total_tokens=total_tokens,
                strategy_used=self.name
            )

        sentences = self._split_sentences(text)
        chunks = []
        current_chunk_sentences = []
        current_tokens = 0
        chunk_index = 0
        current_offset = 0

        for sentence in sentences:
            sentence_tokens = count_tokens(sentence, model)

            # If single sentence exceeds chunk size, fall back to token splitting
            if sentence_tokens > chunk_size:
                # Flush current chunk first
                if current_chunk_sentences:
                    chunk_text = " ".join(current_chunk_sentences)
                    chunks.append(ChunkResult(
                        text=chunk_text,
                        start_offset=current_offset,
                        end_offset=current_offset + len(chunk_text),
                        token_count=current_tokens,
                        chunk_index=chunk_index
                    ))
                    current_offset += len(chunk_text) + 1
                    chunk_index += 1
                    current_chunk_sentences = []
                    current_tokens = 0

                # Split long sentence by tokens
                sub_chunks = split_by_tokens(sentence, chunk_size, overlap, model)
                for sub_text in sub_chunks:
                    chunks.append(ChunkResult(
                        text=sub_text,
                        start_offset=current_offset,
                        end_offset=current_offset + len(sub_text),
                        token_count=count_tokens(sub_text, model),
                        chunk_index=chunk_index
                    ))
                    current_offset += len(sub_text)
                    chunk_index += 1
                continue

            # Check if adding sentence would exceed chunk size
            if current_tokens + sentence_tokens > chunk_size:
                # Save current chunk
                if current_chunk_sentences:
                    chunk_text = " ".join(current_chunk_sentences)
                    chunks.append(ChunkResult(
                        text=chunk_text,
                        start_offset=current_offset,
                        end_offset=current_offset + len(chunk_text),
                        token_count=current_tokens,
                        chunk_index=chunk_index
                    ))
                    chunk_index += 1

                    # Calculate overlap: keep last N tokens worth of sentences
                    overlap_sentences = []
                    overlap_tokens = 0
                    for s in reversed(current_chunk_sentences):
                        s_tokens = count_tokens(s, model)
                        if overlap_tokens + s_tokens <= overlap:
                            overlap_sentences.insert(0, s)
                            overlap_tokens += s_tokens
                        else:
                            break

                    current_offset += len(chunk_text) + 1 - sum(len(s) for s in overlap_sentences)
                    current_chunk_sentences = overlap_sentences
                    current_tokens = overlap_tokens

            current_chunk_sentences.append(sentence)
            current_tokens += sentence_tokens

        # Don't forget the last chunk
        if current_chunk_sentences:
            chunk_text = " ".join(current_chunk_sentences)
            chunks.append(ChunkResult(
                text=chunk_text,
                start_offset=current_offset,
                end_offset=current_offset + len(chunk_text),
                token_count=current_tokens,
                chunk_index=chunk_index
            ))

        return ChunkingResult(
            chunks=chunks,
            original_length=len(text),
            total_tokens=total_tokens,
            strategy_used=self.name
        )


class ParagraphChunker(ChunkingStrategy):
    """
    Chunks text by paragraph boundaries.
    Respects double newlines as paragraph separators.
    """

    @property
    def name(self) -> str:
        return "paragraph"

    def _split_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs."""
        # Split on double newlines or multiple newlines
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip()]

    def chunk(
        self,
        text: str,
        chunk_size: int,
        overlap: int,
        model: str = "text-embedding-3-large"
    ) -> ChunkingResult:
        if not text:
            return ChunkingResult(
                chunks=[],
                original_length=0,
                total_tokens=0,
                strategy_used=self.name
            )

        total_tokens = count_tokens(text, model)

        if total_tokens <= chunk_size:
            chunk = ChunkResult(
                text=text,
                start_offset=0,
                end_offset=len(text),
                token_count=total_tokens,
                chunk_index=0
            )
            return ChunkingResult(
                chunks=[chunk],
                original_length=len(text),
                total_tokens=total_tokens,
                strategy_used=self.name
            )

        paragraphs = self._split_paragraphs(text)
        chunks = []
        current_chunk_paras = []
        current_tokens = 0
        chunk_index = 0
        current_offset = 0

        for para in paragraphs:
            para_tokens = count_tokens(para, model)

            # If single paragraph exceeds chunk size, use sentence chunker as fallback
            if para_tokens > chunk_size:
                # Flush current chunk first
                if current_chunk_paras:
                    chunk_text = "\n\n".join(current_chunk_paras)
                    chunks.append(ChunkResult(
                        text=chunk_text,
                        start_offset=current_offset,
                        end_offset=current_offset + len(chunk_text),
                        token_count=current_tokens,
                        chunk_index=chunk_index
                    ))
                    current_offset += len(chunk_text) + 2
                    chunk_index += 1
                    current_chunk_paras = []
                    current_tokens = 0

                # Use sentence chunker for long paragraph
                sentence_chunker = SentenceChunker()
                sub_result = sentence_chunker.chunk(para, chunk_size, overlap, model)
                for sub_chunk in sub_result.chunks:
                    sub_chunk.chunk_index = chunk_index
                    sub_chunk.start_offset += current_offset
                    sub_chunk.end_offset += current_offset
                    chunks.append(sub_chunk)
                    chunk_index += 1
                current_offset += len(para) + 2
                continue

            # Check if adding paragraph would exceed chunk size
            if current_tokens + para_tokens > chunk_size:
                if current_chunk_paras:
                    chunk_text = "\n\n".join(current_chunk_paras)
                    chunks.append(ChunkResult(
                        text=chunk_text,
                        start_offset=current_offset,
                        end_offset=current_offset + len(chunk_text),
                        token_count=current_tokens,
                        chunk_index=chunk_index
                    ))
                    chunk_index += 1

                    # Simple overlap: keep last paragraph if it fits
                    if current_chunk_paras and count_tokens(current_chunk_paras[-1], model) <= overlap:
                        last_para = current_chunk_paras[-1]
                        current_offset += len(chunk_text) + 2 - len(last_para) - 2
                        current_chunk_paras = [last_para]
                        current_tokens = count_tokens(last_para, model)
                    else:
                        current_offset += len(chunk_text) + 2
                        current_chunk_paras = []
                        current_tokens = 0

            current_chunk_paras.append(para)
            current_tokens += para_tokens

        # Don't forget the last chunk
        if current_chunk_paras:
            chunk_text = "\n\n".join(current_chunk_paras)
            chunks.append(ChunkResult(
                text=chunk_text,
                start_offset=current_offset,
                end_offset=current_offset + len(chunk_text),
                token_count=current_tokens,
                chunk_index=chunk_index
            ))

        return ChunkingResult(
            chunks=chunks,
            original_length=len(text),
            total_tokens=total_tokens,
            strategy_used=self.name
        )


# Strategy registry
CHUNKING_STRATEGIES = {
    "overlap": OverlapChunker,
    "sentence": SentenceChunker,
    "paragraph": ParagraphChunker,
}


def get_chunker(strategy: str = "overlap") -> ChunkingStrategy:
    """
    Get a chunking strategy by name.

    Args:
        strategy: Strategy name ('overlap', 'sentence', 'paragraph')

    Returns:
        ChunkingStrategy instance

    Raises:
        ValueError: If strategy is not recognized
    """
    strategy = strategy.lower()
    if strategy not in CHUNKING_STRATEGIES:
        raise ValueError(
            f"Unknown chunking strategy: {strategy}. "
            f"Available: {list(CHUNKING_STRATEGIES.keys())}"
        )
    return CHUNKING_STRATEGIES[strategy]()


def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 50,
    strategy: str = "overlap",
    model: str = "text-embedding-3-large",
    max_chunks: Optional[int] = None
) -> ChunkingResult:
    """
    Chunk text using the specified strategy.

    This is the main entry point for chunking operations.

    Args:
        text: Text to chunk
        chunk_size: Target chunk size in tokens (default: 512)
        overlap: Overlap between chunks in tokens (default: 50)
        strategy: Chunking strategy ('overlap', 'sentence', 'paragraph')
        model: Model name for token counting
        max_chunks: Optional maximum number of chunks to return

    Returns:
        ChunkingResult with all chunks and metadata
    """
    chunker = get_chunker(strategy)
    result = chunker.chunk(text, chunk_size, overlap, model)

    # Limit chunks if requested
    if max_chunks is not None and len(result.chunks) > max_chunks:
        logger.warning(
            f"Truncating from {len(result.chunks)} to {max_chunks} chunks"
        )
        result.chunks = result.chunks[:max_chunks]

    result.config_used = {
        "chunk_size": chunk_size,
        "overlap": overlap,
        "strategy": strategy,
        "model": model,
        "max_chunks": max_chunks
    }

    logger.debug(
        f"Chunked {len(text)} chars into {len(result.chunks)} chunks "
        f"using {strategy} strategy"
    )

    return result


def should_chunk(
    text: str,
    chunk_size: int = 512,
    model: str = "text-embedding-3-large"
) -> bool:
    """
    Determine if text should be chunked based on its token count.

    Args:
        text: Text to check
        chunk_size: Chunk size threshold in tokens
        model: Model name for token counting

    Returns:
        True if text exceeds chunk_size tokens
    """
    if not text:
        return False
    return count_tokens(text, model) > chunk_size
