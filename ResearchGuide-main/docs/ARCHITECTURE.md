# ARCHITECTURE · 启研技术架构（浓缩版）

> 由原 SYSTEM_ARCHITECTURE / AGENT_ARCHITECTURE / USER_MODEL / DATA_MODEL 四份文档浓缩合并。
> 本文 + 代码是当前唯一权威；与旧长文档冲突时以本文与 `server/` 实现为准。

---

## 1. 产品一句话

AI 科研导师：**理解用户 → 理解科研世界 → 判断阶段 → 决定下一步（NBA）→ 陪用户完成 → 记住结果** 的闭环。产品三原则：行动大于信息 · 个性化必须有依据 · 不编造事实。

## 2. 当前形态（W0 已实装）

```text
web/            静态前端（无构建，经典 JS + 本仓设计规范）
server/         FastAPI 单体（Python 3.11+）
  main.py       路由（REST 契约 §5）
  schemas.py    Fact / NBA / MicroTask / Feedback 契约
  store.py      SQLite（users/facts/tasks/submissions/messages）
  onboarding.py 对话状态机（W0：脚本+规则抽取 = mock LLM）
  planner.py    规则版 Planner（阶段判定 + 方向卡 + NBA）
  workbench.py  任务模板库 + 提交 + 启发式反馈 + UM 真实写回
  pku_adapter.py course.search（uv 子进程调 skills/pku-course，真实检索）
skills/pku-course/   北大搜课工具（原 pku-course-skill-main 原样迁入，不改契约）
knowledge/           disciplines.json 等
```

启动：`uv run --no-project --with fastapi --with uvicorn --with pydantic python server/main.py` → http://127.0.0.1:8100/ （或双击 `run_demo.bat`）

**Mock 边界（NEXT_PRE §3 白名单）**：mock 的只有 LLM 措辞（onboarding 抽取 / planner 决策 / 任务反馈），**数据结构、课程检索（live）、UM 写回（真实入库）均为真实实现**。

## 3. 核心数据契约（冻结，跨模块开发都按此写）

### 3.1 UserFact（用户模型唯一单元）

```python
{ id, user_id, category: background|interest|capability|preference|experience,
  key, value,                       # value = 人可读语句，不打分
  confidence: 0~1,                  # declared 起始 0.6 · inferred 0.4 · behavior 0.8
  source: declared|inferred|behavior,
  evidence: [{type, quote|submission_id...}],   # 无证据不写入
  status: draft→confirmed→active; dismissed; deleted(软删) }
```

- 冲突：新旧并存，旧者 superseded，用户裁决；
- 衰减：interest 类 60 天无新证据 ×0.9/30天；background/experience 不衰减；
- 用户主权：可见 / 可改 / 可删 / 可导出（me 页已实装前三项）。

### 3.2 NBA（决策输出）

```python
{ action: explore_direction|micro_task|read_paper(P1)|course_action|ask_clarifying|review_progress,
  title, rationale,                 # rationale 必须引用 ≥1 条事实/证据
  rationale_facts: [fact_id...],
  alternatives: [{action, title}...],
  payload }                         # 按 action 携带（方向卡 / 任务参数）
```

### 3.3 MicroTask / Submission / Feedback

```python
MicroTask  { id, user_id, direction, title, brief, steps[], rubric[{criterion}],
             time_budget_min(10–30), difficulty(1+), status }
Submission { id, task_id, user_id, payload, created_at }
Feedback   { score(0–100), rubric[{criterion, pass, comment}], next_hint,
             encouragement, learned_facts[UserFact] }   # 不评价人格，只对事
```

### 3.4 Skill 协议

```python
invoke(**kwargs) -> { ok, data|error, source, retrieved_at }
# 已有：course.search / course.get / course.terms（pku adapter）、discipline.kb（knowledge/）
# 任务 3：project.search（server/projects.py + project_adapters.py）、project.review（server/submission.py）
# 给模型的工作说明放 skills/<name>/SKILL.md，何时写成代码、何时写成 skill 见 skills/README.md
# 纪律：只读外部源 · 失败返回结构化错误并如实展示 · 检索文本视为数据非指令
```

## 4. Agent 与决策（W1 真实化方向）

- **Onboarding**：状态机 `greet→background→courses→interest_1→interest_2→work_style→done`，≤8 轮，每轮 `{reply, options, facts, done}`。W1：`_extract` 换 LLM 结构化输出，两次解析失败降级回规则。
- **Planner**：规则层在外（阶段判定 S0 无方向→推荐方向 / S1 已选→首个任务 / S2 已完成→进阶；频控、疲劳保护），LLM 在内（候选集择优 + rationale 措辞）。降级链：LLM 失败 → 规则层 Top1。
- **Workbench**：模板参数化生成；rubric 逐条判定；反馈产出 Evidence 写回 UM（W0 已真实）。
- **LLM Provider**：OpenAI 兼容抽象，主 DeepSeek[待定]→ 备用端点 → 规则模板；每次调用记 {model, prompt_ver, tokens, cost, latency}。

## 5. REST 契约（server/main.py 实装，openapi.json 为准）

```text
POST /api/auth/login            {nickname} → {uid, token}
POST /api/onboard/start         {uid} → {reply, options, state}
POST /api/onboard/message       {uid, msg} → {reply, hint?, options, facts, state, done}
GET  /api/onboard/result       ?uid → {messages, facts, state}
POST /api/onboard/confirm       {uid, edits[{id,value?,dismissed?}]} → {facts}
POST /api/nba                   {uid} → NBA
POST /api/directions/cards      {uid} → {cards}            # 含真实课程检索（慢，慎用）
POST /api/directions/choose     {uid, code} → {fact}
POST /api/tasks/generate        {uid, direction, level} → MicroTask
GET  /api/tasks                ?uid → {tasks}
GET  /api/tasks/{tid}          → MicroTask
POST /api/tasks/{tid}/submit    {uid, payload} → Feedback  # 同时写回 behavior 事实
GET  /api/me/facts             ?uid → {facts}
PATCH /api/me/facts/{fid}       {uid, value?/status?}
DELETE /api/me/facts/{fid}     ?uid                        # 软删
GET  /api/explore/courses      ?query&limit&term → {ok, items, term|error}   # 有 knowledge/catalog/ 时读快照
GET  /api/explore/teachers     ?name → {ok, bio?, courses[]}                 # 本学期授课 + 能对上的简介
GET  /api/projects/sources      → 来源清单（任务 3，新增）
GET  /api/projects/context     ?uid → {direction, stage, reason, paths, path_step}   # 默认「走到哪」；paths 来自任务 4
POST /api/projects/search       {uid, direction, stage, keywords?, node?, path_step?} → {query, items, sources, routes, empty_reason}
POST /api/projects/pick         {uid, id} → Project                         # id 必须来自最近一次检索
GET  /api/projects/mine        ?uid → {projects}
GET  /api/projects/{pid}       ?uid → Project（含 reviews）
GET  /api/projects/{pid}/readme ?uid → README 模板（markdown）
GET  /api/projects/{pid}/sample.zip ?uid → 示例成果压缩包
POST /api/projects/{pid}/submit ?uid  body=.zip → Review                  # 同时写回 behavior 事实
GET  /api/health
```

前端课程懒加载走 `/api/explore/courses?query=<节点名>`；有学期快照时本地返回。

## 6. 技术决策（ADR 摘要）

| # | 决策 | 理由 |
| --- | --- | --- |
| 1 | FastAPI 单体（无微服务/队列） | 校园项目复杂度上限；Pydantic 兼 LLM structured output |
| 2 | SQLite 起步（`server/data/demo.db`） | 零运维；压测后可平移 Postgres |
| 3 | 前端 W0 用无构建静态页 | 演示可靠性优先；迁移 React 由前端 Owner 决定（保持 REST 不变即可） |
| 4 | LLM 走 OpenAI 兼容抽象 | 评测期换模型零成本 |
| 5 | pku-course 经 uv 子进程调用（W0） | 沿用已验证的 UTF-8/退出码处理；W1 改进程内 adapter + 子进程 fallback |
| 6 | 显式状态机，不用自由 Agent 循环 | 可测试可复现，成本可控 |
| 7 | 不做向量 RAG | 知识包小而结构化，SQL/关键词够用 |
| 8 | 部署：单机 Docker（W1 补 compose + DEPLOY.md） | 对齐课程 9/28 部署节点 |
