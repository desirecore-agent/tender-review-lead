# TaskSpec draft builder

The Lead-owned scripts/prepare_task_spec.py provides draft and bind-authority. It requires adjacent _task_spec_io.py and the existing prepare_delegation_input.py; it does not require an installed Evidence Agent or import its checker. Input contracts are schemas/task-role-definition.schema.json and schemas/task-authority-intent.schema.json. Runtime validation is dedicated field/type/ID/scope checking, not a general JSON Schema engine.

Supply three explicit authorized path/full expected SHA256 pairs to draft: exact original UTF8 request, independently authored authority intent, and a model-reviewed role definition. The intent keeps existing authority fields except spec_sha256 and uses intent_version=lead-task-authority-intent/v1. It has exactly one source with text equal to the request. Authority never comes from the generated Spec. The definition provides purpose/role_task, scopes, resources, exact quote selectors, acceptance, failure and delivery once; shared fields are copied consistently into the existing Spec and assignment. Revision is a true integer. Unknown keys, duplicate IDs, unresolved references, quotes or digests fail closed. Resource expected_sha256 must come from independent known facts; the builder reads and compares it, never substitutes a newly observed digest as permission.

Scopes must already be authorized. The future Spec path must be in independent read_grants and definition readonly scope before output. Keep frozen inputs, Lead outputs and callee outputs in distinct existing directories, without ancestor overlap. The current explicit construction write authorization is not a business write scope. The builder creates no directories or grants. Runtime fields are data only: missing declared structure fails; undeclared dependencies and semantic omissions still require review. No default interpreter/version/provider or verified flag is generated.

Draft outputs four exclusive files: NAME.spec.json, NAME.assignment.json, NAME.source-map.json and NAME.draft-manifest.json. Successful status is draft_only, semantic_completeness=not_established. After actual original-to-constraint review, bind-authority separately takes independent intent and the exact Spec path/hash; it rechecks full fields, IDs, source text/hash, scopes and resource bytes. Its only Spec-derived authority field is spec_sha256. It outputs NAME.authority.json with status authority_bound_only, never PASS. All original grants/runtime facts remain unchanged.

Next, use existing prepare_delegation_input.py metadata-preflight with a separate Evidence checker assignment and real Evidence target. Evidence itself performs the actual checker in its verified runtime and delivers actual stdout/exit/invocation evidence. Only after that and semantic review may existing business preparation and Delegate proceed. This builder never executes tools/checkers/interpreters, installs, delegates or authenticates authorization. Do not replace missing authority/runtime/result facts, or treat a coarse quote as complete extraction.

Text/JSON inputs and each output are capped at 256KiB; binary resources are read as original bytes up to 4MiB each, total reads including rechecks 32MiB/256 operations, with the existing 20-second reader budget. Binary NUL is accepted for resources, never text. No symlinks, hardlinks, path traversal or output overwrite. Explicit source snapshots and exclusive held output descriptors are rechecked. Partial files remain on failure; only a final successful return is usable. This is not an atomic multi-file transaction or protection from later same-user edits. Failure emits fixed code labels only, exit 2; no input paths, material text or exception values in errors.

## Complete synthetic input and invocation example

Before running this example, set LEAD_SKILL and EXAMPLE_ROOT to your observed installed Skill and an existing, explicitly authorized private example directory. Set CHECKER_PYTHON, CHECKER_PREFIX, CHECKER_LOCK and CHECKER_LOCK_SHA256 from actual independent checker-runtime facts. Missing facts mean stop; do not guess or borrow an environment. These variables are not Agent defaults. The following creates only new synthetic files/subdirectories; it does not run a checker or authenticate those facts.

```sh
python3 -B - <<'PY'
import hashlib, json, os, pathlib, shlex
root = pathlib.Path(os.environ['EXAMPLE_ROOT'])
assert root.is_absolute() and root.is_dir()
assert not any(p.is_symlink() for p in [root, *root.parents])
for name in ('inputs', 'frozen', 'lead-results', 'callee-results'):
    (root/name).mkdir()  # Exclusive: pre-existing output stops the example.
request = '仅阅读合成输入。\n不得外发。\n'
intent = {
  'intent_version':'lead-task-authority-intent/v1', 'task_id':'synthetic-draft', 'revision':1,
  'target_agent_id':'synthetic-role', 'parent_plan':{'path':str(root/'inputs/PLAN.md'),'revision':1},
  'instruction_sources':[{'source_id':'request','text':request}],
  'read_grants':[{'path':str(root/n),'kind':'directory'} for n in ('inputs','frozen')],
  'callee_write_grants':[{'path':str(root/'callee-results'),'kind':'directory'}],
  'lead_write_grants':[{'path':str(root/'lead-results'),'kind':'directory'}],
  'runtime':{'python_executable':os.environ['CHECKER_PYTHON'],
    'environment_prefix':os.environ['CHECKER_PREFIX'], 'lock_path':os.environ['CHECKER_LOCK'],
    'lock_sha256':os.environ['CHECKER_LOCK_SHA256']}}
definition = {
  'role':'requirements', 'purpose':'Synthetic mapping example', 'role_task':'Inspect synthetic constraints',
  'io_scope':{'read_only_paths':[str(root/n) for n in ('inputs','frozen')],
    'callee_write_paths':[str(root/'callee-results')], 'lead_write_paths':[str(root/'lead-results')]},
  'resources':[],
  'hard_constraints':[
    {'constraint_id':'C1','category':'input_output_scope','source_id':'request',
     'quote':{'text':'仅阅读合成输入。'},'applies_to':'callee','verification':'Observe actual reads'},
    {'constraint_id':'C2','category':'other','source_id':'request',
     'quote':{'text':'不得外发。'},'applies_to':'both','verification':'Observe actual delivery audience'}],
  'acceptance_criteria':[{'criterion_id':'A1','constraint_ids':['C1','C2'],'text':'Match both actual constraints'}],
  'failure_policy':'report_and_stop_affected_work_without_substitution',
  'delivery_requirements':['Raw evidence and limitations']}
values = {'request.txt':request.encode(), 'intent.json':json.dumps(intent,ensure_ascii=False).encode(),
          'definition.json':json.dumps(definition,ensure_ascii=False).encode(),
          'PLAN.md':b'# Synthetic example only\n'}
for name,raw in values.items():
    with (root/'inputs'/name).open('xb') as f: f.write(raw)
args = ['python3','-B',os.environ['LEAD_SKILL']+'/scripts/prepare_task_spec.py','draft']
for flag,name in [('request','request.txt'),('authority-intent','intent.json'),('definition','definition.json')]:
    args += ['--'+flag,str(root/'inputs'/name),hashlib.sha256(values[name]).hexdigest()]
args += ['--output-directory',str(root/'frozen'),'--output-name','example-r1']
print(shlex.join(args))  # Inspect, then run this exact generated draft command.
PY
```

After real draft success, review the request, generated Spec and source-map. The source-map's byte ranges are computed, never typed by the model. A repeated quote without a disambiguating inclusive line range is refused; e.g. quote={text: ..., line_start: 2, line_end: 2}. No whole-paragraph quote establishes completeness. After review, obtain the actual full SHA256 of frozen/example-r1.spec.json and the unchanged inputs/intent.json, then run:

```sh
python3 -B "$LEAD_SKILL/scripts/prepare_task_spec.py" bind-authority \
  --authority-intent "$EXAMPLE_ROOT/inputs/intent.json" "$INTENT_SHA256" \
  --spec "$EXAMPLE_ROOT/frozen/example-r1.spec.json" "$SPEC_SHA256" \
  --output-directory "$EXAMPLE_ROOT/frozen" --output-name example-r1-bound
```

The explicit bind hashes come from original file bytes, not the rendered Read text or a placeholder. This example's empty resource list does not imply real business tasks need no runtime/skills. The synthetic target is only an example identity, never a real Delegate target. To test metadata, use an actual independently authorized Spec/target and a separate Evidence metadata assignment; retain the normal real runtime and checker boundaries.
