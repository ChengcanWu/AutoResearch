# -*- coding: utf-8 -*-
"""检查 knowledge/tutorials/*.json 是否符合 tutorial-distill 的最低纪律。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "knowledge" / "tutorials"

TASK_KINDS = {"reading", "exercise", "problem_set", "lab", "project", "writeup"}
SOFT = ("理解了", "掌握了", "熟悉")


def _urls(data: dict) -> set[str]:
    return {s.get("url") for s in (data.get("sources") or []) if s.get("url")}


def _task_errs(label: str, task: dict | None) -> list[str]:
    errs: list[str] = []
    if not isinstance(task, dict):
        return [f"{label} 缺 task"]
    if task.get("kind") not in TASK_KINDS:
        errs.append(f"{label} task.kind 必须是 {sorted(TASK_KINDS)}")
    prompt = task.get("prompt") or ""
    if not prompt:
        errs.append(f"{label} 缺 task.prompt")
    if any(w in prompt for w in SOFT):
        errs.append(f"{label} 过关标准不可核对")
    if not task.get("from"):
        errs.append(f"{label} 缺 task.from（对照哪一门课/哪一章）")
    for i, alt in enumerate(task.get("alternatives") or []):
        errs.extend(_task_errs(f"{label} alternatives[{i}]", alt))
    return errs


def _node_errs(nid: str, node: dict, urls: set[str]) -> list[str]:
    errs: list[str] = []
    if not (node.get("name") and node.get("why")):
        errs.append(f"节点 {nid} 缺 name/why")
    learn = node.get("learn") or []
    if not isinstance(learn, list) or not learn:
        errs.append(f"节点 {nid} 缺 learn（该学啥）")
    errs.extend(_task_errs(f"节点 {nid}", node.get("task")))
    resources = node.get("resources") or []
    if not resources:
        errs.append(f"节点 {nid} 缺 resources")
    for r in resources:
        u = r.get("url")
        if not u:
            errs.append(f"节点 {nid} 有资源没有 url")
        elif u not in urls:
            errs.append(f"节点 {nid} 引用了 sources 里没有的链接")
        if not (r.get("title") and r.get("use")):
            errs.append(f"节点 {nid} 资源缺 title/use")
    return errs


def check_v2(data: dict) -> list[str]:
    errs: list[str] = []
    status = data.get("status")
    sources = data.get("sources") or []
    urls = _urls(data)
    nodes = data.get("nodes") or {}
    trunk = data.get("trunk") or []
    forks = data.get("forks") or []
    join = data.get("join")

    if status == "ok":
        if len(sources) < 2:
            errs.append("ok 时至少 2 个来源")
        if not data.get("goal"):
            errs.append("缺 goal")
        if len(trunk) < 2:
            errs.append("ok 时 trunk 至少 2 个节点")
        if not isinstance(nodes, dict):
            errs.append("nodes 必须是对象")
            return errs

        cited: set[str] = set(trunk)
        for nid in trunk:
            if nid not in nodes:
                errs.append(f"trunk 引用了不存在的节点 {nid}")

        for fk in forks:
            if not fk.get("why"):
                errs.append(f"分叉 {fk.get('id')} 缺 why（必须引用来源）")
            if not fk.get("source_urls"):
                errs.append(f"分叉 {fk.get('id')} 缺 source_urls")
            for u in fk.get("source_urls") or []:
                if u not in urls:
                    errs.append(f"分叉 {fk.get('id')} 引用了 sources 里没有的链接")
            after = fk.get("after")
            if after not in nodes:
                errs.append(f"分叉 {fk.get('id')} after={after} 不在 nodes 里")
            pick = fk.get("pick")
            if not isinstance(pick, int) or pick < 1:
                errs.append(f"分叉 {fk.get('id')} pick 必须是正整数")
            branches = fk.get("branches") or []
            if len(branches) < 2:
                errs.append(f"分叉 {fk.get('id')} 至少 2 条轨")
            for br in branches:
                bn = br.get("nodes") or []
                if not bn:
                    errs.append(f"分叉轨 {br.get('id')} 没有节点")
                for nid in bn:
                    cited.add(nid)
                    if nid not in nodes:
                        errs.append(f"分叉轨 {br.get('id')} 引用了不存在的节点 {nid}")

        if join:
            jn = join.get("node")
            if not jn:
                errs.append("join 缺 node")
            else:
                cited.add(jn)
                if jn not in nodes:
                    errs.append(f"join 引用了不存在的节点 {jn}")

        extra = set(nodes) - cited
        if extra:
            errs.append(f"孤儿节点（未被 trunk/fork/join 引用）: {sorted(extra)}")

        for nid, node in nodes.items():
            if isinstance(node, dict):
                errs.extend(_node_errs(nid, node, urls))
            else:
                errs.append(f"节点 {nid} 不是对象")
    return errs


def check_v1(data: dict) -> list[str]:
    """旧的 6 步直线稿，重跑成 v2 之前仍能过。"""
    errs: list[str] = []
    status = data.get("status")
    sources = data.get("sources") or []
    urls = _urls(data)
    if status == "ok":
        if len(sources) < 2:
            errs.append("ok 时至少 2 个来源")
        steps = data.get("steps") or []
        if [s.get("step") for s in steps] != [1, 2, 3, 4, 5, 6]:
            errs.append("ok 时必须正好第 1–6 步")
        for s in steps:
            if not (s.get("name") and s.get("focus") and s.get("done_when")):
                errs.append(f"第 {s.get('step')} 步缺 name/focus/done_when")
            if any(w in (s.get("done_when") or "") for w in SOFT):
                errs.append(f"第 {s.get('step')} 步过关标准不可核对")
            for u in s.get("source_urls") or []:
                if u not in urls:
                    errs.append(f"第 {s.get('step')} 步引用了 sources 里没有的链接")
            if not s.get("source_urls"):
                errs.append(f"第 {s.get('step')} 步没有 source_urls")
        if not data.get("goal"):
            errs.append("缺 goal")
    return errs


def check(path: Path) -> list[str]:
    errs: list[str] = []
    data = json.loads(path.read_text(encoding="utf-8"))
    status = data.get("status")
    if status not in ("ok", "insufficient"):
        errs.append("status 必须是 ok 或 insufficient")
    fmt = data.get("format")
    if fmt == "tutorial-tree-v2":
        errs.extend(check_v2(data))
    elif data.get("steps"):
        errs.extend(check_v1(data))
    elif status == "ok":
        errs.append("ok 时需要 format=tutorial-tree-v2 或旧的 steps 1–6")
    return errs


def main() -> int:
    files = sorted(DIR.glob("*.json")) if DIR.exists() else []
    if not files:
        print("没有 knowledge/tutorials/*.json")
        return 1
    bad = 0
    for f in files:
        errs = check(f)
        mark = "FAIL" if errs else "OK"
        print(f"{mark}  {f.name}")
        for e in errs:
            print(f"     {e}")
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
