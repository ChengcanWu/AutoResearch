# DESIGN_SPEC · 启研设计规范 v1.0

> 从旧 Demo「学科瞭望」视觉体系提炼，是本项目**唯一的 UI 视觉权威**。
> 所有新页面/组件必须遵循本规范；规范未覆盖的，参照现有页面类推并回填本文档。
> 实装参照：[web/css/styles.css](../web/css/styles.css)（`:root` 变量区为唯一色值/字体来源）。

---

## 1. 设计立场

面向大一大二的学术工具，气质 = **安静、可信、有书卷气**：

- 低饱和底色 + 一个主色（青绿 teal），信息密度友好；
- 克制的圆角与阴影，不用毛玻璃、不用重渐变、不做暗色模式（V1）；
- 事实与证据永远高亮可辨（引用、来源、置信度是产品核心，必须醒目但不刺眼）。

## 2. 色彩（token 与代码一一对应）

| Token | 值 | 用途 |
| --- | --- | --- |
| `--bg` | `#f3f8f5` | 页面底色（浅青灰绿） |
| `--bg-accent` | `#e8f4ee` | 悬停底 / 分区块底 |
| `--card` | `#ffffff` | 卡片/面板 |
| `--ink` | `#1a2e28` | 主文字（墨绿黑） |
| `--muted` | `#5a6f67` | 次要文字 |
| `--line` | `#d5e6dc` | 描边/分隔线 |
| `--teal` | `#0f766e` | **主色**：按钮、链接、激活态、徽标 |
| `--teal-soft` | `#d8f3ec` | 主色浅底（选中、AI 气泡、徽章底） |
| `--coral` | `#c45c3e` | 强调色：行为证据、删除、警示（少量使用） |
| `--coral-soft` | `#fff8f4` | 强调浅底（新事实卡高亮） |
| `--gold` | `#b9852b` | 辅助：能力类徽章、待确认态 |
| 背景晕染 | `radial-gradient(#dff5ea / #e7f0ff)` | body 顶部两团极浅晕染（沿用旧 Demo） |

**配色纪律**：一个界面主色面积 ≤ 20%；coral 只给「证据/警示」类语义；禁止新增主色系以外的色相（类别徽章已定义 5 类映射，见 §5）。

## 3. 字体

| 层级 | 字体 | 用法 |
| --- | --- | --- |
| 标题/数字大屏 | `"Source Serif 4", "Noto Serif SC", serif`（`--serif`） | 品牌名、页面大标题、卡片标题、分数 |
| 正文/UI | `"Noto Sans SC", "Microsoft YaHei", sans-serif`（`--font`） | 一切正文、按钮、表单 |

- Google Fonts 引入，`display=swap`；断网时回退系统字体，不阻塞；
- 字号阶梯：13（辅助）/ 14–15（正文）/ 1.25–1.4rem（卡片标题，serif）/ clamp(1.8–2.4rem)（页面主标题，serif）；
- 中文与数字之间不手工加空格；数字用 `font-variant-numeric: tabular-nums`（代码/置信度）。

## 4. 形状 / 阴影 / 动效

| Token | 值 | 用途 |
| --- | --- | --- |
| `--radius` | `18px` | 面板/大卡圆角；小元素 12–14px；胶囊 999px |
| `--shadow` | `0 10px 30px rgba(26,46,40,0.06)` | 唯一通用投影（极轻） |

- **胶囊（pill）**是本设计的签名形状：筛选 chip、选项卡、徽章、按钮态；
- 动效只用两个：`courseIn`（重要卡片入场脉冲，box-shadow 扩散）、`factIn`（新事实卡珊瑚色脉冲）；时长 ≤ 0.6s，`ease`；
- 过渡统一 `0.15s ease`（hover/active）。

## 5. 组件清单（已实装，新页面直接复用）

| 组件 | 类名 | 说明 |
| --- | --- | --- |
| 页头 | `.site-header` + `.eyebrow` + `.brand h1`（serif）+ `.tagline` | 左品牌右用户胶囊 |
| 导航胶囊 | `.main-nav .nav-btn` | active 态 teal 填充 |
| 面板 | `.panel` + `.panel-title`（serif）+ `.panel-sub` | 一切内容容器 |
| 筛选/选项 chip | `.chip` | hover teal 描边，active teal 填充 |
| 按钮 | `.btn`（主）/ `.secondary`（描边）/ `.ghost`（弱化）/ `.small` | teal 底白字，圆角 12px |
| 对话气泡 | `.bubble.ai`（浅底）/ `.bubble.user`（teal-soft） | 对话页专用 |
| 事实卡 | `.fact-card` + `.badge.cat-*` + `.conf-bar` | 五类类别色（见下）；新事实加 `.new-fact`（coral 脉冲） |
| 方向推荐卡 | `.dir-card` + `.why-box`（左 teal 竖线）+ `.reading-box`（虚线框） | why_you 必须用 `.why-box` |
| 课程块 | `.course-block`（teal 渐变底+描边）+ `.course-pill` LIVE | 真实检索结果的专属容器 |
| 微任务步骤 | `.step`（checkbox 行卡） | 勾选后划线置灰 |
| rubric 反馈 | `.rubric-item.pass/.fail`（圆形 ✓/✗） | 通过 teal、未过 coral |
| NBA 卡 | `.nba-card`（teal 描边+渐变底+脉冲） | 全站最高视觉优先级 |
| 引用块 | `.why-box` | 左竖线 + 浅底，承载一切「为什么/证据」文本 |
| 流程指示 | `.flow-steps span.on` | 演示链路 ①–⑨ 进度 |

**事实类别色**（徽章唯一映射）：background 蓝 `#1d4ed8` · interest teal · capability 金 `#b9852b` · preference 紫 `#7c3aed` · experience coral。

## 6. 文案与内容规范

- 产品语气：像一位**熟悉又克制的学长**——陈述事实、给出理由、不煽情不卖课；
- 所有 AI 产出必须带理由，UI 上对应「为什么是你 / 证据」区块，禁止无来源断言；
- 检索失败必须如实展示失败（`.course-status` 文案模板：「检索失败（如实说明）：…」），**不许编造兜底数据**；
- 「不知道」选项永远合法且不加负面措辞；
- 数字/时间用半角；中文标点为主。

## 7. 布局

- 内容最大宽度 `1280px` 居中，左右 `40px` 内边距（<920px 收窄为 18px 单列）；
- 主工作区两栏 `.two-col`（1.6fr : 1fr）：左主内容、右辅栏（实时记录/治理原则）；移动端叠放；
- 列表卡片网格 `.dir-cards`：`repeat(auto-fit, minmax(300px, 1fr))`。

## 8. 变更流程

改本规范 = PR + 在 [CHANGELOG.md](CHANGELOG.md) 登记。新增颜色/组件必须先在 styles.css 里以 token 形式落地，再回填 §2/§5。
