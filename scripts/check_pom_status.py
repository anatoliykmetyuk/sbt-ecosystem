#!/usr/bin/env python3
"""
Script to check whether the SBT 2.x form of an sbt plugin is available on Maven Central.

This script checks if a plugin's project directory exists in SBT 2.x format (SBT 2, Scala 3).
It returns HTTP 200 if the SBT 2.x form is available at any version, or 404 if it is not.

Given an artifact specification like: com.github.sbt:sbt-git:2.0.0
(Note: version is parsed but not used - we check if the project is ported at all)
"""

import sys
import warnings

# Suppress urllib3 OpenSSL/LibreSSL warning
# Must be done before importing urllib3 (which is imported by requests)
warnings.filterwarnings('ignore', message='.*urllib3 v2 only supports OpenSSL.*')
warnings.filterwarnings('ignore', category=UserWarning, module='urllib3')

import urllib3
urllib3.disable_warnings()

import requests
from urllib.parse import urlparse

# Maven Central base URL
MAVEN_CENTRAL_BASE = "https://repo1.maven.org/maven2"

def maven_path_to_url_sbt2(organization, name, sbt_version, scala_version):
    """Convert Maven coordinates to Maven Central directory URL for SBT 2.x plugins"""
    org_path = organization.replace('.', '/')
    # SBT 2.x plugins have format: name_sbt{sbtVersion}_{scalaVersion}
    artifact_name = f"{name}_sbt{sbt_version}_{scala_version}"
    return f"{MAVEN_CENTRAL_BASE}/{org_path}/{artifact_name}/"

def check_pom_status(organization, name, version):
    """
    Check whether the SBT 2.x form of the plugin is available on Maven Central.

    Checks if the project directory exists (any version), not a specific version.

    Returns 200 if the SBT 2.x form (SBT 2, Scala 3) is available at any version, 404 if not.
    """
    print(f"Checking if SBT 2.x project exists for: {organization}:{name}:{version}")
    print("=" * 60)

    # SBT 2.x combination: SBT 2 with Scala 3
    sbt_ver = "2"
    scala_ver = "3"

    results = []

    # Check SBT 2.x directory URL (not specific version)
    url = maven_path_to_url_sbt2(organization, name, sbt_ver, scala_ver)
    try:
        response = requests.head(url, timeout=10, allow_redirects=True)
        status = response.status_code
        results.append({
            'url': url,
            'status': status,
            'format': f'SBT 2.x (SBT {sbt_ver}, Scala {scala_ver})'
        })
        print(f"[{status}] {url}")
        print(f"  Format: SBT 2.x (SBT {sbt_ver}, Scala {scala_ver})")
        if status == 200:
            print(f"  ✓ Project is ported to SBT 2.x (at least one version exists)")
        else:
            print(f"  ✗ Project is not ported to SBT 2.x")
    except requests.exceptions.RequestException as e:
        results.append({
            'url': url,
            'status': 'ERROR',
            'error': str(e),
            'format': f'SBT 2.x (SBT {sbt_ver}, Scala {scala_ver})'
        })
        print(f"[ERROR] {url}")
        print(f"  Format: SBT 2.x (SBT {sbt_ver}, Scala {scala_ver})")
        print(f"  Error: {e}")

    print("=" * 60)

    # Summary
    successful = [r for r in results if r['status'] == 200]
    if successful:
        print(f"\n✓ Found {len(successful)} successful URL(s):")
        for r in successful:
            print(f"  [{r['status']}] {r['format']}")
            print(f"    {r['url']}")
    else:
        print("\n✗ No successful URLs found")

    return results

def parse_artifact_spec(spec):
    """Parse artifact specification like 'com.github.sbt:sbt-git:2.0.0'"""
    parts = spec.split(':')
    if len(parts) != 3:
        raise ValueError(f"Invalid artifact specification: {spec}. Expected format: organization:name:version")
    return parts[0], parts[1], parts[2]

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 check_pom_status.py <organization:name:version>")
        print("Example: python3 check_pom_status.py com.github.sbt:sbt-git:2.0.0")
        sys.exit(1)

    artifact_spec = sys.argv[1]

    try:
        organization, name, version = parse_artifact_spec(artifact_spec)
        check_pom_status(organization, name, version)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)

if __name__ == "__main__":
    main()
