![Open Slide 可编辑 PPTX 导出](./assets/cover.optimized.webp)

# Open Slide 可编辑 PPTX 导出

将 Open Slide React 幻灯片导出为高还原、可编辑的 PowerPoint 文件，并完成演讲备注保留、OOXML 校验和 Microsoft PowerPoint 实机验收。

## 解决什么问题

- 当前项目运行时只有 HTML/PDF 导出，需要切换到可编辑 PPTX 分支。
- Web 预览正常，但 PowerPoint 中数字、圆形标识或文字位置发生偏移。
- 最新导出缺少演讲备注，需要从已核准版本安全迁移。
- 需要确认 PPTX 不是整页截图，文字、形状和图片仍可编辑。
- LibreOffice 缺少中文字体时，需要区分渲染环境问题与文件损坏。

## 典型调用

```text
使用 $open-slide-export-editable-pptx 将当前 Open Slide 项目导出为可编辑 PPTX，保留演讲备注，并用 PowerPoint 核对重点页面。
```

```text
使用 $open-slide-export-editable-pptx 检查这份 PPTX 的页数、备注、可编辑对象和 16:9 画布，并诊断导出后的排版偏移。
```

## 目录内容

- `SKILL.md`：完整导出决策、备注策略、PowerPoint 验收和完成门禁。
- `scripts/export_editable_pptx.mjs`：自动触发 Open Slide 的可编辑 PPTX 下载。
- `scripts/merge_pptx_notes.py`：将核准备注迁移到最新导出，同时保留最新页面。
- `scripts/validate_pptx.py`：检查 PPTX 包、页数、备注关系、画布和可编辑对象。
- `scripts/test_pptx_tools.py`：生成最小 OOXML 样例，回归测试备注迁移与异常关系检测。
- `assets/cover.optimized.webp`：发布封面。
