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

    def _generate_env_mapping(self, defaults: RyumemConfig) -> Dict[str, str]:
        """
        Generate env var mapping by introspecting RyumemConfig structure.

        Args:
            defaults: RyumemConfig instance with default values

        Returns:
            Dictionary mapping env var names to config keys
        """
        env_mapping = {}

        # Keep special cases for backward compatibility
        special_cases = {
            "OPENAI_API_KEY": "llm.openai_api_key",
            "GOOGLE_API_KEY": "llm.gemini_api_key",
        }
        env_mapping.update(special_cases)

        # Auto-discover all sections and fields
        for section_name in defaults.model_fields:
            if section_name == "database":  # Skip DB config
                continue

            section_obj = getattr(defaults, section_name)
            section_model_config = getattr(section_obj, 'model_config', {})
            env_prefix = section_model_config.get('env_prefix', f'RYUMEM_{section_name.upper()}_')

            for field_name in section_obj.model_fields:
                env_var_name = f"{env_prefix}{field_name.upper()}"
                config_key = f"{section_name}.{field_name}"

                if env_var_name not in env_mapping and config_key not in env_mapping.values():
                    env_mapping[env_var_name] = config_key

        return env_mapping

    def _infer_data_type(self, field_info) -> str:
        """
        Infer database storage type from Pydantic field annotation.

        Args:
            field_info: Pydantic FieldInfo object

        Returns:
            Data type string: 'bool', 'int', 'float', 'list', 'string'
        """
        import typing

        annotation = field_info.annotation

        # Handle Optional types
        origin = typing.get_origin(annotation)
        if origin is typing.Union:
            args = typing.get_args(annotation)
            # Get the non-None type
            annotation = next((arg for arg in args if arg is not type(None)), annotation)

        # Handle Literal types
        if origin is typing.Literal:
            return 'string'

        # Check actual type
        if annotation is bool or annotation == 'bool':
            return 'bool'
        elif annotation is int or 'int' in str(annotation).lower():
            return 'int'
        elif annotation is float or 'float' in str(annotation).lower():
            return 'float'
        elif annotation is list or 'list' in str(annotation).lower():
            return 'list'
        else:
            return 'string'

    def _build_config_section(
        self,
        section_name: str,
        section_class: type,
        config_dict: Dict[str, Any]
    ):
        """
        Dynamically construct config section from database values.

        Args:
            section_name: Name of the section (e.g., "llm", "workflow")
            section_class: The Pydantic model class (e.g., LLMConfig, WorkflowConfig)
            config_dict: Dictionary of all config values from database

        Returns:
            Instance of the section class populated with database values
        """
        import os
        from pydantic_core import PydanticUndefined

        kwargs = {}
        post_init_attrs = {}  # Fields to set after construction (like API keys with validation_alias)

        for field_name, field_info in section_class.model_fields.items():
            key = f"{section_name}.{field_name}"

            # Get from database or use field default
            if key in config_dict:
                value = config_dict[key]
            else:
                value = field_info.default if field_info.default is not PydanticUndefined else None

            # Special handling for API keys (have validation_alias, can come from env)
            if field_name in ["openai_api_key", "gemini_api_key"]:
                env_key = "OPENAI_API_KEY" if field_name == "openai_api_key" else "GOOGLE_API_KEY"
                value = value or os.getenv(env_key)
                # API keys have validation_alias, so we need to set them after construction
                if value:
                    post_init_attrs[field_name] = value
                continue

            # Handle None values with defaults
            if value is None or value == "":
                default = field_info.default
                if default is not None and default is not PydanticUndefined:
                    value = default

            kwargs[field_name] = value

        # Construct instance
        instance = section_class(**kwargs)

        # Set post-init attributes (like API keys)
        for attr_name, attr_value in post_init_attrs.items():
            setattr(instance, attr_name, attr_value)

        return instance

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

        # DYNAMIC: Generate env mapping from config structure
        env_mapping = self._generate_env_mapping(defaults)

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
                data_type = self._infer_data_type(field_info)

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
        Now fully dynamic - discovers all config sections automatically.

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

        # Get default config to discover sections
        defaults = RyumemConfig()

        # Build all sections dynamically
        section_instances = {}

        for section_name, field_info in RyumemConfig.model_fields.items():
            # Special handling for database config (always from env, never from db)
            if section_name == "database":
                section_instances[section_name] = DatabaseConfig()
                continue

            # Get section class from annotation
            section_class = field_info.annotation

            # Handle Optional types
            if hasattr(section_class, '__origin__'):
                import typing
                origin = typing.get_origin(section_class)
                if origin is typing.Union:
                    args = typing.get_args(section_class)
                    section_class = next((arg for arg in args if arg is not type(None)), section_class)

            # Build section dynamically
            section_instances[section_name] = self._build_config_section(
                section_name,
                section_class,
                config_dict
            )

        # Construct main config
        config = RyumemConfig(**section_instances)

        logger.info(f"Loaded configuration from database with {len(section_instances)} sections")
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
