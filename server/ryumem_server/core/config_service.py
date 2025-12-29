"""
Configuration service for managing Ryumem configuration in the database.
Provides runtime configuration management with database storage.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ryumem.core.config import EpisodeConfig
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


def extract_config_fields(config: RyumemConfig) -> List[Dict[str, Any]]:
    """
    Extract all config fields from a RyumemConfig instance.
    Dynamically introspects the config model to get all fields with metadata.

    Args:
        config: RyumemConfig instance to introspect

    Returns:
        List of dicts with keys: key, value, category, data_type, is_sensitive, description
    """
    fields = []

    # Iterate through all config sections
    for section_name in config.model_fields:
        # Skip database config (circular dependency - can't store db path in the db)
        if section_name == "database":
            continue

        section_value = getattr(config, section_name)

        # Iterate through fields in each section
        for field_name, field_info in section_value.model_fields.items():
            key = f"{section_name}.{field_name}"
            value = getattr(section_value, field_name)

            # Infer data type from type annotation
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

            # Detect sensitive fields (API keys, passwords, tokens, secrets)
            is_sensitive = any(
                s in field_name.lower()
                for s in ['key', 'secret', 'token', 'password']
            )

            # Get description
            description = field_info.description or f"{section_name} {field_name}"

            fields.append({
                'key': key,
                'value': value,
                'category': section_name,
                'data_type': data_type,
                'is_sensitive': is_sensitive,
                'description': description
            })

    return fields


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
        ollama_url = get_value("llm.ollama_base_url", "http://localhost:11434")
        if not ollama_url or ollama_url == "":
            ollama_url = "http://localhost:11434"

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
        embedding_ollama_url = get_value("embedding.ollama_base_url", "http://localhost:11434")
        if not embedding_ollama_url or embedding_ollama_url == "":
            embedding_ollama_url = "http://localhost:11434"

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

        episode_config = EpisodeConfig(
            enable_embeddings=get_value("episode.enable_embeddings", True),
            deduplication_enabled=get_value("episode.deduplication_enabled", True),
            similarity_threshold=get_value("episode.similarity_threshold", 0.95),
            bm25_similarity_threshold=get_value("episode.bm25_similarity_threshold", 0.7),
            time_window_hours=get_value("episode.time_window_hours", 24),
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

        # Get default AgentConfig to extract default values for new fields
        default_agent = AgentConfig()

        agent_config = AgentConfig(
            memory_enabled=get_value("agent.memory_enabled", True),
            enhance_agent_instruction=get_value("agent.enhance_agent_instruction", True),
            default_memory_block=get_value("agent.default_memory_block", default_agent.default_memory_block),
            default_tool_block=get_value("agent.default_tool_block", default_agent.default_tool_block),
            default_query_augmentation_template=get_value("agent.default_query_augmentation_template", default_agent.default_query_augmentation_template),
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
            episode=episode_config,
            search=search_config,
            tool_tracking=tool_tracking_config,
            agent=agent_config,
            system=system_config,
        )

        logger.info("Loaded configuration from database")
        return config

    def ensure_defaults_in_database(self) -> int:
        """
        Ensure all default configuration values are stored in the database.
        Called on startup to populate the database with defaults if empty.

        Returns:
            Number of configs saved
        """
        # Check if database already has configs
        existing = self.db.get_all_configs()
        if existing:
            logger.debug(f"Database already has {len(existing)} configs, checking for missing fields...")
            # Database has configs, but check for missing fields (migration)
            return self.migrate_missing_fields()

        logger.info("Populating database with default configuration values...")

        # Get default config and extract all fields
        defaults = self.get_default_configs()
        fields = extract_config_fields(defaults)

        # Save each field to database
        count = 0
        for field in fields:
            try:
                value_str = self._serialize_value(field['value'], field['data_type'])
                self.db.save_config(
                    key=field['key'],
                    value=value_str,
                    category=field['category'],
                    data_type=field['data_type'],
                    is_sensitive=field['is_sensitive'],
                    description=field['description']
                )
                count += 1
            except Exception as e:
                logger.warning(f"Failed to save default config {field['key']}: {e}")

        logger.info(f"Saved {count} default configs to database")
        return count

    def migrate_missing_fields(self) -> int:
        """
        Migrate missing config fields to the database.
        Automatically adds any new config fields that don't exist in the database.

        Returns:
            Number of fields added
        """
        # Get all fields from current config
        defaults = self.get_default_configs()
        all_fields = extract_config_fields(defaults)

        # Get existing config keys from database
        existing_configs = self.db.get_all_configs()
        existing_keys = {cfg["key"] for cfg in existing_configs}

        # Find missing fields
        missing_fields = [
            field for field in all_fields
            if field["key"] not in existing_keys
        ]

        if not missing_fields:
            logger.debug("No missing config fields - database is up to date")
            return 0

        logger.info(f"Found {len(missing_fields)} missing config fields, adding to database...")

        # Add missing fields
        count = 0
        for field in missing_fields:
            try:
                value_str = self._serialize_value(field['value'], field['data_type'])
                self.db.save_config(
                    key=field['key'],
                    value=value_str,
                    category=field['category'],
                    data_type=field['data_type'],
                    is_sensitive=field['is_sensitive'],
                    description=field['description']
                )
                count += 1
                logger.debug(f"  Added missing field: {field['key']}")
            except Exception as e:
                logger.warning(f"Failed to add missing config {field['key']}: {e}")

        logger.info(f"Added {count} missing config fields to database")
        return count

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
