"""
Ryumem - Bi-temporal Knowledge Graph Memory System
Main class providing the public API.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from ryumem.community.detector import CommunityDetector
from ryumem.core.config import RyumemConfig
from ryumem.core.graph_db import RyugraphDB
from ryumem.core.models import EpisodeType, SearchConfig, SearchResult
from ryumem.ingestion.episode import EpisodeIngestion
from ryumem.maintenance.pruner import MemoryPruner
from ryumem.retrieval.search import SearchEngine
from ryumem.utils.embeddings import EmbeddingClient
from ryumem.utils.llm import LLMClient
from ryumem.utils.llm_ollama import OllamaClient
from ryumem.utils.llm_gemini import GeminiClient

logger = logging.getLogger(__name__)


class Ryumem:
    """
    Ryumem - Bi-temporal Knowledge Graph Memory System.

    A memory system that combines the best of mem0 and graphiti,
    using ryugraph as the graph database layer.

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
        db_path: Optional[str] = None,
        config: Optional[RyumemConfig] = None,
        **kwargs,
    ):
        """
        Initialize Ryumem instance.

        Args:
            db_path: Path to ryugraph database (overrides config)
            config: RyumemConfig instance (if not provided, loads from env)
            **kwargs: Additional config parameters to override

        Example:
            # From environment variables
            ryumem = Ryumem()

            # With explicit config
            ryumem = Ryumem(
                db_path="./data/ryumem.db",
                openai_api_key="sk-...",
                llm_model="gpt-4",
            )

            # With config object
            config = RyumemConfig.from_env()
            ryumem = Ryumem(config=config)
        """
        # Load or create config
        if config is None:
            if "openai_api_key" in kwargs or db_path or "read_only" in kwargs:
                # Create config from kwargs
                config_dict = kwargs.copy()
                if db_path:
                    config_dict["db_path"] = db_path
                if "openai_api_key" not in config_dict:
                    config = RyumemConfig.from_env()
                    config_dict["openai_api_key"] = config.openai_api_key
                config = RyumemConfig(**config_dict)
            else:
                # Load from environment
                config = RyumemConfig.from_env()

        self.config = config

        # Ensure database directory exists (skip for read-only mode)
        read_only = getattr(config, 'read_only', False)
        db_path_obj = Path(config.db_path)
        if not read_only:
            db_path_obj.parent.mkdir(parents=True, exist_ok=True)

        # Initialize core components
        logger.info("Initializing Ryumem...")
        logger.info(f"DEBUG: read_only={read_only}, config.read_only={config.read_only}, db_path={config.db_path}")

        self.db = RyugraphDB(
            db_path=config.db_path,
            embedding_dimensions=config.embedding_dimensions,
            read_only=read_only,
        )

        # Initialize LLM client based on provider
        if config.llm_provider == "ollama":
            logger.info(f"Using Ollama for LLM inference: {config.llm_model}")
            self.llm_client = OllamaClient(
                model=config.llm_model,
                base_url=config.ollama_base_url,
                max_retries=config.max_retries,
                timeout=config.timeout_seconds,
            )
        elif config.llm_provider == "gemini":
            if not config.gemini_api_key:
                raise ValueError("gemini_api_key is required when llm_provider='gemini'")
            logger.info(f"Using Gemini for LLM inference: {config.llm_model}")
            self.llm_client = GeminiClient(
                api_key=config.gemini_api_key,
                model=config.llm_model,
                max_retries=config.max_retries,
                timeout=config.timeout_seconds,
            )
        else:  # openai
            if not config.openai_api_key:
                raise ValueError("openai_api_key is required when llm_provider='openai'")
            logger.info(f"Using OpenAI for LLM inference: {config.llm_model}")
            self.llm_client = LLMClient(
                api_key=config.openai_api_key,
                model=config.llm_model,
                max_retries=config.max_retries,
                timeout=config.timeout_seconds,
            )

        # Initialize embedding client based on provider
        if config.embedding_provider == "gemini":
            if not config.gemini_api_key:
                raise ValueError("gemini_api_key is required when embedding_provider='gemini'")
            logger.info(f"Using Gemini for embeddings: {config.embedding_model}")
            # Use GeminiClient for embeddings
            self.embedding_client = GeminiClient(
                api_key=config.gemini_api_key,
                model=config.embedding_model,
                max_retries=config.max_retries,
                timeout=config.timeout_seconds,
            )
        else:  # openai
            if not config.openai_api_key:
                raise ValueError("openai_api_key is required when embedding_provider='openai'")
            logger.info(f"Using OpenAI for embeddings: {config.embedding_model}")
            self.embedding_client = EmbeddingClient(
                api_key=config.openai_api_key,
                model=config.embedding_model,
                dimensions=config.embedding_dimensions,
                batch_size=config.batch_size,
                timeout=config.timeout_seconds,
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
            entity_similarity_threshold=config.entity_similarity_threshold,
            relationship_similarity_threshold=config.relationship_similarity_threshold,
            max_context_episodes=config.max_context_episodes,
            bm25_index=self.search_engine.bm25_index,
        )

        # Initialize community detector
        self.community_detector = CommunityDetector(
            db=self.db,
            llm_client=self.llm_client,
        )

        # Initialize memory pruner
        self.memory_pruner = MemoryPruner(db=self.db)

        logger.info(f"Ryumem initialized successfully (db: {config.db_path})")

    def add_episode(
        self,
        content: str,
        group_id: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        source: str = "text",
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Add a new episode to the memory system.

        This is the main ingestion method. It will:
        1. Create an episode node
        2. Extract entities and resolve against existing
        3. Extract relationships and resolve against existing
        4. Create MENTIONS edges
        5. Detect and invalidate contradicting facts
        6. Update entity summaries

        Args:
            content: Episode content (text, message, or JSON)
            group_id: Group ID for multi-tenancy (required)
            user_id: Optional user ID
            agent_id: Optional agent ID
            session_id: Optional session ID
            source: Type of episode ("text", "message", or "json")
            metadata: Optional metadata dictionary

        Returns:
            UUID of the created episode

        Example:
            episode_id = ryumem.add_episode(
                content="Alice works at Google in Mountain View",
                group_id="user_123",
                user_id="user_123",
                source="text",
            )
        """
        # Convert source string to EpisodeType
        source_type = EpisodeType.from_str(source)

        episode_id = self.ingestion.ingest(
            content=content,
            group_id=group_id,
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            source=source_type,
            metadata=metadata,
        )

        # Persist BM25 index to disk after ingestion
        bm25_path = str(Path(self.config.db_path).parent / f"{Path(self.config.db_path).stem}_bm25.pkl")
        self.search_engine.bm25_index.save(bm25_path)

        return episode_id

    def add_episodes_batch(
        self,
        episodes: List[Dict],
        group_id: str,
    ) -> List[str]:
        """
        Add multiple episodes in batch.

        Args:
            episodes: List of episode dictionaries with keys:
                - content: Episode content (required)
                - user_id: Optional user ID
                - agent_id: Optional agent ID
                - session_id: Optional session ID
                - source: Optional source type
                - metadata: Optional metadata
            group_id: Group ID for all episodes

        Returns:
            List of episode UUIDs

        Example:
            episodes = [
                {"content": "Alice works at Google"},
                {"content": "Bob lives in San Francisco"},
            ]
            episode_ids = ryumem.add_episodes_batch(episodes, group_id="user_123")
        """
        episode_ids = self.ingestion.ingest_batch(episodes, group_id)

        # Persist BM25 index to disk after batch ingestion
        bm25_path = str(Path(self.config.db_path).parent / f"{Path(self.config.db_path).stem}_bm25.pkl")
        self.search_engine.bm25_index.save(bm25_path)

        return episode_ids

    def search(
        self,
        query: str,
        group_id: str,
        user_id: Optional[str] = None,
        limit: int = 10,
        strategy: str = "semantic",
        similarity_threshold: Optional[float] = None,
        max_depth: int = 2,
        min_rrf_score: Optional[float] = None,
        min_bm25_score: Optional[float] = None,
        rrf_k: Optional[int] = None,
    ) -> SearchResult:
        """
        Search the memory system.

        Args:
            query: Search query text
            group_id: Group ID to search within (required)
            user_id: Optional user ID filter
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
                group_id="user_123",
                strategy="hybrid",
                limit=10,
            )

            for entity in results.entities:
                print(f"Entity: {entity.name} ({entity.entity_type})")
                print(f"Score: {results.scores.get(entity.uuid, 0.0):.3f}")
        """
        # Use default threshold from config if not provided
        if similarity_threshold is None:
            similarity_threshold = self.config.entity_similarity_threshold

        # Create search config
        config = SearchConfig(
            query=query,
            group_id=group_id,
            user_id=user_id,
            limit=limit,
            strategy=strategy,
            similarity_threshold=similarity_threshold,
            max_depth=max_depth,
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
        group_id: str,
        user_id: Optional[str] = None,
        max_depth: int = 2,
    ) -> Dict:
        """
        Get comprehensive context for an entity by name.

        Args:
            entity_name: Name of the entity
            group_id: Group ID
            user_id: Optional user ID
            max_depth: Maximum traversal depth

        Returns:
            Dictionary with entity details and relationships

        Example:
            context = ryumem.get_entity_context(
                entity_name="Alice",
                group_id="user_123",
            )
        """
        # Find entity by name
        entity = self.ingestion.entity_extractor.get_entity_by_name(
            name=entity_name,
            group_id=group_id,
            user_id=user_id,
        )

        if not entity:
            return {}

        # Get context
        return self.search_engine.get_entity_context(
            entity_uuid=entity.uuid,
            max_depth=max_depth,
        )

    def update_communities(
        self,
        group_id: str,
        resolution: float = 1.0,
        min_community_size: int = 2,
    ) -> int:
        """
        Detect/update communities for a group using Louvain algorithm.

        Communities cluster related entities together, enabling:
        - More efficient retrieval (search within relevant clusters)
        - Higher-level summaries and reasoning
        - Token optimization (compress subgraphs)

        This should be called periodically as the knowledge graph grows.

        Args:
            group_id: Group ID to detect communities for
            resolution: Resolution parameter for Louvain (higher = more, smaller communities)
            min_community_size: Minimum number of entities per community

        Returns:
            Number of communities created

        Example:
            # Detect communities after adding many episodes
            num_communities = ryumem.update_communities("user_123")
            print(f"Created {num_communities} communities")

            # Fine-tune community granularity
            num_communities = ryumem.update_communities(
                "user_123",
                resolution=1.5,  # More fine-grained communities
                min_community_size=3,  # Larger minimum size
            )
        """
        return self.community_detector.update_communities(
            group_id=group_id,
            resolution=resolution,
            min_community_size=min_community_size,
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
        group_id: str,
        user_id: Optional[str] = None,
        min_executions: int = 1,
    ) -> Dict:
        """
        Get success rate and performance metrics for a specific tool.

        Args:
            tool_name: Name of the tool
            group_id: Group ID
            user_id: Optional user ID for filtering
            min_executions: Minimum number of executions required

        Returns:
            Dictionary with success rate, usage count, and performance metrics

        Example:
            metrics = ryumem.get_tool_success_rate(
                tool_name="web_search",
                group_id="my_company"
            )
            # Returns: {"success_rate": 0.95, "usage_count": 100, "avg_duration_ms": 250, ...}
        """
        import json

        # Query query episodes (source='message') and extract tools_used from metadata
        query = """
        MATCH (e:Episode)
        WHERE e.source = 'message'
          AND e.group_id = $group_id
          AND e.metadata IS NOT NULL
        """

        params = {"group_id": group_id}

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

        # Aggregate statistics from tools_used arrays in query episodes
        while result.has_next():
            metadata_str = result.get_next()[0]
            if not metadata_str:
                continue

            metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str

            # Extract tools_used array from query episode metadata
            tools_used = metadata.get('tools_used', [])

            # Iterate through tool executions in this query
            for tool_execution in tools_used:
                # Check if this is the tool we're looking for
                if tool_execution.get('tool_name') == tool_name:
                    stats['usage_count'] += 1

                    if tool_execution.get('success'):
                        stats['success_count'] += 1
                    else:
                        stats['failure_count'] += 1
                        if len(stats['recent_errors']) < 5:
                            stats['recent_errors'].append({
                                'error': tool_execution.get('error', ''),
                                'timestamp': tool_execution.get('timestamp', ''),
                            })

                    stats['total_duration_ms'] += tool_execution.get('duration_ms', 0)

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
        user_id: str,
        group_id: str,
        limit: int = 10,
    ) -> List[Dict]:
        """
        Get tools most frequently used by a specific user.

        Args:
            user_id: User ID to analyze
            group_id: Group ID
            limit: Maximum number of tools to return

        Returns:
            List of tool usage dictionaries sorted by frequency

        Example:
            preferences = ryumem.get_user_tool_preferences(
                user_id="alice",
                group_id="my_company"
            )
            # Returns: [{"tool_name": "web_search", "usage_count": 50, ...}, ...]
        """
        import json

        # Query query episodes (source='message') and extract tools_used from metadata
        result = self.db.conn.execute(
            """
            MATCH (e:Episode)
            WHERE e.source = 'message'
              AND e.user_id = $user_id
              AND e.group_id = $group_id
              AND e.metadata IS NOT NULL
            RETURN e.metadata
            """,
            {"user_id": user_id, "group_id": group_id}
        )

        tool_usage = {}

        while result.has_next():
            metadata_str = result.get_next()[0]
            if not metadata_str:
                continue

            metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str

            # Extract tools_used array from query episode metadata
            tools_used = metadata.get('tools_used', [])

            # Iterate through tool executions in this query
            for tool_execution in tools_used:
                tool_name = tool_execution.get('tool_name')

                if tool_name:
                    if tool_name not in tool_usage:
                        tool_usage[tool_name] = {
                            'tool_name': tool_name,
                            'usage_count': 0,
                            'success_count': 0,
                        }

                    tool_usage[tool_name]['usage_count'] += 1
                    if tool_execution.get('success'):
                        tool_usage[tool_name]['success_count'] += 1

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
        Check if an instruction with the given text already exists.

        Args:
            instruction_text: The instruction text to search for
            agent_type: Type of agent (e.g., "google_adk")
            instruction_type: Type of instruction (e.g., "tool_tracking")

        Returns:
            UUID of the existing instruction if found, None otherwise
        """
        logger.info(f"[DB] get_instruction_by_text called: agent_type={agent_type}, instruction_type={instruction_type}")

        query = """
        MATCH (i:AgentInstruction)
        WHERE i.instruction_text = $instruction_text
          AND i.agent_type = $agent_type
          AND i.instruction_type = $instruction_type
        RETURN i.uuid AS uuid
        ORDER BY i.created_at DESC
        LIMIT 1
        """

        result = self.db.execute(query, {
            "instruction_text": instruction_text,
            "agent_type": agent_type,
            "instruction_type": instruction_type
        })

        if result and len(result) > 0:
            logger.info(f"[DB] Found existing instruction: {result[0]['uuid']}")
            return result[0]["uuid"]

        logger.info(f"[DB] No existing instruction found")
        return None

    def save_agent_instruction(
        self,
        instruction_text: str,
        agent_type: str = "google_adk",
        instruction_type: str = "tool_tracking",
        description: str = "",
        original_user_request: Optional[str] = None,
    ) -> str:
        """
        Save custom agent instruction to the database.

        This tracks both what the user originally requested and what instruction
        text will actually be added to the agent's prompt.

        Args:
            instruction_text: The actual instruction text to add to agent prompt (converted/final)
            agent_type: Type of agent (e.g., "google_adk", "custom_agent")
            instruction_type: Type of instruction (e.g., "tool_tracking", "memory_guidance")
            description: User-friendly description of what this instruction does
            original_user_request: Optional original request from user before conversion

        Returns:
            UUID of the created instruction

        Example:
            instruction_id = ryumem.save_agent_instruction(
                instruction_text="TOOL SELECTION:\nAlways check memory...",
                original_user_request="Make the agent check past tool usage",
                agent_type="google_adk",
                description="Custom tool selection guidance"
            )
        """
        import uuid
        from datetime import datetime

        logger.info(f"[DB] save_agent_instruction called: agent_type={agent_type}, instruction_type={instruction_type}")

        # Get version number (count of existing instructions for this type + 1)
        logger.info(f"[DB] Counting existing instructions for versioning...")
        count_query = """
        MATCH (i:AgentInstruction)
        WHERE i.agent_type = $agent_type
          AND i.instruction_type = $instruction_type
        RETURN count(i) AS count
        """
        result = self.db.execute(count_query, {
            "agent_type": agent_type,
            "instruction_type": instruction_type
        })
        version = result[0]["count"] + 1 if result else 1
        logger.info(f"[DB] Current count: {result[0]['count'] if result else 0}, new version will be: {version}")

        # Create new instruction
        instruction_id = str(uuid.uuid4())
        logger.info(f"[DB] Creating new instruction with ID: {instruction_id}")
        insert_query = """
        CREATE (i:AgentInstruction {
            uuid: $uuid,
            agent_type: $agent_type,
            instruction_type: $instruction_type,
            instruction_text: $instruction_text,
            original_user_request: $original_user_request,
            description: $description,
            version: $version,
            created_at: $created_at
        })
        RETURN i.uuid AS uuid
        """

        insert_result = self.db.execute(insert_query, {
            "uuid": instruction_id,
            "agent_type": agent_type,
            "instruction_type": instruction_type,
            "instruction_text": instruction_text,
            "original_user_request": original_user_request or "",
            "description": description,
            "version": version,
            "created_at": datetime.utcnow(),
        })
        logger.info(f"[DB] Insert query executed, result: {insert_result}")
        logger.info(f"[DB] ✓ Instruction saved successfully with ID: {instruction_id}")

        return instruction_id

    def list_agent_instructions(
        self,
        agent_type: Optional[str] = None,
        instruction_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        List all agent instructions with metadata and version history.

        Args:
            agent_type: Optional filter by agent type
            instruction_type: Optional filter by instruction type
            limit: Maximum number of instructions to return

        Returns:
            List of instruction dictionaries with metadata

        Example:
            instructions = ryumem.list_agent_instructions(
                agent_type="google_adk"
            )
            for instr in instructions:
                print(f"Version {instr['version']}: {instr['description']}")
        """
        logger.info(f"[DB] list_agent_instructions called: agent_type={agent_type}, instruction_type={instruction_type}, limit={limit}")

        # Build query
        query = "MATCH (i:AgentInstruction) WHERE true"
        params = {}

        if agent_type:
            query += " AND i.agent_type = $agent_type"
            params["agent_type"] = agent_type

        if instruction_type:
            query += " AND i.instruction_type = $instruction_type"
            params["instruction_type"] = instruction_type

        query += """
        RETURN i.uuid AS instruction_id,
               i.instruction_text AS instruction_text,
               i.agent_type AS agent_type,
               i.instruction_type AS instruction_type,
               i.original_user_request AS original_user_request,
               i.description AS description,
               i.version AS version,
               i.created_at AS created_at
        ORDER BY i.created_at DESC
        LIMIT $limit
        """

        params["limit"] = limit

        logger.info(f"[DB] Executing query with params: {params}")
        result = self.db.execute(query, params)
        logger.info(f"[DB] Query returned {len(result)} result(s)")

        # Format results
        formatted_results = []
        for row in result:
            logger.info(f"[DB]   - Found instruction: id={row['instruction_id']}, version={row['version']}")
            formatted_results.append({
                "instruction_id": row["instruction_id"],
                "instruction_text": row["instruction_text"],
                "name": f"Agent Instruction - {row['agent_type']} - {row['instruction_type']} v{row['version']}",
                "agent_type": row["agent_type"],
                "instruction_type": row["instruction_type"],
                "version": row["version"],
                "description": row["description"],
                "original_user_request": row["original_user_request"],
                "converted_instruction": row["instruction_text"],
                "created_at": str(row["created_at"]),
            })

        logger.info(f"[DB] Returning {len(formatted_results)} formatted instruction(s)")
        return formatted_results

    def prune_memories(
        self,
        group_id: str,
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
            group_id: Group ID to prune
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
            group_id=group_id,
            expired_cutoff_days=expired_cutoff_days,
            min_mentions=min_mentions,
            min_age_days=min_age_days,
            compact_redundant=compact_redundant,
            similarity_threshold=similarity_threshold,
        )

    def delete_group(self, group_id: str) -> None:
        """
        Delete all data for a specific group.

        WARNING: This is irreversible!

        Args:
            group_id: Group ID to delete

        Example:
            ryumem.delete_group("user_123")
        """
        self.db.delete_by_group_id(group_id)
        logger.info(f"Deleted all data for group: {group_id}")

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
        from ryumem.core.models import EntityNode
        for entity_data in entities_data:
            entity = EntityNode(
                uuid=entity_data["uuid"],
                name=entity_data["name"],
                entity_type=entity_data["entity_type"],
                summary=entity_data.get("summary", ""),
                mentions=entity_data["mentions"],
                group_id="",  # Not needed for BM25
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
        from ryumem.core.models import EntityEdge
        for edge_data in edges_data:
            edge = EntityEdge(
                uuid=edge_data["uuid"],
                source_node_uuid=edge_data["source_uuid"],
                target_node_uuid=edge_data["target_uuid"],
                name=edge_data["relation_type"],
                fact=edge_data["fact"],
                mentions=edge_data["mentions"],
                group_id="",  # Not needed for BM25
            )
            self.search_engine.bm25_index.add_edge(edge)

        # Save rebuilt index
        bm25_path = str(Path(self.config.db_path).parent / f"{Path(self.config.db_path).stem}_bm25.pkl")
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
        return f"Ryumem(db_path='{self.config.db_path}', model='{self.config.llm_model}')"
