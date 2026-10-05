# -*- coding: utf-8 -*-
"""抽检表：蒸馏出来的定位句 ↔ 培养方案原文，一屏对照。

用法:
  # 主修（两个卷）
  python tools/curriculum/review.py --kb knowledge/curriculum --raw .work/distill/prose_raw.json --raw .work/distill_sci/prose_raw.json --out docs/curriculum_intros_review.md
  # 辅修 / 双专业
  python tools/curriculum/review.py --kb knowledge/minor --minor --out docs/curriculum_minor_review.md
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compact import norm_name  # noqa: E402
from minor_extract import card_key, dup_keys, load_sections  # noqa: E402

FLUFF = re.compile(r"师资|教师|教授|人数|沿革|荣誉|奖励|排名|评估|招生")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", required=True)
    ap.add_argument("--raw", action="append", default=[], help="主修卷的 prose_raw.json，可给多个卷")
    ap.add_argument("--minor", action="store_true", help="按辅修/双专业层出表（原文在 plans 里，不用 --raw）")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    cards = json.load(open(os.path.join(a.kb, "cards.json"), encoding="utf-8"))
    plans: dict = {}
    pdir = os.path.join(a.kb, "plans")
    if os.path.isdir(pdir):
        for fn in os.listdir(pdir):
            if fn.endswith(".json"):
                p = json.load(open(os.path.join(pdir, fn), encoding="utf-8"))
                plans[p.get("专业") or fn[:-5]] = p
    if a.minor:
        secs = load_sections(a.kb)
        dups = dup_keys(secs)
        by_key = {card_key(c, dups): c for c in cards}
        raw = {}
        for s in secs:
            raw[card_key(s, dups)] = {
                "院系": s["院系"], "类型": s["类型"], "总学分": s["总学分"],
                "简介原文": s.get("简介原文", ""), "培养目标原文": s.get("培养目标原文", ""),
                "核心课程": s.get("核心课程", [])}
        find = lambda name: by_key.get(name, {})                        # noqa: E731
        courses_of = lambda info: (info.get("核心课程") or [])[:5]      # noqa: E731
        title = "辅修 / 双专业定位句 · 抽检表"
    else:
        by_exact = {c["专业"]: c for c in cards}
        pairs = [(norm_name(c["专业"]), c) for c in cards]

        def find(name: str):
            """章节名 → 卡片：先去掉「专业」二字精确比，再取长度最接近的包含匹配。"""
            if name in by_exact:
                return by_exact[name]
            n = norm_name(name)
            best, best_gap = {}, None
            for cn, card in pairs:
                if not cn or not (cn == n or cn in n or n in cn):
                    continue
                gap = abs(len(cn) - len(n))
                if best_gap is None or gap < best_gap:
                    best, best_gap = card, gap
            return best

        raw = {}
        for path in a.raw:
            raw.update(json.load(open(path, encoding="utf-8")))
        courses_of = lambda info: (info.get("代表性必修课") or [])[:5]   # noqa: E731
        title = "专业定位句 · 抽检表"

    rows = []
    for name, info in sorted(raw.items()):
        card = find(name)
        rows.append((name, info.get("院系", ""), card.get("定位", ""), courses_of(info), info))

    lines = [f"# {title}", "",
             "左列是 LLM 从「培养目标/专业简介 + 核心课程」蒸馏出的 ≤40 字定位；",
             "右列是原文片段（含师资、沿革等水分，仅供参考对照，不进库）。",
             f"共 {len(rows)} 条。", "",
             "| # | 院系 / 专业 | 蒸馏定位句 | 核心课程 | 原文片段（截断） |",
             "| --- | --- | --- | --- | --- |"]
    for i, (name, dept, line, courses, info) in enumerate(rows, 1):
        src = (info.get("培养目标原文") or info.get("简介原文") or "").strip()
        src = src.replace("|", "／")
        src = src[:90] + ("…" if len(src) > 90 else "")
        lines.append(f"| {i} | {dept} / {name} | {line or '（未生成）'} | {'、'.join(courses)} | {src} |")

    lines += ["", "## 需要人工确认的条目（原文为空、或只有项目名可依据）", ""]
    # 只列现在还存在于知识库里的条目：重抽一遍之后，有些旧批次里的名字（比如被识别成院系章节的
    # 「工学部北京大学工学院」）已经没有对应的章节了，别让它们混进待确认清单。
    live = set(plans) if plans else None
    weak = [n for n, d, l, c, info in rows
            if (live is None or n in live)
            and (not (info.get("培养目标原文") or info.get("简介原文")) or not c)]
    lines += [f"- {n}" for n in weak] or ["- （无）"]
    open(a.out, "w", encoding="utf-8").write("\n".join(lines))
    print(f"-> {a.out}（{len(rows)} 条，其中信息稀薄 {len(weak)} 条）")


if __name__ == "__main__":
    main()
