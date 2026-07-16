# Agent Skills 仓库规范

## 默认要求

- 默认使用中文，先给结果，再补充必要说明。
- 修改前检查 `git status --short`，不得覆盖或混入用户已有的无关改动。
- Skill 放在 `skills/<skill-name>/`，工具放在 `tools/<tool-name>/`。
- Skill 名称使用小写 kebab-case，并与 `SKILL.md` frontmatter 中的 `name` 保持一致。

## 新建 Skill

每次新建 Skill 时，必须同时交付以下文件：

```text
skills/<skill-name>/
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
mkdir -p skills/<skill-name>/assets
mv <temporary-cover.optimized.webp> \
  skills/<skill-name>/assets/cover.optimized.webp
rm <temporary-cover.png>
```

默认输出应为：

```text
skills/<skill-name>/assets/cover.optimized.webp
```

如果默认的 8% 最小节省阈值导致未生成文件，应根据视觉质量调整 `--quality`、`--max-width` 或临时源图尺寸后重新执行。不得为了满足文件名要求而提交体积更大、文字模糊或存在明显压缩伪影的封面。

README 只引用压缩版。Skill 目录和 Git 变更中不得保留未压缩封面、母版或中间产物。替换已有封面时，只有确认目标文件属于当前任务后才能使用 `--force`。

## 新 Skill 验收

完成前至少执行：

```bash
test -f skills/<skill-name>/SKILL.md
test -f skills/<skill-name>/README.md
test -f skills/<skill-name>/assets/cover.optimized.webp
rg -n "cover\\.optimized\\.webp" skills/<skill-name>/README.md
agent-image-opt --json inspect skills/<skill-name>/assets/cover.optimized.webp
test -z "$(find skills/<skill-name>/assets -maxdepth 1 -type f \
  -name 'cover.*' ! -name 'cover.optimized.webp' -print)"
git diff --check
```

同时确认：

- README 中的封面路径可以解析；
- 压缩封面尺寸和文字清晰度符合发布要求；
- `assets/` 中没有封面源图或压缩中间产物；
- 根 README 已登记新 Skill；
- Git diff 只包含当前任务需要的文件。
