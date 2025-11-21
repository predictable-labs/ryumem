#!/usr/bin/env python3
"""
Database Reset Script

This script safely resets a corrupted Ryugraph database by:
1. Backing up the old database
2. Deleting the corrupted files
3. Creating a fresh database with the correct schema

Usage:
    python reset_db.py [--backup]
"""

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

def reset_database(db_path: str, create_backup: bool = True):
    """
    Reset the database by removing corrupted files and creating fresh schema.

    Args:
        db_path: Path to the database file
        create_backup: Whether to create a backup before deletion
    """
    db_path_obj = Path(db_path)

    # Check if database exists
    if not db_path_obj.exists():
        print(f"✓ Database doesn't exist at {db_path}, will be created fresh")
        return

    print(f"Found database at: {db_path}")

    # Create backup if requested
    if create_backup:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = db_path_obj.parent / f"{db_path_obj.name}.backup_{timestamp}"

        try:
            print(f"Creating backup at: {backup_path}")
            shutil.copy2(db_path, backup_path)
            print(f"✓ Backup created successfully")
        except Exception as e:
            print(f"⚠ Warning: Failed to create backup: {e}")
            response = input("Continue without backup? (y/n): ")
            if response.lower() != 'y':
                print("Aborted")
                sys.exit(1)

    # Remove corrupted database
    try:
        print(f"Removing corrupted database: {db_path}")
        os.remove(db_path)

        # Also remove WAL file if it exists
        wal_path = f"{db_path}.wal"
        if os.path.exists(wal_path):
            print(f"Removing WAL file: {wal_path}")
            os.remove(wal_path)

        # Remove BM25 index file if it exists
        bm25_path = db_path_obj.parent / f"{db_path_obj.stem}_bm25.pkl"
        if bm25_path.exists():
            print(f"Removing BM25 index: {bm25_path}")
            os.remove(bm25_path)

        print("✓ Old database files removed")

    except Exception as e:
        print(f"✗ Error removing database: {e}")
        sys.exit(1)

    # Create fresh database with schema
    print("\nInitializing fresh database...")
    try:
        # Import here to avoid issues if database is corrupted
        from ryumem_server.core.graph_db import RyugraphDB

        # Get embedding dimensions from environment or use default
        embedding_dims = int(os.getenv("RYUMEM_EMBEDDING_DIMENSIONS", "768"))

        # Create new database (this will initialize schema)
        db = RyugraphDB(
            db_path=str(db_path),
            embedding_dimensions=embedding_dims,
        )

        db.close()

        print(f"✓ Fresh database created successfully with {embedding_dims}D embeddings")
        print(f"✓ Database location: {db_path}")

    except Exception as e:
        print(f"✗ Error creating fresh database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    # Get database path from environment
    db_path = os.getenv("RYUMEM_DB_PATH", "./data/ryumem.db")

    # Parse command line arguments
    create_backup = "--no-backup" not in sys.argv

    print("=" * 60)
    print("Ryumem Database Reset Tool")
    print("=" * 60)
    print(f"\nDatabase path: {db_path}")
    print(f"Create backup: {create_backup}")
    print()

    # Confirm with user
    if "--force" not in sys.argv:
        print("⚠ WARNING: This will delete the existing database!")
        if create_backup:
            print("  A backup will be created before deletion.")
        else:
            print("  No backup will be created (--no-backup flag used).")
        print()
        response = input("Continue? (y/n): ")
        if response.lower() != 'y':
            print("Aborted")
            sys.exit(0)

    print()
    reset_database(db_path, create_backup)

    print("\n" + "=" * 60)
    print("✓ Database reset complete!")
    print("=" * 60)
    print("\nYou can now start the server with:")
    print("  cd server && uvicorn main:app --reload")
