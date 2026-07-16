# Agent Skills

一组可复用的 AI Agent Skills，帮助团队把项目级 Agent 工作流做得更清晰、更稳定、可验证。

![GPT-5.6 提示词栈优化器](./skills/optimize-prompt-stack/assets/promo-v2.webp)

## Skills

| Skill | 说明 |
| --- | --- |
| [optimize-prompt-stack](./skills/optimize-prompt-stack/) | 面向 GPT-5.6 审计、迁移并渐进优化项目提示词栈，提供有证据的前后对比。 |

## Tools

| Tool | 说明 |
| --- | --- |
| [agent-image-opt](./tools/agent-image-opt/) | Rust CLI：对 Agent 图片产物做无损 PNG 优化或有损 WebP 压缩，并生成压缩回执。 |

## 使用方式

将需要的 Skill 目录放入你的 Agent Skills 路径后，在任务中引用其名称即可。每个 Skill 的触发范围、执行流程和验证要求见其目录内的 README 与 `SKILL.md`。

## License

本仓库暂未声明许可证；复用前请联系仓库维护者确认。
