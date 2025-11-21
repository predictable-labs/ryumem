"""
Ryumem - Bi-temporal Knowledge Graph Memory System
Client SDK for Ryumem Server.
"""

import logging
import requests
from typing import Dict, List, Optional, Any
from ryumem.core.config import RyumemConfig
from ryumem.core.models import (
    SearchResult,
    EntityNode as Entity,
    EntityEdge as Edge,
    EpisodeNode,
    ToolNode,
    CypherResult,
    EmbeddingResponse,
    LLMResponse
)
from ryumem.core.metadata_models import EpisodeMetadata

logger = logging.getLogger(__name__)


class Ryumem:
    """
    Ryumem Client SDK.
    Connects to a Ryumem Server instance.
    """

    def __init__(
        self,
        server_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize Ryumem client.

        Args:
            server_url: URL of the Ryumem server. If None, checks RYUMEM_API_URL env var, defaults to http://localhost:8000
            api_key: Optional API key for authentication
        """
        import os
        if server_url is None:
            server_url = os.getenv("RYUMEM_API_URL", "http://localhost:8000")

        self.base_url = server_url.rstrip('/')
        self.api_key = api_key

        logger.info(f"Ryumem Client initialized (server: {self.base_url})")

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _post(self, endpoint: str, json: Dict = None) -> Any:
        url = f"{self.base_url}{endpoint}"
        response = requests.post(url, json=json, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def _get(self, endpoint: str, params: Dict = None) -> Any:
        url = f"{self.base_url}{endpoint}"
        response = requests.get(url, params=params, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def _patch(self, endpoint: str, json: Dict = None) -> Any:
        url = f"{self.base_url}{endpoint}"
        response = requests.patch(url, json=json, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    # ==================== Episode Methods ====================

    def get_episode_by_uuid(self, episode_uuid: str) -> Optional[EpisodeNode]:
        """Get episode by UUID via API."""
        try:
            data = self._get(f"/episodes/{episode_uuid}")
            if data:
                # Handle metadata being a JSON string
                if isinstance(data.get("metadata"), str):
                    import json
                    try:
                        data["metadata"] = json.loads(data["metadata"])
                    except json.JSONDecodeError:
                        data["metadata"] = {}
                return EpisodeNode(**data)
            return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def get_episode_by_session_id(self, session_id: str) -> Optional[EpisodeNode]:
        """Get episode by session ID via API."""
        try:
            data = self._get(f"/episodes/session/{session_id}")
            if data:
                # Handle metadata being a JSON string
                if isinstance(data.get("metadata"), str):
                    import json
                    try:
                        data["metadata"] = json.loads(data["metadata"])
                    except json.JSONDecodeError:
                        data["metadata"] = {}
                return EpisodeNode(**data)
            return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def update_episode_metadata(self, episode_uuid: str, metadata: Dict) -> EpisodeNode:
        """Update episode metadata via API and return updated episode."""
        updated_data = self._patch(f"/episodes/{episode_uuid}/metadata", json={"metadata": metadata})
        # Handle metadata being a JSON string
        if isinstance(updated_data.get("metadata"), str):
            import json
            try:
                updated_data["metadata"] = json.loads(updated_data["metadata"])
            except json.JSONDecodeError:
                updated_data["metadata"] = {}
        return EpisodeNode(**updated_data)

    def add_episode(
        self,
        content: str,
        user_id: str,
        session_id: str,
        agent_id: Optional[str] = None,
        source: str = "text",
        metadata: Optional[Dict] = None,
        extract_entities: Optional[bool] = None,
    ) -> str:
        """Add a new episode."""
        payload = {
            "content": content,
            "user_id": user_id,
            "session_id": session_id,
            "source": source,
            "metadata": metadata,
            "extract_entities": extract_entities
        }
        response = self._post("/episodes", json=payload)
        return response["episode_id"]

    def add_memory(
        self,
        content: str,
        user_id: str,
        session_id: str,
        source: str = "text",
    ) -> EpisodeNode:
        """
        Add a memory to an existing episode session.

        Args:
            content: The memory content to add
            user_id: User identifier
            session_id: Session identifier (required)
            source: Episode type (text, message, json)

        Returns:
            Updated EpisodeNode
        """
        episode = self.get_episode_by_session_id(session_id)

        if episode is None:
            raise ValueError(f"Episode not found for session_id: {session_id}")

        # Parse metadata into dict or create new
        if episode.metadata:
            metadata_dict = episode.metadata if isinstance(episode.metadata, dict) else {}
        else:
            metadata_dict = {}

        # Add memory to metadata
        if "memories" not in metadata_dict:
            metadata_dict["memories"] = []

        metadata_dict["memories"].append({
            "content": content,
            "user_id": user_id,
            "session_id": session_id,
            "source": source,
        })

        # Update episode metadata and return updated episode
        return self.update_episode_metadata(episode.uuid, metadata_dict)

    # ==================== Tool Methods ====================

    def save_tool(self, tool_name: str, description: str, name_embedding: List[float]) -> ToolNode:
        """Save a tool via API."""
        response = self._post("/tools", json={
            "tool_name": tool_name,
            "description": description,
            "name_embedding": name_embedding
        })
        return ToolNode(**response)

    def get_tool_by_name(self, name: str) -> Optional[ToolNode]:
        """Get a tool by name via API."""
        try:
            response = self._get(f"/tools/{name}")
            if response:
                return ToolNode(**response)
            return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    # ==================== Query Methods ====================

    def execute(self, query: str, params: Optional[Dict] = None) -> List[CypherResult]:
        """Execute raw Cypher query via API."""
        response = self._post("/cypher/execute", json={"query": query, "params": params or {}})
        results = response.get("results", [])
        return [CypherResult(data=result) for result in results]

    # ==================== Search Methods ====================

    def search(
        self,
        query: str,
        user_id: str,
        session_id: str,
        limit: int = 10,
        strategy: str = "hybrid",
        similarity_threshold: Optional[float] = None,
        max_depth: int = 2,
        min_rrf_score: Optional[float] = None,
        min_bm25_score: Optional[float] = None,
        rrf_k: Optional[int] = None,
    ) -> SearchResult:
        """Search the memory system."""
        payload = {
            "query": query,
            "user_id": user_id,
            "limit": limit,
            "strategy": strategy,
            "min_rrf_score": min_rrf_score,
            "min_bm25_score": min_bm25_score,
        }

        response = self._post("/search", json=payload)

        # Reconstruct SearchResult object
        entities = []
        for e in response.get("entities", []):
            entities.append(Entity(
                uuid=e["uuid"],
                name=e["name"],
                entity_type=e["entity_type"],
                summary=e["summary"],
                mentions=e["mentions"]
            ))

        edges = []
        for e in response.get("edges", []):
            edges.append(Edge(
                uuid=e["uuid"],
                source_node_uuid=e["source_uuid"],
                target_node_uuid=e["target_uuid"],
                name=e["relation_type"],
                fact=e["fact"],
                mentions=e["mentions"]
            ))

        scores = {}
        for e in response.get("entities", []):
            scores[e["uuid"]] = e.get("score", 0.0)
        for e in response.get("edges", []):
            scores[e["uuid"]] = e.get("score", 0.0)

        return SearchResult(
            entities=entities,
            edges=edges,
            scores=scores,
            episodes=response.get("episodes")
        )

    def get_entity_context(
        self,
        entity_name: str,
        user_id: str,
        session_id: str,
        max_depth: int = 2,
    ) -> Dict:
        """
        Get entity context.

        Args:
            entity_name: Name of the entity to look up
            user_id: User identifier (required)
            session_id: Session identifier (required)
            max_depth: Maximum depth for traversal
        """
        try:
            response = self._get(f"/entity/{entity_name}", params={"user_id": user_id, "max_depth": max_depth})

            result = {}
            if response.get("entity"):
                result["entity"] = response["entity"]

            if response.get("relationships"):
                result["relationships"] = response["relationships"]

            result["relationship_count"] = response.get("relationship_count", 0)

            return result

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return {}
            raise

    # ==================== Community Methods ====================

    def update_communities(
        self,
        user_id: str,
        resolution: float = 1.0,
        min_community_size: int = 2,
    ) -> int:
        """Update communities."""
        payload = {
            "resolution": resolution,
            "min_community_size": min_community_size,
            "user_id": user_id
        }
        response = self._post("/communities/update", json=payload)
        return response["num_communities"]

    def prune_memories(
        self,
        user_id: str,
        expired_cutoff_days: int = 90,
        min_mentions: int = 2,
        min_age_days: int = 30,
        compact_redundant: bool = True,
    ) -> Dict:
        """Prune memories."""
        payload = {
            "user_id": user_id,
            "expired_cutoff_days": expired_cutoff_days,
            "min_mentions": min_mentions,
            "min_age_days": min_age_days,
            "compact_redundant": compact_redundant
        }
        response = self._post("/prune", json=payload)
        return response

    # ==================== Agent Instruction Methods ====================

    def save_agent_instruction(
        self,
        base_instruction: str,
        agent_type: str = "google_adk",
        enhanced_instruction: Optional[str] = None,
        query_augmentation_template: Optional[str] = None,
        memory_enabled: bool = False,
        tool_tracking_enabled: bool = False,
    ) -> str:
        """
        Register or update an agent by its base instruction.

        Args:
            base_instruction: The agent's original instruction text (used as unique key)
            agent_type: Type of agent (e.g., "google_adk", "custom_agent")
            enhanced_instruction: Instruction with memory/tool guidance added
            query_augmentation_template: Template for query augmentation
            memory_enabled: Whether memory features are enabled
            tool_tracking_enabled: Whether tool tracking is enabled

        Returns:
            UUID of the agent instruction record
        """
        payload = {
            "base_instruction": base_instruction,
            "agent_type": agent_type,
            "enhanced_instruction": enhanced_instruction,
            "query_augmentation_template": query_augmentation_template,
            "memory_enabled": memory_enabled,
            "tool_tracking_enabled": tool_tracking_enabled,
        }
        response = self._post("/agent-instructions", json=payload)
        return response["instruction_id"]

    def get_instruction_by_text(
        self,
        instruction_text: str,
        agent_type: str,
        instruction_type: str,
    ) -> Optional[str]:
        """
        Get instruction text by key (stored in original_user_request field).

        Args:
            instruction_text: The key to search for (stored in original_user_request)
            agent_type: Type of agent (e.g., "google_adk")
            instruction_type: Type of instruction (e.g., "memory_usage", "agent_instruction")

        Returns:
            The instruction text if found, None otherwise
        """
        try:
            params = {
                "instruction_text": instruction_text,
                "agent_type": agent_type,
                "instruction_type": instruction_type
            }
            response = self._get("/agent-instructions/by-text", params=params)
            return response.get("instruction_text")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def list_agent_instructions(
        self,
        agent_type: Optional[str] = None,
        instruction_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """
        List all agent instructions with optional filters.

        Args:
            agent_type: Optional filter by agent type
            instruction_type: Optional filter by instruction type
            limit: Maximum number of instructions to return

        Returns:
            List of instruction dictionaries ordered by creation date (newest first)
        """
        params = {"limit": limit}
        if agent_type:
            params["agent_type"] = agent_type
        if instruction_type:
            params["instruction_type"] = instruction_type

        response = self._get("/agent-instructions", params=params)
        return response

    # ==================== Embedding & LLM Methods ====================

    def embed(self, text: str) -> EmbeddingResponse:
        """Generate embedding via API."""
        response = self._post("/embeddings", json={"text": text})
        return EmbeddingResponse(
            embedding=response["embedding"],
            model=response.get("model")
        )

    def generate(self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 1000) -> LLMResponse:
        """Generate text via API."""
        response = self._post("/llm/generate", json={
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        })
        return LLMResponse(
            content=response["content"],
            model=response.get("model"),
            tokens_used=response.get("tokens_used")
        )
