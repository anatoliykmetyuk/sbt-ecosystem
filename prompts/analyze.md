# ANALYZE Operation - SBT Repository Analysis Prompt

## Purpose

Analyze a cloned SBT repository and extract all dependency information, producing a JSON output that can be inserted into the SQLite database for tracking the SBT ecosystem migration.

## Input

You will be provided with:
- A path to a cloned repository directory or a URL to a GitHub repository or a URL to scaladex or an artifact identifyer
- The JSON schema file (`database/analyze-schema.json`) that defines the exact output format

## Analysis Process

### Step 1: Repository Metadata

1. Ensure the repository is cloned to `repos/` directory. If the repository is providead as a URL, clone it to `repos/` directory. If the repository is provided as an artifact identifyer, fetch the repository name using `scripts/fetch_plugin_repos.py`.

2. **Repository URL**: Extract from:
   - `build.sbt`: Look for `homepage := Some(url(...))` or `scmInfo`
   - If not found, infer from git remote or directory name
   - Format: `https://github.com/org/repo`

3. **Organization**: Extract from `build.sbt`:
   - Look for `ThisBuild / organization := "..."` or `organization := "..."`
   - Example: `com.github.sbt`, `org.scalameta`

4. **Repository Name**: Extract from:
   - Directory name (if it matches GitHub repo name)
   - Or infer from organization and URL

### Step 2: SBT Version and Status

1. **SBT Version**: Read from `project/build.properties`:
   - Look for `sbt.version=X.X.X`
   - This is the base SBT version

2. **SBT2 Support Check**: Check for SBT2 support:
   - **For plugins**: A plugin is considered ported to SBT 2 if ANY of the following is true:
     - `crossSbtVersions` includes SBT 2.x versions (e.g., `crossSbtVersions := Seq("1.9.0", "2.0.0-RC8")`)
     - `pluginCrossBuild / sbtVersion` maps ANY Scala version to an SBT 2.x version (e.g., `"2.0.0-M2"`, `"2.0.0-RC8"`, `"2.0.0"`, etc.). This is STRONG evidence of SBT 2 support, especially when combined with cross-building for Scala 3.
     - The base `sbtVersion >= 2.0.0` in `project/build.properties`
   - **For libraries**: Check if the base `sbtVersion >= 2.0.0` OR if `pluginCrossBuild / sbtVersion` settings map to SBT 2.x for any Scala version
   - **Key Point**: When `pluginCrossBuild / sbtVersion` maps a Scala version to an SBT 2.x version (like `"2.0.0-M2"` or `"2.0.0-RC8"`), this IS evidence of SBT 2 support. The plugin will cross-build for SBT 2 when using that Scala version.
   - Example of ported plugin: `crossSbtVersions := Seq("1.9.0", "2.0.0-RC8")` means the plugin cross-builds for both SBT 1.9 and SBT 2.0
   - Example of ported plugin: `(pluginCrossBuild / sbtVersion) := { case "3" => "2.0.0-M2"; case "2.12" => "1.5.8" }` means the plugin cross-builds for SBT 2.0 when using Scala 3
   - Example of NOT ported: `crossSbtVersions := "1.2.8" :: Nil` AND `pluginCrossBuild / sbtVersion` only maps to SBT 1.x versions

3. **Status Determination**:
   - `upstream`: If ANY of the following is true:
     - `sbtVersion >= 2.0.0` in `project/build.properties`
     - (For plugins) `crossSbtVersions` includes SBT 2.x versions
     - (For plugins) `pluginCrossBuild / sbtVersion` maps ANY Scala version to an SBT 2.x version (e.g., `"2.0.0-M2"`, `"2.0.0-RC8"`, `"2.0.0"`)
     - (For libraries) `pluginCrossBuild` shows SBT2 support with actual cross-building
   - `blocked`: If migration is blocked by dependencies (check for blocking issues/comments)
   - `experimental`: If in experimental/testing phase
   - `not_ported`: Otherwise (default) - only use this if there is NO evidence of SBT 2.x support

### Step 3: Plugin Dependencies

Read from `project/plugins.sbt` and any `project/*.sbt` files:

1. Look for `addSbtPlugin("org" % "name" % "version")` calls
2. For each plugin, extract:
   - `organization`: First parameter
   - `name`: Second parameter
   - `version`: Third parameter

Example:
```scala
addSbtPlugin("org.scalameta" % "sbt-scalafmt" % "2.5.6")
```
Produces:
```json
{
  "organization": "org.scalameta",
  "name": "sbt-scalafmt",
  "version": "2.5.6"
}
```

### Step 4: Published Artifacts

Analyze `build.sbt` to find all subprojects that publish artifacts:

1. **Find Subprojects**: Look for `lazy val name = project` definitions
2. **For Each Subproject**:
   - **Organization**: From `organization := "..."` or inherited from `ThisBuild / organization`
   - **Name**: From `name := "..."` or `moduleName := "..."`
   - **Version**: From `version := "..."` or inherited from `ThisBuild / version`
   - **Is Plugin**: Check if:
     - `.enablePlugins(SbtPlugin)` is present
     - Or extends `Plugin` trait
     - Or has plugin descriptor
   - **Subproject**: The `lazy val` name (e.g., `plugin`, `library`, `core`)
   - **Is Published**: Check if `publish / skip := true` is NOT set (default is published)
   - **Scala Version**: From `scalaVersion := "..."` or `ThisBuild / scalaVersion`

3. **Library Dependencies**: For each artifact, extract from `libraryDependencies ++= Seq(...)`:
   - Parse each dependency: `"org" %% "name" % "version" % "scope"`
   - Default scope is `Compile` if not specified
   - Scopes: `Test`, `Provided`, `Runtime`, or `Compile`
   - Handle `%%` (Scala version appended) vs `%` (no Scala version)

Example:
```scala
lazy val plugin = project
  .enablePlugins(SbtPlugin)
  .settings(
    name := "sbt-example",
    libraryDependencies ++= Seq(
      "org.scalameta" %% "munit" % "1.1.0" % Test,
      "com.example" % "library" % "1.0.0"
    )
  )
```

Produces:
```json
{
  "organization": "com.example",
  "name": "sbt-example",
  "version": "1.0.0",
  "isPlugin": true,
  "subproject": "plugin",
  "isPublished": true,
  "scalaVersion": "2.12.15",
  "libraryDependencies": [
    {
      "organization": "org.scalameta",
      "name": "munit",
      "version": "1.1.0",
      "scope": "Test"
    },
    {
      "organization": "com.example",
      "name": "library",
      "version": "1.0.0",
      "scope": "Compile"
    }
  ]
}
```

### Step 5: Is Plugin Containing Repo

Set `isPluginContainingRepo` to `true` if ANY published artifact has `isPlugin: true`.

## Output Format

Produce a JSON file that strictly adheres to the schema in `database/analyze-schema.json`.

### Required Fields:
- `repository`: Object with `url`, `organization`, `name`
- `sbtVersion`: String (from build.properties)
- `status`: One of `"not_ported"`, `"blocked"`, `"experimental"`, `"upstream"`
- `isPluginContainingRepo`: Boolean
- `pluginDependencies`: Array (can be empty)
- `publishedArtifacts`: Array (can be empty)

### Important Notes:

1. **Version Handling**:
   - If version is dynamic (e.g., from git tags), use the current checked-out version
   - For SBT plugins with `%%`, the actual artifact name includes Scala version (e.g., `sbt-scalafmt_2.12_1.0`), but store just the base name

2. **Cross-Building**:
   - If a project cross-builds for multiple Scala versions, you may see multiple artifacts
   - Each unique `organization:name:version:scalaVersion` combination is a separate artifact

3. **Dependency Scopes**:
   - `% Test` → scope: `"Test"`
   - `% Provided` → scope: `"Provided"`
   - `% Runtime` → scope: `"Runtime"`
   - No scope specified → scope: `"Compile"`

4. **Plugin Detection**:
   - Look for `.enablePlugins(SbtPlugin)` - this is the most reliable indicator
   - Plugins are published with `_2.12_1.0` suffix, but store base name only

5. **Null Values**:
   - `subproject` can be null if it's the root project
   - `scalaVersion` can be null for non-Scala artifacts
   - `libraryDependencies` array can be empty

## Example Output

```json
{
  "repository": {
    "url": "https://github.com/example/repo",
    "organization": "com.example",
    "name": "repo"
  },
  "sbtVersion": "1.11.4",
  "status": "upstream",
  "isPluginContainingRepo": true,
  "pluginDependencies": [
    {
      "organization": "org.scalameta",
      "name": "sbt-scalafmt",
      "version": "2.5.6"
    }
  ],
  "publishedArtifacts": [
    {
      "organization": "com.example",
      "name": "example-plugin",
      "version": "1.0.0",
      "isPlugin": true,
      "subproject": "plugin",
      "isPublished": true,
      "scalaVersion": "2.12.15",
      "libraryDependencies": [
        {
          "organization": "org.scala-lang",
          "name": "scala-library",
          "version": "2.12.15",
          "scope": "Provided"
        }
      ]
    }
  ]
}
```

## Validation

Before outputting, verify:
1. All required fields are present
2. All enum values are valid (`status`, `scope`)
3. All arrays are present (even if empty)
4. JSON is valid and parseable
5. Repository URL is a valid URI
6. Organization and name match SBT conventions

## Common Pitfalls

1. **Missing SBT2 Support**: Don't just check `build.properties` - for plugins, check BOTH `crossSbtVersions` AND `pluginCrossBuild / sbtVersion`. If `pluginCrossBuild / sbtVersion` maps ANY Scala version to an SBT 2.x version (like `"2.0.0-M2"`), that IS evidence of SBT 2 support and the status should be `upstream`. The plugin will cross-build for SBT 2 when using that Scala version.
2. **Plugin vs Library**: Only artifacts with `.enablePlugins(SbtPlugin)` are plugins
3. **Dependency Scopes**: Default is `Compile`, not missing
4. **Version Extraction**: Handle dynamic versions, SNAPSHOT versions, and version variables
5. **Cross-Build Artifacts**: Each Scala version combination may produce separate artifacts

## Instructions

1. Read all relevant build files (`build.sbt`, `project/*.sbt`, `project/build.properties`)
2. Extract all information systematically
3. Produce JSON output matching the schema exactly
4. Save the output to a file (e.g., `analysis.json`)
5. Verify the JSON is valid before completing
