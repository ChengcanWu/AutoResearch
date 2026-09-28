# TASK_ASSIGNMENTS · 任务分工与协作流程

> 6 人名单：邬程灿 · 刘弘雅 · 陈浩文 · 陈旭 · 别克扎提·拜别提 · 张效端
> W0 核心 Demo（①–⑨ 全链路）已由别克扎提完成并验证（见 [CHANGELOG](CHANGELOG.md)）。
> 本文写清每人 **vibecoding 怎么做** 和 **PR 怎么提**。先读 §0 通用流程，再读自己那节。

---

## 0. 通用流程（每个人都要照做）

### 0.1 vibecoding 标准动作

```text
1. git clone 仓库 → git checkout -b feat/<你的模块名>
2. 新开 AI 会话（Claude Code / Cursor 均可），第一条消息 = §1–§6 中你的「角色卡」
   （复制给 AI，它会按文档与契约开发）
3. 开发完跑「自测清单」→ 全绿才提 PR
4. 卡住 48h → 在群里 @ 对应 Owner，不许沉默等待
```

### 0.2 PR 规则

- 分支命名：`feat/<模块>-<内容>`（如 `feat/llm-planner`）、`fix-`、`docs-`；
- 一个 PR 只做一件事；**不许动别人模块目录的核心逻辑**（公共文件改动在 PR 描述里说明理由）；
- 提交信息：`[模块] 一句话`（如 `[agent] onboarding 抽取接入 DeepSeek`）；
- PR 描述必须含：做了什么 / 怎么自测的 / 截图（涉及 UI 时）；
- Review：PR 指派模块 Owner（见下表）；Owner 24h 内回复；
- 合并：squash merge 到 `main`；合并前 CI 必须绿（张效端负责 CI 起来之前，跑通本地自测即可）。

### 0.3 硬纪律（W1 不破）

- **接口契约冻结**：[ARCHITECTURE.md](ARCHITECTURE.md) §3/§5 的 schema 与端点签名不许单方面改；要改先在群里提议 → 改文档 + CHANGELOG 登记 → 各自同步；
- **mock 白名单**：只许 mock LLM 措辞，不许 mock 数据结构与闭环（课程检索、UM 写回永远真实）；
- **不编造事实**：检索失败要如实展示失败（参考 `loadCourses` 的失败文案）；
- 新页面必须遵循 [DESIGN_SPEC.md](DESIGN_SPEC.md)（颜色/字体/组件直接复用 `web/css/styles.css` 的 token 与类）。

### 0.4 Owner 对照（Review 责任区）

| 模块 | Owner |
| --- | --- |
| server/agents（LLM 接入） | 邬程灿 |
| server/workbench（任务/反馈） | 刘弘雅 |
| skills/ + knowledge/ | 陈浩文 |
| web/（前端全部） | 陈旭 |
| 产品 / UM / 文档体系 | 别克扎提·拜别提 |
| 部署 / CI / 监控 | 张效端 |

---

## 1. 邬程灿 — LLM 真实化（agent 层）

**目标**：把 W0 的三处 mock LLM 换成真实模型调用，接口与降级完全按文档。

**角色卡（复制给 AI）**：
> 你在 `ResearchGuide` 仓库工作，负责把 `server/` 的 mock LLM 真实化。先读 `docs/ARCHITECTURE.md` §2–§5 与 `server/onboarding.py`、`server/planner.py`、`server/workbench.py`，然后：① 新建 `server/llm.py`：OpenAI 兼容 Provider（base_url/key/model 读环境变量 `LLM_BASE_URL/LLM_API_KEY/LLM_MODEL`，超时 15–30s，重试 1 次，失败抛结构化异常）；② 新建 `server/prompts/`：每个 prompt 一个带版本号的 md 文件，调用时记录版本；③ `onboarding._extract`：改为把「本轮问题+用户回答+已有事实」发给 LLM，要求输出 JSON facts（schema 同 `schemas.UserFact`），解析失败 2 次降级回现有规则表；④ `planner`：规则层候选集生成后，LLM 从候选中择优并润色 rationale（必须保留对用户原话的引用），失败降级规则 Top1；⑤ 每次调用把 {model, prompt_ver, tokens, latency, ok} 写日志（print JSON 即可，接 metrics 是张效端的事）。禁止改变 REST 端点签名与 UserFact/NBA schema。

**自测清单**：
- [ ] 不配 API key 时全链路仍可跑通（降级到规则版，行为与 W0 一致）；
- [ ] 配 key 后：onboarding 自由文本能被归纳成 facts（而非原文入库）；rationale 仍引用用户原话；
- [ ] 伪造一次 LLM 超时（把 base_url 改成无效地址），确认 10–30s 内降级、页面不崩。

---

## 2. 刘弘雅 — 任务库扩充 + 反馈真实化（workbench）

**目标**：任务模板从 6 方向×2 级扩到每方向 ≥4 级；反馈从启发式升级为 LLM 判定（配合邬程灿的 Provider）。

**角色卡**：
> 你在 `ResearchGuide` 仓库工作，负责 `server/workbench.py`。先读 `docs/ARCHITECTURE.md` §3.3 与 `server/workbench.py`。任务：① 扩充 `TEMPLATES`：每个方向至少 4 个任务（level 1–4，难度递进，20 分钟内可完成，步骤 3–5 步、rubric 3–4 条且客观可判）；题目来源参考大学通识课作业/经典入门书每章习题，不许出现需要付费/内部资源的步骤；② 反馈判定改为：优先调 `server/llm.py`（若邬程灿已合入；未合入前保持启发式并留好接口），LLM 按 rubric 逐条判 pass + 写一句 comment；③ 写回 UM 的 behavior 事实保持真实（这是硬要求，不许 mock）；④ 给每个任务模板补一个 `sample_payload` 字段（高质量示例提交，供演示「填入示例」按钮用，前端读 `web/js/app.js` 的 demo 按钮处同步改造为读该字段）。

**自测清单**：
- [ ] 6 方向 × 4 级任务都能生成、提交、拿到逐条 rubric 反馈；
- [ ] 低质量提交（<50 字、无原因分析）至少 1 条 rubric 不通过；
- [ ] 每次提交后 `/api/me/facts` 确实新增一条 behavior 事实。

---

## 3. 陈浩文 — 科研智能层（skills + knowledge）

**目标**：把「懂科研世界」做厚：papers 入门读物策展包 + discipline.kb 服务化 + course adapter 进程内化。

**角色卡**：
> 你在 `ResearchGuide` 仓库工作，负责 `skills/` 与 `knowledge/`。先读 `docs/ARCHITECTURE.md` §3.4、§6 与 `server/pku_adapter.py`、`knowledge/disciplines.json`。任务：① 新建 `knowledge/papers/`：策展每方向 3–5 篇入门读物（书章/公开综述/讲义，字段 {direction, title, why, minutes, url, source, retrieved_at}），只收公开可得资源并记录来源；② 新建 `server/skills_registry.py`：统一 Skill 协议（invoke → {ok, data|error, source, retrieved_at}），把 `pku_adapter` 收编为 `course.search`，新增 `discipline.kb`（读 knowledge/disciplines.json 支持按名称/代码/门类查询）；③ 新端点 `GET /api/explore/disciplines?q=&category=` 挂到 main.py（符合现有代码风格，中文注释）；④ （进阶）把 course adapter 从 uv 子进程改为进程内 import `skills/pku-course/scripts/pku.py`，子进程保留为 fallback，测速对比写进 PR 描述。不许改 skills/pku-course 内部代码与契约。

**自测清单**：
- [ ] `discipline.kb` 能按「心理学 / 190 / C」三种方式查到同一学科；
- [ ] papers 包 6 个方向全覆盖且每条有 url + retrieved_at；
- [ ] 修改后 `/api/explore/courses?query=人工智能` 仍返回真实课程（回归）。

---

## 4. 陈旭 — 前端体验（web/）

**目标**：在 W0 六个视图之上补齐「聊天问答页（Mentor）+ 学科探索页（explore）」，并整体打磨演示体验。是否迁移 React 由你评估后在群里拍板（迁移与否都不改 REST 契约；不迁移则继续经典脚本模式，遵守加载顺序）。

**角色卡**：
> 你在 `ResearchGuide` 仓库工作，负责 `web/`。先读 `docs/DESIGN_SPEC.md`（视觉唯一权威）与 `web/js/app.js`、`server/main.py` 的 REST 契约。任务：① 新增「问导师」视图：自由提问聊天页（后端 `POST /api/chat` 由你顺手在 main.py 里加：MVP 版可先基于 facts 上下文 + 检索课程的规则回答，回答末尾必须附一条 NBA 卡——这是产品铁律「信息收口到行动」）；② 新增「学科探索」视图：复用 `knowledge/disciplines.json`（经陈浩文的 `/api/explore/disciplines`；未合入前可直接读 `/static` 外挂不了就先 fetch 本地 json 拷到 web/data/），做学科浏览 + 点入看「在研究什么/大一怎么入门」+ 站内搜课；③ 演示打磨：首屏加演示引导条（9 步链路当前到第几步）、对话页 AI 回复打字机效果、空态/错误态统一用现有 `.note-box` 样式；④ 全程只用 styles.css 已有 token 与组件类，新组件先加 token 再用。禁止引入构建链与 npm 依赖（除非提交 React 迁移决策）。

**自测清单**：
- [ ] 新视图在 <920px 窄屏不破版；
- [ ] 课程检索失败时如实展示失败文案（不编造）；
- [ ] 9 步演示链路（`flowSteps`）在新视图中状态正确推进。

---

## 5. 别克扎提·拜别提 — 产品 / UM / 集成（本 W0 已完成的部分 + W1 职责）

**W0 已交付**：①–⑨ 全链路 Demo（FastAPI + 静态前端 + 真实搜课 + 真实 UM 写回）、设计规范、文档精简、仓库与 GitHub 初始化。

**W1 职责**：
- UM 治理补全：me 页「一键导出 JSON」「清除全部认知（二次确认）」；冲突事实置顶展示（schema 已有 `superseded_by` 预留）；
- 验收：按 [NEXT_PRE_2026-09-28.md](NEXT_PRE_2026-09-28.md) §5 清单组织彩排（9/27），录屏备份；
- 种子用户招募与反馈收集（每条反馈开 Issue）；
- 文档/CHANGELOG 唯一登记人；合并冲突仲裁。

---

## 6. 张效端 — 部署 / CI / 监控

**目标**：让 9/28 演示不依赖开发机，且后续每次 PR 自动验证。

**角色卡**：
> 你在 `ResearchGuide` 仓库工作，负责基建。先读 `docs/ARCHITECTURE.md` §2/§6 与 `server/`、`skills/pku-course/.github/workflows/ci.yml`（可借鉴）。任务：① 写 `Dockerfile` + `docker-compose.yml`：api 容器（python 3.12-slim + uv 安装依赖 + 挂载 skills/ 与 knowledge/，环境变量见 §2 启动命令与 LLM_* 组）+ 前端静态产物由 api 同源托管（现状已是，挂 volume 即可）；② `docs/DEPLOY.md`：从零部署手册 + 回滚；③ `make smoke`（Makefile 或 smoke.py）：health + 一次真实课程检索 + 一次规则 NBA，全绿退出 0；④ GitHub Actions `ci.yml`：push/PR 触发 `python -m pytest server/tests/`（先补 `server/tests/test_smoke.py`：用 fastapi TestClient 跑通 login→onboard→confirm→nba→task→submit 全链路断言）；⑤ `/api/metrics`：内存累计 {requests, errors, p95_latency, llm_calls}，JSON 即可。数据库文件 `server/data/` 必须 gitignore。

**自测清单**：
- [ ] 本机 `docker compose up` 一条命令起全站；
- [ ] CI 在 PR 上跑绿（含 smoke）；
- [ ] 部署态（非开发机/局域网另一台设备）可访问并完成一次演示链路。

---

## 7. 时间表（对齐 9/28 Pre）

| 日期 | 节点 |
| --- | --- |
| 9/25 晚 | 认领 + 建分支；邬程灿/陈旭先动（关键路径） |
| 9/26 | 各模块 PR 首版；张效端 CI 起来 |
| 9/27 上午 | 全链联调（别克扎提主持）+ 合并冻结 |
| 9/27 下午 | 彩排 ×2（掐表 8–10 分钟）+ 录屏备份 |
| 9/28 | Pre（清单见 NEXT_PRE §2） |
