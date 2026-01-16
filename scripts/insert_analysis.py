#!/usr/bin/env python3
"""
Script to insert ANALYZE JSON output into the SQLite database
"""

import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "database" / "sbt_ecosystem.db"
SCHEMA_PATH = Path(__file__).parent.parent / "database" / "schema.sql"

def initialize_database(conn):
    """Initialize database schema if tables don't exist"""
    cursor = conn.cursor()

    # Check if repositories table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='repositories'
    """)

    if cursor.fetchone() is None:
        print("Initializing database schema...")
        # Read and execute schema
        with open(SCHEMA_PATH, 'r') as f:
            schema_sql = f.read()
        cursor.executescript(schema_sql)
        conn.commit()
        print("✓ Database initialized")
    else:
        print("✓ Database already initialized")

def get_or_create_artifact(cursor, org, name, is_plugin, repository_id=None, subproject=None, is_published=True, scala_version=None, status=None):
    """Get existing artifact ID or create new artifact. Only updates fields that are provided (not None), preserving existing values."""
    cursor.execute("""
        SELECT id, repository_id, status FROM artifacts
        WHERE organization = ? AND name = ?
    """, (org, name))
    result = cursor.fetchone()

    if result:
        artifact_id = result[0]
        existing_repository_id = result[1]
        existing_status = result[2]

        # CRITICAL: Preserve existing repository_id if new one is None
        # NEVER overwrite a valid repository_id with NULL - this breaks artifact-repository links!
        if repository_id is None and existing_repository_id is not None:
            repository_id = existing_repository_id

        # If status is not provided but repository_id is, get status from repository
        if status is None and repository_id is not None:
            cursor.execute("SELECT status FROM repositories WHERE id = ?", (repository_id,))
            repo_status_result = cursor.fetchone()
            if repo_status_result:
                status = repo_status_result[0]
            elif existing_status is not None:
                # Preserve existing status if repository doesn't have one
                status = existing_status
        elif status is None and existing_status is not None:
            # Preserve existing status if no new status provided
            status = existing_status

        # Update fields - repository_id is preserved above if it was None
        cursor.execute("""
            UPDATE artifacts
            SET is_plugin = ?, repository_id = ?, subproject = ?, is_published = ?, scala_version = ?, status = ?
            WHERE id = ?
        """, (is_plugin, repository_id, subproject, is_published, scala_version, status, artifact_id))

        return artifact_id
    else:
        # If status is not provided but repository_id is, get status from repository
        if status is None and repository_id is not None:
            cursor.execute("SELECT status FROM repositories WHERE id = ?", (repository_id,))
            repo_status_result = cursor.fetchone()
            if repo_status_result:
                status = repo_status_result[0]

        cursor.execute("""
            INSERT INTO artifacts (organization, name, is_plugin, repository_id, subproject, is_published, scala_version, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (org, name, is_plugin, repository_id, subproject, is_published, scala_version, status))
        return cursor.lastrowid

def insert_analysis(json_path):
    """Insert analysis JSON into database"""
    # Read JSON file
    with open(json_path, 'r') as f:
        data = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Initialize database if needed
    initialize_database(conn)

    try:
        # 1. Insert or update repository (always overwrite with new analysis)
        repo = data['repository']
        cursor.execute("""
            SELECT id FROM repositories WHERE url = ?
        """, (repo['url'],))
        result = cursor.fetchone()

        if result:
            repo_id = result[0]

            # Always overwrite all fields with new analysis data
            cursor.execute("""
                UPDATE repositories
                SET organization = ?, name = ?, is_plugin_containing_repo = ?, status = ?
                WHERE id = ?
            """, (repo['organization'], repo['name'], data['isPluginContainingRepo'], data['status'], repo_id))
        else:
            cursor.execute("""
                INSERT INTO repositories (url, organization, name, is_plugin_containing_repo, status)
                VALUES (?, ?, ?, ?, ?)
            """, (repo['url'], repo['organization'], repo['name'],
                  data['isPluginContainingRepo'], data['status']))
            repo_id = cursor.lastrowid

        print(f"✓ Repository: {repo['organization']}/{repo['name']} (ID: {repo_id})")

        # 2. Delete existing plugin dependencies and insert new ones (overwrite)
        cursor.execute("""
            DELETE FROM repository_plugin_dependencies WHERE repository_id = ?
        """, (repo_id,))

        for plugin_dep in data['pluginDependencies']:
            plugin_art_id = get_or_create_artifact(
                cursor,
                plugin_dep['organization'],
                plugin_dep['name'],
                is_plugin=True,
                repository_id=None,
                is_published=True,
                status=None  # Artifacts without repositories have NULL status
            )

            cursor.execute("""
                INSERT INTO repository_plugin_dependencies (repository_id, plugin_artifact_id, version)
                VALUES (?, ?, ?)
            """, (repo_id, plugin_art_id, plugin_dep['version']))

        print(f"✓ Plugin dependencies: {len(data['pluginDependencies'])}")

        # 3. Insert published artifacts and their dependencies
        # Get repository status for artifacts
        repo_status = data.get('status', 'not_ported')

        for artifact in data['publishedArtifacts']:
            artifact_id = get_or_create_artifact(
                cursor,
                artifact['organization'],
                artifact['name'],
                is_plugin=artifact['isPlugin'],
                repository_id=repo_id,
                subproject=artifact.get('subproject'),
                is_published=artifact.get('isPublished', True),
                scala_version=artifact.get('scalaVersion'),
                status=repo_status  # Artifact status matches repository status
            )

            # Delete existing library dependencies and insert new ones (overwrite)
            cursor.execute("""
                DELETE FROM artifact_dependencies WHERE dependent_artifact_id = ?
            """, (artifact_id,))

            # Insert library dependencies for this artifact
            for lib_dep in artifact.get('libraryDependencies', []):
                # Get or create dependency artifact
                dep_art_id = get_or_create_artifact(
                    cursor,
                    lib_dep['organization'],
                    lib_dep['name'],
                    is_plugin=False,
                    repository_id=None,
                    is_published=True,
                    status=None  # Artifacts without repositories have NULL status
                )

                # Insert artifact dependency
                cursor.execute("""
                    INSERT INTO artifact_dependencies (dependent_artifact_id, dependency_artifact_id, version, scope)
                    VALUES (?, ?, ?, ?)
                """, (artifact_id, dep_art_id, lib_dep['version'], lib_dep['scope']))

            deps_count = len(artifact.get('libraryDependencies', []))
            artifact_type = "Plugin" if artifact['isPlugin'] else "Library"
            print(f"✓ {artifact_type}: {artifact['organization']}:{artifact['name']} ({deps_count} dependencies)")

        conn.commit()
        print(f"\n✓ Successfully inserted analysis data from {json_path}")

    except Exception as e:
        conn.rollback()
        print(f"✗ Error inserting data: {e}")
        raise
    finally:
        conn.close()

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 insert_analysis.py <analysis.json>")
        sys.exit(1)

    json_path = Path(sys.argv[1])
    if not json_path.exists():
        print(f"Error: File not found: {json_path}")
        sys.exit(1)

    insert_analysis(json_path)

if __name__ == "__main__":
    main()
