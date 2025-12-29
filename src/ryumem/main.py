"""
Ryumem - Bi-temporal Knowledge Graph Memory System
Client SDK for Ryumem Server.
"""

import logging
import requests
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from ryumem.core.config import RyumemConfig
from ryumem.core.models import (
    SearchResult,
    EntityNode as Entity,
    EntityEdge as Edge,
    EpisodeNode,
    EpisodeType,
    ToolNode,
    CypherResult,
    EmbeddingResponse,
    LLMResponse
)
from ryumem.core.metadata_models import EpisodeMetadata

logger = logging.getLogger(__name__)


@dataclass
class InstructionCacheEntry:
    """Cache entry for agent instructions."""
    data: Dict[str, Any]
    timestamp: float


class Ryumem:
    """
    Ryumem Client SDK.
    Connects to a Ryumem Server instance.
    """

    def __init__(
        self,
        server_url: Optional[str] = None,
        api_key: Optional[str] = None,
        config_ttl: int = 300,  # 5 minutes default
        custom_tool_summary_fn: Optional['Callable'] = None,
        # Agent config overrides
        memory_enabled: Optional[bool] = None,
        enhance_agent_instruction: Optional[bool] = None,
        # Entity extraction overrides
        extract_entities: Optional[bool] = None,
        # Tool tracking overrides
        track_tools: Optional[bool] = None,
        sample_rate: Optional[float] = None,
        summarize_outputs: Optional[bool] = None,
        max_output_chars: Optional[int] = None,
        sanitize_pii: Optional[bool] = None,
        enhance_descriptions: Optional[bool] = None,
        ignore_errors: Optional[bool] = None,
        track_queries: Optional[bool] = None,
        augment_queries: Optional[bool] = None,
        similarity_threshold: Optional[float] = None,
        top_k_similar: Optional[int] = None,
    ):
        """
        Initialize Ryumem client.

        Args:
            server_url: URL of the Ryumem server. If None, checks RYUMEM_API_URL env var
            api_key: Optional API key for authentication
            config_ttl: Time-to-live for cached config in seconds (default: 300)
            custom_tool_summary_fn: Optional function to generate custom tool summaries (takes ToolExecution, returns str)
            memory_enabled: Override for agent.memory_enabled
            enhance_agent_instruction: Override for agent.enhance_agent_instruction
            extract_entities: Override for entity_extraction.enabled
            track_tools: Override for tool_tracking.track_tools
            sample_rate: Override for tool_tracking.sample_rate
            summarize_outputs: Override for tool_tracking.summarize_outputs
            max_output_chars: Override for tool_tracking.max_output_chars
            sanitize_pii: Override for tool_tracking.sanitize_pii
            enhance_descriptions: Override for tool_tracking.enhance_descriptions
            ignore_errors: Override for tool_tracking.ignore_errors
            track_queries: Override for tool_tracking.track_queries
            augment_queries: Override for tool_tracking.augment_queries
            similarity_threshold: Override for tool_tracking.similarity_threshold
            top_k_similar: Override for tool_tracking.top_k_similar
        """
        import os
        if not server_url:
            server_url = os.getenv("RYUMEM_API_URL") or "https://api.ryumem.io"
        if api_key is None:
            api_key = os.getenv("RYUMEM_API_KEY", "")

        # Add protocol if missing - use HTTPS for production domains, HTTP for localhost
        if not server_url.startswith("http://") and not server_url.startswith("https://"):
            if "localhost" in server_url or "127.0.0.1" in server_url:
                server_url = f"http://{server_url}"
            else:
                server_url = f"https://{server_url}"

        self.base_url = server_url.rstrip('/')
        self.api_key = api_key
        self._config_ttl = config_ttl
        self.custom_tool_summary_fn = custom_tool_summary_fn

        # Store user overrides
        self._config_overrides = {
            'agent': {k: v for k, v in {
                'memory_enabled': memory_enabled,
                'enhance_agent_instruction': enhance_agent_instruction,
            }.items() if v is not None},
            'entity_extraction': {k: v for k, v in {
                'enabled': extract_entities,
            }.items() if v is not None},
            'tool_tracking': {k: v for k, v in {
                'track_tools': track_tools,
                'sample_rate': sample_rate,
                'summarize_outputs': summarize_outputs,
                'max_output_chars': max_output_chars,
                'sanitize_pii': sanitize_pii,
                'enhance_descriptions': enhance_descriptions,
                'ignore_errors': ignore_errors,
                'track_queries': track_queries,
                'augment_queries': augment_queries,
                'similarity_threshold': similarity_threshold,
                'top_k_similar': top_k_similar,
            }.items() if v is not None},
        }

        # Cache for server config
        self._config_cache: Optional['RyumemConfig'] = None
        self._config_cache_time: Optional[float] = None

        # Cache for agent instructions (key: agent_type:instruction_text)
        self._instruction_cache: Dict[str, InstructionCacheEntry] = {}

        logger.info(f"Ryumem Client initialized (server: {self.base_url})")

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _post(self, endpoint: str, json: Dict = None) -> Any:
        url = f"{self.base_url}{endpoint}"
        response = requests.post(url, json=json, headers=self._get_headers())
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"API POST request failed for {endpoint}: {e}")
            if not self.config.tool_tracking.ignore_errors:
                raise
            return None

    def _get(self, endpoint: str, params: Dict = None) -> Any:
        url = f"{self.base_url}{endpoint}"
        response = requests.get(url, params=params, headers=self._get_headers())
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"API GET request failed for {endpoint}: {e}")
            if not self.config.tool_tracking.ignore_errors:
                raise
            return None

    def _patch(self, endpoint: str, json: Dict = None) -> Any:
        url = f"{self.base_url}{endpoint}"
        response = requests.patch(url, json=json, headers=self._get_headers())
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"API PATCH request failed for {endpoint}: {e}")
            if not self.config.tool_tracking.ignore_errors:
                raise
            return None

    def _delete(self, endpoint: str) -> Any:
        url = f"{self.base_url}{endpoint}"
        response = requests.delete(url, headers=self._get_headers())
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"API DELETE request failed for {endpoint}: {e}")
            if not self.config.tool_tracking.ignore_errors:
                raise
            return None

    # ==================== Configuration ====================

    @property
    def config(self) -> RyumemConfig:
        """
        Get configuration from server, apply overrides, and cache with TTL.

        Priority: User overrides > Server config > Defaults

        Server config is refetched based on TTL. User overrides are always
        applied on top of the fetched config, so overridden fields never change
        while non-overridden fields refresh from server.

        Returns:
            RyumemConfig with merged configuration
        """
        import time

        # Check cache validity (always check TTL)
        if self._config_cache is not None and self._config_cache_time is not None:
            age = time.time() - self._config_cache_time
            if age < self._config_ttl:
                logger.debug(f"Using cached config (age: {age:.1f}s)")
                return self._config_cache

        # Fetch server config
        try:
            logger.debug("Fetching config from server...")
            config_data = self._get("/config")
            server_config = RyumemConfig(**config_data)
            logger.info("Config fetched from server successfully")
        except Exception as e:
            logger.warning(f"Failed to fetch config from server: {e}. Using defaults.")
            server_config = RyumemConfig()

        # Apply user overrides on top (they always win)
        merged_config = self._merge_config_overrides(server_config)

        # Cache the merged result
        self._config_cache = merged_config
        self._config_cache_time = time.time()

        return merged_config

    def _merge_config_overrides(self, base_config: RyumemConfig) -> RyumemConfig:
        """Merge user overrides on top of base config."""
        config_dict = base_config.model_dump(exclude_none=True)

        # Deep merge overrides
        for section, overrides in self._config_overrides.items():
            if section in config_dict and overrides:
                config_dict[section].update(overrides)

        return RyumemConfig(**config_dict)

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

                # Handle kind enum conversion
                if "kind" in data and isinstance(data["kind"], str):
                    from ryumem.core.models import EpisodeKind
                    data["kind"] = EpisodeKind.from_str(data["kind"])

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

    def get_triggered_episodes(
        self,
        source_uuid: str,
        source_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[EpisodeNode]:
        """
        Get episodes linked from a source episode via TRIGGERED relationships.

        Args:
            source_uuid: UUID of the source episode
            source_type: Optional filter by episode source type (e.g., 'json')
            limit: Maximum number of episodes to return

        Returns:
            List of triggered episode nodes
        """
        params = {"limit": limit}
        if source_type:
            params["source_type"] = source_type

        data = self._get(f"/episodes/{source_uuid}/triggered", params=params)
        return [EpisodeNode(**episode_data) for episode_data in data]

    def get_config(self) -> RyumemConfig:
        """
        Fetch the current configuration from the server.
        
        Returns:
            RyumemConfig object
        """
        response = self.client.get(f"{self.base_url}/config", headers=self.headers)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch config: {response.text}")
            
        config_data = response.json()
        return RyumemConfig(**config_data)

    def add_episode(
        self,
        content: str,
        user_id: str,
        session_id: str,
        agent_id: Optional[str] = None,
        source: str = "text",
        kind: str = "query",
        metadata: Optional[Dict] = None,
        extract_entities: Optional[bool] = None,
        enable_embeddings: Optional[bool] = None,
        deduplication_enabled: Optional[bool] = None,
    ) -> str:
        """Add a new episode."""
        # Apply config default if not provided
        if extract_entities is None:
            extract_entities = self.config.entity_extraction.enabled

        payload = {
            "content": content,
            "user_id": user_id,
            "session_id": session_id,
            "source": source,
            "kind": kind,
            "metadata": metadata,
            "extract_entities": extract_entities,
            "enable_embeddings": enable_embeddings,
            "deduplication_enabled": deduplication_enabled,
        }
        response = self._post("/episodes", json=payload)

        # Handle correct response format (expected)
        if "episode_id" in response:
            return response["episode_id"]

        # Handle alternate single-object formats
        if "uuid" in response:
            return response["uuid"]
        if "id" in response:
            return response["id"]

        # Server bug workaround: POST returning GET response (paginated list)
        # This happens when server routing is misconfigured
        if "episodes" in response and isinstance(response["episodes"], list):
            if len(response["episodes"]) > 0:
                episode = response["episodes"][0]
                return episode.get("uuid") or episode.get("id") or episode.get("episode_id")
            else:
                # Empty list means episode wasn't created - try with PUT instead
                logger.warning("POST /episodes returned empty list, trying PUT")
                try:
                    put_response = self._patch(f"/episodes/{session_id}", json=payload)
                    if "uuid" in put_response:
                        return put_response["uuid"]
                except:
                    pass

                # Last resort: create via direct database call
                # For now, just raise error
                raise ValueError(
                    f"Failed to create episode: POST /episodes returned empty list. "
                    f"Server may have routing issue or episode already exists for session_id={session_id}"
                )

        logger.error(f"Unexpected response format from /episodes: {response}")
        raise KeyError(f"Response missing episode identifier. Got keys: {list(response.keys())}")

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

    def batch_save_tools(self, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Batch save multiple tools via API.

        Args:
            tools: List of tool dicts, each containing:
                - tool_name: str
                - description: str
                - name_embedding: List[float] (optional)

        Returns:
            Dict with statistics:
                - saved: int (number of new tools created)
                - updated: int (number of existing tools updated)
                - failed: int (number of tools that failed)
                - errors: List[str] (error messages if any)
        """
        response = self._post("/tools/batch", json={"tools": tools})
        return response

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
        strategy: Optional[str] = None,
        similarity_threshold: Optional[float] = None,
        max_depth: int = 2,
        min_rrf_score: Optional[float] = None,
        min_bm25_score: Optional[float] = None,
        rrf_k: Optional[int] = None,
        kinds: Optional[List[str]] = None,
    ) -> SearchResult:
        """Search the memory system."""
        # Apply config defaults
        if strategy is None:
            strategy = self.config.tool_tracking.similarity_strategy
        if similarity_threshold is None:
            similarity_threshold = self.config.tool_tracking.similarity_threshold

        payload = {
            "query": query,
            "user_id": user_id,
            "limit": limit,
            "strategy": strategy,
            "similarity_threshold": similarity_threshold,
            "max_depth": max_depth,
            "min_rrf_score": min_rrf_score,
            "min_bm25_score": min_bm25_score,
            "rrf_k": rrf_k,
            "kinds": kinds,
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

        # Parse episodes into EpisodeNode objects
        episodes = []
        for ep in response.get("episodes", []):
            episodes.append(EpisodeNode(
                uuid=ep["uuid"],
                name=ep.get("name", ""),
                content=ep["content"],
                source=EpisodeType.from_str(ep.get("source", "text")),
                source_description=ep.get("source_description", ""),
                user_id=ep.get("user_id"),
                agent_id=ep.get("agent_id"),
                metadata=ep.get("metadata") or {}  # Handle None metadata
            ))
            if ep.get("uuid"):
                scores[ep["uuid"]] = ep.get("score", 0.0)

        return SearchResult(
            entities=entities,
            edges=edges,
            scores=scores,
            episodes=episodes
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
        memory_enabled: Optional[bool] = None,
        tool_tracking_enabled: Optional[bool] = None,
    ) -> str:
        """
        Register or update an agent by its base instruction.

        Args:
            base_instruction: The agent's original instruction text (used as unique key)
            agent_type: Type of agent (e.g., "google_adk", "custom_agent")
            enhanced_instruction: Instruction with memory/tool guidance added
            query_augmentation_template: Template for query augmentation
            memory_enabled: Whether memory features are enabled (defaults to config)
            tool_tracking_enabled: Whether tool tracking is enabled (defaults to config)

        Returns:
            UUID of the agent instruction record
        """
        # Apply config defaults
        if memory_enabled is None:
            memory_enabled = self.config.agent.memory_enabled
        if tool_tracking_enabled is None:
            tool_tracking_enabled = self.config.tool_tracking.track_tools

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
    ) -> Optional[str]:
        """
        Get instruction text by key (stored in original_user_request field).

        Args:
            instruction_text: The key to search for (stored in original_user_request)
            agent_type: Type of agent (e.g., "google_adk")

        Returns:
            The instruction text if found, None otherwise
        """
        try:
            params = {
                "instruction_text": instruction_text,
                "agent_type": agent_type,
            }
            response = self._get("/agent-instructions/by-text", params=params)
            return response.get("instruction_text")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def clear_instruction_cache(self) -> None:
        """Clear the instruction cache. Useful after updating instructions via API."""
        self._instruction_cache.clear()
        logger.debug("Instruction cache cleared")

    def list_agent_instructions(
        self,
        agent_type: Optional[str] = None,
        current_instruction: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """
        List all agent instructions with optional filters and resolution logic.

        If current_instruction is provided, the server will check if it matches
        any stored base_instruction and return the appropriate instruction (from DB
        or enhanced version of current).

        Results are cached with TTL using the same timeout as config cache.

        Args:
            agent_type: Optional filter by agent type
            current_instruction: Optional instruction to resolve/enhance
            limit: Maximum number of instructions to return

        Returns:
            List of instruction dictionaries ordered by creation date (newest first)
        """
        import time
        import hashlib

        # Create cache key from agent_type and current_instruction
        cache_key = f"{agent_type or 'all'}:{hashlib.sha256((current_instruction or '').encode()).hexdigest()}"

        # Check cache validity
        if cache_key in self._instruction_cache:
            cache_entry = self._instruction_cache[cache_key]
            age = time.time() - cache_entry.timestamp
            if age < self._config_ttl:
                logger.debug(f"Using cached instruction (age: {age:.1f}s)")
                return [cache_entry.data] if cache_entry.data else []

        # Fetch from server
        params = {"limit": limit}
        if agent_type:
            params["agent_type"] = agent_type
        if current_instruction:
            params["current_instruction"] = current_instruction

        response = self._get("/agent-instructions", params=params)

        # Cache the first result (since we typically use limit=1 and only need first item)
        if response and len(response) > 0:
            self._instruction_cache[cache_key] = InstructionCacheEntry(
                data=response[0],
                timestamp=time.time()
            )
            logger.debug(f"Cached instruction for key: {cache_key[:32]}...")

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

    def reset_database(self) -> Dict[str, str]:
        """
        Reset the entire database - delete all nodes and relationships.

        WARNING: This is irreversible! All data will be permanently deleted.
        Useful for test cleanup.

        Returns:
            Response dict with status and message
        """
        return self._delete("/database/reset")
