---
name: fireworks-tech-graph
description: 将自然语言转换为经过几何门禁的技术图，覆盖软件架构、数据流、流程图、时序图、C4 评审、云部署、事件流、可观测性排查、Agent/记忆系统、UML、ER、网络拓扑、时间线和技术概念图；可交付 SVG、PNG、聚焦的语义 GIF 动效与离线交互 HTML。用户提出“画图”“可视化”“生成 GIF”“让这张图动起来”等请求时使用；不用于照片、普通插画或定量数据统计图。
---

# Fireworks Tech Graph

把系统描述转换为可验证、可编辑、可发布的技术图。首轮结果始终视为候选，必须经过结构校验、实际渲染、视觉回读和有界修正后才能交付。

上游项目：[yizhiyanhua-ai/fireworks-tech-graph](https://github.com/yizhiyanhua-ai/fireworks-tech-graph)，当前内化包版本见 `package.json`。

## 运行时定位

先把本 `SKILL.md` 所在目录解析为 `SKILL_ROOT`。不得假设当前工作目录就是 Skill 目录，也不得假设一次 shell 调用中的变量会保留到下一次。

```bash
SKILL_ROOT="${CLAUDE_SKILL_DIR:-/absolute/path/from-codex-skill-metadata}"
python3 "$SKILL_ROOT/scripts/fireworks.py" doctor
```

- Claude Code 使用 `${CLAUDE_SKILL_DIR}`。
- Codex 使用已加载 Skill 元数据给出的绝对目录，替换占位路径。
- 读取参考文件、模板、fixture 或脚本前都从 `SKILL_ROOT` 解析。

## 强制执行闭环

严格按以下顺序推进，不跳过门禁：

```text
Prompt
  → Diagram Contract
  → Semantic IR
  → Style Spec
  → Route Planner
  → SVG Build
  → Structural Validation
  → PNG Visual Readback
  → Targeted Revision
  → Verified SVG + PNG / GIF / HTML
```

1. **分类**：判断图类型、受众、阅读方向和输出格式。
2. **抽取结构**：列出层级、容器、节点、边、数据、控制流、异常路径和边界。
3. **建立契约**：明确必含事实、可省略信息、语义形状和箭头含义。
4. **加载构图规则**：读取 `references/composition-quality-contract.md`。
5. **选择风格**：默认 Style 1；指定风格时读取对应 `references/style-N-*.md`。
6. **选择语义契约**：Style 9–12 分别使用 C4、Cloud Fabric、Event Transit、Ops Pulse 语义门禁。
7. **映射图元**：按形状词汇表和 `references/icons.md` 选择节点、容器与产品图标。
8. **规划线路**：先确定 corridor、端口、waypoint 和标签区域，再生成 SVG。
9. **结构校验**：运行统一 CLI 或 `validate-svg.sh`，检查 XML、marker、路径、箭头穿框和几何预算。
10. **导出 PNG**：默认 1920px 宽，优先使用 cairosvg；其他渲染器读取 `references/png-export.md`。
11. **视觉回读**：实际查看 PNG，检查裁切、重叠、文字、层级、留白、走线和图例。
12. **定向修正**：每轮只修复已诊断的坐标、间距、标签或 corridor，默认最多两轮。
13. **按需扩展**：用户明确要求时生成 GIF 或离线交互 HTML。
14. **交付证据**：返回产物路径、图类型、风格、校验命令和视觉复核状态。

不得只凭主观判断声称完成。最终至少报告：

```text
validation: passed
visual_review: passed
```

若运行环境无法读图，必须如实报告 `visual_review: skipped (image reader unavailable)`。

## 统一 CLI

```bash
SKILL_ROOT="${CLAUDE_SKILL_DIR:-/absolute/path/from-codex-skill-metadata}"

python3 "$SKILL_ROOT/scripts/fireworks.py" doctor
python3 "$SKILL_ROOT/scripts/fireworks.py" validate architecture input.json
python3 "$SKILL_ROOT/scripts/fireworks.py" render architecture input.json diagram.svg --report layout.json
python3 "$SKILL_ROOT/scripts/fireworks.py" check diagram.svg
python3 "$SKILL_ROOT/scripts/fireworks.py" inspect diagram.svg
python3 "$SKILL_ROOT/scripts/fireworks.py" export-html diagram.svg diagram.html --title "System Architecture"
python3 "$SKILL_ROOT/scripts/fireworks.py" animate diagram.svg diagram.gif
python3 "$SKILL_ROOT/scripts/fireworks.py" examples
```

辅助入口：

```bash
SKILL_ROOT="${CLAUDE_SKILL_DIR:-/absolute/path/from-codex-skill-metadata}"

python3 "$SKILL_ROOT/scripts/generate-from-template.py" architecture diagram.svg input.json
"$SKILL_ROOT/scripts/validate-svg.sh" diagram.svg
"$SKILL_ROOT/scripts/generate-diagram.sh" -t architecture -s 1 -o diagram.svg
"$SKILL_ROOT/scripts/test-all-styles.sh"
```

## 图类型路由

### 系统与工程图

- **软件架构图**：按客户端、网关、服务、数据、基础设施分层；容器边界和协议标签必须明确。
- **数据流图**：突出数据类型、转换、存储与读写方向；控制流不能冒充数据流。
- **流程图 / 活动图**：使用开始、过程、决策、I/O、结束节点；分支必须标注条件并能汇合。
- **时序图**：参与者沿横轴，时间向下；同步、异步、返回、alt/opt/loop 语义保持一致。
- **网络拓扑**：按 Internet、Edge、Core、Access、Endpoint 分层，标明区域、子网、协议或带宽。
- **时间线 / 路线图**：阶段沿时间轴排列，里程碑和依赖关系不可混淆。
- **概念图 / 脑图 / 对比图**：围绕核心概念组织语义分组，避免伪造流程关系。

### UML 与数据模型

完整支持 14 类 UML 映射：类图、组件图、部署图、包图、复合结构图、对象图、用例图、活动图、状态机图、序列图、通信图、时序图、交互概览图和 ER 图。具体结构、尺寸和符号读取 `README.zh.md` 与模板目录。

- 类图保留类名、属性、方法、可见性、继承、实现、聚合、组合和多重性。
- 用例图把 Actor 放在系统边界外，用例放在边界内，并区分 include、extend 与泛化。
- 状态机图使用初态、终态、选择、fork/join、guard 和 entry/exit/do 语义。
- ER 图标明主键、外键、实体、关系和基数；识别关系与非识别关系采用不同线型。

### AI / Agent 内建模式

支持 RAG、Agentic Search、Mem0、Multi-Agent、Tool Call、短期/长期记忆、向量库、图数据库、规划器、评审器、工具层和反馈循环。抽取时必须区分：

- 输入与上下文；
- Agent / 编排器 / LLM；
- 工具调用与外部服务；
- 记忆读写和检索；
- 异步事件与重试；
- 回答、产物和可观测性出口。

## 12 种视觉风格

| Style | 名称 | 适用场景 |
| ---: | --- | --- |
| 1 | 扁平图标风（默认） | 通用架构、教学和文档 |
| 2 | 暗黑极客风 | Tool Call、终端和开发者工作流 |
| 3 | 工程蓝图风 | 微服务、基础设施和技术评审 |
| 4 | Notion 极简风 | 记忆分类、知识层级和轻量说明 |
| 5 | 玻璃态卡片风 | Multi-Agent 协作和任务编排 |
| 6 | Claude 官方风格 | 温暖、克制的系统架构 |
| 7 | OpenAI 官方风格 | API、模型、工具与交付链路 |
| 8 | 暗黑奢华风 | 需要 AI 手绘的高质感技术图 |
| 9 | C4 评审画布 | 单一 C4 层级、职责和协议评审 |
| 10 | Cloud Fabric | Region/VPC、双活和跨区复制 |
| 11 | Event Transit | Topic、Consumer Group、DLQ 和状态投影 |
| 12 | Ops Pulse | Golden Signals、Trace 和可靠性排查 |

Styles 1–12 are enabled。Style 8 由 Agent 读取 `references/style-8-dark-luxury.md` 手工绘制；Style 9–12 还必须通过对应工程语义契约。

选定风格后必须加载准确的 token、字体、材质、图元和 SVG 模式，不得只换背景颜色。

## 工程语义契约

- **Style 9 / C4 Review**：只展示一个 C4 抽象层级；组件包含职责、技术栈、评审状态；关系标签使用“动作 + 协议”。
- **Style 10 / Cloud Fabric**：展示全局入口、Region/VPC 归属、部署模式和具名跨边界机制；禁止无归属云图标。
- **Style 11 / Event Transit**：使用 Topic 轨道、编号处理站、显式 Junction、Consumer Group、DLQ 和状态投影。
- **Style 12 / Ops Pulse**：固定观察窗口；每个服务呈现四个 Golden Signals、编号关键跳、遥测导出与关联 Trace。

在渲染前使用 `fireworks.py validate`；缺少事实、重复 ID、悬空引用、非法 waypoint、非有限坐标或语义矛盾必须 fail closed。

## 构图与几何门禁

默认采用以下发布基线，具体预算以 `references/composition-quality-contract.md` 为准：

- 主路径零交叉、零无意义跨线桥；
- 单条线路最多 2 个折点，全图最多 8 个折点；
- 节点间距至少 40px，容器内边距至少 20px；
- 线路使用明确端口并保持短直正交段；
- 标签不得覆盖节点、线路、分区标题或画布边界；
- 图例自动避让；使用 2 种及以上箭头语义时必须出现图例；
- 文字必须位于安全区，禁止裁切、压缩、遮挡和超小字号；
- 首屏先读出系统主题，再读分组，最后读局部细节。

## 形状词汇表

| 概念 | 形状 |
| --- | --- |
| 用户 | 头像或标准 Actor |
| LLM / Model | 带脑/火花图标的圆角矩形，可用双边框 |
| Agent / Orchestrator | 六边形或双边框圆角矩形 |
| 短期记忆 | 虚线圆角矩形 |
| 长期记忆 | 实线数据库圆柱 |
| Vector Store | 带内环或网格线的圆柱 |
| Graph DB | 相连圆点簇 |
| Tool / Function | 工具图标矩形 |
| API / Gateway | 单边框六边形 |
| Queue / Stream | 水平管道或轨道 |
| File / Document | 折角文档矩形 |
| Browser / UI | 带标题栏的窗口矩形 |
| Decision | 菱形，仅用于流程语义 |
| External Service | 云图标或虚线边界矩形 |
| Data / Artifact | 平行四边形 |

## 箭头语义

| 流类型 | 默认颜色与线型 | 含义 |
| --- | --- | --- |
| 主数据流 | 蓝色实线 | 请求、响应或核心数据路径 |
| 控制 / 触发 | 橙色实线 | 一个组件触发另一个组件 |
| 记忆读取 | 绿色实线 | 从存储检索 |
| 记忆写入 | 绿色虚线 | 写入或持久化 |
| 异步 / 事件 | 灰色虚线 | 非阻塞事件流 |
| Embedding / Transform | 紫色细实线 | 数据转换 |
| Feedback / Loop | 紫色曲线 | 迭代推理或反馈循环 |

风格文件可覆盖颜色和线宽，但不得改变语义。

## SVG 生成策略

- 简单标准图优先使用 `templates/` 和 `generate-from-template.py`，降低 XML 与坐标错误。
- 复杂图使用版本化 Diagram IR，通过 `fireworks.py validate` 归一化后再渲染。
- Style 8 按参考规范手工绘制，但仍必须经过同样的结构和视觉门禁。
- SVG 必须纯内联，不依赖远端字体、图片或脚本；文本内容需要 XML 转义。
- 路径 marker 引用必须完整，箭头终点不能穿入节点内部。
- 生成产物不得携带密钥、内部 URL、用户隐私或未经允许的品牌素材。

## 输出格式

### SVG + PNG

默认同时交付可编辑 SVG 与 1920px PNG。必须先校验 SVG，再导出并回读 PNG；不能只验证 XML。

### 离线交互 HTML

`export-html` 生成经过清洗的单文件 HTML，支持平移、缩放、复位、明暗主题、复制 SVG，以及 1×–4× SVG/PNG/JPEG/WebP 下载。不得嵌入远端脚本或未清洗输入。

### 聚焦语义 GIF

以下表达均视为动效请求：

- “让这张图动起来”
- “生成 GIF”
- “制作 GIF”
- “Animate this diagram”
- “Generate a GIF”

只接受本生成器产出的语义 SVG，只输出 GIF。Styles 1–12 are enabled；默认 960px、5.75 秒、20fps、115 帧，并写出 `<output>.motion.json`。正式时间线使用 `+2s-settled-flow`：先构建线路，再保持完整数据流，最后执行 reset。动效角色、阶段、顺序、方向、必要颜色或几何不符合契约时必须 fail closed。详细规则读取 `references/motion-effects.md`。

## 依赖与降级

- 基础 SVG 校验只需 Python 3。
- PNG 推荐 `cairosvg`；备选 `rsvg-convert`，兼容性差异见 `references/png-export.md`。
- GIF 需要 FFmpeg/FFprobe、Chrome/Chromium 和 Skill 根目录中的 `puppeteer-core@25.3.0`。
- 缐少可选依赖时只降级对应输出，不得伪造成功；报告可安装命令和已完成产物。
- 用户未要求 GIF 或 HTML 时，不自动增加重型依赖和额外交付物。

## 边界

- 不用于照片、人物插画、普通营销图片或像素艺术。
- 不把定量数据图表伪装为技术架构图；统计图应使用专门图表工具。
- 不为补齐画面臆造系统组件、协议、指标或业务事实。
- 不绕过结构验证、语义契约或视觉回读门禁。
- 不修改上游脚本来掩盖输入错误；优先修正 Diagram IR 或用户事实。
- 用户只要 Mermaid 或代码原生图时，使用对应确定性工具，而不是强制生成 SVG 视觉稿。

## 完成标准

只有同时满足以下条件才结束：

- 图类型、风格、受众和阅读方向与需求一致；
- 必需事实完整，假设已明确，未编造关键系统信息；
- SVG 结构、marker、路径、语义契约和几何预算通过；
- PNG 已真实导出并回读，裁切、重叠、文字、走线和图例通过；
- 用户要求的 GIF 或 HTML 已生成并通过对应验证；
- 产物路径、尺寸、格式、校验证据和限制已回传；
- 中间源图、临时渲染和失败产物已清理，不污染用户仓库。
