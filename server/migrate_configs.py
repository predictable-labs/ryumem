#!/usr/bin/env python3
"""
Migration script to add new config fields to existing databases.

This script:
1. Checks which config fields are missing from the database
2. Adds new config fields (agent.default_memory_block, agent.default_tool_block, agent.default_query_augmentation_template)
3. Updates the database with new default values from AgentConfig

Run this after updating the config defaults in src/ryumem/core/config.py
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from ryumem_server.core.config import RyumemConfig, AgentConfig
from ryumem_server.core.graph_db import RyugraphDB
from ryumem_server.core.config_service import ConfigService, extract_config_fields

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_missing_config_fields(db: RyugraphDB, config: RyumemConfig) -> list:
    """
    Check which config fields are missing from the database.

    Args:
        db: Database instance
        config: RyumemConfig with all fields (including new ones)

    Returns:
        List of missing config field dictionaries
    """
    logger.info("Checking for missing config fields...")

    # Get all fields from current config
    all_fields = extract_config_fields(config)

    # Get existing config keys from database
    existing_configs = db.get_all_configs()
    existing_keys = {cfg["key"] for cfg in existing_configs}

    # Find missing fields
    missing_fields = [
        field for field in all_fields
        if field["key"] not in existing_keys
    ]

    return missing_fields


def migrate_config_fields(db: RyugraphDB, config_service: ConfigService, dry_run: bool = True) -> dict:
    """
    Migrate config fields - add missing fields to the database.

    Args:
        db: Database instance
        config_service: ConfigService instance
        dry_run: If True, only report what would be changed without updating

    Returns:
        dict with migration statistics
    """
    stats = {
        "total_existing": 0,
        "missing_fields": 0,
        "added": 0,
        "errors": 0
    }

    try:
        # Get default config with all fields (including new ones)
        default_config = RyumemConfig()

        # Check which fields are missing
        missing_fields = get_missing_config_fields(db, default_config)

        stats["missing_fields"] = len(missing_fields)
        stats["total_existing"] = len(db.get_all_configs())

        logger.info("=" * 70)
        logger.info(f"Total existing config fields: {stats['total_existing']}")
        logger.info(f"Missing config fields: {stats['missing_fields']}")
        logger.info("=" * 70)

        if stats["missing_fields"] == 0:
            logger.info("\n✓ No missing config fields - database is up to date!")
            return stats

        logger.info("\nMissing config fields:")
        for field in missing_fields:
            value_preview = str(field['value'])[:60]
            if len(str(field['value'])) > 60:
                value_preview += "..."
            logger.info(f"  - {field['key']}")
            logger.info(f"    Type: {field['data_type']}")
            logger.info(f"    Value: {value_preview}")
            logger.info("")

        if not dry_run:
            logger.info("Adding missing config fields to database...\n")

            for field in missing_fields:
                try:
                    value_str = config_service._serialize_value(field['value'], field['data_type'])
                    db.save_config(
                        key=field['key'],
                        value=value_str,
                        category=field['category'],
                        data_type=field['data_type'],
                        is_sensitive=field['is_sensitive'],
                        description=field['description']
                    )
                    stats["added"] += 1
                    logger.info(f"  ✓ Added: {field['key']}")
                except Exception as e:
                    logger.error(f"  ✗ Failed to add {field['key']}: {e}")
                    stats["errors"] += 1
        else:
            logger.info("[DRY RUN] Would add these fields to the database\n")
            stats["added"] = stats["missing_fields"]

        return stats

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        stats["errors"] += 1
        return stats


def find_all_databases(data_dir: str = "./data") -> list:
    """
    Find all database files in the data directory.

    Args:
        data_dir: Directory to search for databases

    Returns:
        List of database paths
    """
    import os
    from pathlib import Path

    data_path = Path(data_dir)
    if not data_path.exists():
        logger.warning(f"Data directory not found: {data_dir}")
        return []

    # Find all .db files, excluding BM25 index files
    db_paths = []
    for item in data_path.iterdir():
        if item.is_file() and item.suffix == ".db" and "bm25" not in item.name.lower():
            db_paths.append(str(item))

    return sorted(db_paths)


def migrate_database(db_path: str, embedding_dimensions: int, dry_run: bool) -> dict:
    """
    Migrate a single database.

    Args:
        db_path: Path to database
        embedding_dimensions: Embedding dimensions for the database
        dry_run: Whether to run in dry-run mode

    Returns:
        Migration statistics
    """
    try:
        logger.info(f"\n{'='*70}")
        logger.info(f"Migrating: {db_path}")
        logger.info(f"{'='*70}\n")

        # Initialize database and config service
        db = RyugraphDB(db_path=db_path, embedding_dimensions=embedding_dimensions)
        config_service = ConfigService(db)

        # Run migration
        stats = migrate_config_fields(db, config_service, dry_run=dry_run)
        stats["db_path"] = db_path

        return stats

    except Exception as e:
        logger.error(f"Failed to migrate {db_path}: {e}")
        return {
            "db_path": db_path,
            "total_existing": 0,
            "missing_fields": 0,
            "added": 0,
            "errors": 1,
            "error_message": str(e)
        }


def main():
    """Run the migration script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate config fields - add missing fields to database(s)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run for all databases (default - shows what would be added)
  python migrate_agent_configs.py

  # Actually execute the migration for all databases
  python migrate_agent_configs.py --execute

  # Use a specific database
  python migrate_agent_configs.py --execute --db-path /path/to/db

  # Specify data directory to search
  python migrate_agent_configs.py --execute --data-dir /path/to/data
        """
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually execute the migration (default is dry-run mode)"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Path to specific database (default: migrate all databases in data-dir)"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="./data",
        help="Directory to search for databases (default: ./data)"
    )

    args = parser.parse_args()

    # Determine if we're doing a dry run
    dry_run = not args.execute

    print("=" * 70)
    print("Config Fields Migration Script")
    print("=" * 70)
    print(f"Mode: {'🧪 DRY RUN' if dry_run else '🔧 EXECUTE'}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if dry_run:
        print("\n⚠️  Running in DRY RUN mode - no changes will be made")
        print("⚠️  Use --execute flag to actually apply changes\n")
    else:
        print("\n🔧 EXECUTE mode - changes will be applied to database!")
        response = input("\nAre you sure you want to proceed? (yes/no): ")
        if response.lower() != "yes":
            print("Migration cancelled")
            return
        print("")

    print("=" * 70)
    print("")

    try:
        # Load default config to get embedding dimensions
        config = RyumemConfig()

        # Determine which databases to migrate
        if args.db_path:
            # Single database specified
            db_paths = [args.db_path]
            logger.info(f"Migrating single database: {args.db_path}\n")
        else:
            # Find all databases in data directory
            db_paths = find_all_databases(args.data_dir)
            if not db_paths:
                logger.warning(f"No databases found in {args.data_dir}")
                print("\n⚠️  No databases found to migrate")
                return

            logger.info(f"Found {len(db_paths)} database(s) in {args.data_dir}:")
            for db_path in db_paths:
                logger.info(f"  - {db_path}")
            print("")

        # Migrate each database
        all_stats = []
        for db_path in db_paths:
            stats = migrate_database(db_path, config.embedding.dimensions, dry_run)
            all_stats.append(stats)

        # Print overall summary
        print("\n" + "=" * 70)
        print("Overall Migration Summary:")
        print("=" * 70)

        total_dbs = len(all_stats)
        total_existing = sum(s["total_existing"] for s in all_stats)
        total_missing = sum(s["missing_fields"] for s in all_stats)
        total_added = sum(s["added"] for s in all_stats)
        total_errors = sum(s["errors"] for s in all_stats)

        print(f"  Databases processed:     {total_dbs}")
        print(f"  Total existing fields:   {total_existing}")
        print(f"  Total missing fields:    {total_missing}")
        print(f"  Total fields added:      {total_added}")
        print(f"  Total errors:            {total_errors}")
        print("=" * 70)

        # Print per-database details if multiple databases
        if len(all_stats) > 1:
            print("\nPer-Database Details:")
            print("=" * 70)
            for stats in all_stats:
                db_name = Path(stats["db_path"]).name
                print(f"\n{db_name}:")
                print(f"  Existing: {stats['total_existing']}, Missing: {stats['missing_fields']}, Added: {stats['added']}, Errors: {stats['errors']}")
                if stats.get("error_message"):
                    print(f"  Error: {stats['error_message']}")

        if dry_run:
            print("\n✓ Dry run complete. Use --execute to apply changes.")
        else:
            if total_errors == 0:
                print("\n✓ Migration completed successfully for all databases!")
            else:
                print(f"\n⚠️  Migration completed with {total_errors} errors")

    except Exception as e:
        logger.error(f"\n❌ Migration failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
