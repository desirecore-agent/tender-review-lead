# Tender Review Lead — Orchestration Agent

**Status:** Pre-release draft — not production-ready, not published.

## Overview

The **tender-review-lead** agent orchestrates bid document review for the `tender-review` team on the DesireCore platform. It receives tender documents, coordinates parallel specialist reviews (commercial pricing, technical visual, evidence verification), merges findings into a single report, and delivers a structured audit package with transparent uncertainty.

### What it does

- **File inventory & hashing** — builds a verifiable manifest of all input files with SHA-256 hashes.
- **Contract-driven validation** — validates all six v1.2 contract products against authoritative JSON Schemas before any business logic runs.
- **Parallel delegation** — assigns evidence, commercial, and visual review tasks to specialist agents with full context.
- **Single-writer report merge** — the lead agent writes the final consolidated report; no other agent writes findings into it.
- **Independent re-verification** — after specialist review, an independent evidence reviewer re-reads critical bilateral evidence and checks negative cases.

### What it does NOT do

- Does **not** modify original tender documents (read-only).
- Does **not** authenticate signatures, seals, or document provenance.
- Does **not** make binding qualification or disqualification decisions — only the authorized human reviewer or procurement authority does.
- Does **not** guarantee compliance, winning, or legal standing.

## Team Structure

```
tender-review (team)
├── tender-review-lead        ← this agent (orchestrator, report writer)
├── tender-review-commercial  ← pricing & commercial analysis
├── tender-review-visual      ← technical parameter & image verification
├── tender-review-evidence    ← evidence validation & independent re-check
└── tender-review-requirements← clause qualification & requirement mapping
```

## Prerequisites

- DesireCore client matched to the actually released team minimum and verified capabilities; do not infer an unreleased revision's final minimum from historical tests.
- Evidence's own Python ≥ 3.9 isolated environment initialized from its reviewed lock. TaskSpec checker compatibility also depends on the mode requirements below; Python version alone does not establish support.
- An independently reviewed `tender-evidence-review` release installed, with matching release ref/commit, formal code, public docs, dependency lock, notices, and initialized runtime. Missing or mismatched evidence blocks validation.
- The team repository with `shared/contracts/schemas/` containing the six v1.2 contract schemas.

## Usage

```sh
# Validate a complete six-product pack
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

## Contract v1.2

Six mandatory JSON products per review cycle:

| Product | File | Purpose |
|---------|------|---------|
| Project Profile | `project-profile.json` | Procurement context, classification, applicable regulations |
| File Manifest | `file-manifest.json` | Input file inventory with SHA-256, roles, page counts |
| Requirements Matrix | `requirements.json` | Clause-by-clause extraction with source attribution |
| Coverage Ledger | `coverage.json` | Per-file, per-item review coverage with closure status |
| Findings | `findings.json` | Issues with severity, certainty, bilateral evidence, and observation method |
| Review Report | `review-report.json` | Final report with conclusion, unresolved items, tool failures |

All schemas live at `<TEAM_ROOT>/shared/contracts/schemas/` and use JSON Schema Draft-07.

## Limitations

- The validator performs **structural and schema validation** of the data pack. Machine validation does not equal business consistency or independent re-reading.
- Cloud model providers may process text and images submitted for analysis. This does not authorize external redistribution of confidential materials.
- No guarantee of compliance, qualification, or bid success.
- Historical development paths, test results, and agent-specific working directories are excluded from published documentation.

## License

Original content: MIT (DesireCore Contributors).
Platform and third-party dependencies retain their respective licenses.

## TaskSpec checker mode compatibility

Evidence itself runs the [read-only TaskSpec checker](skills/tender-review-orchestration/templates/delegation-task.md); Lead does not borrow its venv. `file-posix` requires POSIX safe directory-fd/no-follow/nonblocking IO and signal support, and existing scope paths. Actual device/inode ancestry checks overlap and case aliases; unknown future scopes fail and must first be prepared by an authorized workflow.

Windows/POSIX can use the `inline` length-framed protocol with original spec/source/resource/lock bytes and authorized capture-receipt references. It never opens Spec/authority locators. It checks logical grants, bytes and references, not actual physical directory separation or file stability at capture. Results explicitly remain not_checked_inline and caller_supplied_not_authenticated. File work needing physical proof still requires independent platform/host and actual capture evidence; inline pass cannot bypass a file-mode failure.

Internal deadline and external platform timeout are distinct: file mode uses signal, inline uses its own thread watchdog. This revision has current-host actual file/alias/budget and Windows namespace/portable neutral tests, not native Windows machine acceptance. No all-platform production readiness is claimed. See the linked guide for the binary frame, complete limits and cmd.exe invocation.
