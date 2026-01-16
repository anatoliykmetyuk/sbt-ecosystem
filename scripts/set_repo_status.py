#!/usr/bin/env python3
"""
Script to manually set the status of a repository in the database.
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "database" / "sbt_ecosystem.db"

VALID_STATUSES = ["not_ported", "blocked", "experimental", "upstream"]


def set_repository_status(repo_identifier, status):
    """Set the status of a repository"""
    # Validate status
    if status not in VALID_STATUSES:
        print(f"Error: Invalid status '{status}'")
        print(f"Valid statuses: {', '.join(VALID_STATUSES)}")
        sys.exit(1)

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
            SELECT id, organization, name, status
            FROM repositories
            WHERE organization = ? AND name = ?
        """, (org, name))

        result = cursor.fetchone()

        if not result:
            print(f"Error: Repository '{org}/{name}' not found in database")
            sys.exit(1)

        repo_id, repo_org, repo_name, old_status = result

        # Update status
        cursor.execute("""
            UPDATE repositories
            SET status = ?, updated_at = datetime('now')
            WHERE id = ?
        """, (status, repo_id))

        conn.commit()

        print(f"✓ Updated repository: {repo_org}/{repo_name}")
        print(f"  Status changed: {old_status} → {status}")

    except Exception as e:
        conn.rollback()
        print(f"Error updating repository status: {e}")
        raise
    finally:
        conn.close()


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 set_repo_status.py <organization/name> <status>")
        print("Example: python3 set_repo_status.py com.augustnagro/magnum experimental")
        print(f"\nValid statuses: {', '.join(VALID_STATUSES)}")
        sys.exit(1)

    repo_identifier = sys.argv[1]
    status = sys.argv[2]

    set_repository_status(repo_identifier, status)


if __name__ == "__main__":
    main()
