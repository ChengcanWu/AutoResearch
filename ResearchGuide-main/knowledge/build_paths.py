# -*- coding: utf-8 -*-
"""从 docs/paths/*.md（任务 4 的方向路径）生成 knowledge/paths.json，给「项目」检索用。

用法：uv run --no-project python knowledge/build_paths.py
路径文档改了、或者甲补上 认知.md / 经济.md 之后跑一次；server/tests 会检查两边是否一致。
只抄步骤名、「先弄懂什么」「做完怎样算过了」，不改原意；缺字段或步数不对就报错，不猜。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "paths"
OUT = ROOT / "knowledge" / "paths.json"

# 文件名 → 方向树代码（与 web/js/app.js 的 FIELD_TREES、server/planner.py 的 DIRECTIONS 一致）
CODES = {"数学": "math", "人工智能": "ai", "认知": "psy", "经济": "econ"}

# 路径第几步 → 项目阶段（0 只学了概念 · 1 做过小任务 · 2 学完一块 · 3 做过项目）
STEP_TO_STAGE = {1: 0, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3}

# docs/paths/改树建议.md §5「给任务 3 的接口」里的阶段—项目形态（原文，供模型参考）
FORM = {
    1: "复现一个小基线、把一个小结跑出来（入门赛、课程公开作业题）",
    2: "复现一个小基线、把一个小结跑出来（入门赛、课程公开作业题）",
    3: "复现一个小任务的 3 组设置对比",
    4: "复现一篇经典论文的小子集结果",
    5: "复现一篇经典论文的小子集结果",
    6: "一次改进或消融，写成含失败分析的实验报告",
}

ABOUT = ("任务 4 方向路径的机读版，由 knowledge/build_paths.py 从 docs/paths/*.md 生成，不要手改。"
         "只抄步骤名、先弄懂什么、做完怎样算过了；project_stage 是任务 3 的换算（第 1 步→只学了概念，2→做过小任务，3–4→学完一块，5–6→做过项目），"
         "project_form 抄自 docs/paths/改树建议.md §5。")


def _plain(s: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"\1", s).strip()


def parse(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    head = re.search(r"^> 方向：(.+?) ｜.*?核对日期：(\S+)", text, re.M)
    goal = re.search(r"^> 终点定义：(.+)$", text, re.M)
    if not head or not goal:
        raise ValueError(f"{path.name}: 缺少「> 方向：… ｜ … 核对日期：…」或「> 终点定义：…」")
    steps = []
    for m in re.finditer(r"^### 第 (\d) 步 · (.+?)\n(.*?)(?=^### 第 |^## |\Z)", text, re.M | re.S):
        n, name, body = int(m.group(1)), m.group(2).strip(), m.group(3)

        def field(label: str) -> str:
            f = re.search(r"^- \*\*" + label + r"\*\*：(.+)$", body, re.M)
            if not f:
                raise ValueError(f"{path.name} 第 {n} 步缺少「{label}」")
            return _plain(f.group(1))

        steps.append({"step": n, "name": name, "focus": field("先弄懂什么"), "done_when": field("做完怎样算过了"),
                      "project_stage": STEP_TO_STAGE[n], "project_form": FORM[n]})
    if [s["step"] for s in steps] != list(range(1, 7)):
        raise ValueError(f"{path.name}: 需要第 1–6 步，实际是 {[s['step'] for s in steps]}")
    return {"name": head.group(1).strip(), "source_doc": f"docs/paths/{path.name}", "checked_at": head.group(2),
            "goal": _plain(goal.group(1)), "steps": steps}


def build() -> dict:
    paths = {}
    for stem, code in CODES.items():
        f = DOCS / f"{stem}.md"
        if f.exists():
            paths[code] = parse(f)
    return {"about": ABOUT, "paths": paths}


if __name__ == "__main__":
    data = build()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for code, p in data["paths"].items():
        print(f"{code}: {p['name']}（{p['source_doc']}，核对 {p['checked_at']}）{len(p['steps'])} 步")
    missing = [s for s in CODES if not (DOCS / f"{s}.md").exists()]
    if missing:
        print("还没有：" + "、".join(missing), file=sys.stderr)
