"""
Entity extraction and resolution module.
Extracts entities from text and resolves them against existing entities in the graph.
"""

import hashlib
import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from ryumem.core.graph_db import RyugraphDB
from ryumem.core.models import EntityNode
from ryumem.utils.cache import entity_extraction_cache, summary_cache
from ryumem.utils.embeddings import EmbeddingClient
from ryumem.utils.llm import LLMClient

logger = logging.getLogger(__name__)


def _sanitize_user_id(user_id: Any) -> Optional[str]:
    """
    Sanitize user_id value from database.
    Converts nan (float) to None, which can happen when SQLite returns NULL.

    Args:
        user_id: Raw user_id value from database

    Returns:
        None if user_id is None or nan, otherwise the string value
    """
    if user_id is None:
        return None
    # Check if it's a float nan
    if isinstance(user_id, float) and math.isnan(user_id):
        return None
    return user_id


class EntityExtractor:
    """
    Handles entity extraction from text and resolution against existing entities.
    """

    def __init__(
        self,
        db: RyugraphDB,
        llm_client: LLMClient,
        embedding_client: EmbeddingClient,
        similarity_threshold: float = 0.7,
    ):
        """
        Initialize entity extractor.

        Args:
            db: Ryugraph database instance
            llm_client: LLM client for extraction
            embedding_client: Embedding client for similarity search
            similarity_threshold: Threshold for entity deduplication (0.0-1.0)
        """
        self.db = db
        self.llm_client = llm_client
        self.embedding_client = embedding_client
        self.similarity_threshold = similarity_threshold

        logger.info(f"Initialized EntityExtractor with threshold: {similarity_threshold}")

    def extract_and_resolve(
        self,
        content: str,
        group_id: str,
        user_id: Optional[str] = None,
        context: Optional[str] = None,
    ) -> Tuple[List[EntityNode], Dict[str, str]]:
        """
        Extract entities from content and resolve them against existing entities.

        This is the main entry point that:
        1. Extracts entities using LLM
        2. Generates embeddings for entities
        3. Searches for similar existing entities
        4. Resolves duplicates (merge or create new)
        5. Saves entities to database

        Args:
            content: Text content to extract entities from
            group_id: Group ID for multi-tenancy
            user_id: Optional user ID
            context: Optional context from previous episodes

        Returns:
            Tuple of (resolved_entities, entity_name_to_uuid_map)
        """
        # Step 1: Extract entities using LLM
        extracted = self._extract_entities_with_llm(
            content=content,
            user_id=user_id or group_id,
            context=context
        )

        if not extracted:
            logger.info("No entities extracted from content")
            return [], {}

        logger.info(f"Extracted {len(extracted)} raw entities")

        # Step 2: Generate embeddings for all extracted entities
        # Embed entity name + type for richer semantic context
        entity_texts = [
            f"{e['entity']} ({e['entity_type']})"
            for e in extracted
        ]
        embeddings = self.embedding_client.embed_batch(entity_texts)

        # Step 3: Resolve each entity (find existing or create new)
        resolved_entities: List[EntityNode] = []
        entity_map: Dict[str, str] = {}  # Maps entity name -> UUID

        for entity_data, embedding in zip(extracted, embeddings):
            entity_name = entity_data["entity"]
            entity_type = entity_data["entity_type"]

            # Search for similar existing entities
            logger.debug(f"Searching for similar entities to '{entity_name}' (threshold: {self.similarity_threshold})")
            similar = self.db.search_similar_entities(
                embedding=embedding,
                group_id=group_id,
                threshold=self.similarity_threshold,
                limit=5,  # Get top 5 to see what's available
                user_id=user_id,
            )

            if similar:
                # Log all similar entities found
                logger.info(f"📊 Found {len(similar)} similar entities for '{entity_name}':")
                for idx, sim_entity in enumerate(similar, 1):
                    logger.info(f"   {idx}. '{sim_entity['name']}' - similarity: {sim_entity['similarity']:.4f}, mentions: {sim_entity.get('mentions', 0)}")

                # Use the most similar entity
                existing = similar[0]
                entity_uuid = existing["uuid"]

                logger.info(
                    f"✅ Deduplicating: '{entity_name}' → existing entity '{existing['name']}' "
                    f"(UUID: {entity_uuid[:8]}..., similarity: {existing['similarity']:.4f}, mentions: {existing.get('mentions', 0)} → {existing.get('mentions', 0) + 1})"
                )

                # Create entity node with existing UUID to update mentions
                entity = EntityNode(
                    uuid=entity_uuid,
                    name=existing["name"],  # Use canonical name from DB
                    entity_type=entity_type,
                    summary=existing.get("summary", ""),
                    name_embedding=embedding,
                    mentions=existing.get("mentions", 0) + 1,
                    group_id=group_id,
                    user_id=user_id,
                )

                # Save to DB (will increment mentions)
                self.db.save_entity(entity)
                resolved_entities.append(entity)
                entity_map[entity_name.lower().replace(" ", "_")] = entity_uuid

            else:
                # No similar entity found - create new one
                entity_uuid = str(uuid4())
                logger.info(f"✨ Creating NEW entity '{entity_name}' (type: {entity_type}, UUID: {entity_uuid[:8]}...)")

                entity = EntityNode(
                    uuid=entity_uuid,
                    name=entity_name,
                    entity_type=entity_type,
                    summary="",  # Will be updated later with context
                    name_embedding=embedding,
                    mentions=1,
                    created_at=datetime.utcnow(),
                    group_id=group_id,
                    user_id=user_id,
                )

                # Save to DB
                self.db.save_entity(entity)
                resolved_entities.append(entity)
                entity_map[entity_name.lower().replace(" ", "_")] = entity_uuid

                logger.info(f"💾 Saved new entity '{entity_name}' to database")

        logger.info(
            f"Resolved {len(resolved_entities)} entities "
            f"({len([e for e in resolved_entities if e.mentions == 1])} new, "
            f"{len([e for e in resolved_entities if e.mentions > 1])} existing)"
        )

        return resolved_entities, entity_map

    def _extract_entities_with_llm(
        self,
        content: str,
        user_id: str,
        context: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        Extract entities from content using LLM.
        Uses cache to avoid redundant API calls.

        Args:
            content: Text content
            user_id: User ID for self-reference resolution
            context: Optional context

        Returns:
            List of dicts with 'entity' and 'entity_type' keys
        """
        # Check cache first
        cache_key = hashlib.sha256(
            f"entity_extraction|{content}|{user_id}|{context or ''}".encode()
        ).hexdigest()

        cached_result = entity_extraction_cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"💾 Cache HIT for entity extraction: '{content[:50]}...'")
            return cached_result

        try:
            logger.debug(f"🌐 API call for entity extraction: '{content[:50]}...'")
            entities = self.llm_client.extract_entities(
                text=content,
                user_id=user_id,
                context=context,
            )

            # Normalize entity names (lowercase, replace spaces with underscores)
            normalized = []
            seen = set()

            for entity in entities:
                name = entity["entity"].lower().replace(" ", "_")
                if name not in seen:
                    normalized.append({
                        "entity": name,
                        "entity_type": entity["entity_type"].upper().replace(" ", "_")
                    })
                    seen.add(name)

            # Cache the result
            entity_extraction_cache.set(cache_key, normalized)

            return normalized

        except Exception as e:
            logger.error(f"Error extracting entities with LLM: {e}")
            return []

    def update_entity_summary(
        self,
        entity_uuid: str,
        new_context: str,
    ) -> None:
        """
        Update an entity's summary with new context.
        Uses cache to avoid redundant API calls.

        Args:
            entity_uuid: UUID of entity to update
            new_context: New contextual information about the entity
        """
        # Get existing entity
        entity_data = self.db.get_entity_by_uuid(entity_uuid)
        if not entity_data:
            logger.warning(f"Entity {entity_uuid} not found for summary update")
            return

        # Get existing relationships for context
        relationships = self.db.get_entity_relationships(entity_uuid)

        # Build context from relationships
        rel_context = []
        for rel in relationships[:5]:  # Limit to 5 most recent
            rel_context.append(f"- {rel['relation_type']}: {rel['other_name']}")

        context_str = "\n".join(rel_context) if rel_context else "No relationships yet."

        # Check cache first
        cache_key = hashlib.sha256(
            f"summary|{entity_uuid}|{entity_data.get('summary', '')}|{context_str}|{new_context}".encode()
        ).hexdigest()

        cached_summary = summary_cache.get(cache_key)
        if cached_summary is not None:
            logger.debug(f"💾 Cache HIT for summary update: entity {entity_data['name']}")
            new_summary = cached_summary
        else:
            # Generate updated summary using LLM
            messages = [
                {
                    "role": "system",
                    "content": """You are an expert at creating concise entity summaries.
Given an entity name, its existing summary, relationships, and new context, create an updated summary.
The summary should be 1-2 sentences capturing the most important information."""
                },
                {
                    "role": "user",
                    "content": f"""Entity: {entity_data['name']}
Type: {entity_data['entity_type']}

Existing summary: {entity_data.get('summary', 'None')}

Known relationships:
{context_str}

New context: {new_context}

Create an updated summary:"""
                }
            ]

            try:
                logger.debug(f"🌐 API call for summary update: entity {entity_data['name']}")
                response = self.llm_client.generate(messages, temperature=0.3)
                new_summary = response.get("content", "").strip()

                if new_summary:
                    # Cache the result
                    summary_cache.set(cache_key, new_summary)

            except Exception as e:
                logger.error(f"Error updating entity summary: {e}")
                return

        if new_summary:
            # Update entity with new summary
            entity = EntityNode(
                uuid=entity_uuid,
                name=entity_data["name"],
                entity_type=entity_data["entity_type"],
                summary=new_summary,
                mentions=entity_data["mentions"],
                group_id=entity_data["group_id"],
                user_id=_sanitize_user_id(entity_data.get("user_id")),
            )
            self.db.save_entity(entity)
            logger.debug(f"Updated summary for entity {entity_data['name']}")

    def get_entity_by_name(
        self,
        name: str,
        group_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[EntityNode]:
        """
        Find an entity by name using embedding similarity.

        Args:
            name: Entity name to search for
            group_id: Group ID
            user_id: Optional user ID

        Returns:
            EntityNode if found, None otherwise
        """
        # Generate embedding for name
        embedding = self.embedding_client.embed(name)

        # Search for similar entities
        similar = self.db.search_similar_entities(
            embedding=embedding,
            group_id=group_id,
            threshold=self.similarity_threshold,
            limit=1,
            user_id=user_id,
        )

        if similar:
            result = similar[0]
            return EntityNode(
                uuid=result["uuid"],
                name=result["name"],
                entity_type=result["entity_type"],
                summary=result.get("summary", ""),
                mentions=result["mentions"],
                group_id=result["group_id"],
                user_id=result.get("user_id"),
            )

        return None
