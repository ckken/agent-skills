![Codex Git CI/CD 自动驾驶](./assets/cover.optimized.webp)

# Codex Git CI/CD 自动驾驶

为 Codex 与 GPT-5.6 定制的智能 Git、worktree 和 CI/CD 工作流，把多工作树体检、任务隔离、验证、提交、推送、CI 修复和任务交接串成可恢复的自动化闭环。

## 解决什么问题

- 防止脏工作树中误提交用户已有改动。
- 自动识别全部 worktree、分支占用、脏状态、锁定、上游、ahead/behind、冲突和 CI 平台。
- 为并行任务规划独立 worktree，并在回收前验证干净状态与 commit 集成关系。
- 按仓库真值源选择测试、构建和发布门禁。
- 对 CI 失败做根因分类和最小修复，不盲目重跑。
- 将 commit、验证、CI、PR、发布和下一步固化为高保真 handoff。
- 支持长任务换会话、换 Agent 或人工接管后直接恢复。

## 典型调用

```text
使用 $codex-git-cicd 完成当前改动的检查、作用域提交、push 和 CI 验收；保留无关脏改，并生成可继续执行的 handoff。
```

只做诊断：

```text
使用 $codex-git-cicd 审查当前仓库的 Git 和 CI 状态，给出风险与恢复方案，不修改文件。
```

长任务交接：

```text
使用 $codex-git-cicd 把当前任务整理成最大化 handoff，包含 HEAD、差异、验证证据、阻塞、恢复命令和下一步。
```

隔离并行任务：

```text
使用 $codex-git-cicd 为当前任务规划独立 Git worktree；保留主工作区脏改，检查分支占用，并给出创建、集成、handoff 和安全回收步骤。
```

## 自带工具

```bash
python3 scripts/git_cicd.py inspect --repo .
python3 scripts/git_cicd.py inspect --repo . --json
python3 scripts/git_cicd.py worktree create --repo . \
  --path ../repo-task --branch codex/task --base origin/main --json
python3 scripts/git_cicd.py worktree close --repo . \
  --path ../repo-task --integrated-into origin/main --json
python3 scripts/git_cicd.py handoff --repo . \
  --objective "完成当前变更并通过 CI" \
  --scope "仅提交本任务文件" \
  --remote-state "push=UNKNOWN" \
  --next "核对 staged diff 后提交"
```

`inspect` 和 `worktree` 规划器完全只读；规划被阻塞时返回退出码 `3`。`handoff` 默认输出到终端，只有传入 `--output` 才写文件。工具不会执行 worktree 创建或删除、提交、push、rebase、reset 或 force-push。

## 目录内容

- `SKILL.md`：完整自动驾驶状态机、权限边界和完成标准。
- `scripts/git_cicd.py`：多 worktree 仓库体检、生命周期规划与 handoff 生成器。
- `scripts/test_git_cicd.py`：确定性脚本测试。
- `references/ci-adapters.md`：GitHub、GitLab 和通用 CI 适配策略。
- `references/worktree-runbook.md`：worktree 创建、协作、集成和安全回收手册。
- `references/handoff-contract.md`：可恢复交接包的数据合同。
- `assets/cover.optimized.webp`：发布封面。

## 设计原则

自动化负责收集事实、执行已授权动作和验证结果；高风险历史重写、保护规则绕过、发布审批和范围扩张始终保留明确决策点。

参考：[OpenAI Codex Skills 文档](https://developers.openai.com/codex/skills) 与 [OpenAI `gh-fix-ci` Skill](https://github.com/openai/skills/tree/main/skills/.curated/gh-fix-ci)。
