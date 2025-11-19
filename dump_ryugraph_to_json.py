#!/usr/bin/env python3
"""
Script to dump all data from RyuGraph database to JSON format.
Exports Episodes, Entities, Communities, Tools, and all relationships.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import ryu as ryugraph


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


def dump_database(db_path: str, output_file: str) -> None:
    """
    Dump all data from RyuGraph database to JSON.

    Args:
        db_path: Path to the RyuGraph database
        output_file: Path to output JSON file
    """
    print(f"Opening database at: {db_path}")
    db = ryugraph.Database(db_path, read_only=True)
    conn = ryugraph.Connection(db)

    data = {
        "metadata": {
            "exported_at": datetime.now().isoformat(),
            "database_path": db_path,
        },
        "nodes": {},
        "relationships": {}
    }

    # Export Episodes
    print("Exporting Episodes...")
    episodes_query = """
    MATCH (e:Episode)
    RETURN
        e.uuid AS uuid,
        e.name AS name,
        e.content AS content,
        e.source AS source,
        e.source_description AS source_description,
        e.created_at AS created_at,
        e.valid_at AS valid_at,
        e.user_id AS user_id,
        e.agent_id AS agent_id,
        e.metadata AS metadata,
        e.entity_edges AS entity_edges
    """
    episodes = execute_query(conn, episodes_query)
    data["nodes"]["episodes"] = episodes
    print(f"  Exported {len(episodes)} episodes")

    # Export Entities
    print("Exporting Entities...")
    entities_query = """
    MATCH (e:Entity)
    RETURN
        e.uuid AS uuid,
        e.name AS name,
        e.entity_type AS entity_type,
        e.summary AS summary,
        e.mentions AS mentions,
        e.created_at AS created_at,
        e.user_id AS user_id,
        e.labels AS labels,
        e.attributes AS attributes
    """
    entities = execute_query(conn, entities_query)
    data["nodes"]["entities"] = entities
    print(f"  Exported {len(entities)} entities")

    # Export Communities
    print("Exporting Communities...")
    communities_query = """
    MATCH (c:Community)
    RETURN
        c.uuid AS uuid,
        c.name AS name,
        c.summary AS summary,
        c.created_at AS created_at,
        c.members AS members,
        c.member_count AS member_count
    """
    communities = execute_query(conn, communities_query)
    data["nodes"]["communities"] = communities
    print(f"  Exported {len(communities)} communities")

    # Export Tools
    print("Exporting Tools...")
    tools_query = """
    MATCH (t:Tool)
    RETURN
        t.uuid AS uuid,
        t.tool_name AS tool_name,
        t.description AS description,
        t.mentions AS mentions,
        t.created_at AS created_at
    """
    tools = execute_query(conn, tools_query)
    data["nodes"]["tools"] = tools
    print(f"  Exported {len(tools)} tools")

    # Export AgentInstructions
    print("Exporting AgentInstructions...")
    instructions_query = """
    MATCH (a:AgentInstruction)
    RETURN
        a.uuid AS uuid,
        a.agent_type AS agent_type,
        a.instruction_type AS instruction_type,
        a.instruction_text AS instruction_text,
        a.original_user_request AS original_user_request,
        a.description AS description,
        a.version AS version,
        a.active AS active,
        a.created_at AS created_at
    """
    instructions = execute_query(conn, instructions_query)
    data["nodes"]["agent_instructions"] = instructions
    print(f"  Exported {len(instructions)} agent instructions")

    # Export RELATES_TO relationships
    print("Exporting RELATES_TO relationships...")
    relates_to_query = """
    MATCH (source:Entity)-[r:RELATES_TO]->(target:Entity)
    RETURN
        r.uuid AS uuid,
        source.uuid AS source_uuid,
        source.name AS source_name,
        target.uuid AS target_uuid,
        target.name AS target_name,
        r.name AS relation_type,
        r.fact AS fact,
        r.created_at AS created_at,
        r.valid_at AS valid_at,
        r.invalid_at AS invalid_at,
        r.expired_at AS expired_at,
        r.episodes AS episodes,
        r.mentions AS mentions,
        r.attributes AS attributes
    """
    relates_to = execute_query(conn, relates_to_query)
    data["relationships"]["relates_to"] = relates_to
    print(f"  Exported {len(relates_to)} RELATES_TO relationships")

    # Export MENTIONS relationships
    print("Exporting MENTIONS relationships...")
    mentions_query = """
    MATCH (episode:Episode)-[r:MENTIONS]->(entity:Entity)
    RETURN
        r.uuid AS uuid,
        episode.uuid AS episode_uuid,
        episode.name AS episode_name,
        entity.uuid AS entity_uuid,
        entity.name AS entity_name,
        r.created_at AS created_at
    """
    mentions = execute_query(conn, mentions_query)
    data["relationships"]["mentions"] = mentions
    print(f"  Exported {len(mentions)} MENTIONS relationships")

    # Export HAS_MEMBER relationships
    print("Exporting HAS_MEMBER relationships...")
    has_member_query = """
    MATCH (community:Community)-[r:HAS_MEMBER]->(entity:Entity)
    RETURN
        r.uuid AS uuid,
        community.uuid AS community_uuid,
        community.name AS community_name,
        entity.uuid AS entity_uuid,
        entity.name AS entity_name,
        r.created_at AS created_at
    """
    has_member = execute_query(conn, has_member_query)
    data["relationships"]["has_member"] = has_member
    print(f"  Exported {len(has_member)} HAS_MEMBER relationships")

    # Export TRIGGERED relationships
    print("Exporting TRIGGERED relationships...")
    triggered_query = """
    MATCH (source:Episode)-[r:TRIGGERED]->(target:Episode)
    RETURN
        r.uuid AS uuid,
        source.uuid AS source_episode_uuid,
        source.name AS source_episode_name,
        target.uuid AS target_episode_uuid,
        target.name AS target_episode_name,
        r.created_at AS created_at
    """
    triggered = execute_query(conn, triggered_query)
    data["relationships"]["triggered"] = triggered
    print(f"  Exported {len(triggered)} TRIGGERED relationships")

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
    print(f"File size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
    print(f"\nSummary:")
    print(f"  Episodes: {len(episodes)}")
    print(f"  Entities: {len(entities)}")
    print(f"  Communities: {len(communities)}")
    print(f"  Tools: {len(tools)}")
    print(f"  Agent Instructions: {len(instructions)}")
    print(f"  RELATES_TO: {len(relates_to)}")
    print(f"  MENTIONS: {len(mentions)}")
    print(f"  HAS_MEMBER: {len(has_member)}")
    print(f"  TRIGGERED: {len(triggered)}")
    print(f"{'='*60}")


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = "./data/memory.db"

    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        # Generate timestamped output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"./ryugraph_dump_{timestamp}.json"

    # Check if database exists
    if not Path(db_path).exists():
        print(f"Error: Database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    try:
        dump_database(db_path, output_file)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
