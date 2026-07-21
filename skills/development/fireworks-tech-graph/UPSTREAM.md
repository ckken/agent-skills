# 上游同步记录

- 项目：[yizhiyanhua-ai/fireworks-tech-graph](https://github.com/yizhiyanhua-ai/fireworks-tech-graph)
- 上游版本：`1.2.0`
- 上游提交：`50c819d68fd4fee330b3010988cd13e98b678d44`
- 内化日期：`2026-07-21`
- License：MIT

## 本仓库调整

- 将 `SKILL.md` 重写为中文执行入口，保留 Codex / Claude Code 双运行时兼容和上游测试要求。
- 将 `README.md` 调整为中文产品入口，保留完整中文手册 `README.zh.md`。
- 使用 ImageGen 生成本仓库专属宣传封面，并通过 `agent-image-opt` 压缩为 `assets/cover.optimized.webp`。
- 将 Codex 展示元数据改为中文。
- 其余 CLI、schema、模板、references、fixtures、测试和动态样例保持上游 `1.2.0` 发行包内容。

## 后续更新

更新前先比较上游 `package.json`、`CHANGELOG.md` 和本文件记录的提交；同步后重新运行：

```bash
python3 -B -m unittest discover -s tests -v
python3 scripts/fireworks.py doctor
```

不得覆盖本仓库的中文入口、Codex 元数据和封面；若上游测试合同变化，应同步更新中文文档中的对应兼容标识。
