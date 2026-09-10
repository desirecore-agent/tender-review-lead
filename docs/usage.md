# Usage Guide

## Overview

This guide covers how to run a tender review using the `tender-review` team on DesireCore.

## Prerequisites

1. DesireCore platform ≥ 10.0.136 installed and running.
2. Python ≥ 3.9 available in an isolated virtual environment.
3. The `tender-evidence-review` skill installed (provides the validator).
4. The `tender-review` team repository with `shared/contracts/schemas/`.

> **Installation check**: Before running these commands, verify the installed Evidence release ref, validator code, public Skill/docs, reviewed dependency lock, and initialized isolated runtime with its verification receipt, as specified in `dependencies.md`. Verify all six team schemas against their release identities and hashes. Missing or mismatched prerequisites block validation; results from another installation do not satisfy this check.

## Workflow

### Step 1: Prepare Input Files

Place all tender documents (PDF, DOCX, images) in a directory. The lead agent will build a file manifest with SHA-256 hashes.

### Step 2: Trigger Review

Initiate the review through the lead agent. It will:

1. Build the file manifest (`file-manifest.json`) with immutable `manifest_id`.
2. Extract the requirements matrix (`requirements.json`) from tender-side documents.
3. Assign parallel reviews to commercial, visual, and requirements specialists.
4. Collect specialist outputs and trigger independent evidence re-verification.
5. Merge into a final consolidated report (`review-report.json`).

### Step 3: Validate the Data Pack

After review, validate the six-product data pack:

```sh
# Validate a complete pack
"$VALIDATOR_PYTHON" "$EVIDENCE_SKILL_DIR/scripts/validate_report.py" \
  --pack "$PACK_DIR" \
  --schemas "$TEAM_ROOT/shared/contracts/schemas" \
  --json

# Validate a review pack (independent re-check output)
"$VALIDATOR_PYTHON" "$EVIDENCE_SKILL_DIR/scripts/validate_report.py" \
  --pack "$REVIEW_PACK_DIR" \
  --schemas "$TEAM_ROOT/shared/contracts/schemas" \
  --review-pack --json
```

> `$VALIDATOR_PYTHON`, `$EVIDENCE_SKILL_DIR`, and `$TEAM_ROOT` are resolved at runtime by the installed skill and team configuration. Do not hard-code personal paths.

### Step 4: Interpret Results

- **exit 0, result=pass**: All six products structurally valid, all business rules satisfied.
- **exit 1**: Normal structural/business violations use `result=fail`; schema-load failures under `--json` may instead return a structured `{error}` object on stdout without `result`.
- **exit 2**: Invocation/import/argparse error. Stderr may be a JSON error or argparse usage text. Automation must treat every nonzero exit as failure before parsing the available envelope.

> Machine validation pass ≠ report conclusion pass. An `exit 0 / result=pass` means the data pack passes structural and business-rule checks. It does not mean all documents have been independently re-read or that the bid is complete.

## Important Notes

- **Partial is valid**: A pack with `conclusion=partial_only` and `exit 0 / result=pass` is structurally valid. The report honestly declares incomplete coverage — this is a feature, not a bug.
- **Schema validation is structural**: The validator checks JSON Schema conformance and business rules. It does not verify the truthfulness of document content.
- **No bid-winning guarantee**: This is an assistance-level pre-submission review tool.
- **Material rights**: Users must have the legal right to process the documents they submit. Configuration of a model provider does not authorize external redistribution.
- **Incompleteness and errors are not success**: Unchecked items, unresolved tool failures, and parsing errors are honest limitations — they are never treated as passing checks.
