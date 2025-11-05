"""
Embedding client wrapper for OpenAI embedding models.
Handles batching, caching, and error handling.
"""

import hashlib
import logging
from typing import List

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from ryumem.utils.cache import embedding_cache

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """
    Wrapper for OpenAI embedding client with batching and retry logic.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-large",
        dimensions: int = 3072,
        batch_size: int = 100,
        timeout: int = 30,
    ):
        """
        Initialize embedding client.

        Args:
            api_key: OpenAI API key
            model: Embedding model name
            dimensions: Embedding dimensions
            batch_size: Maximum batch size for embedding requests
            timeout: Timeout in seconds for API calls
        """
        self.client = OpenAI(api_key=api_key, timeout=timeout)
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size

        logger.info(f"Initialized EmbeddingClient with model: {model}, dimensions: {dimensions}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def embed(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        Uses cache to avoid redundant API calls.

        Args:
            text: Input text to embed

        Returns:
            Embedding vector as list of floats
        """
        try:
            # Clean text
            text = text.replace("\n", " ").strip()
            if not text:
                logger.warning("Empty text provided for embedding, returning zero vector")
                return [0.0] * self.dimensions

            # Check cache first
            cache_key = hashlib.sha256(
                f"{self.model}|{self.dimensions}|{text}".encode()
            ).hexdigest()

            cached_embedding = embedding_cache.get(cache_key)
            if cached_embedding is not None:
                logger.debug(f"💾 Cache HIT for embedding: '{text[:50]}...'")
                return cached_embedding

            # Call OpenAI API
            logger.debug(f"🌐 API call for embedding: '{text[:50]}...'")
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimensions,
            )

            embedding = response.data[0].embedding

            # Cache the result
            embedding_cache.set(cache_key, embedding)

            logger.debug(f"Generated embedding for text: '{text[:50]}...' (dim: {len(embedding)})")
            return embedding

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches.
        Uses cache to avoid redundant API calls.

        Args:
            texts: List of input texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # Clean texts
        texts = [text.replace("\n", " ").strip() for text in texts]

        all_embeddings: List[List[float]] = []
        uncached_texts: List[tuple[int, str]] = []  # (original_index, text)

        try:
            # Check cache for each text
            for i, text in enumerate(texts):
                cache_key = hashlib.sha256(
                    f"{self.model}|{self.dimensions}|{text}".encode()
                ).hexdigest()

                cached_embedding = embedding_cache.get(cache_key)
                if cached_embedding is not None:
                    all_embeddings.append(cached_embedding)
                else:
                    # Need to generate this embedding
                    uncached_texts.append((i, text))
                    all_embeddings.append(None)  # Placeholder

            logger.info(f"💾 Cache: {len(texts) - len(uncached_texts)}/{len(texts)} embeddings cached")

            # If all were cached, return early
            if not uncached_texts:
                return all_embeddings

            # Generate embeddings for uncached texts
            texts_to_embed = [text for _, text in uncached_texts]
            new_embeddings: List[List[float]] = []

            # Process in batches
            for i in range(0, len(texts_to_embed), self.batch_size):
                batch = texts_to_embed[i:i + self.batch_size]

                # Call OpenAI API
                logger.debug(f"🌐 API call for {len(batch)} embeddings (batch {i // self.batch_size + 1})")
                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch,
                    dimensions=self.dimensions,
                )

                # Extract embeddings in order
                batch_embeddings = [data.embedding for data in response.data]
                new_embeddings.extend(batch_embeddings)

                logger.debug(f"Generated {len(batch_embeddings)} embeddings (batch {i // self.batch_size + 1})")

            # Cache and insert new embeddings at correct positions
            for (original_index, text), embedding in zip(uncached_texts, new_embeddings):
                cache_key = hashlib.sha256(
                    f"{self.model}|{self.dimensions}|{text}".encode()
                ).hexdigest()
                embedding_cache.set(cache_key, embedding)
                all_embeddings[original_index] = embedding

            logger.info(f"Generated {len(new_embeddings)} new embeddings, total {len(all_embeddings)}")
            return all_embeddings

        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            raise

    def cosine_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score (0.0-1.0)
        """
        import numpy as np

        # Convert to numpy arrays
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        # Calculate cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)

        return float(similarity)

    def find_most_similar(
        self,
        query_embedding: List[float],
        candidate_embeddings: List[List[float]],
        threshold: float = 0.7,
        top_k: int = 5,
    ) -> List[tuple[int, float]]:
        """
        Find most similar embeddings to a query embedding.

        Args:
            query_embedding: Query embedding vector
            candidate_embeddings: List of candidate embedding vectors
            threshold: Minimum similarity threshold
            top_k: Maximum number of results to return

        Returns:
            List of (index, similarity_score) tuples, sorted by similarity descending
        """
        if not candidate_embeddings:
            return []

        # Calculate similarities
        similarities = [
            (i, self.cosine_similarity(query_embedding, candidate))
            for i, candidate in enumerate(candidate_embeddings)
        ]

        # Filter by threshold and sort
        filtered = [(i, score) for i, score in similarities if score >= threshold]
        filtered.sort(key=lambda x: x[1], reverse=True)

        # Return top k
        return filtered[:top_k]
