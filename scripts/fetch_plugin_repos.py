#!/usr/bin/env python3
"""
Script to fetch plugin repository URLs from Maven Central POM files
"""

import sqlite3
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

DB_PATH = Path(__file__).parent.parent / "database" / "sbt_ecosystem.db"

# Maven Central base URL
MAVEN_CENTRAL_BASE = "https://repo1.maven.org/maven2"

def maven_path_to_url(organization, name, version, scala_version="2.12", sbt_version="1.0"):
    """Convert Maven coordinates to Maven Central URL path"""
    org_path = organization.replace('.', '/')
    # SBT plugins have format: name_scalaVersion_sbtVersion
    artifact_name = f"{name}_{scala_version}_{sbt_version}"
    return f"{MAVEN_CENTRAL_BASE}/{org_path}/{artifact_name}/{version}/{artifact_name}-{version}.pom"

def fetch_pom(organization, name, version, scala_version="2.12", sbt_version="1.0"):
    """Fetch POM file from Maven Central"""
    url = maven_path_to_url(organization, name, version, scala_version, sbt_version)
    print(f"  Trying: {url}")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        print(f"  ✓ Found POM")
        return response.text
    except requests.exceptions.RequestException:
        return None

def extract_scm_url(pom_xml):
    """Extract SCM URL from POM XML"""
    try:
        root = ET.fromstring(pom_xml)
        # Register namespaces
        ns = {'maven': 'http://maven.apache.org/POM/4.0.0'}

        # Try to find SCM section
        scm = root.find('.//maven:scm', ns)
        if scm is not None:
            # Try connection or developerConnection
            connection = scm.find('maven:connection', ns)
            url_elem = scm.find('maven:url', ns)
            developer_connection = scm.find('maven:developerConnection', ns)

            # Prefer developerConnection, then url, then connection
            scm_url = None
            if developer_connection is not None and developer_connection.text:
                scm_url = developer_connection.text
            elif url_elem is not None and url_elem.text:
                scm_url = url_elem.text
            elif connection is not None and connection.text:
                scm_url = connection.text

            if scm_url:
                # Convert SCM URL format (scm:git:https://...) to regular URL
                if scm_url.startswith('scm:git:'):
                    scm_url = scm_url.replace('scm:git:', '')
                elif scm_url.startswith('scm:'):
                    parts = scm_url.split(':', 2)
                    if len(parts) > 2:
                        scm_url = parts[2]
                    else:
                        scm_url = parts[-1]

                # Fix double slashes
                scm_url = scm_url.replace('https:///', 'https://').replace('http:///', 'http://')

                # Remove .git suffix if present and convert to https if needed
                if scm_url.endswith('.git'):
                    scm_url = scm_url[:-4]

                # Convert git@github.com:user/repo.git to https://github.com/user/repo
                if scm_url.startswith('git@'):
                    scm_url = scm_url.replace('git@', 'https://').replace(':', '/')
                    if scm_url.endswith('.git'):
                        scm_url = scm_url[:-4]

                return scm_url

        # Fallback: try to find homepage
        homepage = root.find('.//maven:url', ns)
        if homepage is not None and homepage.text:
            # If homepage looks like a GitHub URL, use it
            if 'github.com' in homepage.text:
                return homepage.text

    except ET.ParseError as e:
        print(f"  Error parsing POM XML: {e}")
    except Exception as e:
        print(f"  Error extracting SCM URL: {e}")

    return None

def update_plugin_repositories():
    """Fetch repository URLs for plugins and update database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all plugins without repository_id
    cursor.execute("""
        SELECT id, organization, name, version
        FROM artifacts
        WHERE is_plugin = 1 AND repository_id IS NULL
        ORDER BY organization, name
    """)

    plugins = cursor.fetchall()

    print(f"Found {len(plugins)} plugins to look up")
    print("=" * 60)

    for plugin in plugins:
        print(f"\nPlugin: {plugin['organization']}:{plugin['name']}:{plugin['version']}")

        # Fetch POM - SBT plugins use _scalaVersion_sbtVersion in artifact name
        # Try common combinations: 2.12/1.0, 2.12/1.0, 2.13/1.0
        pom_xml = None
        for scala_ver, sbt_ver in [("2.12", "1.0"), ("2.13", "1.0"), ("2.12", "2.0")]:
            pom_xml = fetch_pom(plugin['organization'], plugin['name'], plugin['version'], scala_ver, sbt_ver)
            if pom_xml:
                break

        if pom_xml:
            repo_url = extract_scm_url(pom_xml)
            if repo_url:
                print(f"  Found repository URL: {repo_url}")
                # Check if repository already exists
                cursor.execute("""
                    SELECT id FROM repositories WHERE url = ?
                """, (repo_url,))
                existing = cursor.fetchone()

                if existing:
                    repo_id = existing['id']
                    print(f"  Repository already exists in database (ID: {repo_id})")
                else:
                    # Extract org/name from URL for new repository
                    # Try to parse GitHub URL
                    if 'github.com' in repo_url:
                        parts = repo_url.rstrip('/').split('/')
                        if len(parts) >= 2:
                            repo_name = parts[-1]
                            org_name = parts[-2] if len(parts) > 1 else None
                            # Try to infer organization from URL or use a placeholder
                            org = org_name if org_name else 'unknown'

                            cursor.execute("""
                                INSERT INTO repositories (url, organization, name, sbt_version, is_plugin_containing_repo, status)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (repo_url, org, repo_name, 'unknown', 1, 'not_ported'))
                            repo_id = cursor.lastrowid
                            print(f"  Created new repository entry (ID: {repo_id})")
                        else:
                            print(f"  Could not parse repository URL: {repo_url}")
                            repo_id = None
                    else:
                        print(f"  Non-GitHub URL, skipping repository creation: {repo_url}")
                        repo_id = None

                if repo_id:
                    # Update artifact to link to repository
                    cursor.execute("""
                        UPDATE artifacts
                        SET repository_id = ?
                        WHERE id = ?
                    """, (repo_id, plugin['id']))
                    print(f"  Updated artifact to link to repository")
            else:
                print("  Could not extract repository URL from POM")
        else:
            print("  Could not fetch POM file")

    conn.commit()
    conn.close()
    print("\n" + "=" * 60)
    print("Done!")

if __name__ == "__main__":
    update_plugin_repositories()
