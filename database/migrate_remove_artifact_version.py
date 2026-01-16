#!/usr/bin/env python3
"""
Migration script to remove version column from artifacts table
and change unique constraint from (organization, name, version) to (organization, name)
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
        print("Starting migration: Remove version column from artifacts")
        print("=" * 60)

        # Step 1: Handle duplicate (organization, name) pairs
        print("\nStep 1: Handling duplicate (organization, name) pairs...")
        cursor.execute("""
            SELECT organization, name, COUNT(*) as count
            FROM artifacts
            GROUP BY organization, name
            HAVING COUNT(*) > 1
        """)
        duplicates = cursor.fetchall()

        if duplicates:
            print(f"  Found {len(duplicates)} artifacts with multiple versions")

            for org, name, count in duplicates:
                # Get all versions of this artifact
                cursor.execute("""
                    SELECT id, version, repository_id, status, created_at
                    FROM artifacts
                    WHERE organization = ? AND name = ?
                    ORDER BY
                        CASE WHEN repository_id IS NOT NULL THEN 0 ELSE 1 END,
                        created_at DESC
                """, (org, name))
                artifacts = cursor.fetchall()

                # Keep the first one (prefer one with repository_id, then most recent)
                keep_id = artifacts[0][0]
                keep_version = artifacts[0][1]

                print(f"  {org}:{name} - keeping id {keep_id} (version {keep_version}), removing {count - 1} duplicates")

                # Update foreign keys in artifact_dependencies
                for artifact_id, _, _, _, _ in artifacts[1:]:
                    # Update dependent_artifact_id
                    cursor.execute("""
                        UPDATE artifact_dependencies
                        SET dependent_artifact_id = ?
                        WHERE dependent_artifact_id = ?
                    """, (keep_id, artifact_id))

                    # Update dependency_artifact_id
                    cursor.execute("""
                        UPDATE artifact_dependencies
                        SET dependency_artifact_id = ?
                        WHERE dependency_artifact_id = ?
                    """, (keep_id, artifact_id))

                # Update foreign keys in repository_plugin_dependencies
                for artifact_id, _, _, _, _ in artifacts[1:]:
                    cursor.execute("""
                        UPDATE repository_plugin_dependencies
                        SET plugin_artifact_id = ?
                        WHERE plugin_artifact_id = ?
                    """, (keep_id, artifact_id))

                # Delete duplicate artifacts
                duplicate_ids = [a[0] for a in artifacts[1:]]
                placeholders = ','.join('?' * len(duplicate_ids))
                cursor.execute(f"""
                    DELETE FROM artifacts
                    WHERE id IN ({placeholders})
                """, duplicate_ids)
        else:
            print("  No duplicates found")

        conn.commit()
        print("  ✓ Duplicates handled")

        # Step 2: Drop old index
        print("\nStep 2: Dropping old index...")
        try:
            cursor.execute("DROP INDEX IF EXISTS idx_artifacts_org_name_version")
            print("  ✓ Dropped idx_artifacts_org_name_version")
        except Exception as e:
            print(f"  Note: {e}")

        # Step 3: Drop old unique constraint (SQLite doesn't support DROP CONSTRAINT directly)
        # We'll recreate the table
        print("\nStep 3: Recreating artifacts table without version column...")

        # Create new table
        cursor.execute("""
            CREATE TABLE artifacts_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization TEXT NOT NULL,
                name TEXT NOT NULL,
                is_plugin BOOLEAN NOT NULL DEFAULT 0,
                repository_id INTEGER,
                subproject TEXT,
                is_published BOOLEAN DEFAULT 1,
                status TEXT CHECK(status IN ('not_ported', 'blocked', 'experimental', 'upstream')),
                scala_version TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (repository_id) REFERENCES repositories(id) ON DELETE SET NULL,
                UNIQUE(organization, name)
            )
        """)

        # Copy data (excluding version column)
        cursor.execute("""
            INSERT INTO artifacts_new
            (id, organization, name, is_plugin, repository_id, subproject, is_published, status, scala_version, created_at, updated_at)
            SELECT
                id, organization, name, is_plugin, repository_id, subproject, is_published, status, scala_version, created_at, updated_at
            FROM artifacts
        """)

        # Drop old table
        cursor.execute("DROP TABLE artifacts")

        # Rename new table
        cursor.execute("ALTER TABLE artifacts_new RENAME TO artifacts")

        print("  ✓ Table recreated")

        # Step 4: Recreate indexes
        print("\nStep 4: Recreating indexes...")
        cursor.execute("CREATE INDEX idx_artifacts_org_name ON artifacts(organization, name)")
        cursor.execute("CREATE INDEX idx_artifacts_repository_id ON artifacts(repository_id)")
        cursor.execute("CREATE INDEX idx_artifacts_is_plugin ON artifacts(is_plugin)")
        cursor.execute("CREATE INDEX idx_artifacts_status ON artifacts(status)")
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
