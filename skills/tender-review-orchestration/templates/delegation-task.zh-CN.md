# TaskSpec 填写与传递

这是填写规程，不是可直接执行的任务或平台工具 Schema。私有运行 JSON 使用 [delegation-task.schema.json](../schemas/delegation-task.schema.json)，不增加第六/第七类业务产物、不改变团队权限；含用户路径、指令或结果的任务规格不得作为 Agent 资产发布。

## 准备版本

1. 阅读权威请求、当前 Plan revision 及适用规则。只把授权指令摘录保存在允许的私有任务位置，赋予稳定来源 ID 和完整 SHA-256；摘录须忠实、足够完整地保留条件/例外。不抄凭据，使用受保护绑定；保真与访问授权无法同时满足时报告。模型选摘录可能遗漏指令，须与原始请求核对并报告差异。
2. 填 task_id、递增 revision、purpose、parent_plan 和实际 named target。将**每条**硬约束映射到 source_id 和准确 source_quote；类别只组织检查表，不重定义要求。不新造字段放工具参数或猜测的模型/运行时配置。
3. 必需资源填写当前准确路径/哈希，适用时填版本；任务要求正式 Skill/helper、已有且自身所有的运行时和依赖锁时，须真实解析。事实缺失阻断受影响任务，不将新建环境或未锁定依赖安装假定为等价替代；本模板没有通用固定依赖版本。
4. 填准确授权只读路径、callee 写入路径及单独的 lead 写入路径；协调只包含必需的具体 spec/来源文件，数据不能扩大授权。所有权分离，总审不能临时或永久改写 callee 输出。验收和交付要求从真实上游义务填写，包括被要求的完整原始证据、实际执行身份、命令超时/private temp 和失败记录。
5. 检查严格 Schema：未知字段、错误类型、空必填值、缩写哈希拒绝。还须检查来源/约束/资源/验收 ID 唯一，引用均解析，引文是准确来源子串，必需类别/资源无遗漏，范围不扩大或矛盾，验收覆盖适用约束。语义核对必须执行，但平台不会自动提供，Schema 也不保证。按下节请 Evidence 用自身已核实的锁定环境及独立 stdin authority 执行公开只读前检，Lead 不借其解释器。无法执行就记未核并阻断受影响业务委派，不安装新依赖或虚报成功。
6. 写入新的版本化 JSON 文件后计算完整 SHA-256，把版本/哈希在文件外传递以避免循环自哈希。保留旧版本并说明授权变更；不修改已派发规格却继续引用旧哈希。

## 派发文本检查

Delegate 的 task 文本应包含有界目标、spec 精确绝对路径、任务 ID/revision/完整 SHA-256 和授权来源路径。明确要求 callee：**核对当前已验证内联完整原请求/Spec及文件身份、revision、来源映射，缺内联时才实际Read授权原件；缺内容/身份或前提不满足时在业务前报告blocked/unverified**。如实区分内联接收与实际工具Read，不虚构Read回执；业务材料读取、Skill与checker执行仍须真实回执。硬约束逐字可用，不自由重写成另一流程。

选择 Delegate 参数前读取当前 ToolCatalog 和实际团队成员。工具 Schema 可能要求额外的 work-context/attempt/intent 字段，本说明不固定四参数调用。TaskSpec 中有某信息不表示存在 `name`、依赖版本、model、timeout、task-spec 或 permission 工具参数；配置契约的专业初始 sync/async 委派按输入准备指南使用 taskSource，不并带 task/context；不支持 source 的动作不可作为替代。运行时工具按其实际 Schema 调用。

SendMessage 用于澄清、进度和交付协调，采用支持的 `to`/`content` 选项；完整流程仍用 Delegate。等待答复与纯通知不同，给 Agent 的消息不能证明送达指定 child run。需要时先 InspectRuns 再用实际支持的特定 run interject/resume；新增尝试前核实唯一已有后继。任务要求新上下文时须从实际运行/上下文证据确认，isolated 或新 ID 均不证明零继承历史。

## 子方和总审回执

记录 spec ID/revision/hash、工具真实返回的 target/run/session 引用、spec Read 证据，以及每约束 satisfied/blocked/unverified 和实际证据位置。包含未决前提及每次失败命令/事件、要求的完整 request/stdout/stderr/exit、产物路径/哈希。这些是任务记录，不是新工具参数，也不替代业务契约。

总审核对上游请求 → spec → 派发指令 → 实际执行/交付。来源到规格或规格到派发的遗漏归总审传递缺陷，不能归为子方违反了未收到的指令；子方独立偏离另行归因。不为了整理结果覆盖成员报告；原始结果保留，总审另写回执，恢复后的哈希不能抹去此前写入。独立验收依赖指定审查者和底层证据，不由子方自报或总审摘要代替。

## 文件交付不等于通知

检查真实 delivery envelope 和附件回执。deliverables 为空而 final text 仅列文件时，视为已引用但尚未收集，直至总审实际读取并核对授权文件哈希。SendMessage 不附带文件；需要附件时使用当前 SendUserMessage（Send）Schema 并核真实治理受众，child run 可能交给总审而不是直达用户。不编造附件字段，不重复 Delegate 已收集的完成通知。

## 由 Evidence 执行前检

[公开检查器](../scripts/check_task_spec.py) 使用 Evidence 现有已审 jsonschema/referencing 依赖闭包。总审通过实际支持的 Delegate 调用发送有限核验请求，逐字保留原始授权并传冻结 spec 路径/哈希；此前检引导请求遵循本公开协议，不递归要求另一份业务 TaskSpec，只授权前检，不执行或修改 callee 业务结果。Evidence 提供自身已核实解释器/prefix/lock 事实，Lead 不运行其他 Agent 的 venv。

独立的 [authority 输入](../schemas/delegation-authority.schema.json) 从 stdin 提供，其中 task/revision/target/Plan/spec 哈希及 inline 原始指令来自权威请求，不取自生成的 spec。读/写 grants 来自原始允许范围，只加入明确授权的具体协调文件。file grant 仅允许该文件，directory grant 允许其后代；检查器自用 Evidence 锁是独立 runtime 绑定，不扩大 callee 的读范围；authority.runtime 只表示检查器运行环境，不能替换 TaskSpec 中业务 callee 的原始运行时/依赖约束。检查器不能认证 authority 由谁编写，总审和独立审查者须与原始请求对照。

TaskSpec 优先使用 inline instruction_sources（source_id、text、sha256）；文件来源（source_id、path、sha256）仅在字节与独立原文一致、且位于调用方 grant 和 spec 读范围内时支持。来源按字节精确比较，包括空格/换行；引文须为准确子串，ID 唯一、引用解析、每条已声明硬约束具有验收引用。这不能证明所有自然语言义务都已被提取。

Evidence 使用其安装和授权任务实际解析的路径运行：

```sh
"$EVIDENCE_PYTHON" "$LEAD_SKILL_DIR/scripts/check_task_spec.py"   --mode file-posix --spec "$TASK_SPEC_PATH" < "$AUTHORITY_JSON"
```

authority JSON 文件是调用方私有的 stdin 传输载体，由独立原始指令准备，不是 TaskSpec 内的字段；须放在已授权协调存储内并排除秘密，不把原始指令插值为 shell 代码。脚本仅向 stdout 写一条 JSON；若捕获/重定向，只能用 Evidence 单独授权的回执输出，不能覆盖输入或成员结果。

[结果 Schema](../schemas/delegation-check-result.schema.json) 定义输出。exit 0 且 result=pass 只表示相应模式的确定性检查完成，还须核准确 expected spec_sha256、全部检查项及模式/物理范围/文件稳定性标志；即使通过，semantic_completeness 仍固定为 not_established。exit 1 表示数据不合法、绑定变化或越权范围，exit 2 表示依赖/运行时/安全 IO 不可用、调用或 IO 错误；非零一律阻断受影响业务委派。`--help` 是用法文本，不是验证结果。总审继续原文约束映射比较，并保留 Evidence 实际调用/输出回执后再业务委派；独立实质验收仍分开进行。

大型业务输入通过授权的小型输入清单绑定；此前检检查元数据/Skill/helper/lock，不代替成员实际读文档或图片。超限资源明确拒绝，不静默跳过。

文件模式界限：stdin/spec/schema JSON 各≤1 MiB，普通来源/资源/锁文件各≤4 MiB，总读取≤32 MiB，含稳定性复读在内≤256次，检查器截止时间20秒。文件模式 grant/claim 要规范化且范围路径实际存在；拒绝符号链接、多硬链接、特殊文件、双前导斜杠、穿越，以及真实设备/inode祖先链显示的只读/成员/总审写入所有权重叠（含本机大小写别名）。未来范围先由授权流程准备，checker不创建。spec 派生文件在 stat/open 前先验证授权，以 dir_fd 逐目录锚定并使用 O_DIRECTORY/O_NOFOLLOW/O_NONBLOCK 和身份/哈希复核；本地 Schema 身份精确且仅允许片段 ref，不联网。缺少安全打开标志或实时 alarm 能力的宿主返回 unavailable，不降低检查。runtime 核 Evidence prefix/解释器及已审锁中的精确安装版本；原 wheel 安装来源仍由 Evidence 真实环境回执证明。文件哈希不证明资源版本语义、子模型选择、超时实际应用或未来遵守。

## Portable 全 inline 传输

Windows 及不使用文件读取模式的调用方采用 [inline transport Schema](../schemas/delegation-inline-transport.schema.json)。独立授权的采集者先获取**原始字节**，保留实际采集工具回执，再传 spec_bytes_base64、每个必需文件源/资源的 captures（path/bytes_base64）、runtime_lock_bytes_base64 和 capture_receipt_refs。来源 path 仅是逻辑绑定，checker不打开。所有捕获路径须在原 caller grants 内且确实被该规格需要，少件、额外或越权捕获拒绝。不要把显示带行号的 Read 摘要重新编码成“原始字节”，也不要只交未经核验的 digest。Spec SHA 针对原字节，不针对重序列化 JSON。

transport.authority 仍由独立原请求准备并按严格 authority Schema 检查，不能让 Spec 自授授权；inline 的 authority.runtime 省略 lock_path，锁原始字节按独立 lock_sha256 核对。path_flavor 明确 posix/windows，Windows 保守拒绝设备命名空间、保留名、ADS、尾部点/空格和常见大小写重叠；这不是实际文件系统规范身份核验，也不识别所有 junction/短名等物理别名。已有文件模式物理失败不能通过切换 inline 变成可执行任务。

stdin 使用**ASCII 十进制 UTF-8 payload 字节数 + LF + 精确该长度的无 BOM JSON 原字节**。头最多16字节，payload最多8MiB；只消费一个声明帧，不消费其后流字节。可以由独立已授权采集流程把该帧写入私有传输文件，然后运行：

```sh
"$EVIDENCE_PYTHON" "$LEAD_SKILL_DIR/scripts/check_task_spec.py" --mode inline < "$INLINE_FRAME"
```

Windows stdin 切换二进制读取，避免 CRLF 转换改变帧长度；不得给 inline 再传 --spec 文件参数。authority/spec各≤1MiB，单捕获文件≤4MiB，合计解码捕获≤8MiB；内部 watchdog 覆盖完整帧读取和校验，等待不完整帧也会退出。20秒截止仅属于 checker，不改变子任务原有的进程超时要求；外部平台 timeout 仍须按真实工具及授权请求设置，不能将它冒称内部保障。

结果必须保留 mode=inline、physical_scope_status=not_checked_inline、file_stability_status=not_checked_inline、deadline_mode=thread-watchdog、capture_provenance=caller_supplied_not_authenticated。checks.stability 仅指提供的字节缓冲区哈希一致，不指采集时的文件稳定性；receipt refs 只是引用，不被checker自动取回或认证。总审/独立审查者须另核实际授权采集回执及所需物理范围证据，未具备就保持未核，不能仅凭inline pass启动依赖该证明的文件工作。当前已测portable协议和Windows路径语义，不代表真实Windows或全平台生产验收。

Windows 的上述重定向示例使用 **cmd.exe**，不是 PowerShell 的文本管道；对应变量语法为：

```bat
"%EVIDENCE_PYTHON%" "%LEAD_SKILL_DIR%\scripts\check_task_spec.py" --mode inline < "%INLINE_FRAME%"
```

由实际工具选择获准 shell；不要用会重新编码/展开字节的文本管道代替二进制帧。命令只传可信路径，原始任务文本始终在帧中，不插入命令字符串。
