# -*- coding: utf-8 -*-
"""蒸馏「这个专业是干什么的」那一句话。

培养方案里的「专业简介 / 培养目标」全是套话（师资多少、沿革多久、培养复合型人才），
所以流程是：**抽原文 → 交给 LLM 压成 ≤40 字 → 人工抽检**，成品存 intros.json，
原文另存一份（intros_raw.json）供抽检对照。

用法:
  python distill.py --kb knowledge/curriculum --pdf "<文科卷.pdf>" --out .work/distill --batches 6
  python distill.py --out .work/distill --merge        # 合并 out_*.json → intros.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_curriculum import HEADING_RE, squeeze  # noqa: E402
from compact import core_courses, load_plans  # noqa: E402

INTRO_HEADS = ("专业简介", "培养目标", "专业概况", "学科简介", "专业介绍")
STOP_HEADS = ("培养要求", "毕业要求", "课程设置", "课程地图", "师资", "学制", "联系方式")


def prose_of(text: str, cap: int = 700) -> dict:
    """把 一、专业简介 / 二、培养目标 的原文按段取出来（去掉页眉页脚）。"""
    buckets: dict[str, list[str]] = {}
    cur = None
    for raw in text.split("\n"):
        s = squeeze(raw)
        m = HEADING_RE.match(s)
        if m:
            t = squeeze(m.group(1))
            if any(t.startswith(h) for h in INTRO_HEADS):
                cur = "简介"
                continue
            if t.startswith("培养目标"):
                cur = "目标"
                continue
            if any(t.startswith(h) for h in STOP_HEADS):
                cur = None
            continue
        if cur and s and "北京大学本科培养方案" not in s and not re.match(r"^[·\d]+$", s):
            buckets.setdefault(cur, []).append(s)
    return {k: "".join(v)[:cap] for k, v in buckets.items()}


def make_batches(args) -> None:
    import pdfplumber

    plans = load_plans(args.kb)
    sections = json.load(open(os.path.join(args.kb, "sections.json"), encoding="utf-8"))
    os.makedirs(args.out, exist_ok=True)
    raw: dict[str, dict] = {}

    with pdfplumber.open(args.pdf) as pdf:
        for e in sections:
            name = e["name"]
            plan = plans.get(name)
            if not plan or plan.get("类别") not in ("专业", "项目") or not e.get("pdf_start"):
                continue
            text = "\n".join((pdf.pages[p - 1].extract_text() or "")
                             for p in range(e["pdf_start"],
                                            min(e["pdf_start"] + 3, len(pdf.pages)) + 1))
            pr = prose_of(text)
            raw[name] = {
                "院系": plan.get("院系", ""),
                "类别": plan.get("类别", ""),
                "门类/专业类": "",
                "简介原文": pr.get("简介", ""),
                "培养目标原文": pr.get("目标", ""),
                "代表性必修课": core_courses(plan, 10),
                "毕业总学分": plan["学分结构"].get("毕业总学分"),
                "专业必修": plan["指纹"].get("专业必修学分_方案原文"),
                "数学底子": (plan["指纹"].get("必修_能力课程名") or {}).get("数学", [])[:4],
            }

    json.dump(raw, open(os.path.join(args.out, "prose_raw.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    items = sorted(raw.items())
    n = max(1, args.batches)
    size = (len(items) + n - 1) // n
    for i in range(n):
        chunk = dict(items[i * size:(i + 1) * size])
        if not chunk:
            continue
        json.dump(chunk, open(os.path.join(args.out, f"batch_{i + 1}.json"), "w",
                              encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"batch_{i + 1}.json: {len(chunk)} 个专业")


def merge(args) -> None:
    out: dict[str, str] = {}
    for fn in sorted(os.listdir(args.out)):
        if fn.startswith("out_") and fn.endswith(".json"):
            out.update(json.load(open(os.path.join(args.out, fn), encoding="utf-8")))
    json.dump(out, open(os.path.join(args.out, "intros.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"合并 {len(out)} 条 → {os.path.join(args.out, 'intros.json')}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", default="")
    ap.add_argument("--pdf", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--batches", type=int, default=6)
    ap.add_argument("--merge", action="store_true")
    a = ap.parse_args()
    merge(a) if a.merge else make_batches(a)
