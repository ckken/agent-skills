# Agent Skills

一组可复用的 AI Agent Skills，帮助团队把项目级 Agent 工作流做得更清晰、更稳定、可验证。

![Kenvo AI Agent Skills 合集](./assets/agent-skills-cover.webp)

## Skills

| Skill | 说明 |
| --- | --- |
| [optimize-prompt-stack](./skills/optimize-prompt-stack/) | 面向 GPT-5.6 审计、迁移并渐进优化项目提示词栈，提供有证据的前后对比。 |
| [agent-image-optimizer](./skills/agent-image-optimizer/) | 自动下载并使用 `agent-image-opt`，安全完成图片检查、预览、有损/无损优化与 JSON 回执。 |
| [ip-visual-identity](./skills/ip-visual-identity/) | 从用户提供的 IP 参考图建立可复用的角色身份锚点，减少系列视觉中的角色漂移。 |
| [ip-cover-designer](./skills/ip-cover-designer/) | 基于指定 IP 制作 README、文章、网页 Hero 和社交媒体封面。 |
| [ip-promo-poster](./skills/ip-promo-poster/) | 基于指定 IP 制作功能发布图、宣传海报和多尺寸传播物料。 |

## Tools

| Tool | 说明 |
| --- | --- |
| [agent-image-opt](./tools/agent-image-opt/) | Rust CLI：推送源码变更后自动构建多平台二进制，并提供给 `agent-image-optimizer` 下载使用。 |

开发者首次克隆后运行 `make setup-hooks`，提交 `agent-image-opt` 相关修改时会自动执行本地 release build；推送到 `main` 后会创建带源码提交 SHA 的 [最新 Release](https://github.com/ckken/agent-skills/releases/latest)。

## 使用方式

将需要的 Skill 目录放入你的 Agent Skills 路径后，在任务中引用其名称即可。每个 Skill 的触发范围、执行流程和验证要求见其目录内的 README 与 `SKILL.md`。

## License

本仓库暂未声明许可证；复用前请联系仓库维护者确认。
