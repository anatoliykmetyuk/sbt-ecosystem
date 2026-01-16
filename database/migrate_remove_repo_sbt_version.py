#!/usr/bin/env python3
"""
Migration script to remove sbt_version column from repositories table
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "database" / "sbt_ecosystem.db"

def migrate():
    """Perform the migration"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("Starting migration: Remove sbt_version column from repositories")
        print("=" * 60)

        # Step 1: Recreate table without sbt_version column
        print("\nStep 1: Recreating repositories table without sbt_version column...")

        # Create new table
        cursor.execute("""
            CREATE TABLE repositories_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                organization TEXT NOT NULL,
                name TEXT NOT NULL,
                is_plugin_containing_repo BOOLEAN NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'not_ported' CHECK(status IN ('not_ported', 'blocked', 'experimental', 'upstream')),
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(organization, name)
            )
        """)

        # Copy data (excluding sbt_version column)
        cursor.execute("""
            INSERT INTO repositories_new
            (id, url, organization, name, is_plugin_containing_repo, status, created_at, updated_at)
            SELECT
                id, url, organization, name, is_plugin_containing_repo, status, created_at, updated_at
            FROM repositories
        """)

        # Drop old table
        cursor.execute("DROP TABLE repositories")

        # Rename new table
        cursor.execute("ALTER TABLE repositories_new RENAME TO repositories")

        print("  ✓ Table recreated")

        # Step 2: Recreate indexes
        print("\nStep 2: Recreating indexes...")
        cursor.execute("CREATE INDEX idx_repositories_url ON repositories(url)")
        cursor.execute("CREATE INDEX idx_repositories_org_name ON repositories(organization, name)")
        cursor.execute("CREATE INDEX idx_repositories_status ON repositories(status)")
        print("  ✓ Indexes recreated")

        conn.commit()
        print("\n" + "=" * 60)
        print("✓ Migration completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"\n✗ Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
