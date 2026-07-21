# Agent Skills 仓库规范

## 默认要求

- 默认使用中文，先给结果，再补充必要说明。
- 修改前检查 `git status --short`，不得覆盖或混入用户已有的无关改动。
- 开源 Skill 放在 `skills/<category>/<skill-name>/`，工具放在 `tools/<tool-name>/`。根 README 只登记开源 Skill。
- 分类目录和 Skill 名称使用小写 kebab-case；Skill 名称需与 `SKILL.md` frontmatter 中的 `name` 保持一致。

## Git / CI/CD 自动驾驶

- 本仓库的 Git、worktree、提交、推送、CI 和 handoff 默认使用 [`codex-git-cicd`](skills/development/codex-git-cicd/SKILL.md)；开始时先运行仓库与全部 worktree 体检，再按其状态机推进。
- 对修改型任务，本项目规则视为已授权自动完成 `VERIFY → COMMIT → PUSH → CI → HANDOFF`，无需逐步等待人工确认；用户明确要求只读、只修改、只提交、暂不推送或限定其他终点时，以用户边界为准。
- 自动提交必须按任务隔离，只暂存本任务文件；发现用户已有改动、错误产物或其他任务内容时保留原状，并采用局部暂存或独立 worktree。
- push 前刷新远端并处理 ahead/behind；push 后核对远端 HEAD 和对应 CI。没有触发 CI 时明确记录原因，不把本地测试等同于远端流水线。
- 不自动 force-push、合并 PR、创建 tag、发布、部署、删除分支或强制删除 worktree；这些高风险或生产动作仍需用户明确授权。
- 失败或外部阻塞时停止扩大写操作，输出可恢复 handoff，包含 worktree、分支、HEAD、验证证据、阻塞和下一条原子动作。

## 新建 Skill

每次新建 Skill 时，必须同时交付以下文件：

```text
skills/<category>/<skill-name>/
├── SKILL.md
├── README.md
└── assets/
    └── cover.optimized.webp
```

- `SKILL.md`：包含有效 frontmatter、触发范围、执行流程、边界和验证要求。
- `README.md`：面向使用者说明用途、典型调用方式和目录内容，并在开头引用压缩封面：

  ```markdown
  ![<Skill 展示名称>](./assets/cover.optimized.webp)
  ```

- `assets/cover.optimized.webp`：通过本仓库的 `agent-image-opt` 生成的发布版本，不得手工改扩展名或用未验证文件代替。
- 封面源图只作为压缩过程中的临时文件，压缩和视觉验收完成后删除，不提交到仓库。
- 在根目录 `README.md` 的 Skills 表格中登记新 Skill。

## 封面压缩

封面默认使用 16:9，推荐尺寸为 1600 × 900。生成临时源图后，必须使用 `agent-image-opt` 检查、预览并压缩：

```bash
agent-image-opt --json doctor
agent-image-opt --json inspect <temporary-cover.png>
agent-image-opt --json optimize <temporary-cover.png> \
  --preset poster \
  --dry-run
agent-image-opt --json optimize <temporary-cover.png> \
  --preset poster
mkdir -p skills/<category>/<skill-name>/assets
mv <temporary-cover.optimized.webp> \
  skills/<category>/<skill-name>/assets/cover.optimized.webp
rm <temporary-cover.png>
```

默认输出应为：

```text
skills/<category>/<skill-name>/assets/cover.optimized.webp
```

如果默认的 8% 最小节省阈值导致未生成文件，应根据视觉质量调整 `--quality`、`--max-width` 或临时源图尺寸后重新执行。不得为了满足文件名要求而提交体积更大、文字模糊或存在明显压缩伪影的封面。

README 只引用压缩版。Skill 目录和 Git 变更中不得保留未压缩封面、母版或中间产物。替换已有封面时，只有确认目标文件属于当前任务后才能使用 `--force`。

## 新 Skill 验收

完成前至少执行：

```bash
test -f skills/<category>/<skill-name>/SKILL.md
test -f skills/<category>/<skill-name>/README.md
test -f skills/<category>/<skill-name>/assets/cover.optimized.webp
rg -n "cover\\.optimized\\.webp" skills/<category>/<skill-name>/README.md
agent-image-opt --json inspect skills/<category>/<skill-name>/assets/cover.optimized.webp
test -z "$(find skills/<category>/<skill-name>/assets -maxdepth 1 -type f \
  -name 'cover.*' ! -name 'cover.optimized.webp' -print)"
git diff --check
```

同时确认：

- README 中的封面路径可以解析；
- 压缩封面尺寸和文字清晰度符合发布要求；
- `assets/` 中没有封面源图或压缩中间产物；
- 根 README 已登记新 Skill；
- Git diff 只包含当前任务需要的文件。
