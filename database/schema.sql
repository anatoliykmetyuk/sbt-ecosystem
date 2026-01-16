-- SBT Ecosystem Migration System - Database Schema
-- SQLite database for tracking repositories, artifacts, and dependencies

-- Repositories table
CREATE TABLE repositories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    organization TEXT NOT NULL,
    name TEXT NOT NULL,
    is_plugin_containing_repo BOOLEAN NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'not_ported' CHECK(status IN ('not_ported', 'blocked', 'experimental', 'upstream')),
    note TEXT,  -- Optional note about the repository (e.g., blocking reasons, special requirements)
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(organization, name)
);

-- Artifacts table (JARs/plugins published by repositories or referenced as dependencies)
CREATE TABLE artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization TEXT NOT NULL,
    name TEXT NOT NULL,
    is_plugin BOOLEAN NOT NULL DEFAULT 0,
    repository_id INTEGER,  -- NULL if artifact is known only from dependencies
    subproject TEXT,  -- Name of subproject that publishes this (if from repository)
    is_published BOOLEAN DEFAULT 1,
    status TEXT CHECK(status IN ('not_ported', 'blocked', 'experimental', 'upstream')),  -- Same as repository status, NULL if artifact has no repository
    scala_version TEXT,  -- May be NULL for non-Scala artifacts
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (repository_id) REFERENCES repositories(id) ON DELETE SET NULL,
    UNIQUE(organization, name)
);

-- Plugin dependencies: repositories depend on SBT plugins
CREATE TABLE repository_plugin_dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repository_id INTEGER NOT NULL,
    plugin_artifact_id INTEGER NOT NULL,
    version TEXT NOT NULL,  -- Version of plugin that repository depends on (may differ from artifact version)
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (repository_id) REFERENCES repositories(id) ON DELETE CASCADE,
    FOREIGN KEY (plugin_artifact_id) REFERENCES artifacts(id) ON DELETE CASCADE,
    UNIQUE(repository_id, plugin_artifact_id, version)
);

-- Artifact dependencies: artifacts can depend on other artifacts
-- (useful for building complete dependency graphs)
CREATE TABLE artifact_dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dependent_artifact_id INTEGER NOT NULL,
    dependency_artifact_id INTEGER NOT NULL,
    version TEXT NOT NULL,  -- Version of dependency that artifact depends on (may differ from artifact version)
    scope TEXT CHECK(scope IN ('Compile', 'Test', 'Provided', 'Runtime')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (dependent_artifact_id) REFERENCES artifacts(id) ON DELETE CASCADE,
    FOREIGN KEY (dependency_artifact_id) REFERENCES artifacts(id) ON DELETE CASCADE,
    UNIQUE(dependent_artifact_id, dependency_artifact_id, version, scope)
);

-- Indexes for performance
CREATE INDEX idx_repositories_url ON repositories(url);
CREATE INDEX idx_repositories_org_name ON repositories(organization, name);
CREATE INDEX idx_repositories_status ON repositories(status);

CREATE INDEX idx_artifacts_org_name ON artifacts(organization, name);
CREATE INDEX idx_artifacts_repository_id ON artifacts(repository_id);
CREATE INDEX idx_artifacts_is_plugin ON artifacts(is_plugin);
CREATE INDEX idx_artifacts_status ON artifacts(status);

CREATE INDEX idx_repo_plugin_deps_repo ON repository_plugin_dependencies(repository_id);
CREATE INDEX idx_repo_plugin_deps_plugin ON repository_plugin_dependencies(plugin_artifact_id);

CREATE INDEX idx_artifact_deps_dependent ON artifact_dependencies(dependent_artifact_id);
CREATE INDEX idx_artifact_deps_dependency ON artifact_dependencies(dependency_artifact_id);
