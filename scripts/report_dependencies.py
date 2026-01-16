#!/usr/bin/env python3
"""
Script to generate a recursive dependency report for a repository.
Shows all plugin dependencies and their source repositories in a tree format.
"""

import sqlite3
import sys
from pathlib import Path
from collections import defaultdict

DB_PATH = Path(__file__).parent.parent / "database" / "sbt_ecosystem.db"

# ANSI color codes
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RESET = "\033[0m"


def get_status_letter(status):
    """Convert status to single letter indicator"""
    if status is None:
        return "?"  # Artifact without known repository
    status_map = {
        "not_ported": "X",  # Not yet ported
        "experimental": "E",
        "upstream": "✓",  # Upstream-ported (tick mark)
        "blocked": "B"
    }
    return status_map.get(status, "?")


def find_repository(cursor, org, name):
    """Find repository by organization and name"""
    cursor.execute("""
        SELECT id, organization, name, status
        FROM repositories
        WHERE organization = ? AND name = ?
    """, (org, name))
    return cursor.fetchone()


def get_plugin_dependencies(cursor, repository_id):
    """Get all plugin dependencies for a repository"""
    cursor.execute("""
        SELECT
            a.id,
            a.organization,
            a.name,
            a.repository_id,
            a.status,
            rpd.version as dep_version
        FROM repository_plugin_dependencies rpd
        JOIN artifacts a ON rpd.plugin_artifact_id = a.id
        WHERE rpd.repository_id = ?
        ORDER BY a.organization, a.name
    """, (repository_id,))
    return cursor.fetchall()


def get_repository_for_plugin(cursor, plugin_artifact_id):
    """Get repository information for a plugin artifact"""
    cursor.execute("""
        SELECT r.id, r.organization, r.name, r.status
        FROM artifacts a
        JOIN repositories r ON a.repository_id = r.id
        WHERE a.id = ? AND a.repository_id IS NOT NULL
    """, (plugin_artifact_id,))
    return cursor.fetchone()


def format_repo_name(org, name):
    """Format repository name as organization/name"""
    return f"{org}/{name}"


def format_artifact_name(org, name, version=None):
    """Format artifact name with optional version"""
    if version:
        return f"{org}:{name}:{version}"
    return f"{org}:{name}"


def colorize_status_letter(status_letter):
    """Colorize status letter: X=red, ✓=green, others=no color"""
    if status_letter == "X":
        return f"{RED}{status_letter}{RESET}"
    elif status_letter == "✓":
        return f"{GREEN}{status_letter}{RESET}"
    else:
        return status_letter


def colorize_already_visited(text):
    """Colorize (already visited) text in yellow"""
    return f"{YELLOW}{text}{RESET}"


def print_dependency_tree(cursor, repository_id, org, name, status, visited_repos, visited_artifacts, indent=""):
    """Recursively print dependency tree"""
    # Format the current repository/artifact
    status_letter = get_status_letter(status)
    colored_status = colorize_status_letter(status_letter)
    repo_name = format_repo_name(org, name)
    print(f"{indent}{colored_status} {repo_name}")

    # Mark as visited
    visited_repos.add(repository_id)

    # Get plugin dependencies
    plugin_deps = get_plugin_dependencies(cursor, repository_id)

    if not plugin_deps:
        return

    # Process each plugin dependency
    for i, (plugin_id, plugin_org, plugin_name, plugin_repo_id, plugin_status, dep_version) in enumerate(plugin_deps):
        is_last = (i == len(plugin_deps) - 1)
        tree_char = "└─" if is_last else "├─"
        child_indent = indent + tree_char + " "
        next_indent = indent + ("   " if is_last else "│  ")

        artifact_key = (plugin_org, plugin_name)

        # Try to find repository for this plugin FIRST
        repo_info = get_repository_for_plugin(cursor, plugin_id)

        if repo_info:
            # Plugin comes from a repository - always show as repository
            plugin_repo_id, plugin_repo_org, plugin_repo_name, plugin_repo_status = repo_info

            if plugin_repo_id in visited_repos:
                # Already visited this repository
                status_letter = get_status_letter(plugin_repo_status)
                colored_status = colorize_status_letter(status_letter)
                repo_name = format_repo_name(plugin_repo_org, plugin_repo_name)
                already_visited_text = colorize_already_visited("(already visited)")
                print(f"{child_indent}{colored_status} {repo_name} {already_visited_text}")
                continue

            # Mark artifact as visited to avoid processing it again elsewhere
            visited_artifacts.add(artifact_key)

            # Only check repository status to decide whether to recurse
            # Repository status is the source of truth, not artifact status
            if plugin_repo_status == "upstream":
                # Plugin is ported - don't recurse deeper, just show it
                status_letter = get_status_letter(plugin_repo_status)
                colored_status = colorize_status_letter(status_letter)
                repo_name = format_repo_name(plugin_repo_org, plugin_repo_name)
                print(f"{child_indent}{colored_status} {repo_name}")
            else:
                # Plugin is not ported - recurse to show its dependencies
                print_dependency_tree(
                    cursor,
                    plugin_repo_id,
                    plugin_repo_org,
                    plugin_repo_name,
                    plugin_repo_status,
                    visited_repos,
                    visited_artifacts,
                    next_indent
                )
        else:
            # Plugin doesn't have a known repository - show as artifact
            if artifact_key in visited_artifacts:
                # Show as already visited - use artifact status if available
                status_letter = get_status_letter(plugin_status)
                colored_status = colorize_status_letter(status_letter)
                artifact_name = format_artifact_name(plugin_org, plugin_name, dep_version)
                print(f"{child_indent}{colored_status} {artifact_name}")
                continue

            visited_artifacts.add(artifact_key)

            # Plugin doesn't have a known repository - use artifact status if available
            # If artifact status is "upstream", we still show it but don't recurse (no repo to recurse into anyway)
            status_letter = get_status_letter(plugin_status)
            colored_status = colorize_status_letter(status_letter)
            artifact_name = format_artifact_name(plugin_org, plugin_name, dep_version)
            print(f"{child_indent}{colored_status} {artifact_name}")


def generate_report(repo_identifier):
    """Generate dependency report for a repository"""
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
        repo_info = find_repository(cursor, org, name)

        if not repo_info:
            print(f"Error: Repository '{org}/{name}' not found in database")
            sys.exit(1)

        repo_id, repo_org, repo_name, repo_status = repo_info

        # Print header
        print(f"Dependency Report for: {format_repo_name(repo_org, repo_name)}")
        print(f"Status: {repo_status or 'unknown'}")
        print("=" * 60)
        print()
        print("Legend:")
        print("  ✓ = upstream (ported)")
        print("  X = not_ported")
        print("  E = experimental")
        print("  B = blocked")
        print("  ? = artifact without known repository")
        print()
        print("Dependency Tree:")
        print()

        # Generate tree
        visited_repos = set()
        visited_artifacts = set()
        print_dependency_tree(
            cursor,
            repo_id,
            repo_org,
            repo_name,
            repo_status,
            visited_repos,
            visited_artifacts,
            ""
        )

    except Exception as e:
        print(f"Error generating report: {e}")
        raise
    finally:
        conn.close()


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 report_dependencies.py <organization/name>")
        print("Example: python3 report_dependencies.py com.augustnagro/magnum")
        sys.exit(1)

    repo_identifier = sys.argv[1]
    generate_report(repo_identifier)


if __name__ == "__main__":
    main()
