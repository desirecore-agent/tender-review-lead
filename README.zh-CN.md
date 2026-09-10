# Tender Review Lead — 编排智能体

**状态**：发布前草稿 — 非生产就绪、未发布。

## 概述

**tender-review-lead** 是 DesireCore 平台上标书联合审查团队的编排智能体。接收投标文件后，协调并行专业审查（商务报价、技术图像、证据复核），合并发现为统一报告，交付结构化审计包并透明标注不确定性。

### 职责

- **文件台账与哈希** — 为每个输入文件生成稳定 file_id 和 SHA-256，建立可验证清单。
- **契约驱动校验** — 业务逻辑运行前，先按六份 v1.2 JSON Schema 校验全部产物。
- **并行委派** — 向专业成员委派任务时传递完整上下文、输入路径、契约版本、输出目录与验收标准。
- **单写合并报告** — 最终报告由总审单写合并；其他成员不写入最终报告。
- **独立复核** — 专业审查后，独立复核员重读严重项双边证据并检查负例。

### 不做什么

- **不修改**原始投标文件（只读）。
- **不鉴真** — 印章、签名、证照只报告可见内容，不鉴定真伪。
- **不做出**资格否决或法律裁定 — 正式评审决定由授权用户或依法有权的评审机构作出。
- **不承诺**中标、合规或法律效力。

## 团队结构

```
tender-review（团队）
├── tender-review-lead         ← 本智能体（编排、报告单写）
├── tender-review-commercial   ← 商务报价分析
├── tender-review-visual       ← 技术参数与图像检查
├── tender-review-evidence     ← 证据校验与独立复核
└── tender-review-requirements ← 条款资格与需求映射
```

## 前置条件

- DesireCore 客户端须匹配实际已发行团队的最低版本和已核能力；未发行修订的最终最低版本不得从历史测试推断。
- Evidence 自身按已审依赖锁初始化的 Python ≥ 3.9 隔离环境。TaskSpec checker 还受下方模式兼容条件约束，不能仅凭 Python 版本断言支持。
- 已安装且独立审查通过的 `tender-evidence-review` 发行版；其 ref/commit、正式代码、公开文档、依赖锁、许可声明和初始化运行时必须与发行证据一致，任一缺失或不匹配即阻断。
- 团队仓库 `shared/contracts/schemas/` 包含六份 v1.2 契约 Schema。

## 用法

```sh
# 校验完整六件包
"$VALIDATOR_PYTHON" "$EVIDENCE_SKILL_DIR/scripts/validate_report.py" \
  --pack "$PACK_DIR" \
  --schemas "$TEAM_ROOT/shared/contracts/schemas" \
  --json

# 校验复核产物包（独立复核员输出）
"$VALIDATOR_PYTHON" "$EVIDENCE_SKILL_DIR/scripts/validate_report.py" \
  --pack "$REVIEW_PACK_DIR" \
  --schemas "$TEAM_ROOT/shared/contracts/schemas" \
  --review-pack --json
```

> `$VALIDATOR_PYTHON`、`$EVIDENCE_SKILL_DIR` 和 `$TEAM_ROOT` 由已安装技能和团队配置在运行时解析，不硬编码个人路径。

## 合约 v1.2

每轮审查必须生成六份 JSON 产物：

| 产物 | 文件 | 用途 |
|------|------|------|
| 项目画像 | `project-profile.json` | 采购背景、分类、适用法规 |
| 文件台账 | `file-manifest.json` | 输入文件清单（SHA-256、角色、页数） |
| 条款矩阵 | `requirements.json` | 逐条条款提取与来源归属 |
| 覆盖台账 | `coverage.json` | 逐文件逐项覆盖记录与闭合状态 |
| 发现 | `findings.json` | 问题记录（严重性、确定性、双边证据、观察方法） |
| 审查报告 | `review-report.json` | 最终报告（结论、未解决项、工具失败） |

所有 Schema 位于 `<TEAM_ROOT>/shared/contracts/schemas/`，使用 JSON Schema Draft-07。

## 限制

- 校验器执行**结构和 Schema 校验**。机器校验 ≠ 业务一致性，也 ≠ 独立重读已发生。
- 云模型提供方可能处理提交的文本和图像。这不构成对外分发材料的授权。
- 不保证合规、资格或中标。
- 历史开发路径、测试结果和智能体工作目录不纳入公开文档。

## 许可

原创内容：MIT（DesireCore Contributors）。
平台和第三方依赖保留各自许可。

## TaskSpec 检查器模式兼容

由 Evidence 本人运行 [TaskSpec 只读检查器](skills/tender-review-orchestration/templates/delegation-task.zh-CN.md)，总审不借其 venv。文件模式 `file-posix` 仅限提供安全目录 fd/no-follow/nonblocking 及 signal 的 POSIX 宿主，并要求检查的范围路径已存在；实际设备/inode祖先链核重叠、大小写别名等，未知未来范围拒绝，先由授权流程准备。

Windows/POSIX 可使用 `inline` 长度帧协议传原始 spec/source/resource/lock 字节及授权采集回执引用；不打开 Spec/authority 自述路径。它只核逻辑授权/字节/引用，不核实际物理目录隔离或采集文件稳定性，结果固定声明 not_checked_inline 和 caller_supplied_not_authenticated。需要物理证明的文件工作仍须另核平台/宿主与真实采集证据，不能靠 inline pass 绕过文件模式失败。

内部 deadline 与外部平台 timeout 分开：文件模式用 signal，inline 用自己的线程 watchdog。本修订已有本机真实文件/alias/预算和 Windows 路径语义/portable 中性测试，没有原生 Windows 实机验收，不宣称全平台生产就绪。完整说明、二进制帧格式及 cmd.exe 示例见上方链接。
