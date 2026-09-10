# Dependencies

## Ownership

This Lead Agent and the Team package do **not** bundle, manage, or lock the business-report validator or its Python dependencies. The Lead Skill includes a separate read-only TaskSpec checker; the Evidence member runs it in its own already verified, locked environment, as described below. Validation is an external conditional capability supplied only by an independently reviewed `tender-evidence-review` release.

## Installation gate

Before enabling validation, the installer/operator must verify that one Evidence release has matching:

- immutable release ref/commit and formal validator code;
- public Skill/docs and NOTICE;
- independently reviewed `requirements.lock` with exact versions, hashes, and license closure;
- an isolated Python >= 3.9 runtime initialized from that lock and its verification receipt.

If the lock, docs, runtime receipt, code identity, or release evidence is absent, pending, or mismatched, validation is **blocked**. Do not infer a dependency version from this Lead package, install an unreviewed latest version, or fall back to a degraded validator.

## Platform

- DesireCore client must match the actual released team compatibility profile and capability evidence; the final minimum for an unreleased revision remains unpinned.
- Platform license: the LICENSE of the specific installed DesireCore version.
- Validator execution is local after the reviewed runtime is installed; dependency acquisition follows the Evidence release's reviewed installation policy.

## Verify this installation

Evaluate these prerequisites against the files and runtime in the current installation. A verification receipt from another installation or release does not establish that this installation can run validation.

## TaskSpec preflight

The Lead Skill ships `scripts/check_task_spec.py` and its four adjacent Draft-07 data/output schemas. It uses only the Python standard library plus the `jsonschema`/`referencing` closure already specified by the independently reviewed Evidence dependency lock. No second lock, installer, dependency download or subprocess is included. Evidence itself runs the checker with its verified private interpreter; the lead must not borrow that environment. Check the actual lock hash, installed distribution versions and environment receipt before use. This checker confirms prefix/interpreter identity and package versions against the supplied lock, not the original wheel-installation provenance.

The caller provides independent authority JSON on stdin; it binds task/revision/spec hash, original non-secret instruction text, original path grants and the Evidence runtime/lock. Do not derive authority from TaskSpec claims. The checker-owned lock is separate from the business callee's read grants. Inline original instructions avoid unnecessary source-file access; file sources/resources can be read only within the separately authorized scope. No network refs, writes or installs occur. Existing platform approvals and file access still apply.

Use the [TaskSpec guide](../skills/tender-review-orchestration/templates/delegation-task.md) for CLI and return semantics. A finite Evidence preflight request uses that published checker protocol and the original authority; it does not recursively need another unvalidated business TaskSpec. On pass the lead may continue its constraint comparison and real business delegation. Pass does not prove semantic completeness or that a model will obey. Missing runtime, mismatched lock, unsafe file handles or unavailable permission returns explicit failure; never fall back to a new environment. File mode is POSIX-only and requires directory-fd/no-follow/nonblocking IO and SIGALRM, with existing scope paths. Windows uses the all-inline data protocol below rather than silently falling into file-mode refusal.

## Modes and compatibility boundary

- `--mode file-posix --spec ...`: the checker reads authorized files and verifies physical scopes using device/inode ancestry. It rejects double-leading slashes, actual same-identity/nested aliases including case aliases, and missing scope paths. Future output scopes must first be prepared by an already authorized workflow, never by this checker; unproved paths fail. Per-file/total budgets are enforced before reads and stability rechecks retain their original limits.
- `--mode inline`: a bounded Windows/POSIX data protocol receives original spec/source/resource/lock bytes and capture-receipt references in a length-framed stdin request. Digest-only placeholders fail. It never opens Spec/authority locators; only trusted installed package schemas and existing dependency metadata are read. Business paths undergo conservative logical grant/overlap checks only. Physical scope and file stability remain not_checked_inline, with caller_supplied_not_authenticated capture provenance. This mode cannot override a failed physical check.

Both modes use Evidence's existing locked isolated environment, without an installer. File mode has an internal signal deadline; inline mode uses its own thread watchdog across frame reading and validation. An external platform command timeout is an additional boundary, not the internal mechanism. Windows namespace/portable protocol neutral tests ran on the current host, not native Windows; no all-platform production acceptance is claimed. Before real file operations, independently establish any required platform/host physical-scope and authorized-capture evidence; otherwise that part remains blocked.
