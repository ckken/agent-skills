# Apple Design

将 Apple 的界面设计与流体物理动效方法论翻译到 Web 平台（CSS、Pointer Events、`requestAnimationFrame`、Motion / Framer Motion 等弹簧库）。适用于构建或评审手势驱动 UI、弹簧动画、拖拽 / 滑动 / Sheet 交互、动量与可中断过渡、半透明材质与层次、排版（光学字号、字距、行距）、减弱动效，以及 Apple 风格界面背后的设计基础（反馈、空间一致性、克制）。

核心主线：**当动效从屏幕当前值起步、继承用户速度、向前投射动量，并且能在任意时刻被抓取并反向时，界面才真正“活”起来。** 弹簧是实现这一切自然的工具，因为它天然可中断且感知速度。

## 涵盖要点

- **Response（响应）**：按下即反馈，消除每一点延迟，反馈在交互全程连续而非只在结束。
- **Direct manipulation（直接操作）**：1:1 跟随指针，保留抓取偏移，不做中心吸附。
- **Interruptibility（可中断性）**：动效从当前值与当前速度重启，绝不跳变。
- **Springs over animation（弹簧优于动画）**：用弹簧描述行为，时长与曲线随物理参数推导。
- **Velocity handoff（速度传递）**：拖拽释放时把手势速度喂给弹簧。
- **Momentum projection（动量投射）**：动效朝手势预测方向前进。
- **Spatial consistency（空间一致性）**：对称路径、锚定原点。
- **Gesture hints / Rubber-banding（手势提示 / 橡皮筋）**：朝手势方向暗示，软边界提示极限。
- **Frame-level smoothness（帧级平滑）**：60/120fps，避免主线程抖动。
- **Materials & depth（材质与深度）**：半透明传递层次。
- **Multimodal feedback（多模态反馈）**：动效 + 声音 + 触感协同。
- **Reduced motion & accessibility（减弱动效与无障碍）**：尊重系统偏好与可访问性。
- **Typography（排版）**：光学字号、字距、行距。
- **Design foundations（设计基础）**：八大原则与流程。

## 典型调用

```text
使用 $apple-design 审查这个抽屉 / Sheet 交互的动效与手势，检查可中断性、速度传递与边界行为。
```

```text
使用 $apple-design 实现一个支持拖拽、橡皮筋边界和动量释放的卡片堆叠组件。
```

```text
使用 $apple-design 评审这套界面的材质层次、排版与减弱动效策略。
```

## 来源

源自 Apple WWDC 设计演讲（核心为 *Designing Fluid Interfaces*，WWDC 2018），提炼并翻译到 Web 平台。

## 目录内容

- [`SKILL.md`](./SKILL.md)：触发范围、响应 / 直接操作 / 可中断性 / 弹簧 / 速度传递 / 动量投射 / 空间一致性 / 手势细节 / 帧率 / 材质 / 多模态反馈 / 无障碍 / 排版 / 设计基础 / 流程，以及 Quick Reference。
