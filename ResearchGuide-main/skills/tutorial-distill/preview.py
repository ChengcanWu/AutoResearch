# -*- coding: utf-8 -*-
"""把 tutorial-tree-v2 JSON 打成 mermaid 流程图 + 每个节点的学什么/做什么/链接。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

KIND_ZH = {
    "reading": "读",
    "exercise": "做习题",
    "problem_set": "做作业",
    "lab": "做实验",
    "project": "做项目",
    "writeup": "写记录",
}


def _esc(text: str) -> str:
    return (text or "").replace('"', "#quot;")


def mermaid(data: dict) -> str:
    nodes = data.get("nodes") or {}
    trunk = data.get("trunk") or []
    forks = data.get("forks") or []
    join = data.get("join")
    lines = ["flowchart TD"]
    seen: set[str] = set()

    def decl(nid: str) -> None:
        if nid in seen or nid not in nodes:
            return
        seen.add(nid)
        lines.append(f'  {nid}["{_esc(nodes[nid].get("name") or nid)}"]')

    for nid in trunk:
        decl(nid)
    for a, b in zip(trunk, trunk[1:]):
        lines.append(f"  {a} --> {b}")

    last_trunk = trunk[-1] if trunk else None
    join_id = (join or {}).get("node") if join else None
    if join_id:
        decl(join_id)

    for fk in forks:
        fid = fk.get("id") or "fork"
        after = fk.get("after") or last_trunk
        pick = fk.get("pick") or 1
        lines.append(f'  {fid}{{"选 {pick} 条"}}')
        if after:
            lines.append(f"  {after} --> {fid}")
        for br in fk.get("branches") or []:
            bn = br.get("nodes") or []
            label = _esc(br.get("name") or br.get("id") or "")
            prev = fid
            for i, nid in enumerate(bn):
                decl(nid)
                arrow = f' -- "{label}" -->' if i == 0 else " -->"
                lines.append(f"  {prev}{arrow} {nid}")
                prev = nid
            if join_id and prev:
                lines.append(f"  {prev} --> {join_id}")
    return "\n".join(lines)


def _task_block(task: dict, indent: str = "") -> list[str]:
    kind = KIND_ZH.get(task.get("kind") or "", task.get("kind") or "")
    lines = [f"{indent}- **做什么（{kind}）**：{task.get('prompt')}"]
    if task.get("from"):
        lines.append(f"{indent}  - 对照：{task['from']}")
    for alt in task.get("alternatives") or []:
        lines.extend(_task_block(alt, indent + "  "))
    return lines


def cards(data: dict) -> str:
    nodes = data.get("nodes") or {}
    order: list[str] = []
    for nid in data.get("trunk") or []:
        if nid not in order:
            order.append(nid)
    for fk in data.get("forks") or []:
        for br in fk.get("branches") or []:
            for nid in br.get("nodes") or []:
                if nid not in order:
                    order.append(nid)
    join = data.get("join") or {}
    if join.get("node") and join["node"] not in order:
        order.append(join["node"])

    chunks: list[str] = []
    for nid in order:
        node = nodes.get(nid) or {}
        lines = [f"### `{nid}` {node.get('name', '')}", ""]
        if node.get("why"):
            lines.append(f"- **为什么现在做**：{node['why']}")
        learn = node.get("learn") or []
        if learn:
            lines.append("- **该学啥**：")
            for item in learn:
                lines.append(f"  - {item}")
        task = node.get("task") or {}
        lines.extend(_task_block(task))
        lines.append("- **打开这些页**：")
        for r in node.get("resources") or []:
            lines.append(f"  - [{r.get('title')}]({r.get('url')}) — {r.get('use')}")
        chunks.append("\n".join(lines))
    return "\n\n".join(chunks)


def render(data: dict) -> str:
    forks = data.get("forks") or []
    fork_notes = []
    for fk in forks:
        fork_notes.append(f"- 分叉 `{fk.get('id')}`（选 {fk.get('pick')} 条）：{fk.get('why')}")
    head = [
        f"# {data.get('id')} {data.get('name')}",
        "",
        data.get("goal") or "",
        "",
        "```mermaid",
        mermaid(data),
        "```",
        "",
    ]
    if fork_notes:
        head.extend(["分叉依据：", *fork_notes, ""])
    head.append(cards(data))
    return "\n".join(head)


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python skills/tutorial-distill/preview.py knowledge/tutorials/520.40.json")
        return 1
    path = Path(sys.argv[1])
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != "tutorial-tree-v2":
        print(f"{path.name} 还不是 tutorial-tree-v2（旧 6 步直线稿）。")
        return 1
    print(render(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
