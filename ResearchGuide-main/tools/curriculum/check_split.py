# -*- coding: utf-8 -*-
r"""回归检查：把公共基础课程摘出 plans/ 之后，一门课都不许丢。

做法：拿「摘之前的 plans」和「摘之后的 plans + public_courses.json」对账——
每个章节的 (课号, 课程名) 集合必须完全一致（差集非空就是 bug）。

用法:
  # 1) 先把没摘过的 plans 存一份
  git checkout <首次抽取的提交> -- ResearchGuide-main/knowledge/curriculum/plans
  xcopy /E /I ResearchGuide-main\knowledge\curriculum\plans .work\plans_orig
  # 2) 重新生成知识库
  python tools/curriculum/extract_curriculum.py --out knowledge/curriculum --refingerprint
  # 3) 对账
  python tools/curriculum/check_split.py --orig .work/plans_orig --kb knowledge/curriculum
"""
from __future__ import annotations

import argparse
import json
import os


def courses(plan: dict) -> set:
    return {(c.get("课号"), c.get("课程名称"))
            for m in plan.get("课程表", []) for c in m.get("课程", [])}


def load_plans(path: str) -> dict[str, dict]:
    out = {}
    if os.path.isdir(path):
        files = [os.path.join(path, f) for f in sorted(os.listdir(path)) if f.endswith(".json")]
    else:
        files = [path]
    for fp in files:
        plan = json.load(open(fp, encoding="utf-8"))
        out[plan.get("专业") or os.path.basename(fp)[:-5]] = plan
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orig", required=True, help="摘公共课之前的 plans 目录")
    ap.add_argument("--kb", required=True)
    a = ap.parse_args()

    before = load_plans(a.orig)
    after = load_plans(os.path.join(a.kb, "plans"))
    pub = json.load(open(os.path.join(a.kb, "public_courses.json"), encoding="utf-8"))
    shared = {k: v for k, v in pub.items() if not k.startswith("_")}

    moved: dict[str, set] = {}
    for code, node in shared.items():
        for owner in node.get("出现于", []):
            moved.setdefault(owner, set()).add((node["课号"], node["课程名称"]))

    bad = 0
    for name, plan in before.items():
        lost = courses(plan) - (courses(after.get(name, {})) | moved.get(name, set()))
        if lost:
            bad += 1
            print(f"!! {name} 丢了 {len(lost)} 门：{sorted(lost)[:5]}")
    print(f"[{'失败' if bad else '通过'}] 章节 {len(before)} 个，丢课 {bad} 个；"
          f"共享公共课 {len(shared)} 门、涉及 {len(moved)} 个章节")


if __name__ == "__main__":
    main()
