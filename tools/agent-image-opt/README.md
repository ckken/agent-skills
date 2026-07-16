# agent-image-opt

面向 ImageGen、截图、海报和 README 资源的 Rust 图片优化 CLI。支持无损 PNG 优化与有损 WebP 输出；默认不覆盖原图，并可生成 JSON 回执。

## 构建

```bash
cargo build --release
```

二进制位于 `target/release/agent-image-opt`。

## 有损压缩

适合海报、信息图、截图和照片，输出 WebP。默认 `poster` 预设为质量 88，重点保留含中文标题的 Agent 海报清晰度。

```bash
agent-image-opt promo.png --preset poster
agent-image-opt assets/ --recursive --preset ui --quality 92 --report image-opt-report.json
agent-image-opt poster.png --max-width 1440 --dry-run
```

预设：`poster`（88）、`ui`（92）、`illustration`（86）、`photo`（82）。

## 无损压缩

PNG 输入默认使用 `oxipng` 优化，像素不变；其他格式可使用无损 WebP 重编码。

```bash
agent-image-opt diagram.png --mode lossless
agent-image-opt image.jpg --mode lossless --format webp
```

## 写入策略

- 默认在源文件旁生成 `*.optimized.webp` 或 `*.optimized.png`。
- 仅当文件至少缩小 8% 时才写出，可通过 `--min-savings` 修改。
- `--dry-run` 只计算结果，不写文件。
- `--in-place` 显式允许替换源文件；`--force` 允许覆盖既有优化文件。
