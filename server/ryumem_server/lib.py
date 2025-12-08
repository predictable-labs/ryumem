"""
Ryumem - Bi-temporal Knowledge Graph Memory System
Main class providing the public API.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from ryumem_server.core.config import RyumemConfig
from ryumem_server.core.graph_db import RyugraphDB
from ryumem_server.core.models import EpisodeNode, EpisodeType, SearchConfig, SearchResult
from ryumem_server.ingestion.episode import EpisodeIngestion
from ryumem_server.maintenance.pruner import MemoryPruner
from ryumem_server.retrieval.search import SearchEngine
from ryumem_server.utils.embeddings import EmbeddingClient
from ryumem_server.utils.llm import LLMClient
from ryumem_server.utils.llm_ollama import OllamaClient
from ryumem_server.utils.llm_gemini import GeminiClient
from ryumem_server.utils.llm_litellm import LiteLLMClient

logger = logging.getLogger(__name__)


class Ryumem:
    """
    Ryumem - Bi-temporal Knowledge Graph Memory System.

    A memory system using ryugraph as the graph database layer.

    Features:
    - Episode-first ingestion
    - Entity and relationship extraction
    - Bi-temporal data model (valid_at, invalid_at, expired_at)
    - Hybrid retrieval (semantic + graph traversal)
    - Full multi-tenancy support
    - Automatic contradiction detection and resolution
    """

    def __init__(
        self,
        config: Optional[RyumemConfig] = None,
        db_path: Optional[str] = None,
    ):
        """
        Initialize Ryumem instance.

        Args:
            config: RyumemConfig instance (if not provided, loads from env)
            db_path: Optional override for database path

        Example:
            # From environment variables (.env file)
            ryumem = Ryumem()

            # With config object
            config = RyumemConfig()
            ryumem = Ryumem(config=config)

            # With custom config
            config = RyumemConfig()
            config.database.db_path = "./data/custom.db"
            config.llm.provider = "openai"
            config.llm.model = "gpt-4o-mini"
            ryumem = Ryumem(config=config)
            
            # With explicit db_path (overrides config)
            ryumem = Ryumem(db_path="./data/customer_1.db")
        """
        # Load or create config
        if config is None:
            # Load from environment by default
            config = RyumemConfig()

        # Override db_path if provided
        if db_path:
            config.database.db_path = db_path

        self.config = config

        # Ensure database directory exists
        db_path_obj = Path(config.database.db_path)
        db_path_obj.parent.mkdir(parents=True, exist_ok=True)

        # Validate API keys are present for configured providers
        config.validate_api_keys()

        # Initialize core components
        logger.info("Initializing Ryumem...")
        logger.info(f"DEBUG: db_path={config.database.db_path}")

        self.db = RyugraphDB(
            db_path=config.database.db_path,
            embedding_dimensions=config.embedding.dimensions,
        )

        # Initialize ConfigService and load configs
        from ryumem_server.core.config_service import ConfigService
        self.config_service = ConfigService(self.db)

        # Load config from database (uses Pydantic defaults if DB is empty)
        # This ensures we use the database as the source of truth
        db_config = self.config_service.load_config_from_database()
        
        # Merge DB config with runtime overrides (like db_path)
        # We keep the db_path from the initial config as it's not stored in DB
        db_config.database.db_path = config.database.db_path
        self.config = db_config

        # Initialize LLM client based on provider
        if config.llm.provider == "litellm":
            logger.info(f"Using LiteLLM for LLM inference: {config.llm.model}")
            self.llm_client = LiteLLMClient(
                model=config.llm.model,
                max_retries=config.llm.max_retries,
                timeout=config.llm.timeout_seconds,
            )
        elif config.llm.provider == "ollama":
            logger.info(f"Using Ollama for LLM inference: {config.llm.model}")
            self.llm_client = OllamaClient(
                model=config.llm.model,
                base_url=config.llm.ollama_base_url,
                max_retries=config.llm.max_retries,
                timeout=config.llm.timeout_seconds,
            )
        elif config.llm.provider == "gemini":
            if not config.llm.gemini_api_key:
                raise ValueError("gemini_api_key is required when llm_provider='gemini'")
            logger.info(f"Using Gemini for LLM inference: {config.llm.model}")
            self.llm_client = GeminiClient(
                api_key=config.llm.gemini_api_key,
                model=config.llm.model,
                max_retries=config.llm.max_retries,
                timeout=config.llm.timeout_seconds,
            )
        else:  # openai
            if not config.llm.openai_api_key:
                raise ValueError("openai_api_key is required when llm_provider='openai'")
            logger.info(f"Using OpenAI for LLM inference: {config.llm.model}")
            self.llm_client = LLMClient(
                api_key=config.llm.openai_api_key,
                model=config.llm.model,
                max_retries=config.llm.max_retries,
                timeout=config.llm.timeout_seconds,
            )

        # Initialize embedding client based on provider
        if config.embedding.provider == "ollama":
            logger.info(f"Using Ollama for embeddings: {config.embedding.model}")
            self.embedding_client = OllamaClient(
                model=config.embedding.model,
                base_url=config.embedding.ollama_base_url,
                timeout=config.embedding.timeout_seconds,
            )
        elif config.embedding.provider == "litellm":
            logger.info(f"Using LiteLLM for embeddings: {config.embedding.model}")
            self.embedding_client = LiteLLMClient(
                model=config.embedding.model,
                max_retries=config.llm.max_retries,
                timeout=config.embedding.timeout_seconds,
            )
        elif config.embedding.provider == "gemini":
            if not config.llm.gemini_api_key:
                raise ValueError("gemini_api_key is required when embedding_provider='gemini'")
            logger.info(f"Using Gemini for embeddings: {config.embedding.model}")
            # Use GeminiClient for embeddings
            self.embedding_client = GeminiClient(
                api_key=config.llm.gemini_api_key,
                model=config.embedding.model,
                max_retries=config.llm.max_retries,
                timeout=config.embedding.timeout_seconds,
            )
        else:  # openai
            if not config.llm.openai_api_key:
                raise ValueError("openai_api_key is required when embedding_provider='openai'")
            logger.info(f"Using OpenAI for embeddings: {config.embedding.model}")
            self.embedding_client = EmbeddingClient(
                api_key=config.llm.openai_api_key,
                model=config.embedding.model,
                dimensions=config.embedding.dimensions,
                batch_size=config.embedding.batch_size,
                timeout=config.embedding.timeout_seconds,
            )

        # Initialize search engine first (creates BM25 index)
        self.search_engine = SearchEngine(
            db=self.db,
            embedding_client=self.embedding_client,
        )

        # Try to load existing BM25 index from disk
        bm25_path = str(db_path_obj.parent / f"{db_path_obj.stem}_bm25.pkl")
        if self.search_engine.bm25_index.load(bm25_path):
            logger.info(f"Loaded BM25 index from {bm25_path}")
            # Check if index is empty but database has data - rebuild if needed
            stats = self.search_engine.bm25_index.stats()
            if stats["entity_count"] == 0 and stats["edge_count"] == 0:
                logger.info("BM25 index is empty, rebuilding from database...")
                self._rebuild_bm25_index()
        else:
            logger.info("No existing BM25 index found, will rebuild from database if needed")

        # Initialize ingestion pipeline with BM25 index
        self.ingestion = EpisodeIngestion(
            db=self.db,
            llm_client=self.llm_client,
            embedding_client=self.embedding_client,
            entity_similarity_threshold=config.entity_extraction.entity_similarity_threshold,
            relationship_similarity_threshold=config.entity_extraction.relationship_similarity_threshold,
            max_context_episodes=config.entity_extraction.max_context_episodes,
            bm25_index=self.search_engine.bm25_index,
            enable_entity_extraction=config.entity_extraction.enabled,
            episode_similarity_threshold=config.entity_extraction.episode_similarity_threshold,
            episode_deduplication_time_window_hours=config.entity_extraction.episode_deduplication_time_window_hours,
        )

        # Initialize memory pruner
        self.memory_pruner = MemoryPruner(db=self.db)

        logger.info(f"Ryumem initialized successfully (db: {config.database.db_path})")

    def add_episode(
        self,
        content: str,
        user_id: str,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        source: str = "text",
        kind: str = "query",
        metadata: Optional[Dict] = None,
        extract_entities: Optional[bool] = None,
    ) -> str:
        """
        Add a new episode to the memory system.

        This is the main ingestion method. It will:
        1. Create an episode node
        2. Extract entities and resolve against existing (if enabled)
        3. Extract relationships and resolve against existing (if enabled)
        4. Create MENTIONS edges (if entities extracted)
        5. Detect and invalidate contradicting facts (if enabled)
        6. Update entity summaries (if enabled)

        Args:
            content: Episode content (text, message, or JSON)
            user_id: User ID (required)
            agent_id: Optional agent ID
            session_id: Optional session ID
            source: Type of episode ("text", "message", or "json")
            metadata: Optional metadata dictionary
            extract_entities: Override config setting for entity extraction (None uses config default)

        Returns:
            UUID of the created episode

        Example:
            episode_id = ryumem.add_episode(
                content="Alice works at Google in Mountain View",
                user_id="user_123",
                source="text",
                extract_entities=False,  # Skip entity extraction for this episode
            )
        """
        # Convert source string to EpisodeType
        source_type = EpisodeType.from_str(source)

        # Convert kind string to EpisodeKind
        from ryumem_server.core.models import EpisodeKind
        kind_enum = EpisodeKind.from_str(kind)

        episode_id = self.ingestion.ingest(
            content=content,
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            source=source_type,
            kind=kind_enum,
            metadata=metadata,
            extract_entities=extract_entities,
        )

        # Persist BM25 index to disk after ingestion
        bm25_path = str(Path(self.config.database.db_path).parent / f"{Path(self.config.database.db_path).stem}_bm25.pkl")
        self.search_engine.bm25_index.save(bm25_path)

        return episode_id

    def add_episodes_batch(
        self,
        episodes: List[Dict],
        user_id: str,
    ) -> List[str]:
        """
        Add multiple episodes in batch.

        Args:
            episodes: List of episode dictionaries with keys:
                - content: Episode content (required)
                - agent_id: Optional agent ID
                - session_id: Optional session ID
                - source: Optional source type
                - metadata: Optional metadata
            user_id: User ID (required)

        Returns:
            List of episode UUIDs

        Example:
            episodes = [
                {"content": "Alice works at Google"},
                {"content": "Bob lives in San Francisco"},
            ]
            episode_ids = ryumem.add_episodes_batch(episodes, user_id="user_123")
        """
        episode_ids = self.ingestion.ingest_batch(episodes, user_id)

        # Persist BM25 index to disk after batch ingestion
        bm25_path = str(Path(self.config.database.db_path).parent / f"{Path(self.config.database.db_path).stem}_bm25.pkl")
        self.search_engine.bm25_index.save(bm25_path)

        return episode_ids

    def get_episode_by_uuid(self, episode_uuid: str) -> Optional[Dict]:
        """
        Get a single episode by its UUID.

        Args:
            episode_uuid: UUID of the episode

        Returns:
            Episode dictionary or None if not found

        Example:
            episode = ryumem.get_episode_by_uuid("64b0c94c-8653-434a-8c41-414053f87eba")
            if episode:
                print(f"Content: {episode['content']}")
        """
        return self.db.get_episode_by_uuid(episode_uuid)

    def update_episode_metadata(self, episode_uuid: str, metadata: Dict) -> Dict:
        """
        Update metadata for an existing episode.

        Args:
            episode_uuid: UUID of the episode
            metadata: New metadata dictionary to set

        Returns:
            Result dictionary

        Example:
            ryumem.update_episode_metadata(
                episode_uuid="64b0c94c-8653-434a-8c41-414053f87eba",
                metadata={"session_id": "1234", "runs": [...]}
            )
        """
        return self.db.update_episode_metadata(episode_uuid, metadata)

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
            source_type: Optional filter by episode source type
            limit: Maximum number of episodes to return

        Returns:
            List of triggered episode nodes
        """
        return self.db.get_triggered_episodes(source_uuid, source_type, limit)

    def search(
        self,
        query: str,
        user_id: str,
        limit: int = 10,
        strategy: Optional[str] = None,
        similarity_threshold: Optional[float] = None,
        max_depth: int = 2,
        min_rrf_score: Optional[float] = None,
        min_bm25_score: Optional[float] = None,
        rrf_k: Optional[int] = None,
        kinds: Optional[List[str]] = None,
    ) -> SearchResult:
        """
        Search the memory system.

        Args:
            query: Search query text
            user_id: User ID (required)
            limit: Maximum number of results (default: 10)
            strategy: Search strategy - "semantic", "traversal", or "hybrid" (default: "hybrid")
            similarity_threshold: Minimum similarity threshold (default: from config)
            max_depth: Maximum depth for graph traversal (default: 2)
            min_rrf_score: Minimum RRF score threshold for hybrid search (default: 0.025)
            min_bm25_score: Minimum BM25 score threshold for keyword search (default: 0.1)
            rrf_k: RRF constant for hybrid search (default: 60)

        Returns:
            SearchResult with entities, edges, and scores

        Example:
            results = ryumem.search(
                query="Tell me about Alice",
                user_id="user_123",
                strategy="hybrid",
                limit=10,
            )

            for entity in results.entities:
                print(f"Entity: {entity.name} ({entity.entity_type})")
                print(f"Score: {results.scores.get(entity.uuid, 0.0):.3f}")
        """
        # Use default threshold from config if not provided
        if similarity_threshold is None:
            similarity_threshold = self.config.entity_extraction.entity_similarity_threshold

        # Create search config
        config = SearchConfig(
            query=query,
            user_id=user_id,
            limit=limit,
            strategy=strategy,
            similarity_threshold=similarity_threshold,
            max_depth=max_depth,
            kinds=kinds,
        )

        # Override with explicit parameters if provided
        if min_rrf_score is not None:
            config.min_rrf_score = min_rrf_score
        if min_bm25_score is not None:
            config.min_bm25_score = min_bm25_score
        if rrf_k is not None:
            config.rrf_k = rrf_k

        return self.search_engine.search(config)

    def get_entity_context(
        self,
        entity_name: str,
        user_id: str,
        max_depth: int = 2,
    ) -> Dict:
        """
        Get comprehensive context for an entity by name.

        Args:
            entity_name: Name of the entity
            user_id: User ID (required)
            max_depth: Maximum traversal depth

        Returns:
            Dictionary with entity details and relationships

        Example:
            context = ryumem.get_entity_context(
                entity_name="Alice",
                user_id="user_123",
            )
        """
        # Find entity by name
        entity = self.ingestion.entity_extractor.get_entity_by_name(
            name=entity_name,
            user_id=user_id,
        )

        if not entity:
            return {}

        # Get context
        return self.search_engine.get_entity_context(
            entity_uuid=entity.uuid,
            max_depth=max_depth,
        )

    # Tool Analytics Methods

    def get_all_tools(self) -> List[Dict]:
        """
        Get all registered tools.

        Returns:
            List of tool dictionaries with name and description

        Example:
            tools = ryumem.get_all_tools()
            # Returns: [{"tool_name": "search_database", "description": "...", ...}]
        """
        return self.db.get_all_tools()

    def get_tool_success_rate(
        self,
        tool_name: str,
        user_id: Optional[str] = None,
        min_executions: int = 1,
    ) -> Dict:
        """
        Get success rate and performance metrics for a specific tool.

        Args:
            tool_name: Name of the tool
            user_id: Optional user ID for filtering
            min_executions: Minimum number of executions required

        Returns:
            Dictionary with success rate, usage count, and performance metrics

        Example:
            metrics = ryumem.get_tool_success_rate(
                tool_name="web_search",
                user_id="user_123"
            )
            # Returns: {"success_rate": 0.95, "usage_count": 100, "avg_duration_ms": 250, ...}
        """
        import json
        from ryumem_server.core.metadata_models import EpisodeMetadata

        # Query query episodes (source='message') and extract tools_used from metadata
        query = """
        MATCH (e:Episode)
        WHERE e.source = 'message'
          AND e.metadata IS NOT NULL
        """

        params = {}

        if user_id:
            query += " AND e.user_id = $user_id"
            params["user_id"] = user_id

        query += " RETURN e.metadata AS metadata"

        result = self.db.conn.execute(query, params)

        stats = {
            'tool_name': tool_name,
            'usage_count': 0,
            'success_count': 0,
            'failure_count': 0,
            'total_duration_ms': 0,
            'recent_errors': [],
        }

        # Aggregate statistics using EpisodeMetadata methods
        while result.has_next():
            metadata_str = result.get_next()[0]
            if not metadata_str:
                continue

            metadata_dict = json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str

            # Parse into Pydantic model
            try:
                episode_metadata = EpisodeMetadata(**metadata_dict)
                episode_stats = episode_metadata.get_tool_stats(tool_name)

                # Aggregate into overall stats
                stats['usage_count'] += episode_stats['usage_count']
                stats['success_count'] += episode_stats['success_count']
                stats['failure_count'] += episode_stats['failure_count']
                stats['total_duration_ms'] += episode_stats['total_duration_ms']
                stats['recent_errors'].extend(episode_stats['recent_errors'][:5 - len(stats['recent_errors'])])
            except Exception:
                # Skip episodes that don't match the new structure
                continue

        # Calculate derived metrics
        if stats['usage_count'] >= min_executions:
            stats['success_rate'] = stats['success_count'] / stats['usage_count']
            stats['avg_duration_ms'] = stats['total_duration_ms'] / stats['usage_count']
        else:
            stats['success_rate'] = 0.0
            stats['avg_duration_ms'] = 0

        del stats['success_count']
        del stats['total_duration_ms']

        return stats

    def get_user_tool_preferences(
        self,
        user_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        """
        Get tools most frequently used by a specific user.

        Args:
            user_id: Optional user ID to filter by
            limit: Maximum number of tools to return

        Returns:
            List of tool usage dictionaries sorted by frequency

        Example:
            preferences = ryumem.get_user_tool_preferences(
                user_id="alice"
            )
            # Returns: [{"tool_name": "web_search", "usage_count": 50, ...}, ...]
        """
        import json
        from ryumem_server.core.metadata_models import EpisodeMetadata

        # Query query episodes (source='message') and extract tools_used from metadata
        query = """
            MATCH (e:Episode)
            WHERE e.source = 'message'
              AND e.metadata IS NOT NULL
        """

        params = {}

        if user_id:
            query += " AND e.user_id = $user_id"
            params["user_id"] = user_id

        query += " RETURN e.metadata"

        result = self.db.conn.execute(query, params)

        tool_usage = {}

        while result.has_next():
            metadata_str = result.get_next()[0]
            if not metadata_str:
                continue

            metadata_dict = json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str

            # Parse into Pydantic model and get tool usage
            try:
                episode_metadata = EpisodeMetadata(**metadata_dict)
                episode_tool_usage = episode_metadata.get_all_tool_usage()

                # Merge into overall tool_usage
                for tool_name, usage in episode_tool_usage.items():
                    if tool_name not in tool_usage:
                        tool_usage[tool_name] = {
                            'tool_name': tool_name,
                            'usage_count': 0,
                            'success_count': 0,
                        }

                    tool_usage[tool_name]['usage_count'] += usage['usage_count']
                    tool_usage[tool_name]['success_count'] += usage['success_count']
            except Exception:
                # Skip episodes that don't match the new structure
                continue

        # Calculate success rates and format
        result_list = []
        for usage in tool_usage.values():
            usage['success_rate'] = (
                usage['success_count'] / usage['usage_count']
                if usage['usage_count'] > 0 else 0.0
            )
            del usage['success_count']
            result_list.append(usage)

        # Sort by usage count
        result_list.sort(key=lambda x: x['usage_count'], reverse=True)

        return result_list[:limit]

    def get_instruction_by_text(
        self,
        instruction_text: str,
        agent_type: str,
        instruction_type: str,
    ) -> Optional[str]:
        """
        Get instruction by key (original_user_request).

        This method uses original_user_request as a lookup key to retrieve
        the actual instruction_text from the database.

        Args:
            instruction_text: The key to search for (stored in original_user_request)
            agent_type: Type of agent (e.g., "google_adk")
            instruction_type: Type of instruction (e.g., "memory_usage", "tool_tracking")

        Returns:
            The instruction_text content if found, None otherwise
        """
        logger.info(f"[DB] get_instruction_by_text called: key={instruction_text}, agent_type={agent_type}, instruction_type={instruction_type}")

        query = """
        MATCH (i:AgentInstruction)
        WHERE i.original_user_request = $instruction_text
          AND i.agent_type = $agent_type
          AND i.instruction_type = $instruction_type
        RETURN i.instruction_text AS instruction_text
        ORDER BY i.created_at DESC
        LIMIT 1
        """

        result = self.db.execute(query, {
            "instruction_text": instruction_text,
            "agent_type": agent_type,
            "instruction_type": instruction_type
        })

        if result and len(result) > 0:
            logger.info(f"[DB] Found instruction with key '{instruction_text}'")
            return result[0]["instruction_text"]

        logger.info(f"[DB] No instruction found for key '{instruction_text}'")
        return None

    def save_agent_instruction(
        self,
        base_instruction: str,
        agent_type: str = "google_adk",
        enhanced_instruction: Optional[str] = None,
        query_augmentation_template: Optional[str] = None,
        memory_enabled: bool = True,
        tool_tracking_enabled: bool = False,
    ) -> str:
        """
        Register or update an agent by its base instruction.

        Uses base_instruction as the unique key. MERGE behavior means this will
        update existing agent records instead of creating duplicates.

        Args:
            base_instruction: The agent's original instruction text (used as unique key)
            agent_type: Type of agent (e.g., "google_adk", "custom_agent")
            enhanced_instruction: Instruction with memory/tool guidance added
            query_augmentation_template: Template for query augmentation
            memory_enabled: Whether memory features are enabled
            tool_tracking_enabled: Whether tool tracking is enabled

        Returns:
            UUID of the agent instruction record

        Example:
            instruction_id = ryumem.save_agent_instruction(
                base_instruction="You are a helpful assistant.",
                enhanced_instruction="You are a helpful assistant.\n\nMEMORY USAGE:...",
                query_augmentation_template="[Previous Attempt]...",
                memory_enabled=True
            )
        """
        import uuid
        from datetime import datetime

        logger.info(f"[DB] save_agent_instruction called: agent_type={agent_type}")

        # First, try to find existing agent - only return uuid to avoid property errors
        find_query = """
        MATCH (i:AgentInstruction)
        WHERE i.agent_type = $agent_type
        RETURN i.uuid AS uuid
        LIMIT 1
        """

        try:
            existing = self.db.execute(find_query, {"agent_type": agent_type})
        except Exception as e:
            # If query fails, assume no existing nodes
            logger.warning(f"[DB] Could not query existing agents: {e}")
            existing = []

        instruction_id = str(uuid.uuid4())

        if existing and len(existing) > 0:
            # Update existing agent (migrate to new schema)
            instruction_id = existing[0].get("uuid", instruction_id)
            logger.info(f"[DB] Migrating existing agent instruction: {instruction_id}")

            # Update existing agent with new properties
            update_query = """
            MATCH (i:AgentInstruction {uuid: $uuid})
            SET i.base_instruction = $base_instruction,
                i.enhanced_instruction = $enhanced_instruction,
                i.query_augmentation_template = $query_augmentation_template,
                i.memory_enabled = $memory_enabled,
                i.tool_tracking_enabled = $tool_tracking_enabled,
                i.updated_at = $updated_at
            RETURN i.uuid AS uuid
            """
            result = self.db.execute(update_query, {
                "uuid": instruction_id,
                "base_instruction": base_instruction,
                "enhanced_instruction": enhanced_instruction or base_instruction,
                "query_augmentation_template": query_augmentation_template or "",
                "memory_enabled": memory_enabled,
                "tool_tracking_enabled": tool_tracking_enabled,
                "updated_at": datetime.utcnow(),
            })
            logger.info(f"[DB] Migrated agent to new schema: {instruction_id}")
        else:
            # Create new agent with new schema
            create_query = """
            CREATE (i:AgentInstruction {
                uuid: $uuid,
                base_instruction: $base_instruction,
                agent_type: $agent_type,
                enhanced_instruction: $enhanced_instruction,
                query_augmentation_template: $query_augmentation_template,
                memory_enabled: $memory_enabled,
                tool_tracking_enabled: $tool_tracking_enabled,
                created_at: $created_at,
                updated_at: $updated_at
            })
            RETURN i.uuid AS uuid
            """
            result = self.db.execute(create_query, {
                "uuid": instruction_id,
                "base_instruction": base_instruction,
                "agent_type": agent_type,
                "enhanced_instruction": enhanced_instruction or base_instruction,
                "query_augmentation_template": query_augmentation_template or "",
                "memory_enabled": memory_enabled,
                "tool_tracking_enabled": tool_tracking_enabled,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            })
            logger.info(f"[DB] Created new agent instruction: {instruction_id}")
        logger.info(f"[DB] ✓ Instruction saved successfully with ID: {instruction_id}")

        return instruction_id

    def list_agent_instructions(
        self,
        agent_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        List all registered agent configurations.

        Args:
            agent_type: Optional filter by agent type
            limit: Maximum number of instructions to return

        Returns:
            List of agent configuration dictionaries

        Example:
            agents = ryumem.list_agent_instructions(agent_type="google_adk")
            for agent in agents:
                print(f"Agent: {agent['base_instruction'][:50]}...")
        """
        logger.info(f"[DB] list_agent_instructions called: agent_type={agent_type}, limit={limit}")

        # Build query
        query = "MATCH (i:AgentInstruction) WHERE true"
        params = {}

        if agent_type:
            query += " AND i.agent_type = $agent_type"
            params["agent_type"] = agent_type

        query += """
        RETURN i.uuid AS instruction_id,
               i.base_instruction AS base_instruction,
               i.enhanced_instruction AS enhanced_instruction,
               i.query_augmentation_template AS query_augmentation_template,
               i.agent_type AS agent_type,
               i.memory_enabled AS memory_enabled,
               i.tool_tracking_enabled AS tool_tracking_enabled,
               i.created_at AS created_at,
               i.updated_at AS updated_at
        ORDER BY i.updated_at DESC
        LIMIT $limit
        """

        params["limit"] = limit

        logger.info(f"[DB] Executing query with params: {params}")
        result = self.db.execute(query, params)
        logger.info(f"[DB] Query returned {len(result)} result(s)")

        # Format results
        formatted_results = []
        for row in result:
            logger.info(f"[DB]   - Found agent: id={row['instruction_id']}, type={row['agent_type']}")
            formatted_results.append({
                "instruction_id": row["instruction_id"],
                "base_instruction": row["base_instruction"],
                "enhanced_instruction": row["enhanced_instruction"],
                "query_augmentation_template": row["query_augmentation_template"],
                "agent_type": row["agent_type"],
                "memory_enabled": row["memory_enabled"],
                "tool_tracking_enabled": row["tool_tracking_enabled"],
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
            })

        logger.info(f"[DB] Returning {len(formatted_results)} formatted agent(s)")
        return formatted_results

    def prune_memories(
        self,
        user_id: str,
        expired_cutoff_days: int = 90,
        min_mentions: int = 2,
        min_age_days: int = 30,
        compact_redundant: bool = True,
        similarity_threshold: float = 0.95,
    ) -> Dict[str, int]:
        """
        Prune and compact memories to keep the graph efficient.

        This performs:
        - Delete facts that were invalidated/expired long ago
        - Remove entities with very few mentions (likely noise)
        - Merge near-duplicate relationship facts

        Should be called periodically to maintain graph health.

        Args:
            user_id: User ID to prune
            expired_cutoff_days: Delete expired edges older than N days (default: 90)
            min_mentions: Minimum mentions for entities to keep (default: 2)
            min_age_days: Minimum age before pruning low-mention entities (default: 30)
            compact_redundant: Whether to merge redundant edges (default: True)
            similarity_threshold: Similarity threshold for merging edges (default: 0.95)

        Returns:
            Dictionary with pruning statistics

        Example:
            # Basic pruning with defaults
            stats = ryumem.prune_memories("user_123")
            print(f"Pruning results: {stats}")

            # Custom pruning parameters
            stats = ryumem.prune_memories(
                "user_123",
                expired_cutoff_days=60,  # More aggressive
                min_mentions=3,  # Higher quality threshold
                compact_redundant=True,
            )
        """
        return self.memory_pruner.prune_all(
            user_id=user_id,
            expired_cutoff_days=expired_cutoff_days,
            min_mentions=min_mentions,
            min_age_days=min_age_days,
            compact_redundant=compact_redundant,
            similarity_threshold=similarity_threshold,
        )

    def delete_user(self, user_id: str) -> None:
        """
        Delete all data for a specific user.

        WARNING: This is irreversible!

        Args:
            user_id: User ID to delete

        Example:
            ryumem.delete_user("user_123")
        """
        self.db.delete_by_user_id(user_id)
        logger.info(f"Deleted all data for user: {user_id}")

    def reset(self) -> None:
        """
        Reset the entire database.

        WARNING: This will delete ALL data irreversibly!

        Example:
            ryumem.reset()
        """
        logger.warning("Resetting entire Ryumem database...")
        self.db.reset()
        logger.info("Database reset complete")

    def _rebuild_bm25_index(self) -> None:
        """
        Rebuild BM25 index from existing database data.

        This is useful when:
        - BM25 index file was lost or corrupted
        - Database was populated before BM25 persistence was added
        - Need to ensure BM25 index is in sync with database
        """
        # Clear existing index
        self.search_engine.bm25_index.clear()

        # Get all entities from database
        all_entities_query = """
        MATCH (e:Entity)
        RETURN
            e.uuid AS uuid,
            e.name AS name,
            e.entity_type AS entity_type,
            e.summary AS summary,
            e.mentions AS mentions
        """
        entities_data = self.db.execute(all_entities_query, {})

        # Rebuild entity index
        from ryumem_server.core.models import EntityNode
        for entity_data in entities_data:
            entity = EntityNode(
                uuid=entity_data["uuid"],
                name=entity_data["name"],
                entity_type=entity_data["entity_type"],
                summary=entity_data.get("summary", ""),
                mentions=entity_data["mentions"],
            )
            self.search_engine.bm25_index.add_entity(entity)

        # Get all edges from database
        all_edges_query = """
        MATCH (s:Entity)-[r:RELATES_TO]->(t:Entity)
        RETURN
            r.uuid AS uuid,
            s.uuid AS source_uuid,
            t.uuid AS target_uuid,
            r.name AS relation_type,
            r.fact AS fact,
            r.mentions AS mentions
        """
        edges_data = self.db.execute(all_edges_query, {})

        # Rebuild edge index
        from ryumem_server.core.models import EntityEdge
        for edge_data in edges_data:
            edge = EntityEdge(
                uuid=edge_data["uuid"],
                source_node_uuid=edge_data["source_uuid"],
                target_node_uuid=edge_data["target_uuid"],
                name=edge_data["relation_type"],
                fact=edge_data["fact"],
                mentions=edge_data["mentions"],
            )
            self.search_engine.bm25_index.add_edge(edge)

        # Save rebuilt index
        bm25_path = str(Path(self.config.database.db_path).parent / f"{Path(self.config.database.db_path).stem}_bm25.pkl")
        self.search_engine.bm25_index.save(bm25_path)

        logger.info(
            f"Rebuilt BM25 index: {len(entities_data)} entities, {len(edges_data)} edges"
        )

    def close(self) -> None:
        """
        Close the database connection.

        Example:
            ryumem.close()
        """
        self.db.close()
        logger.info("Ryumem connection closed")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

    def __repr__(self) -> str:
        """String representation"""
        return f"Ryumem(db_path='{self.config.database.db_path}', model='{self.config.llm.model}')"
