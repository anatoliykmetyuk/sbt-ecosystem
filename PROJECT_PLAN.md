# SBT Ecosystem Migration System - Project Plan

## Overview

A system for managing and migrating SBT (Scala Build Tool) ecosystem repositories from SBT1 to SBT2. The system tracks repositories, their artifacts, dependencies, and migration status, with AI-powered analysis and migration capabilities.

## Core Concepts

### Repositories and Artifacts

- **Repositories**: Source code repositories containing SBT projects
- **Artifacts**: Publishable JAR files produced by subprojects
  - **Libraries**: Regular JAR files that are dependencies
  - **Plugins**: Special JAR files that also function as SBT plugins
    - Plugins are technically just JAR files, but have a special role
    - They require source code changes during migration (not just build file changes)
    - Regular libraries only need build file updates (SBT version bump)

### Dependency Graph

- Repositories build artifacts (JARs/plugins)
- Artifacts have dependencies on other artifacts
- Plugins can depend on other repositories/artifacts
- Forms an interconnected dependency graph
- Stored in **SQLite** database (file-based database)

### Repository Status

Repositories can have one of the following statuses:
- **Not Ported**: Not yet migrated to SBT2
- **Blocked**: Migration blocked by dependencies (references issue numbers)
- **Experimental**: Migrated but in experimental/testing phase
- **Upstream**: Fully migrated and merged upstream

## Operations

### 1. ANALYZE (repo)

**Purpose**: Extract dependency information from a cloned repository and populate the database.

**Process**:
1. Works on a cloned repository (local filesystem)
2. AI-powered analysis of the repository
3. Reads build files (e.g., `build.sbt`, `project/*.sbt`)
4. Extracts:
   - All artifacts published by subprojects
   - All dependencies (artifacts the repo depends on)
   - All plugin dependencies (with source repository URLs)
   - Artifact metadata (published status, JAR signatures, plugin detection)
   - SBT version and porting status
   - Whether the repo contains plugins
5. Outputs JSON with structured information (see `analyze-schema.json`)
6. JSON is mechanically inserted into SQLite database via script
7. Links artifacts to the repository in the dependency graph

**Key Questions Answered by Output**:
- What plugins does the repo depend on? → `pluginDependencies` array
- What are the repo URLs these plugins live in? → `pluginDependencies[].sourceRepositoryUrl`
- Is the repo a plugin-containing repo? → `isPluginContainingRepo` boolean
- Is this repo ported to sbt2? → `isPortedToSbt2` boolean

**Implementation**:
- Initially implemented as a Markdown file containing:
  - AI prompt with exact instructions
  - Exact input format (folder path to cloned repository)
  - Exact output format (JSON schema - see `analyze-schema.json` and `analyze-example.json`)
- The prompt guides AI to analyze build files and extract dependency information

### 2. PORT (repo)

**Purpose**: Migrate a repository from SBT1 to SBT2.

**Process**:
1. Determines if the repository contains plugins or just libraries
2. **If Plugin**:
   - Uses AI-powered prompt guidance for migrating plugins
   - Requires source code changes (plugin code migration)
   - Migrates both build files and plugin source code
3. **If Library**:
   - Uses simpler prompt for library migration
   - Only bumps SBT version to SBT2 in build files
   - No source code changes needed
4. Both paths use separate, specialized prompts

**Implementation**:
- Prompt-based approach (similar to ANALYZE)
- Separate prompts for plugin vs library migration
- Markdown files containing migration guidance

### 3. TEST (repo)

**Purpose**: Test a migrated repository.

**Process**:
- For experimental repos: publish all experimental DAGs, then run tests
- Validates that migration was successful

### 4. TEST_ALL

**Purpose**: Test all repositories in the ecosystem.

**Process**:
- **For upstream (merged) repos**: Clone all and run tests
- **For experimental repos**: Clone all, publish master branch, then test
- Can be containerized for isolated testing

### 5. VIEW_GRAPH (repo)

**Purpose**: Visualize the dependency graph for a repository or the ecosystem.

**Process**:
- Queries SQLite database for dependency information
- Renders graph visualization (nodes = artifacts/repos, edges = dependencies)
- Can be shared/exported

## Database Schema (SQLite)

The SQLite database stores:
- Repository metadata
- Artifact information (JARs, plugins)
- Dependency relationships
- Status information
- Plugin detection flags
- Published status
- JAR signatures

## Implementation Approach

### Phase 1: Core Infrastructure
- [ ] Set up SQLite database schema
- [ ] Create database connection and ORM/query layer
- [ ] Implement repository cloning mechanism
- [x] Create JSON schema for ANALYZE output (see `analyze-schema.json`)

### Phase 2: ANALYZE Operation
- [ ] Create ANALYZE prompt markdown file
  - Define input format (repository folder structure)
  - Define output JSON schema (reference `analyze-schema.json`)
  - Include instructions for extracting:
    - Published artifacts
    - Dependencies
    - Plugin dependencies (with source repository URLs)
    - Artifact metadata
    - SBT2 porting status
    - Plugin-containing repo detection
- [ ] Create script to:
  - Invoke AI with prompt
  - Parse JSON output
  - Insert data into SQLite database
- [ ] Test on sample repositories

### Phase 3: PORT Operation
- [ ] Create plugin detection logic/prompt
- [ ] Create plugin migration prompt markdown file
  - Guidance for migrating plugin source code
  - SBT2 plugin API changes
  - Build file updates for plugins
- [ ] Create library migration prompt markdown file
  - Simple SBT version bump guidance
  - Build file updates only
- [ ] Create script to:
  - Detect plugin vs library
  - Invoke appropriate AI prompt
  - Apply migration changes
- [ ] Test on sample repositories

### Phase 4: TEST Operations
- [ ] Implement TEST(repo) operation
- [ ] Implement TEST_ALL operation
- [ ] Add containerization support (optional)
- [ ] Integrate with CI/CD if needed

### Phase 5: VIEW_GRAPH Operation
- [ ] Create graph visualization tool
- [ ] Query SQLite for dependency data
- [ ] Render graph (using graphviz, d3.js, or similar)
- [ ] Add export/sharing capabilities

### Phase 6: Status Management
- [ ] Implement status tracking system
- [ ] Add blocking issue tracking
- [ ] Create status update workflows

## File Structure

```
sbt-ecosystem/
├── PROJECT_PLAN.md (this file)
├── prompts/
│   ├── analyze.md          # ANALYZE operation prompt
│   ├── port-plugin.md      # Plugin migration prompt
│   └── port-library.md     # Library migration prompt
├── scripts/
│   ├── analyze.py          # ANALYZE operation script
│   ├── port.py             # PORT operation script
│   ├── test.py             # TEST operations
│   └── view_graph.py       # Graph visualization
├── database/
│   ├── schema.sql          # SQLite schema
│   └── migrations/         # Database migrations
├── src/                    # Core library code (if needed)
└── tests/                  # Test repositories and test suite
```

## Key Design Decisions

1. **AI-Powered Analysis**: Using AI to parse build files provides flexibility for various SBT project structures
2. **Prompt-Based Approach**: Markdown prompts allow easy iteration and refinement of AI instructions
3. **SQLite Database**: File-based database is simple, portable, and sufficient for dependency graph storage
4. **JSON Intermediate Format**: Separates AI output from database insertion, allowing validation and debugging
5. **Plugin vs Library Distinction**: Critical for determining migration complexity and approach

## Success Criteria

- [ ] Can analyze any SBT1 repository and extract complete dependency information
- [ ] Can successfully migrate libraries (SBT version bump only)
- [ ] Can successfully migrate plugins (build + source code changes)
- [ ] Dependency graph accurately represents ecosystem relationships
- [ ] Status tracking helps prioritize and manage migration work
- [ ] Testing validates migrated repositories work correctly

## Future Enhancements

- Batch processing for multiple repositories
- Dependency conflict detection
- Migration progress dashboards
- Automated testing in CI/CD
- Rollback capabilities
- Integration with issue trackers for blocking issues
