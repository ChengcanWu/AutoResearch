# 启研 · AI Research Mentor

> 它认识你，它懂科研世界，它决定你此刻最值得做的一件事，陪你做完，记住结果，再给下一步。

面向大一大二、不知道自己适不适合科研、该研究什么、从哪开始的学生。区别于「又一个 AI 问答工具」的是一个闭环：

```text
理解用户 → 理解科研世界 → 判断阶段 → 决定下一步(NBA)
    ↑                                      ↓
更新认知  ←  记录行为与结果  ←  陪用户完成行动
```

产品三原则：**行动大于信息 · 个性化必须有依据 · 不编造事实**。

## 当前状态：W0 Thin Slice（9/28 演示版）

①–⑨ 演示链路已全部实装：昵称登录 → 初始对话（5 轮，选项卡+「不知道」）→ 初始认知确认（可改可删）→ 3 张方向推荐卡（引用你的原话 + **北大真实课程实时检索** + 入门读物）→ 20 分钟微任务 → 提交 → rubric 逐条反馈 → **行为证据真实写回用户模型** → 进阶 NBA。

三处 LLM 环节（对话抽取 / 决策措辞 / 任务反馈）当前为规则演示版（数据结构与闭环真实），W1 接入真实模型——分工见 [docs/TASK_ASSIGNMENTS.md](docs/TASK_ASSIGNMENTS.md)。

## 快速开始

```bash
# 需 Python 3.11+ 与 uv（搜课功能）；前端无构建步骤
# 对话 / 下一步 / 方向理由 / 任务反馈要接模型时：
# 复制 .env.example 为 .env 并填 LLM_API_KEY，或在网页首页点「连接模型 API」。
run_demo.bat                # Windows 双击即跑
# 或：
uv run --no-project --with fastapi --with uvicorn --with pydantic python server/main.py
# 打开 http://127.0.0.1:8100/
```

## 边学边练（任务 3）

侧栏「项目」：选方向和「走到哪」，从公开来源实时检索可以做的练手项目（每条带来源链接和检索时间，查不到就空着）；选一个，按要求打成 `.zip` 交上来，按五条标准逐条评阅并写回画像。说明见 [docs/TASK3_PROJECTS.md](docs/TASK3_PROJECTS.md)；离线测试：`uv run --no-project --with pytest --with fastapi --with pydantic --with httpx pytest server/tests`（不联网、不调模型；PR 上由 GitHub Actions 自动跑，见仓库根目录 `.github/workflows/tests.yml`）。

## 目录结构

```text
web/                前端（无构建静态页；设计规范 docs/DESIGN_SPEC.md）
server/             FastAPI 后端（路由/契约/状态机/Planner/Workbench/搜课适配）
skills/pku-course/  北大搜课工具（uv 子进程调用，契约不改）
skills/project-*/   给模型的工作说明（SKILL.md）；代码与 skill 的分工见 skills/README.md
knowledge/          学科知识包（disciplines.json）、项目来源清单（project_sources.json）
docs/               TASK_ASSIGNMENTS / ARCHITECTURE / DESIGN_SPEC / NEXT_PRE / CHANGELOG
```

## 协作

- 开发流程、6 人分工、vibecoding 角色卡与 PR 规则：**[docs/TASK_ASSIGNMENTS.md](docs/TASK_ASSIGNMENTS.md)**
- 接口契约（冻结）：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) §3/§5
- 文档变更一律登记 [docs/CHANGELOG.md](docs/CHANGELOG.md)
