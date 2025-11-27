"""
Configuration service for managing Ryumem configuration in the database.
Provides migration from .env to database and runtime configuration management.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from dotenv import dotenv_values

from ryumem_server.core.config import (
    AgentConfig,
    DatabaseConfig,
    EmbeddingConfig,
    EntityExtractionConfig,
    LLMConfig,
    RyumemConfig,
    SearchConfig,
    SystemConfig,
    ToolTrackingConfig,
)
from ryumem_server.core.graph_db import RyugraphDB

logger = logging.getLogger(__name__)


class ConfigService:
    """
    Service for managing system configuration stored in the database.
    Handles migration from .env files and provides CRUD operations for config values.
    """

    def __init__(self, db: RyugraphDB):
        """
        Initialize the config service.

        Args:
            db: Database connection (must be in READ_WRITE mode for migrations)
        """
        self.db = db

    def _serialize_value(self, value: Any, data_type: str) -> str:
        """
        Serialize a value to string for database storage.

        Args:
            value: Value to serialize
            data_type: Type hint for deserialization

        Returns:
            Serialized string value
        """
        if value is None:
            return ""
        if data_type == "list":
            return json.dumps(value)
        if data_type == "bool":
            return str(value).lower()
        return str(value)

    def _deserialize_value(self, value_str: str, data_type: str) -> Any:
        """
        Deserialize a string value from database to its proper type.

        Args:
            value_str: String value from database
            data_type: Type to deserialize to

        Returns:
            Deserialized value
        """
        if not value_str:
            return None

        if data_type == "string":
            return value_str
        elif data_type == "int":
            return int(value_str)
        elif data_type == "float":
            return float(value_str)
        elif data_type == "bool":
            return value_str.lower() in ("true", "1", "yes")
        elif data_type == "list":
            return json.loads(value_str)
        else:
            return value_str

    def get_default_configs(self) -> RyumemConfig:
        """
        Get default configuration model.
        Returns a RyumemConfig instance with all default values.
        """
        return RyumemConfig()

    def migrate_from_env(self, env_path: Optional[str] = None) -> Tuple[int, int]:
        """
        One-time migration: Read .env file and populate database with config values.
        Uses default values from pydantic models as fallback.

        Args:
            env_path: Path to .env file (defaults to server/.env)

        Returns:
            Tuple of (migrated_count, skipped_count)
        """
        # Check if already migrated
        existing_configs = self.db.get_all_configs()
        if existing_configs:
            logger.info(f"Configuration already migrated ({len(existing_configs)} configs in DB)")
            return (0, len(existing_configs))

        logger.info("Starting configuration migration from .env to database...")

        # Load .env file if it exists
        env_values = {}
        if env_path and os.path.exists(env_path):
            env_values = dotenv_values(env_path)
            logger.info(f"Loaded {len(env_values)} values from {env_path}")
        elif os.path.exists(".env"):
            env_values = dotenv_values(".env")
            logger.info(f"Loaded {len(env_values)} values from .env")
        else:
            logger.warning("No .env file found - using default configuration values")
            logger.warning("To customize: Create a .env file with RYUMEM_* environment variables")
            logger.warning("Key settings: RYUMEM_LLM_PROVIDER, RYUMEM_LLM_MODEL, RYUMEM_EMBEDDING_PROVIDER, RYUMEM_EMBEDDING_MODEL")

        # Get default config model
        defaults = self.get_default_configs()

        # ENV variable mapping (from .env names to config keys)
        env_mapping = {
            # API Keys
            "OPENAI_API_KEY": "llm.openai_api_key",
            "GOOGLE_API_KEY": "llm.gemini_api_key",

            # Database
            "RYUMEM_DB_PATH": "database.db_path",

            # LLM
            "RYUMEM_LLM_PROVIDER": "llm.provider",
            "RYUMEM_LLM_MODEL": "llm.model",
            "RYUMEM_LLM_OLLAMA_BASE_URL": "llm.ollama_base_url",
            "RYUMEM_LLM_ENTITY_EXTRACTION_TEMPERATURE": "llm.entity_extraction_temperature",
            "RYUMEM_LLM_RELATION_EXTRACTION_TEMPERATURE": "llm.relation_extraction_temperature",
            "RYUMEM_LLM_TOOL_SUMMARIZATION_TEMPERATURE": "llm.tool_summarization_temperature",
            "RYUMEM_LLM_ENTITY_EXTRACTION_MAX_TOKENS": "llm.entity_extraction_max_tokens",
            "RYUMEM_LLM_RELATION_EXTRACTION_MAX_TOKENS": "llm.relation_extraction_max_tokens",
            "RYUMEM_LLM_TOOL_SUMMARIZATION_MAX_TOKENS": "llm.tool_summarization_max_tokens",
            "RYUMEM_LLM_TIMEOUT_SECONDS": "llm.timeout_seconds",
            "RYUMEM_LLM_MAX_RETRIES": "llm.max_retries",

            # Embedding
            "RYUMEM_EMBEDDING_PROVIDER": "embedding.provider",
            "RYUMEM_EMBEDDING_MODEL": "embedding.model",
            "RYUMEM_EMBEDDING_DIMENSIONS": "embedding.dimensions",
            "RYUMEM_EMBEDDING_BATCH_SIZE": "embedding.batch_size",
            "RYUMEM_EMBEDDING_TIMEOUT_SECONDS": "embedding.timeout_seconds",

            # Entity Extraction
            "RYUMEM_ENTITY_ENABLED": "entity_extraction.enabled",
            "RYUMEM_ENTITY_ENTITY_SIMILARITY_THRESHOLD": "entity_extraction.entity_similarity_threshold",
            "RYUMEM_ENTITY_RELATIONSHIP_SIMILARITY_THRESHOLD": "entity_extraction.relationship_similarity_threshold",
            "RYUMEM_ENTITY_MAX_CONTEXT_EPISODES": "entity_extraction.max_context_episodes",

            # Search
            "RYUMEM_SEARCH_DEFAULT_LIMIT": "search.default_limit",
            "RYUMEM_SEARCH_DEFAULT_STRATEGY": "search.default_strategy",
            "RYUMEM_SEARCH_MAX_TRAVERSAL_DEPTH": "search.max_traversal_depth",
            "RYUMEM_SEARCH_RRF_K": "search.rrf_k",
            "RYUMEM_SEARCH_MIN_RRF_SCORE": "search.min_rrf_score",
            "RYUMEM_SEARCH_MIN_BM25_SCORE": "search.min_bm25_score",

            # Tool Tracking
            "RYUMEM_TOOL_TRACKING_TRACK_TOOLS": "tool_tracking.track_tools",
            "RYUMEM_TOOL_TRACKING_TRACK_QUERIES": "tool_tracking.track_queries",
            "RYUMEM_TOOL_TRACKING_AUGMENT_QUERIES": "tool_tracking.augment_queries",
            "RYUMEM_TOOL_TRACKING_SIMILARITY_THRESHOLD": "tool_tracking.similarity_threshold",
            "RYUMEM_TOOL_TRACKING_TOP_K_SIMILAR": "tool_tracking.top_k_similar",

            # System
            "RYUMEM_SYSTEM_CORS_ORIGINS": "system.cors_origins",
            "RYUMEM_SYSTEM_LOG_LEVEL": "system.log_level",
        }

        # Reverse mapping for quick lookup
        key_to_env = {v: k for k, v in env_mapping.items()}

        # Iterate through config sections and fields
        migrated = 0
        using_defaults = []

        for section_name in defaults.model_fields:
            # Skip database config (circular dependency)
            if section_name == "database":
                continue

            section_value = getattr(defaults, section_name)

            for field_name, field_info in section_value.model_fields.items():
                key = f"{section_name}.{field_name}"
                value = getattr(section_value, field_name)

                # Override with env value if present
                env_key = key_to_env.get(key)
                if env_key and env_key in env_values:
                    value = env_values[env_key]
                else:
                    # Track important defaults being used
                    if key in ["llm.provider", "llm.model", "embedding.provider", "embedding.model"]:
                        using_defaults.append(f"{key}={value}")

                # Infer data type from annotation for serialization
                ann_str = str(field_info.annotation).lower()
                if 'bool' in ann_str:
                    data_type = 'bool'
                elif 'int' in ann_str and 'float' not in ann_str:
                    data_type = 'int'
                elif 'float' in ann_str:
                    data_type = 'float'
                elif 'list' in ann_str:
                    data_type = 'list'
                else:
                    data_type = 'string'

                # Detect sensitive fields
                is_sensitive = any(s in field_name.lower() for s in ['key', 'secret', 'token', 'password'])

                # Save to database
                self.db.save_config(
                    key=key,
                    value=self._serialize_value(value, data_type),
                    category=section_name,
                    data_type=data_type,
                    is_sensitive=is_sensitive,
                    description=field_info.description or f"{section_name} {field_name}"
                )
                migrated += 1

        logger.info(f"Migration complete: {migrated} configs saved to database")

        # Warn about important defaults being used
        if using_defaults and not env_values:
            logger.warning(f"Using default values for: {', '.join(using_defaults)}")
            logger.warning("Consider setting these in .env for your use case")

        return (migrated, 0)

    def load_config_from_database(self) -> RyumemConfig:
        """
        Load configuration from database and construct a RyumemConfig instance.

        Returns:
            RyumemConfig instance populated from database values
        """
        # Get all configs from database
        db_configs = self.db.get_all_configs()

        if not db_configs:
            logger.warning("No configs found in database, using defaults")
            return RyumemConfig()

        # Convert to dict for easier access
        config_dict = {}
        for cfg in db_configs:
            key = cfg["key"]
            value = self._deserialize_value(cfg["value"], cfg["data_type"])
            config_dict[key] = value

        # Build nested config structure
        def get_value(key: str, default: Any = None) -> Any:
            return config_dict.get(key, default)

        # Construct config objects
        # DatabaseConfig ALWAYS comes from environment variables, never from database
        # (circular dependency: need db_path to open database, can't store it in database)
        database_config = DatabaseConfig()

        # Build LLM config with environment variables for API keys
        import os

        # Get ollama_base_url, ensure it's never None (use default if empty/None)
        ollama_url = get_value("llm.ollama_base_url", "http://100.108.18.43:11434")
        if not ollama_url or ollama_url == "":
            ollama_url = "http://100.108.18.43:11434"

        llm_config = LLMConfig(
            provider=get_value("llm.provider", "ollama"),
            model=get_value("llm.model", "qwen2.5:7b"),
            ollama_base_url=ollama_url,
            entity_extraction_temperature=get_value("llm.entity_extraction_temperature", 0.3),
            relation_extraction_temperature=get_value("llm.relation_extraction_temperature", 0.3),
            tool_summarization_temperature=get_value("llm.tool_summarization_temperature", 0.3),
            entity_extraction_max_tokens=get_value("llm.entity_extraction_max_tokens", 2000),
            relation_extraction_max_tokens=get_value("llm.relation_extraction_max_tokens", 2000),
            tool_summarization_max_tokens=get_value("llm.tool_summarization_max_tokens", 100),
            timeout_seconds=get_value("llm.timeout_seconds", 180),
            max_retries=get_value("llm.max_retries", 3),
        )

        # Set API keys from database values or environment
        # Pydantic's validation_alias means these are set via environment variables
        openai_key = get_value("llm.openai_api_key") or os.getenv("OPENAI_API_KEY")
        gemini_key = get_value("llm.gemini_api_key") or os.getenv("GOOGLE_API_KEY")

        if openai_key:
            llm_config.openai_api_key = openai_key
        if gemini_key:
            llm_config.gemini_api_key = gemini_key

        # Get embedding ollama_base_url, ensure it's never None
        embedding_ollama_url = get_value("embedding.ollama_base_url", "http://100.108.18.43:11434")
        if not embedding_ollama_url or embedding_ollama_url == "":
            embedding_ollama_url = "http://100.108.18.43:11434"

        embedding_config = EmbeddingConfig(
            provider=get_value("embedding.provider", "ollama"),
            model=get_value("embedding.model", "nomic-embed-text"),
            ollama_base_url=embedding_ollama_url,
            dimensions=get_value("embedding.dimensions", 768),
            batch_size=get_value("embedding.batch_size", 100),
            timeout_seconds=get_value("embedding.timeout_seconds", 180),
        )

        entity_extraction_config = EntityExtractionConfig(
            enabled=get_value("entity_extraction.enabled", False),
            entity_similarity_threshold=get_value("entity_extraction.entity_similarity_threshold", 0.65),
            relationship_similarity_threshold=get_value("entity_extraction.relationship_similarity_threshold", 0.8),
            max_context_episodes=get_value("entity_extraction.max_context_episodes", 5),
        )

        search_config = SearchConfig(
            default_limit=get_value("search.default_limit", 10),
            default_strategy=get_value("search.default_strategy", "hybrid"),
            max_traversal_depth=get_value("search.max_traversal_depth", 2),
            rrf_k=get_value("search.rrf_k", 60),
            min_rrf_score=get_value("search.min_rrf_score", 0.025),
            min_bm25_score=get_value("search.min_bm25_score", 0.1),
        )

        tool_tracking_config = ToolTrackingConfig(
            track_tools=get_value("tool_tracking.track_tools", True),
            track_queries=get_value("tool_tracking.track_queries", True),
            augment_queries=get_value("tool_tracking.augment_queries", True),
            similarity_threshold=get_value("tool_tracking.similarity_threshold", 0.3),
            top_k_similar=get_value("tool_tracking.top_k_similar", 5),
            sample_rate=get_value("tool_tracking.sample_rate", 1.0),
            summarize_outputs=get_value("tool_tracking.summarize_outputs", True),
            max_output_chars=get_value("tool_tracking.max_output_chars", 1000),
            sanitize_pii=get_value("tool_tracking.sanitize_pii", True),
            enhance_descriptions=get_value("tool_tracking.enhance_descriptions", False),
            ignore_errors=get_value("tool_tracking.ignore_errors", True),
        )

        agent_config = AgentConfig(
            memory_enabled=get_value("agent.memory_enabled", True),
            enhance_agent_instruction=get_value("agent.enhance_agent_instruction", True),
        )

        system_config = SystemConfig(
            cors_origins=get_value("system.cors_origins", "http://localhost:3000,http://localhost:3001"),
            log_level=get_value("system.log_level", "INFO"),
        )

        # Construct main config
        config = RyumemConfig(
            database=database_config,
            llm=llm_config,
            embedding=embedding_config,
            entity_extraction=entity_extraction_config,
            search=search_config,
            tool_tracking=tool_tracking_config,
            agent=agent_config,
            system=system_config,
        )

        logger.info("Loaded configuration from database")
        return config

    def get_all_configs_grouped(self, mask_sensitive: bool = True) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all configs grouped by category.

        Args:
            mask_sensitive: Whether to mask sensitive values

        Returns:
            Dictionary mapping category names to lists of configs
        """
        all_configs = self.db.get_all_configs()

        # Group by category
        grouped = {}
        for cfg in all_configs:
            category = cfg["category"]
            if category not in grouped:
                grouped[category] = []

            # Mask sensitive values if requested
            # Show first 4 and last 6 characters for API keys
            if mask_sensitive and cfg["is_sensitive"] and cfg["value"]:
                value_str = cfg["value"]
                if len(value_str) > 10:  # Need at least 11 chars to show 4 + 6
                    cfg["value"] = value_str[:4] + "***" + value_str[-6:]
                else:
                    cfg["value"] = "***"

            grouped[category].append(cfg)

        return grouped

    def update_config(self, key: str, value: Any) -> bool:
        """
        Update a single configuration value.

        Args:
            key: Configuration key
            value: New value

        Returns:
            True if updated successfully
        """
        # Get existing config to determine data type
        existing = self.db.get_config(key)
        if not existing:
            logger.warning(f"Config key not found: {key}")
            return False

        # Serialize value
        value_str = self._serialize_value(value, existing["data_type"])

        # Update in database
        self.db.save_config(
            key=key,
            value=value_str,
            category=existing["category"],
            data_type=existing["data_type"],
            is_sensitive=existing["is_sensitive"],
            description=existing["description"]
        )

        logger.info(f"Updated config: {key} = {value_str}")
        return True

    def update_multiple_configs(self, updates: Dict[str, Any]) -> Tuple[int, List[str]]:
        """
        Update multiple configuration values.

        Args:
            updates: Dictionary of key-value pairs to update

        Returns:
            Tuple of (success_count, failed_keys)
        """
        success_count = 0
        failed_keys = []

        for key, value in updates.items():
            if self.update_config(key, value):
                success_count += 1
            else:
                failed_keys.append(key)

        logger.info(f"Batch update: {success_count} succeeded, {len(failed_keys)} failed")
        return (success_count, failed_keys)

    def validate_config_value(self, key: str, value: Any) -> Tuple[bool, Optional[str]]:
        """
        Validate a configuration value without saving.

        Args:
            key: Configuration key
            value: Value to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get existing config
        existing = self.db.get_config(key)
        if not existing:
            return (False, f"Unknown configuration key: {key}")

        # Type validation
        data_type = existing["data_type"]
        try:
            if data_type == "int":
                int(value)
            elif data_type == "float":
                float(value)
            elif data_type == "bool":
                if not isinstance(value, bool) and str(value).lower() not in ("true", "false", "1", "0", "yes", "no"):
                    return (False, f"Invalid boolean value: {value}")
            elif data_type == "list":
                if not isinstance(value, list):
                    json.loads(value)  # Validate JSON string
        except (ValueError, json.JSONDecodeError) as e:
            return (False, f"Type validation failed: {e}")

        # Domain-specific validation
        if key == "llm.provider" and value not in ["openai", "ollama", "gemini", "litellm"]:
            return (False, f"Invalid LLM provider: {value}")
        if key == "embedding.provider" and value not in ["openai", "gemini", "ollama", "litellm"]:
            return (False, f"Invalid embedding provider: {value}")
        if key == "search.default_strategy" and value not in ["semantic", "traversal", "hybrid"]:
            return (False, f"Invalid search strategy: {value}")

        # API key validation when changing providers
        import os
        if key == "llm.provider":
            if value == "openai":
                # Check if OpenAI API key exists in database or environment
                openai_key_cfg = self.db.get_config("llm.openai_api_key")
                openai_key = (openai_key_cfg and openai_key_cfg["value"]) or os.getenv("OPENAI_API_KEY")
                if not openai_key:
                    return (False, "Cannot switch to OpenAI provider: OPENAI_API_KEY is not configured. Please set the API key first.")
            elif value == "gemini":
                # Check if Gemini API key exists in database or environment
                gemini_key_cfg = self.db.get_config("llm.gemini_api_key")
                gemini_key = (gemini_key_cfg and gemini_key_cfg["value"]) or os.getenv("GOOGLE_API_KEY")
                if not gemini_key:
                    return (False, "Cannot switch to Gemini provider: GOOGLE_API_KEY is not configured. Please set the API key first.")
            # litellm and ollama don't require specific API keys here

        if key == "embedding.provider":
            if value == "openai":
                # Check if OpenAI API key exists
                openai_key_cfg = self.db.get_config("llm.openai_api_key")
                openai_key = (openai_key_cfg and openai_key_cfg["value"]) or os.getenv("OPENAI_API_KEY")
                if not openai_key:
                    return (False, "Cannot switch to OpenAI embedding provider: OPENAI_API_KEY is not configured. Please set the API key first.")
            elif value == "gemini":
                # Check if Gemini API key exists
                gemini_key_cfg = self.db.get_config("llm.gemini_api_key")
                gemini_key = (gemini_key_cfg and gemini_key_cfg["value"]) or os.getenv("GOOGLE_API_KEY")
                if not gemini_key:
                    return (False, "Cannot switch to Gemini embedding provider: GOOGLE_API_KEY is not configured. Please set the API key first.")
            # ollama and litellm don't require specific API keys here

        return (True, None)
