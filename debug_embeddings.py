"""Quick debug script to check if entities have embeddings."""

from ryumem.core.graph_db import RyugraphDB

db = RyugraphDB(db_path="./data/example_memory.db", embedding_dimensions=3072)

# Check entities
query = """
MATCH (e:Entity)
RETURN
    e.uuid AS uuid,
    e.name AS name,
    e.name_embedding IS NOT NULL AS has_embedding,
    e.group_id AS group_id
LIMIT 10
"""

results = db.execute(query, {})

print(f"Found {len(results)} entities:")
for r in results:
    print(f"  - {r['name']}: has_embedding={r['has_embedding']}, group_id={r['group_id']}")

# Count total
count_query = """
MATCH (e:Entity)
RETURN
    count(*) AS total,
    sum(CASE WHEN e.name_embedding IS NOT NULL THEN 1 ELSE 0 END) AS with_embeddings
"""

counts = db.execute(count_query, {})
print(f"\nTotal stats: {counts}")

db.close()
