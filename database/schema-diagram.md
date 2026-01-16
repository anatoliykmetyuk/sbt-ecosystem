# SBT Ecosystem Database Schema

## Entity Relationship Diagram

```mermaid
erDiagram
    repositories ||--o{ artifacts : "publishes"
    repositories ||--o{ repository_plugin_dependencies : "depends on"
    artifacts ||--o{ repository_plugin_dependencies : "referenced as"
    artifacts ||--o{ artifact_dependencies : "depends on (dependent)"
    artifacts ||--o{ artifact_dependencies : "depends on (dependency)"

    repositories {
        int id PK
        string url UK "Repository URL (e.g., https://github.com/org/repo)"
        string organization UK "e.g., com.example [UK: (org,name)]"
        string name UK "Repository name [UK: (org,name)]"
        boolean is_plugin_containing_repo "Publishes plugins?"
        string status "not_ported|blocked|experimental|upstream"
        datetime created_at
        datetime updated_at
    }

    artifacts {
        int id PK
        string organization UK "e.g., org.scalameta [UK: (org,name)]"
        string name UK "Artifact name [UK: (org,name)]"
        boolean is_plugin "Is SBT plugin?"
        int repository_id FK "NULL if known only from deps"
        string subproject "Subproject name (if from repo)"
        boolean is_published "Actually published?"
        string status "not_ported|blocked|experimental|upstream (nullable, matches repo status)"
        string scala_version "Scala version (nullable)"
        datetime created_at
        datetime updated_at
    }

    repository_plugin_dependencies {
        int id PK
        int repository_id UK "Repository using plugin (FK) [UK: (repo,plugin,version)]"
        int plugin_artifact_id UK "Plugin artifact (FK) [UK: (repo,plugin,version)]"
        string version UK "Version repo depends on [UK: (repo,plugin,version)]"
        datetime created_at
    }

    artifact_dependencies {
        int id PK
        int dependent_artifact_id UK "Artifact that depends (FK) [UK: (dep,dep_on,version,scope)]"
        int dependency_artifact_id UK "Artifact depended upon (FK) [UK: (dep,dep_on,version,scope)]"
        string version UK "Version depended on [UK: (dep,dep_on,version,scope)]"
        string scope UK "Compile|Test|Provided|Runtime [UK: (dep,dep_on,version,scope)]"
        datetime created_at
    }
```

**Unique Key Constraints:**
- `repositories`: `(organization, name)` - composite unique key
- `artifacts`: `(organization, name)` - composite unique key
- `repository_plugin_dependencies`: `(repository_id, plugin_artifact_id, version)` - composite unique key
- `artifact_dependencies`: `(dependent_artifact_id, dependency_artifact_id, version, scope)` - composite unique key

## Table Descriptions

### repositories
Stores information about SBT repositories (source code repositories). Each repository can have a status indicating its migration state. The `status` field indicates whether the repository has been ported to SBT 2.x (`upstream`), is blocked, experimental, or not yet ported.

### artifacts
Stores all artifacts (JARs/plugins) that are either:
- Published by a repository (repository_id is set)
- Referenced as dependencies (repository_id is NULL)

This allows tracking artifacts we know about from dependencies even before analyzing their source repository.

**Unique constraint**: `(organization, name)` - artifacts are uniquely identified by organization and name. Version information is not stored at the artifact level, as different versions of the same artifact are treated as the same logical artifact for migration tracking purposes.

The `status` field reflects whether the artifact is published for SBT2:
- For artifacts with a repository: status matches the repository's status
- For artifacts without a repository: status is NULL (unknown)

### repository_plugin_dependencies
Junction table linking repositories to the SBT plugins they depend on. Repositories depend on plugins directly (from `plugins.sbt` files). Plugins are special artifacts that require source code changes during migration.

### artifact_dependencies
Stores direct artifact-to-artifact dependencies. Artifacts can depend on other artifacts (both plugins and libraries). This enables building complete dependency graphs at the artifact level.

## Key Design Decisions

1. **Artifacts can exist without repositories**: An artifact might be known from dependencies before its source repository is analyzed. This is why `repository_id` is nullable.

2. **Repositories only depend on plugins**: Repositories declare plugin dependencies in `plugins.sbt`. Library dependencies are declared at the artifact level (in `build.sbt`), so they're tracked in `artifact_dependencies`, not at the repository level.

3. **Simple dependency model**:
   - Repositories → Plugins (via `repository_plugin_dependencies`)
   - Artifacts → Artifacts (via `artifact_dependencies`)
   - This reflects the actual SBT build structure where repositories use plugins, and artifacts depend on other artifacts.

4. **Version tracking in dependencies**: Both `repository_plugin_dependencies` and `artifact_dependencies` store the specific version that is depended upon. The `artifacts` table does not store version information - artifacts are uniquely identified by `(organization, name)` only. Version information is preserved in dependency relationships where it's needed.

5. **Timestamps**: All tables include `created_at` for audit trails, and repositories/artifacts have `updated_at` for tracking changes.

---

## ANALYZE JSON Schema Structure

The ANALYZE operation produces JSON output that maps directly to the database schema. Below is a diagram showing the JSON structure:

```mermaid
classDiagram
    class AnalyzeOutput {
        +object repository
        +string status
        +boolean isPluginContainingRepo
        +array pluginDependencies
        +array publishedArtifacts
    }

    class Repository {
        +string url
        +string organization
        +string name
    }

    class PluginDependency {
        +string organization
        +string name
        +string version
    }

    class PublishedArtifact {
        +string organization
        +string name
        +string version
        +boolean isPlugin
        +string subproject
        +boolean isPublished
        +string scalaVersion
        +array libraryDependencies
    }

    class LibraryDependency {
        +string organization
        +string name
        +string version
        +string scope
    }

    AnalyzeOutput --> Repository : contains
    AnalyzeOutput --> PluginDependency : contains array
    AnalyzeOutput --> PublishedArtifact : contains array
    PublishedArtifact --> LibraryDependency : contains array
```

### JSON Schema Mapping to Database

| JSON Path | Database Table | Database Column |
|-----------|---------------|-----------------|
| `repository.url` | `repositories` | `url` |
| `repository.organization` | `repositories` | `organization` |
| `repository.name` | `repositories` | `name` |
| `status` | `repositories` | `status` |
| `isPluginContainingRepo` | `repositories` | `is_plugin_containing_repo` |
| `pluginDependencies[].organization` | `artifacts` | `organization` |
| `pluginDependencies[].name` | `artifacts` | `name` |
| `pluginDependencies[].version` | `repository_plugin_dependencies` | `version` |
| `publishedArtifacts[].organization` | `artifacts` | `organization` |
| `publishedArtifacts[].name` | `artifacts` | `name` |
| `publishedArtifacts[].isPlugin` | `artifacts` | `is_plugin` |
| `publishedArtifacts[].subproject` | `artifacts` | `subproject` |
| `publishedArtifacts[].isPublished` | `artifacts` | `is_published` |
| `status` (from repository) | `artifacts` | `status` |
| `publishedArtifacts[].scalaVersion` | `artifacts` | `scala_version` |
| `publishedArtifacts[].libraryDependencies[].organization` | `artifacts` | `organization` |
| `publishedArtifacts[].libraryDependencies[].name` | `artifacts` | `name` |
| `publishedArtifacts[].libraryDependencies[].version` | `artifact_dependencies` | `version` |
| `publishedArtifacts[].libraryDependencies[].scope` | `artifact_dependencies` | `scope` |

**Note**: The `sbtVersion` field in the JSON is used during analysis but is not stored in the database. The `publishedArtifacts[].version` field is also not stored in the `artifacts` table - artifacts are uniquely identified by `(organization, name)` only.

### JSON Schema Notes

1. **Repository-level data**: The top-level `repository`, `status`, and `isPluginContainingRepo` fields map directly to the `repositories` table. The `sbtVersion` field in the JSON is used during analysis to determine status but is not stored in the database.

2. **Plugin dependencies**: The `pluginDependencies` array creates entries in:
   - `artifacts` table (for the plugin artifact itself)
   - `repository_plugin_dependencies` table (linking repository to plugin)

3. **Published artifacts**: Each item in `publishedArtifacts` creates an entry in the `artifacts` table with `repository_id` set to the analyzed repository. The artifact's `status` field is set to match the repository's status.

4. **Library dependencies**: Each `libraryDependencies` item within a `publishedArtifact` creates:
   - An entry in `artifacts` table (for the dependency artifact, if not already present)
   - An entry in `artifact_dependencies` table (linking the artifact to its dependency)
