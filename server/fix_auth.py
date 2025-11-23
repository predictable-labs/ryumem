
from ryumem_server.core.graph_db import RyugraphDB
import datetime
import os

# Ensure we are in the right directory or point to the right path
db_path = "./data/master_auth.db"
print(f"Connecting to {db_path}")

try:
    db = RyugraphDB(db_path=db_path, embedding_dimensions=384)

    customer_id = "demo_company"
    api_key = "change_this_to_a_secure_random_string"

    # Check if exists
    existing = db.execute(
        "MATCH (c:Customer {customer_id: $cid}) RETURN c",
        {"cid": customer_id}
    )

    if existing:
        print(f"Updating existing customer {customer_id}")
        db.execute(
            "MATCH (c:Customer {customer_id: $cid}) SET c.api_key = $key",
            {"cid": customer_id, "key": api_key}
        )
    else:
        print(f"Creating new customer {customer_id}")
        db.execute(
            """
            CREATE (c:Customer {
                customer_id: $cid,
                api_key: $key,
                created_at: $created_at
            })
            """,
            {
                "cid": customer_id,
                "key": api_key,
                "created_at": datetime.datetime.utcnow().isoformat()
            }
        )

    print("Done. API Key registered.")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
