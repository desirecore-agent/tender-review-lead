# 依赖说明

## 所有权

本 Lead Agent 和 Team 包**不捆绑、管理或锁定**业务报告校验器脚本或其 Python 依赖。业务校验能力是外部条件能力，由已独立审查的 `tender-evidence-review` 发行版提供。Lead Skill 另含只读 TaskSpec 检查器，由 Evidence 成员在其自身已核实、已锁定环境中运行，见下文。

## 安装门禁

启用校验前，安装器/操作者必须核同一个 Evidence 发行版的：

- 不可变发行 ref/commit 与正式校验代码；
- 公开 Skill/文档及 NOTICE；
- 已独立审查、带精确版本/哈希/许可闭包的 `requirements.lock`；
- 按该锁初始化的 Python >= 3.9 隔离运行时及验证回执。

锁、文档、运行时回执、代码身份或发行证据任一缺失、pending 或不匹配，校验就**阻断**。不得从本 Lead 包猜依赖版本、安装未审 latest 版本或降级运行校验器。

## 平台

- DesireCore 客户端须匹配实际发行团队的兼容 profile 及能力证据，未发行修订的最终最低版本仍待固定。
- 平台许可：具体安装版本自带的 LICENSE。
- 已审运行时安装后，校验在本地执行；依赖获取遵循 Evidence 发行版已审安装策略。

## 验证当前安装

根据当前安装中的文件和运行时核验上述前提。其他安装或发行版的验证回执不能证明当前安装能够执行校验。

## TaskSpec 前检

Lead Skill 发布 `scripts/check_task_spec.py` 和相邻四份 Draft-07 数据/输出 Schema。仅使用 Python 标准库及独立已审 Evidence 依赖锁中已有 jsonschema/referencing 闭包，不新增第二套锁、安装器、依赖下载或子进程。由 Evidence 本人用已核实私有解释器运行，Lead 不借其环境；使用前核实际 lock 哈希、安装分发包版本和环境回执。检查器比对 prefix/解释器及锁定包版本，不代替原始 wheel 安装来源审查。

调用方在 stdin 独立提供 authority JSON，绑定任务/revision/spec 哈希、原始非秘密指令、原授权路径和 Evidence runtime/lock；不能从 TaskSpec 自述推导 authority。检查器自己的锁文件与业务 callee 的读授权分离。优先 inline 原始指令以减少文件访问，文件来源/资源只在独立授权范围内读取，不联网解析 ref、不写文件、不安装。平台既有审批及文件权限仍适用。

CLI 和返回语义见 [TaskSpec 说明](../skills/tender-review-orchestration/templates/delegation-task.zh-CN.md)。有限 Evidence 前检请求使用此公开检查协议和原始 authority，不递归要求另一份尚未校验的业务 TaskSpec。通过后总审继续原文约束比较及真实业务委派；pass 不证明语义完整或模型将遵守。环境缺失、锁不符、不安全文件句柄或权限不可用均明确失败，不能另建环境兜底。文件模式只限具备目录 fd/no-follow/nonblocking 和 SIGALRM 的 POSIX 宿主，且范围路径须已存在；Windows 使用下述全 inline 数据协议，不静默套用文件模式。

## 模式与兼容界限

- `--mode file-posix --spec ...`：校验器自己读取授权文件，用真实设备/inode祖先链核物理范围；拒绝双前导斜杠、大小写等实际同一身份/嵌套别名及缺失范围路径。未来输出范围须由已有授权流程先准备，不由 checker 创建；不能证明时拒绝。逐文件和总预算都在读取前限制，稳定性复读保留最初上限。
- `--mode inline`：Windows/POSIX 可用的有界全 inline 协议，经 stdin 长度帧提供 spec 和所有必需来源/资源/锁的原始字节及采集回执引用，不接受只有 digest 的占位。不会打开 Spec/authority 中的路径，只读取自身已安装包 Schema 与已有依赖元数据；业务路径仅作保守逻辑授权/重叠比较。物理范围和文件稳定性固定为 not_checked_inline，采集来源为 caller_supplied_not_authenticated，不能借此覆盖物理检查失败。

两模式仍用 Evidence 自己的已锁定隔离环境，无新安装器。文件模式用内部 signal 截止时间，inline 用自身线程 watchdog 覆盖帧读取及验证；外部平台命令 timeout 是额外边界，不是内部计时实现。Windows 路径语义和 portable 协议已有本机中性测试，但尚未真实 Windows 运行；不得宣称全平台生产验收。实际文件操作前须取得需要的独立平台/宿主物理范围与授权采集证据，未具备则该部分仍阻断。
