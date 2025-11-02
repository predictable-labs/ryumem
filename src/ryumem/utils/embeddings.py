"""
Embedding client wrapper for OpenAI embedding models.
Handles batching, caching, and error handling.
"""

import logging
from typing import List

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

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

            # Call OpenAI API
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimensions,
            )

            embedding = response.data[0].embedding

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

        try:
            # Process in batches
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i:i + self.batch_size]

                # Call OpenAI API
                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch,
                    dimensions=self.dimensions,
                )

                # Extract embeddings in order
                batch_embeddings = [data.embedding for data in response.data]
                all_embeddings.extend(batch_embeddings)

                logger.debug(f"Generated {len(batch_embeddings)} embeddings (batch {i // self.batch_size + 1})")

            logger.info(f"Generated {len(all_embeddings)} embeddings total")
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
