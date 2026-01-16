# CHECK_ARTIFACT_STATUS Operation - Batch Artifact Status Check

## Purpose

Check the SBT 2.x porting status of multiple artifacts by querying Maven Central, then update the database with the discovered statuses upon user confirmation.

## Input

You will be provided with:
- A list of artifact identifiers in the format `organization:name:version`
- Example: `com.github.sbt:sbt-dynver:5.0.1`

The list may be provided as:
- A text file with one artifact per line
- A list in the user's message
- Any other format the user specifies

## Prerequisites

**IMPORTANT**: Before running any scripts, you must activate the Python virtual environment:

```bash
# Activate the virtual environment
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate     # On Windows
```

All script executions must be done within the activated virtual environment.

## Process

### Step 1: Parse Artifact List

1. Extract all artifact identifiers from the input
2. Validate format: each must be `organization:name:version` (exactly 2 colons)
3. Report any invalid formats to the user

### Step 2: Check Each Artifact

For each artifact in the list:

1. **Run the check script**: Execute `scripts/check_pom_status.py` with the artifact identifier
   ```bash
   # Ensure virtual environment is activated first
   python3 scripts/check_pom_status.py <organization:name:version>
   ```

2. **Interpret the results**:
   - **HTTP 200**: The artifact is ported to SBT 2.x → status should be `upstream`
   - **HTTP 404**: The artifact is NOT ported to SBT 2.x → status should be `not_ported`
   - **ERROR**: Network or other error → report to user, do not set status

3. **Collect results**: Build a summary table showing:
   - Artifact identifier
   - HTTP status code
   - Determined status (`upstream` or `not_ported`)
   - Any errors encountered

### Step 3: Report Findings

Present the results to the user in a clear format:

```
Artifact Status Check Results
=============================

Ported to SBT 2.x (200):
  ✓ com.github.sbt:sbt-dynver:5.0.1 → upstream
  ✓ com.github.sbt:sbt-pgp:2.2.1 → upstream

Not ported to SBT 2.x (404):
  ✗ com.typesafe:sbt-mima-plugin:1.1.3 → not_ported
  ✗ org.portable-scala:sbt-scala-native-crossproject:1.3.2 → not_ported
  ✗ org.scala-native:sbt-scala-native:0.5.4 → not_ported

Errors:
  ⚠ org.example:plugin:1.0.0 → Network timeout

Total: 6 checked, 2 ported, 3 not ported, 1 error
```

### Step 4: Request Confirmation

Ask the user to confirm before updating the database:

```
Would you like to update the database with these statuses? (yes/no)
```

### Step 5: Update Database (Upon Confirmation)

If the user confirms:

1. For each artifact with a determined status (not errors):
   - Run `scripts/set_repo_status.py` with the artifact identifier and status:
     ```bash
     # Ensure virtual environment is activated first
     python3 scripts/set_repo_status.py <organization:name:version> <status>
     ```
   - Where `<status>` is either `upstream` or `not_ported`

2. Report success/failure for each update

3. Provide a final summary:
   ```
   Database Update Summary
   =======================
   ✓ Updated 5 artifacts successfully
   ✗ Failed to update 0 artifacts
   ⚠ Skipped 1 artifacts (errors)
   ```

## Important Notes

1. **Status Values**: Only use `upstream` (for HTTP 200) or `not_ported` (for HTTP 404). Do not use `blocked` or `experimental` based on Maven Central checks.

2. **Error Handling**:
   - If a check fails due to network issues, report it but do not update that artifact
   - If an artifact is not found in the database, report it but continue with others

3. **Batch Processing**:
   - Process artifacts sequentially to avoid overwhelming Maven Central
   - Add a small delay between requests if processing many artifacts (e.g., 0.5 seconds)

4. **Database Updates**:
   - Only update artifacts that exist in the database
   - If an artifact doesn't exist, inform the user but continue with others

5. **Confirmation Required**:
   - Always wait for explicit user confirmation before updating the database
   - If user says "no", do not make any database changes

## Example Workflow

```
User provides:
  com.github.sbt:sbt-dynver:5.0.1
  com.github.sbt:sbt-pgp:2.2.1
  com.typesafe:sbt-mima-plugin:1.1.3

AI activates virtual environment:
  source venv/bin/activate

AI executes:
  python3 scripts/check_pom_status.py com.github.sbt:sbt-dynver:5.0.1
  python3 scripts/check_pom_status.py com.github.sbt:sbt-pgp:2.2.1
  python3 scripts/check_pom_status.py com.typesafe:sbt-mima-plugin:1.1.3

AI reports:
  Ported (200): 2 artifacts
  Not ported (404): 1 artifact

User confirms: yes

AI executes (virtual environment still activated):
  python3 scripts/set_repo_status.py com.github.sbt:sbt-dynver:5.0.1 upstream
  python3 scripts/set_repo_status.py com.github.sbt:sbt-pgp:2.2.1 upstream
  python3 scripts/set_repo_status.py com.typesafe:sbt-mima-plugin:1.1.3 not_ported

AI reports: All 3 artifacts updated successfully
```

## Scripts Used

- `scripts/check_pom_status.py`: Checks Maven Central for SBT 2.x availability
- `scripts/set_repo_status.py`: Updates artifact status in the database
