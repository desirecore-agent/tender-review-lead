# 使用指南

## 概述

本指南介绍如何在 DesireCore 上使用 `tender-review` 团队执行标书审查。

## 前置条件

1. DesireCore 平台 ≥ 10.0.136 已安装并运行。
2. Python ≥ 3.9 可用（隔离虚拟环境）。
3. 已安装 `tender-evidence-review` 技能（提供校验器）。
4. `tender-review` 团队仓库包含 `shared/contracts/schemas/`。

> **安装核验**：执行这些命令前，按 `dependencies.zh-CN.md` 核验当前安装的 Evidence 发行 ref、校验代码、公开 Skill/文档、已审依赖锁、已初始化的隔离运行时及其验证回执。核验团队六份 Schema 的发行身份与哈希。前提缺失或不匹配时阻断校验；其他安装的结果不能满足此项核验。

## 工作流程

### 步骤 1：准备输入文件

将所有投标文件（PDF、DOCX、图像）放入一个目录。总审智能体将构建带 SHA-256 哈希的文件台账。

### 步骤 2：触发审查

通过总审智能体发起审查，它将：

1. 构建文件台账（`file-manifest.json`），赋予不可变 `manifest_id`。
2. 从招标侧文件提取条款矩阵（`requirements.json`）。
3. 并行分配商务、图像、条款专业审查。
4. 收集专业输出，触发独立证据复核。
5. 合并为最终统一报告（`review-report.json`）。

### 步骤 3：校验数据包

审查完成后，校验六件产物数据包：

```sh
# 校验完整包
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

### 步骤 4：解读结果

- **exit 0, result=pass**：六件产物结构合法，业务规则全部满足。
- **exit 1**：普通结构/业务违规使用 `result=fail`；`--json` 下 Schema 加载失败也可能在 stdout 返回结构化 `{error}` 而没有 `result`。
- **exit 2**：调用、导入或 argparse 错误；stderr 可能是 JSON 错误，也可能是 argparse usage。自动化必须先把任何非零退出视为失败，再解析实际封套。

> 机器校验通过 ≠ 报告结论通过。`exit 0 / result=pass` 表示数据包通过结构和业务规则检查，不代表所有文件已独立重读或标书已完整。

## 重要说明

- **诚实 partial 是有效状态**：`conclusion=partial_only` 且 `exit 0 / result=pass` 表示结构合法但覆盖未完全闭合——这是诚实声明，不是错误。
- **Schema 校验是结构性的**：校验器检查 JSON Schema 合规性和业务规则，不验证文档内容真实性。
- **不承诺中标**：这是投标准备阶段的辅助审查工具。
- **材料权利**：用户必须有权处理提交的文件。配置模型提供方不构成对外分发材料的授权。
- **未完成和错误不是成功**：未检查项、未解决工具失败和解析错误是诚实的局限，绝不当作检查通过处理。
