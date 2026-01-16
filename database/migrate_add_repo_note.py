#!/usr/bin/env python3
"""
Migration script to add note column to repositories table
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
        print("Starting migration: Add note column to repositories table")
        print("=" * 60)

        # Check if column already exists
        cursor.execute("PRAGMA table_info(repositories)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'note' in columns:
            print("\nNote: Column 'note' already exists in repositories table")
            print("Skipping migration.")
            return

        # Step 1: Add note column
        print("\nStep 1: Adding note column to repositories table...")
        cursor.execute("""
            ALTER TABLE repositories
            ADD COLUMN note TEXT
        """)
        print("  ✓ Column added")

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
