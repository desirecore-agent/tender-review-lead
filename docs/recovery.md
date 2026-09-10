# Recovery Guide

## Overview

This guide covers failure recovery during a tender review — how to diagnose, resume, and handle unrecoverable errors.

> **Important**: Recovery does not guarantee resumption from the exact point of process interruption. It uses platform mechanisms to diagnose state and create new runs that continue work via `contextMode="continue"`.

## Failure Categories

### 1. Member Task Failure

When a delegated specialist agent fails (timeout, crash, incomplete output):

1. **Inspect the run** — use the platform's run inspection (`InspectRuns`) to identify the failure cause and any subsequent runs.
2. **Check for in-flight successors** — if a retry or follow-up run is already in progress, wait for it rather than starting a new one.
3. **Resume with context** — use the platform's resume mechanism with the original `run_id` and `contextMode="continue"`. This creates a **new run** that inherits the prior context; it does not restart the process from the exact interruption point.
4. **If relationship is unclear, stop** — do not guess which run to resume; document the uncertainty.

### 2. Missing or Corrupted Contract Schema

If contract schema files are missing, corrupted, or have wrong identity:

- The validator returns a structured error (exit 1 or 2).
- **Do not bypass** the contract check — this is a hard gate.
- **Restore from a release-bound source**: select an independently verified installed/team release and verify its release version/ref plus expected file hashes before reading `shared/contracts/schemas/`. Atomically replace corrupted files; never hand-edit Schema content. After replacement, re-check each of the six exact `$id`, `$schema`, `contract_version` identities and its expected SHA-256 before validation resumes.

### 3. Schema Validation Failure

If data products fail JSON Schema validation:

- Check `schema_errors` in the output for the specific field and message.
- Fix the data product, not the schema.
- Re-validate after fix; do not skip validation to proceed to business checks.

### 4. Business Rule Violation

If structural validation passes but business rules fail:

- Review the `violations` array for rule IDs and affected paths.
- Common issues: unclosed coverage, unresolved tool failures, missing bilateral evidence, version binding mismatch.
- Fix the specific product and re-validate.

### 5. Tool Failure (PDF Rendering, etc.)

If a platform tool fails during review:

- The failure is recorded honestly in the report's open items.
- **Never** silently skip the affected check.
- Re-run after the tool is restored; do not claim the check passed without evidence.

## Version Invalidation

When materials change after a review cycle:

- A new `manifest_id` is generated.
- All coverage and findings bound to the old `manifest_id` are invalidated.
- Only the affected portions (identified by SHA-256 dependency) are re-checked.
- Stale conclusions must not be reused until re-check is complete.

## What NOT to Do

- Do not modify original tender documents to fix validation errors.
- Do not delete violation records to achieve a clean exit code.
- Do not re-run with different parameters hoping for a different result without fixing the underlying data.
- Do not resume a run without first verifying its relationship to the current state via `InspectRuns`.
- Do not hand-edit schema files — always restore from the verified published source.

## Platform Recovery Mechanism

The DesireCore platform provides:

- **Run inspection** (`InspectRuns`) — view the full history and status of any agent run; identify the source of failure and any unique successor.
- **Resume** (`contextMode="continue"`) — create a new run that inherits the prior run's context and continues work; this is not a process-level restart from the interruption point.
- **Interrupt** — stop a running task when the approach is clearly wrong.

These operate on the agent execution layer, not on the data. Recovery always starts with diagnosing the data state.
