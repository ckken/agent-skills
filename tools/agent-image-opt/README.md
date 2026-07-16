# agent-image-opt

面向 ImageGen、截图、海报和 README 资源的 Rust 图片优化 CLI。支持无损 PNG 优化与有损 WebP 输出；默认不覆盖原图，并可生成 JSON 回执。该工具完全离线运行，不需要账号、网络或鉴权。

## 构建

```bash
make build
make install-local
```

`make install-local` 将二进制安装到 `~/.local/bin/agent-image-opt`。确保该目录已加入 `PATH` 后，可从任意仓库调用。

## 命令

```bash
# 离线运行状态；JSON 不需要鉴权
agent-image-opt --json doctor

# 读取图片尺寸、格式、透明通道与推荐预设
agent-image-opt --json inspect assets/ --recursive

# 显式执行优化；默认生成新文件
agent-image-opt --json optimize promo.png --preset poster

# 低层转换入口：按指定编码与质量处理单张图
agent-image-opt --json transcode promo.png --format webp --quality 88
```

## 有损压缩

适合海报、信息图、截图和照片，输出 WebP。默认 `poster` 预设为质量 88，重点保留含中文标题的 Agent 海报清晰度。

```bash
agent-image-opt optimize promo.png --preset poster
agent-image-opt optimize assets/ --recursive --preset ui --quality 92 --report image-opt-report.json
agent-image-opt optimize poster.png --max-width 1440 --dry-run
```

预设：`poster`（88）、`ui`（92）、`illustration`（86）、`photo`（82）。

## 无损压缩

PNG 输入默认使用 `oxipng` 优化，像素不变；其他格式可使用无损 WebP 重编码。

```bash
agent-image-opt optimize diagram.png --mode lossless
agent-image-opt optimize image.jpg --mode lossless --format webp
```

## 写入策略

- 默认在源文件旁生成 `*.optimized.webp` 或 `*.optimized.png`。
- 仅当文件至少缩小 8% 时才写出，可通过 `--min-savings` 修改。
- `--dry-run` 只计算结果，不写文件。
- `--in-place` 显式允许替换源文件；`--force` 允许覆盖既有优化文件。

## JSON 策略

传入全局 `--json` 时，标准输出只包含一个 JSON 对象；成功对象包含 `ok: true`、`operation` 和对应结果。失败对象包含 `ok: false` 与不含敏感信息的 `error.code`、`error.message`，并以非零状态码退出。

`optimize` / `transcode` 的结果项包含源文件、目标文件、源/目标字节数、节省比例、尺寸和源文件 SHA-256。进度文本只在未使用 `--json` 时输出。

## 提交前构建

仓库提供 `.githooks/pre-commit`：当暂存内容涉及 `tools/agent-image-opt/` 时自动运行 `make build`。克隆仓库后执行一次：

```bash
make setup-hooks
```
