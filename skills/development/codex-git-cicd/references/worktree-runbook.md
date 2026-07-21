# Git Worktree 生命周期手册

worktree 用于隔离工作目录和 index，让不同分支拥有独立 checkout。所有 worktree 仍共享对象库、refs、stash 和部分配置，因此它不是完整沙箱。

## 何时使用

- 主工作区有必须保留的脏改，但新任务需要从稳定基线开始；
- 两个任务文件集合独立，可并行开发或验证；
- 热修复、发布回归或长时间构建不应阻塞主 checkout；
- 需要把一个稳定目录与明确分支交给新 Agent 接手。

以下情况保持串行：共享同一文件、锁文件、迁移、端口、数据库、生成目录或外部发布状态。多个 worktree 不会消除这些竞争。

## 建立拓扑基线

先运行：

```bash
git worktree list --porcelain
git status --short --branch
git branch -vv
git rev-parse --git-common-dir
```

对每个 worktree 记录：路径、分支、HEAD、detached/bare、dirty、locked、prunable、任务所有者、base 和集成目标。一个分支只能由一个 worktree 占用；不要用 `--ignore-other-worktrees` 绕过保护。

## 规划创建

推荐让 Skill 的只读规划器先验证：

```bash
python3 <skill-dir>/scripts/git_cicd.py worktree create \
  --repo . \
  --path ../repo-task \
  --branch codex/task \
  --base origin/main \
  --json
```

`READY` 后才执行返回的命令。常见模式：

```bash
# 新任务分支
git worktree add -b codex/task ../repo-task origin/main

# 复用未被占用的本地分支
git worktree add ../repo-task codex/task

# 只读调查或构建，不绑定分支
git worktree add --detach ../repo-audit origin/main
```

仓库内使用 `.worktrees/<task>` 时，先确认 `.worktrees/` 已被 ignore；否则优先使用仓库外的同级目录。创建后立即复查 `git worktree list --porcelain` 和目标 worktree 的 `git status --short`。

## 协作与 handoff

- 每个 worktree 只指定一个写入所有者；跨 Agent 共享同一 worktree 时串行交接。
- handoff 固定写入目标 worktree、分支、HEAD、base、集成目标、改动、验证、CI 和清理条件。
- stash 在同一仓库的 worktree 间共享。必须使用可识别名称并记录来源；不要依赖 `stash@{0}` 作为长期身份。
- fetch、创建或删除 refs 会影响全部 worktree；执行前重新检查拓扑。
- hooks、仓库配置、对象维护和部分缓存可能共享；不能把 worktree 当安全隔离边界。

## 集成

在任务 worktree 中完成提交和本地验证，推送与 PR 仍按仓库策略执行。集成前确认：

- staged diff 只属于当前任务；
- branch HEAD 与 CI/PR head SHA 对齐；
- 目标分支已刷新，分叉策略明确；
- 其他 worktree 没有占用准备切换或删除的分支；
- merge、rebase、cherry-pick 或 PR 由项目规则决定，不因使用 worktree 改变。

## 安全回收

先生成回收计划：

```bash
python3 <skill-dir>/scripts/git_cicd.py worktree close \
  --repo . \
  --path ../repo-task \
  --integrated-into origin/main \
  --json
```

只有同时满足以下条件才执行返回的 `git worktree remove`：

- 目标不是当前 worktree；
- worktree 可访问、未锁定且工作区干净；
- HEAD 已包含在指定集成目标中；
- handoff、PR、CI 和发布状态已保存；
- 用户授权包含回收该路径。

删除 worktree 不会删除分支。分支删除需要再次确认已合并、已推送或明确不再需要，并作为独立动作处理。禁止默认使用 `git worktree remove --force`。

路径丢失或元数据陈旧时先 dry-run：

```bash
git worktree prune --dry-run --verbose
```

确认输出只包含目标记录后，才在明确授权下执行实际 `prune`。锁定 worktree 先读取锁定原因，不机械 `unlock`。

## 故障恢复

- 分支显示已占用：用 `git worktree list --porcelain` 找到所有者，不绕过保护。
- worktree dirty：停止回收，提交、移交或由所有者明确处理改动。
- HEAD 未集成：推送保留分支或完成 PR/merge；不要删除目录掩盖未集成 commit。
- 路径被手工删除：用 `prune --dry-run --verbose` 检查元数据，再决定是否 prune。
- rebase/merge 中断：在发生操作的同一 worktree 恢复；不要从另一个 worktree 猜测执行 `--continue` 或 `--abort`。
