#!/usr/bin/env python3
"""
Script to set the note for a repository in the database.
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "database" / "sbt_ecosystem.db"


def set_repository_note(repo_identifier, note):
    """Set the note of a repository"""
    # Parse repository identifier (organization/name)
    if "/" not in repo_identifier:
        print(f"Error: Repository identifier must be in format 'organization/name'")
        print(f"Got: {repo_identifier}")
        sys.exit(1)

    org, name = repo_identifier.split("/", 1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Find the repository
        cursor.execute("""
            SELECT id, organization, name
            FROM repositories
            WHERE organization = ? AND name = ?
        """, (org, name))

        result = cursor.fetchone()

        if not result:
            print(f"Error: Repository '{org}/{name}' not found in database")
            sys.exit(1)

        repo_id, repo_org, repo_name = result

        # Update note
        cursor.execute("""
            UPDATE repositories
            SET note = ?, updated_at = datetime('now')
            WHERE id = ?
        """, (note if note else None, repo_id))

        conn.commit()

        print(f"✓ Updated repository: {repo_org}/{repo_name}")
        if note:
            print(f"  Note set: {note}")
        else:
            print(f"  Note cleared")

    except Exception as e:
        conn.rollback()
        print(f"Error updating repository note: {e}")
        raise
    finally:
        conn.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 set_repo_note.py <organization/name> [note]")
        print()
        print("Examples:")
        print("  python3 set_repo_note.py com.example/repo 'requires Java version < 17'")
        print("  python3 set_repo_note.py com.example/repo ''  # Clear note")
        sys.exit(1)

    repo_identifier = sys.argv[1]
    note = sys.argv[2] if len(sys.argv) > 2 else None

    set_repository_note(repo_identifier, note)


if __name__ == "__main__":
    main()
