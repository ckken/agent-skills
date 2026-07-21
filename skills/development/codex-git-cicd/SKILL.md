---
name: codex-git-cicd
description: 面向 Codex 与 GPT-5.6 自动完成 Git 和 CI/CD 闭环，并生成可恢复的高保真 handoff。用于仓库体检、脏工作树隔离、分支与提交规划、测试门禁、push、PR、CI 失败诊断、发布交接、长任务换会话或换 Agent；强调最小权限、作用域提交、证据化验证和安全恢复。只审查时不修改仓库，明确要求提交、推送、发布或修复时才执行对应写操作；不自动 force-push、重写共享历史或绕过保护规则。
---

# Codex Git CI/CD 自动驾驶

把 Git 操作、CI 验证和任务交接组织成一个可恢复的状态机。先识别真实仓库状态，再选择最小安全动作；每个阶段都留下机器可读证据和面向下一位 Agent 的 handoff。

## 核心合同

- 先读取适用的 `AGENTS.md`、仓库说明、CI 配置和发布规则。
- 修改前运行 `git status --short`，区分当前任务、用户已有改动和生成物。
- 只暂存当前任务文件；不把无关脏改、密钥、日志或本地产物带入提交。
- 把工作区状态、Git 状态、远端状态、CI 状态和发布状态分开验证。
- 写操作必须来自用户目标或正常实施流程；审查、诊断和规划默认只读。
- 禁止自动执行 `reset --hard`、删除分支、重写共享历史、跳过钩子或保护规则。
- 只有明确授权且已证明安全时才考虑 force-push；优先 `--force-with-lease`，并再次核对远端 HEAD。
- 任何失败都转为可恢复状态，不用重复提交或盲目重跑掩盖根因。
- 任务完成、暂停、阻塞、上下文过长或换 Agent 前都生成 handoff。

## 状态机

按以下顺序推进，不跳过门禁：

```text
DISCOVER -> ISOLATE -> IMPLEMENT -> VERIFY -> COMMIT -> PUSH -> CI -> DELIVER
    |          |           |          |         |       |      |
    +----------+-----------+----------+---------+-------+-------> HANDOFF
```

- `DISCOVER`：读取规则，获取分支、HEAD、上游、ahead/behind、冲突和 CI 类型。
- `ISOLATE`：确定本次文件清单、风险、验证命令和禁止触碰范围。
- `IMPLEMENT`：执行已授权改动，持续保持单一任务边界。
- `VERIFY`：运行与风险匹配的 lint、测试、类型检查、构建或 smoke。
- `COMMIT`：检查 staged diff，只提交目标范围并使用可追踪提交信息。
- `PUSH`：先处理上游漂移，再推送当前分支并验证远端分支。
- `CI`：定位失败 job 和首个有效错误，最小修复并复验。
- `DELIVER`：回传 commit、分支、PR/发布链接、验证结果和残余风险。
- `HANDOFF`：固化所有已验证状态、恢复点和下一条动作。

## 1. 仓库体检

从 Skill 目录运行只读体检：

```bash
python3 <skill-dir>/scripts/git_cicd.py inspect --repo .
python3 <skill-dir>/scripts/git_cicd.py inspect --repo . --json
```

体检结果用于确定：

- 是否位于 Git 仓库、是否处于 detached HEAD；
- 当前分支、HEAD、upstream、ahead/behind；
- staged、unstaged、untracked、冲突文件；
- GitHub Actions、GitLab CI、CircleCI、Jenkins 等 CI 入口；
- 从 `package.json`、`Makefile`、`pyproject.toml` 等发现的候选验证命令。

脚本不会输出远端 URL，也不会读取或回显凭据。状态不清时不要进入写阶段。

## 2. 隔离任务作用域

建立明确集合：

- `target_files`：本任务允许修改和提交的文件；
- `preserve_files`：用户已有或其他任务的改动；
- `generated_files`：需要验证是否应提交的构建产物；
- `verification_plan`：按改动风险选择的本地门禁；
- `remote_actions`：是否允许 push、PR、merge、tag、release 或 deploy。

同一文件同时含本任务和用户改动时，优先使用交互式暂存或构造最小补丁；无法可靠拆分就停止并说明冲突，不覆盖用户内容。

## 3. 实施与本地门禁

优先使用仓库已有命令和 CI 真值源，不自创平行流程。验证顺序通常为：

1. 目标文件格式与静态检查；
2. 受影响单元测试；
3. 类型检查或构建；
4. 跨模块集成测试；
5. 高风险变更的 acceptance、浏览器或部署 smoke。

每条命令记录 `PASS`、`FAIL`、`SKIP` 或 `BLOCKED`，并保留命令与简短证据。失败时先定位根因，不把重试当修复。

## 4. 安全提交与推送

提交前至少检查：

```bash
git status --short
git diff --check
git diff --cached --check
git diff --cached --stat
git diff --cached
```

确认 staged diff 只包含 `target_files` 后再提交。push 前执行 `git fetch` 或等价远端刷新，判断：

- `behind = 0`：可以按授权 push；
- 仅本地 ahead：正常 push；
- 双向分叉：先报告并选择 merge、rebase 或新分支，不擅自重写历史；
- 默认分支或受保护分支：优先功能分支和 PR；
- detached HEAD：先创建明确分支再提交。

push 后核对远端分支包含本地 HEAD。用户只说“提交”不等于授权 push；用户说“上传”“push”“发布”时，完成对应远端闭环。

## 5. CI 诊断与自动恢复

先识别平台能力，再读取 [ci-adapters.md](references/ci-adapters.md)。处理顺序：

1. 找到与当前 commit 对应的 workflow、pipeline 和失败 job；
2. 提取首个有效错误、失败命令、运行环境和是否可复现；
3. 区分代码失败、测试波动、环境/凭据、配额、基础设施和策略门禁；
4. 本地可复现时做最小修复并运行同级验证；
5. 仅对明确的瞬时基础设施失败重跑；
6. 新提交后等待对应新 commit 的 CI，不混用旧 run 结果；
7. 所有必需检查通过后才报告完成。

不得为了变绿删除测试、放宽断言、静默忽略失败或绕过 required checks。

## 6. 最大化 handoff

handoff 不是总结，而是下一位 Codex、GPT-5.6 Agent 或人工维护者可直接继续执行的恢复快照。读取 [handoff-contract.md](references/handoff-contract.md)，并在每个稳定检查点生成：

```bash
python3 <skill-dir>/scripts/git_cicd.py handoff \
  --repo . \
  --objective "完成当前 Git/CI/CD 任务" \
  --scope "仅处理已确认的目标文件" \
  --check "unit-tests=PASS" \
  --decision "保留用户已有未提交改动" \
  --next "核对 staged diff 后提交" \
  --output .codex/handoffs/git-cicd.md
```

交接包必须包含：目标和成功标准、授权边界、分支/HEAD/upstream、ahead/behind、改动分组、已运行验证、CI/PR/发布状态、关键决策、阻塞、恢复命令、下一条原子动作和完成条件。

优先在以下节点刷新同一 handoff：

- 修改前基线；
- 本地验证完成；
- commit 后；
- push 后；
- CI 通过或失败根因已确认；
- PR、merge、tag、release 或 deploy 后；
- 任务暂停、换会话、换 Agent 或出现外部阻塞前。

交接文件是否提交由仓库规则决定；默认把它视为运行态文件，不擅自纳入产品提交。若 Codex 运行时支持任务 handoff/thread 工具，可在文件状态稳定后创建新任务并发送该交接包；若不支持，就将文件路径和恢复命令交给用户。

## 7. 完成判定

只有同时满足以下条件才结束：

- 目标改动已完成，Git diff 与授权范围一致；
- 必需本地验证通过，跳过项有原因；
- 用户要求的 commit、push、PR、CI、merge、release 或 deploy 已真实完成；
- 远端状态对应当前 commit，不引用过期 CI；
- 无关工作区改动仍被保留；
- handoff 已更新，可从当前稳定点恢复；
- 最终回报包含 commit/分支/链接、验证证据和残余风险。

## 输出格式

最终先给结果，再列：

1. Git/CI/CD 当前状态；
2. 实际修改和提交范围；
3. 验证命令及结果；
4. commit、分支、PR、CI 或发布链接；
5. handoff 路径与下一步；
6. 未解决风险或明确阻塞。

不要声称未查询的远端状态已完成，也不要把本地命令成功等同于 CI、合并或生产发布成功。
