# Agent Image Optimizer

供 AI Agent 使用的离线图片压缩 Skill。操作规则位于 [`SKILL.md`](./SKILL.md)，底层 Rust CLI 源码位于 [`tools/agent-image-opt`](../../tools/agent-image-opt/)。

## 安装 CLI

macOS / Linux：

```bash
curl -fsSL https://raw.githubusercontent.com/ckken/agent-skills/main/skills/agent-image-optimizer/scripts/install.sh | sh
```

Windows PowerShell：

```powershell
irm https://raw.githubusercontent.com/ckken/agent-skills/main/skills/agent-image-optimizer/scripts/install.ps1 | iex
```

安装器会根据系统下载 [最新的 `agent-image-opt` Release](https://github.com/ckken/agent-skills/releases/latest) 中对应的二进制，并在写入前校验 `SHA256SUMS`。

默认安装目录：

- macOS / Linux：`~/.local/bin`
- Windows：`~/.local/bin`

可通过 `AGENT_IMAGE_OPT_INSTALL_DIR` 修改安装目录。重新运行安装器即可更新到最新构建。

## 从源码安装

仓库贡献者可以运行：

```bash
make -C tools/agent-image-opt install-local
```
