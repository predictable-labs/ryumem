#!/usr/bin/env python3
"""
Script to dump all SystemConfig data from RyuGraph database to JSON format.
Exports all configuration settings stored in the database.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import ryugraph


def serialize_value(value: Any) -> Any:
    """Convert values to JSON-serializable format."""
    if isinstance(value, datetime):
        return value.isoformat()
    elif isinstance(value, (list, tuple)):
        return [serialize_value(v) for v in value]
    elif isinstance(value, dict):
        return {k: serialize_value(v) for k, v in value.items()}
    elif hasattr(value, '__dict__'):
        return str(value)
    return value


def execute_query(conn: ryugraph.Connection, query: str) -> List[Dict[str, Any]]:
    """Execute a Cypher query and return results as dictionaries."""
    try:
        results = conn.execute(query)
        df = results.get_as_df()
        records = df.to_dict('records')
        # Serialize all values
        return [{k: serialize_value(v) for k, v in record.items()} for record in records]
    except Exception as e:
        print(f"Warning: Query failed: {e}", file=sys.stderr)
        return []


def dump_configs(db_path: str, output_file: str, mask_sensitive: bool = True) -> None:
    """
    Dump all SystemConfig data from RyuGraph database to JSON.

    Args:
        db_path: Path to the RyuGraph database
        output_file: Path to output JSON file
        mask_sensitive: Whether to mask sensitive values (API keys)
    """
    print(f"Opening database at: {db_path}")
    db = ryugraph.Database(db_path, read_only=True)
    conn = ryugraph.Connection(db)

    # Export SystemConfig nodes
    print("Exporting SystemConfig nodes...")
    configs_query = """
    MATCH (c:SystemConfig)
    RETURN
        c.key AS key,
        c.value AS value,
        c.category AS category,
        c.data_type AS data_type,
        c.is_sensitive AS is_sensitive,
        c.description AS description,
        c.updated_at AS updated_at
    ORDER BY c.category, c.key
    """
    configs = execute_query(conn, configs_query)

    # Mask sensitive values if requested
    if mask_sensitive:
        for config in configs:
            if config.get('is_sensitive') and config.get('value'):
                value_str = str(config['value'])
                if len(value_str) > 10:
                    config['value'] = value_str[:4] + "***" + value_str[-6:]
                    config['value_masked'] = True
                else:
                    config['value'] = "***"
                    config['value_masked'] = True
            else:
                config['value_masked'] = False

    print(f"  Exported {len(configs)} configuration settings")

    # Group configs by category
    configs_by_category = {}
    for config in configs:
        category = config['category']
        if category not in configs_by_category:
            configs_by_category[category] = []
        configs_by_category[category].append(config)

    # Prepare output data
    data = {
        "metadata": {
            "exported_at": datetime.now().isoformat(),
            "database_path": db_path,
            "total_configs": len(configs),
            "categories": list(configs_by_category.keys()),
            "sensitive_values_masked": mask_sensitive
        },
        "configs_by_category": configs_by_category,
        "configs_all": configs
    }

    # Write to JSON file
    print(f"\nWriting data to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Print summary
    file_size = Path(output_file).stat().st_size
    print(f"\n{'='*60}")
    print("Export complete!")
    print(f"{'='*60}")
    print(f"Output file: {output_file}")
    print(f"File size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
    print(f"\nSummary:")
    print(f"  Total configs: {len(configs)}")
    print(f"  Categories: {len(configs_by_category)}")
    print(f"  Sensitive values masked: {mask_sensitive}")

    print(f"\nConfigs by category:")
    for category, category_configs in sorted(configs_by_category.items()):
        print(f"  {category}: {len(category_configs)} settings")
        for config in category_configs:
            sensitive_marker = " [SENSITIVE]" if config.get('is_sensitive') else ""
            print(f"    - {config['key']}: {config['value']}{sensitive_marker}")

    print(f"{'='*60}")


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # Default to server database path
        db_path = "./server/data/ryumem.db"

    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        # Generate timestamped output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"./configs_dump_{timestamp}.json"

    # Option to show unmasked values
    mask_sensitive = True
    if len(sys.argv) > 3 and sys.argv[3] == "--no-mask":
        mask_sensitive = False
        print("WARNING: Sensitive values will NOT be masked!")

    # Check if database exists
    if not Path(db_path).exists():
        print(f"Error: Database not found at {db_path}", file=sys.stderr)
        print(f"Hint: Try one of these paths:", file=sys.stderr)
        print(f"  - ./server/data/ryumem.db", file=sys.stderr)
        print(f"  - ./data/ryumem.db", file=sys.stderr)
        sys.exit(1)

    try:
        dump_configs(db_path, output_file, mask_sensitive)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
