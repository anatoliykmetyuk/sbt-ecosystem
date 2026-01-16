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

def get_or_create_artifact(cursor, org, name, version, is_plugin, repository_id=None, subproject=None, is_published=True, scala_version=None, status=None):
    """Get existing artifact ID or create new artifact. Only fills in NULL values for existing artifacts."""
    cursor.execute("""
        SELECT id, repository_id, subproject, is_published, scala_version, status FROM artifacts
        WHERE organization = ? AND name = ? AND version = ?
    """, (org, name, version))
    result = cursor.fetchone()

    if result:
        artifact_id = result[0]
        existing_repo_id, existing_subproject, existing_is_published, existing_scala_version, existing_status = result[1:]

        # Only update NULL fields, don't overwrite existing data
        updates = []
        params = []

        if repository_id is not None and existing_repo_id is None:
            updates.append("repository_id = ?")
            params.append(repository_id)
            # If we're setting repository_id and status is provided, also update status
            if status is not None and existing_status is None:
                updates.append("status = ?")
                params.append(status)

        if subproject is not None and existing_subproject is None:
            updates.append("subproject = ?")
            params.append(subproject)

        if existing_is_published is None:
            updates.append("is_published = ?")
            params.append(is_published)

        if scala_version is not None and existing_scala_version is None:
            updates.append("scala_version = ?")
            params.append(scala_version)

        # If repository_id exists but status is NULL, try to get status from repository
        if existing_repo_id is not None and existing_status is None:
            cursor.execute("SELECT status FROM repositories WHERE id = ?", (existing_repo_id,))
            repo_status_result = cursor.fetchone()
            if repo_status_result:
                updates.append("status = ?")
                params.append(repo_status_result[0])

        if updates:
            params.append(artifact_id)
            cursor.execute(f"""
                UPDATE artifacts
                SET {', '.join(updates)}
                WHERE id = ?
            """, params)

        return artifact_id
    else:
        # If status is not provided but repository_id is, get status from repository
        if status is None and repository_id is not None:
            cursor.execute("SELECT status FROM repositories WHERE id = ?", (repository_id,))
            repo_status_result = cursor.fetchone()
            if repo_status_result:
                status = repo_status_result[0]

        cursor.execute("""
            INSERT INTO artifacts (organization, name, version, is_plugin, repository_id, subproject, is_published, scala_version, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (org, name, version, is_plugin, repository_id, subproject, is_published, scala_version, status))
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
        # 1. Insert or update repository (only fill NULL values)
        repo = data['repository']
        cursor.execute("""
            SELECT id, organization, name, sbt_version, is_plugin_containing_repo, status
            FROM repositories WHERE url = ?
        """, (repo['url'],))
        result = cursor.fetchone()

        if result:
            repo_id = result[0]
            existing_org, existing_name, existing_sbt_version, existing_is_plugin, existing_status = result[1:]

            # Only update NULL fields, don't overwrite existing data
            updates = []
            params = []

            if existing_org is None:
                updates.append("organization = ?")
                params.append(repo['organization'])

            if existing_name is None:
                updates.append("name = ?")
                params.append(repo['name'])

            if existing_sbt_version is None:
                updates.append("sbt_version = ?")
                params.append(data['sbtVersion'])

            if existing_is_plugin is None:
                updates.append("is_plugin_containing_repo = ?")
                params.append(data['isPluginContainingRepo'])

            if existing_status is None:
                updates.append("status = ?")
                params.append(data['status'])

            if updates:
                params.append(repo_id)
                cursor.execute(f"""
                    UPDATE repositories
                    SET {', '.join(updates)}
                    WHERE id = ?
                """, params)
        else:
            cursor.execute("""
                INSERT INTO repositories (url, organization, name, sbt_version, is_plugin_containing_repo, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (repo['url'], repo['organization'], repo['name'], data['sbtVersion'],
                  data['isPluginContainingRepo'], data['status']))
            repo_id = cursor.lastrowid

        print(f"✓ Repository: {repo['organization']}/{repo['name']} (ID: {repo_id})")

        # 2. Insert plugin dependencies
        for plugin_dep in data['pluginDependencies']:
            plugin_art_id = get_or_create_artifact(
                cursor,
                plugin_dep['organization'],
                plugin_dep['name'],
                plugin_dep['version'],
                is_plugin=True,
                repository_id=None,
                is_published=True,
                status=None  # Artifacts without repositories have NULL status
            )

            cursor.execute("""
                INSERT OR IGNORE INTO repository_plugin_dependencies (repository_id, plugin_artifact_id, version)
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
                artifact['version'],
                is_plugin=artifact['isPlugin'],
                repository_id=repo_id,
                subproject=artifact.get('subproject'),
                is_published=artifact.get('isPublished', True),
                scala_version=artifact.get('scalaVersion'),
                status=repo_status  # Artifact status matches repository status
            )

            # Insert library dependencies for this artifact
            for lib_dep in artifact.get('libraryDependencies', []):
                # Get or create dependency artifact
                dep_art_id = get_or_create_artifact(
                    cursor,
                    lib_dep['organization'],
                    lib_dep['name'],
                    lib_dep['version'],
                    is_plugin=False,
                    repository_id=None,
                    is_published=True,
                    status=None  # Artifacts without repositories have NULL status
                )

                # Insert artifact dependency
                cursor.execute("""
                    INSERT OR IGNORE INTO artifact_dependencies (dependent_artifact_id, dependency_artifact_id, version, scope)
                    VALUES (?, ?, ?, ?)
                """, (artifact_id, dep_art_id, lib_dep['version'], lib_dep['scope']))

            deps_count = len(artifact.get('libraryDependencies', []))
            artifact_type = "Plugin" if artifact['isPlugin'] else "Library"
            print(f"✓ {artifact_type}: {artifact['organization']}:{artifact['name']}:{artifact['version']} ({deps_count} dependencies)")

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
