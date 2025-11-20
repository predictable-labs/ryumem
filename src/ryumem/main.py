"""
Ryumem - Bi-temporal Knowledge Graph Memory System
Client SDK for Ryumem Server.
"""

import logging
import requests
from typing import Dict, List, Optional, Any, Union
from ryumem.core.config import RyumemConfig
from ryumem.core.models import SearchResult, EntityNode as Entity, EntityEdge as Edge, EpisodeNode

logger = logging.getLogger(__name__)

class DBProxy:
    """
    Proxy for database operations that are now handled by the server.
    Maintains backward compatibility for integrations accessing ryumem.db.*
    """
    def __init__(self, client: "Ryumem"):
        self.client = client

    def get_episode_by_uuid(self, episode_uuid: str) -> Optional[EpisodeNode]:
        """Get episode by UUID via API."""
        try:
            data = self.client._get(f"/episodes/{episode_uuid}")
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

    def update_episode_metadata(self, episode_uuid: str, metadata: Dict) -> Dict:
        """Update episode metadata via API."""
        return self.client._patch(f"/episodes/{episode_uuid}/metadata", json={"metadata": metadata})

    def execute(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Execute raw Cypher query via API."""
        response = self.client._post("/cypher/execute", json={"query": query, "params": params or {}})
        return response.get("results", [])

    def get_episode_by_session_id(self, session_id: str) -> Optional[EpisodeNode]:
        """Get episode by session ID via API."""
        try:
            data = self.client._get(f"/episodes/session/{session_id}")
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

    def save_tool(self, tool_name: str, description: str, name_embedding: List[float]) -> None:
        """Save a tool via API."""
        self.client._post("/tools", json={
            "tool_name": tool_name,
            "description": description,
            "name_embedding": name_embedding
        })

    def get_tool_by_name(self, name: str) -> Optional[Dict]:
        """Get a tool by name via API."""
        try:
            return self.client._get(f"/tools/{name}")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

class EmbeddingClientProxy:
    """Proxy for embedding client."""
    def __init__(self, client: "Ryumem"):
        self.client = client

    def embed(self, text: str) -> List[float]:
        """Generate embedding via API."""
        response = self.client._post("/embeddings", json={"text": text})
        return response["embedding"]

class LLMClientProxy:
    """Proxy for LLM client."""
    def __init__(self, client: "Ryumem"):
        self.client = client

    def generate(self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 1000) -> Dict[str, str]:
        """Generate text via API."""
        response = self.client._post("/llm/generate", json={
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        })
        return {"content": response["content"]}

class Ryumem:
    """
    Ryumem Client SDK.
    Connects to a Ryumem Server instance.
    """

    def __init__(
        self,
        server_url: Optional[str] = None,
        config: Optional[RyumemConfig] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize Ryumem client.

        Args:
            server_url: URL of the Ryumem server. If None, checks RYUMEM_API_URL env var, defaults to http://localhost:8000
            config: Optional RyumemConfig (mostly unused in client mode, but kept for compat)
            api_key: Optional API key for authentication
        """
        import os
        if server_url is None:
            server_url = os.getenv("RYUMEM_API_URL", "http://localhost:8000")

        self.base_url = server_url.rstrip('/')
        self.api_key = api_key
        self.config = config or RyumemConfig()
        
        # Initialize proxies
        self.db = DBProxy(self)
        self.embedding_client = EmbeddingClientProxy(self)
        self.llm_client = LLMClientProxy(self)
        
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

    def add_episode(
        self,
        content: str,
        user_id: str,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
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

    def get_episode_by_uuid(self, episode_uuid: str) -> Optional[Dict]:
        """Get episode by UUID."""
        return self.db.get_episode_by_uuid(episode_uuid)

    def update_episode_metadata(self, episode_uuid: str, metadata: Dict) -> Dict:
        """Update episode metadata."""
        return self.db.update_episode_metadata(episode_uuid, metadata)

    def search(
        self,
        query: str,
        user_id: str,
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
            scores=scores
        )

    def get_entity_context(
        self,
        entity_name: str,
        user_id: str,
        max_depth: int = 2,
    ) -> Dict:
        """Get entity context."""
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
