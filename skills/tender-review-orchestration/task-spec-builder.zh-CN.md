# TaskSpec草稿builder

Lead自有 scripts/prepare_task_spec.py 提供draft、bind-authority，依赖同目录_task_spec_io.py及已有prepare_delegation_input.py，不要求安装Evidence、不import其checker。输入契约为schemas/task-role-definition.schema.json和schemas/task-authority-intent.schema.json。运行时仅做专用字段/类型/ID/scope检查，不是通用JSON Schema引擎。

draft三组明确授权path/完整expected SHA256分别为原始UTF8请求、独立authority意图、模型审阅角色定义。intent保留原authority字段但省略spec_sha256，用intent_version=lead-task-authority-intent/v1，唯一source文本须精确等于原请求，不能从Spec反推。definition单次填写purpose/role_task、scope/resources、原文quote、验收/失败/交付；程序一致复制重复字段。revision严格整数，未知键/重复ID/悬空引用/引用与hash不符拒绝。资源expected_sha256来自独立事实，不能把新读出的摘要反当预期授权。

所有scope均已授权。输出前最终Spec路径须同时被独立read_grants和definition readonly覆盖。冻结输入、Lead结果、callee结果用独立已存在目录，不得祖先交叠。当前构建写授权不变成业务write scope；builder不创建目录/不授权限。runtime仅作为数据，明确结构缺项拒绝；模型漏声明依赖及语义遗漏仍需审阅，不生成默认解释器/版本/provider或verified标志。

draft排他输出NAME.spec.json、NAME.assignment.json、NAME.source-map.json、NAME.draft-manifest.json；成功仅draft_only，semantic_completeness=not_established。实际对照原文约束审阅后，bind-authority另接独立intent与Spec真实path/hash，复核完整字段/ID/原文/hash/scope/资源字节，唯一从Spec取得的authority字段是spec_sha256，原grant/runtime保持。输出NAME.authority.json，状态authority_bound_only，不是PASS。

随后沿用prepare_delegation_input.py的metadata-preflight：另有Evidence本人checker assignment和真实Evidence目标。Evidence自己在已核环境运行真实checker并交实际stdout/exit/调用回执。此前检和语义审阅完成后才可业务prepare/Delegate。builder不执行工具/checker/解释器、不安装/委派、不认证授权；禁止补未知authority/runtime/result或把粗引用当完整语义提取。

文本/JSON输入与每输出256KiB；binary资源原bytes每个4MiB，含复验累计32MiB/256次读取，沿用20秒reader预算。资源允许NUL，文本不允许。拒绝软硬链接/穿越/覆盖输出。复验输入快照及排他持有输出fd；失败保留部分文件，只有最终成功返回可用，不是多文件原子事务或永久防同用户修改。错误仅固定code，退出2，不含输入路径、材料正文或异常值。

## 完整合成输入与调用示例

下方自包含示例与英文版相同。先填本次真实LEAD_SKILL、已授权现存EXAMPLE_ROOT与来自独立事实的CHECKER_PYTHON/PREFIX/LOCK/LOCK_SHA256；未解析就停，不猜值/借环境。样例只建新合成文件，真实hash现场计算，不运行checker，不证明runtime来源。原文唯一匹配；重复时明确line_start/line_end并仍需唯一，byte范围由程序算。生成后先审阅草稿再bind，后续仍走真实Evidence。示例target仅合成身份不可直接当真实委派目标。

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
