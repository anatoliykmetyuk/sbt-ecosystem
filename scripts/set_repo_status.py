#!/usr/bin/env python3
"""
Script to manually set the status of a repository or artifact in the database.
Supports both repository identifiers (organization/name) and artifact identifiers (organization:name:version).
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "database" / "sbt_ecosystem.db"

VALID_STATUSES = ["not_ported", "blocked", "experimental", "upstream"]


def validate_status(status):
    """Validate status value"""
    if status not in VALID_STATUSES:
        print(f"Error: Invalid status '{status}'")
        print(f"Valid statuses: {', '.join(VALID_STATUSES)}")
        sys.exit(1)


def set_repository_status(repo_identifier, status):
    """Set the status of a repository"""
    validate_status(status)

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


def set_artifact_status(artifact_identifier, status):
    """Set the status of an artifact"""
    validate_status(status)

    # Parse artifact identifier (organization:name:version)
    if ":" not in artifact_identifier:
        print(f"Error: Artifact identifier must be in format 'organization:name:version'")
        print(f"Got: {artifact_identifier}")
        sys.exit(1)

    parts = artifact_identifier.split(":")
    if len(parts) != 3:
        print(f"Error: Artifact identifier must be in format 'organization:name:version'")
        print(f"Got: {artifact_identifier}")
        sys.exit(1)

    org, name, version = parts

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Find the artifact
        cursor.execute("""
            SELECT id, organization, name, version, status, repository_id
            FROM artifacts
            WHERE organization = ? AND name = ? AND version = ?
        """, (org, name, version))

        result = cursor.fetchone()

        if not result:
            print(f"Error: Artifact '{org}:{name}:{version}' not found in database")
            sys.exit(1)

        artifact_id, artifact_org, artifact_name, artifact_version, old_status, repo_id = result

        # Update status
        cursor.execute("""
            UPDATE artifacts
            SET status = ?, updated_at = datetime('now')
            WHERE id = ?
        """, (status, artifact_id))

        conn.commit()

        print(f"✓ Updated artifact: {artifact_org}:{artifact_name}:{artifact_version}")
        if old_status:
            print(f"  Status changed: {old_status} → {status}")
        else:
            print(f"  Status set: {status} (was NULL)")
        if repo_id:
            cursor.execute("SELECT organization, name FROM repositories WHERE id = ?", (repo_id,))
            repo_info = cursor.fetchone()
            if repo_info:
                print(f"  Repository: {repo_info[0]}/{repo_info[1]}")

    except Exception as e:
        conn.rollback()
        print(f"Error updating artifact status: {e}")
        raise
    finally:
        conn.close()


def set_status(identifier, status):
    """Set status for either a repository or artifact based on identifier format"""
    # Determine if it's a repository (contains /) or artifact (contains : and has 3 parts)
    # Check for artifact format first (more specific: org:name:version)
    if ":" in identifier:
        parts = identifier.split(":")
        if len(parts) == 3:
            # Artifact identifier: organization:name:version
            set_artifact_status(identifier, status)
            return

    # Check for repository format (org/name)
    if "/" in identifier:
        # Repository identifier: organization/name
        set_repository_status(identifier, status)
        return

    # Neither format matched
    print(f"Error: Identifier must be either:")
    print(f"  - Repository format: 'organization/name'")
    print(f"  - Artifact format: 'organization:name:version'")
    print(f"Got: {identifier}")
    sys.exit(1)


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 set_repo_status.py <identifier> <status>")
        print()
        print("Identifier formats:")
        print("  - Repository: organization/name")
        print("    Example: com.augustnagro/magnum")
        print("  - Artifact: organization:name:version")
        print("    Example: org.scalameta:sbt-scalafmt:2.5.6")
        print()
        print(f"Valid statuses: {', '.join(VALID_STATUSES)}")
        sys.exit(1)

    identifier = sys.argv[1]
    status = sys.argv[2]

    set_status(identifier, status)


if __name__ == "__main__":
    main()
