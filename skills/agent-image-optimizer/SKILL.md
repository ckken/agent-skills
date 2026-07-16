---
name: agent-image-optimizer
description: 使用 agent-image-opt 对 ImageGen、截图、海报和 README 图片做安全的无损或有损压缩；先检查图片，再生成可审计的新文件或 JSON 回执。用于减少 Agent 图片产物体积、发布到 GitHub/SkillHub/Wiki 前优化资源，或批量处理图片目录。
---

# Agent 图片优化器

按“安装 → 检查 → 预览 → 写入 → 验证”的顺序使用 `agent-image-opt` CLI。压缩过程完全离线运行，不需要账号或鉴权；首次安装或更新时从本仓库的 GitHub Release 下载经过 SHA-256 校验的二进制。

## 开始前

先确认命令已经安装并且编码器可用：

```bash
command -v agent-image-opt
agent-image-opt --json doctor
```

如果命令不存在，运行 Skill 内置安装器：

```bash
<this-skill-dir>/scripts/install.sh
```

Windows PowerShell 使用：

```powershell
<this-skill-dir>\scripts\install.ps1
```

如果只有 GitHub 仓库访问权限，可使用 [README.md](README.md) 中的远程安装命令。重新运行安装器即可更新到最新 Release。仓库贡献者仍可通过 `make -C tools/agent-image-opt install-local` 从源码安装。

## 安全检查路径

先读取图片元数据与推荐预设，不写文件：

```bash
agent-image-opt --json inspect <image-or-directory> --recursive
```

再用 `--dry-run` 评估目标体积、尺寸和压缩比例。JSON 标准输出可直接交给后续 Agent 分析。

```bash
agent-image-opt --json optimize <image> --preset poster --dry-run
```

## 写入路径

默认在原图旁边创建 `*.optimized.webp` 或 `*.optimized.png`，不会覆盖原图。

- 海报、长图、ImageGen 成图：`--preset poster`，默认质量 88。
- 截图、信息图与小字 UI：`--preset ui`，默认质量 92。
- 带透明通道的插画：`--preset illustration`。
- 照片：`--preset photo`。
- 必须像素不变的 PNG：`--mode lossless`。

```bash
agent-image-opt --json optimize poster.png --preset poster --report image-opt-report.json
agent-image-opt --json optimize diagram.png --mode lossless
agent-image-opt --json optimize assets/ --recursive --preset ui --report image-opt-report.json
```

## 低层转换入口

仅当预设不够用时使用 `transcode`，明确指定格式与质量：

```bash
agent-image-opt --json transcode source.png --format webp --quality 90 --dry-run
```

不要把 `transcode` 当作默认路径；优先使用 `inspect` 与 `optimize` 的预设和最小节省阈值。

## 规则

- 默认保留源图；只有用户明确要求时才使用 `--in-place`。
- 默认低于 8% 节省时不写出；不要为微小收益反复重编码。
- 含中文或细小文字的海报优先 `poster` / `ui`，先 `--dry-run` 再视觉检查。
- 只在用户明确要求时使用 `--force` 覆盖已有优化产物。
- `--json` 下仅解析 JSON；失败会返回机器可读错误且退出非零。
