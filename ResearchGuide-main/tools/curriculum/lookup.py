# -*- coding: utf-8 -*-
"""检索入口：按「用户会怎么说」把院系-专业/辅修查出来。

为什么单独一个文件：卡片层里同一个专业有 2–4 种写法（专业目录名、章节名、去掉方向括号、
去掉「专业」二字），检索时不能靠 `==` 硬比。这里把这些写法建成别名索引，并且**保留歧义**：
一个别名对上多个专业时（「信息与计算科学」对图灵班/智班/普通班），返回全部候选而不是随便挑一个——
这正是产品要输出的「专业簇」。

用法：
  python tools/curriculum/lookup.py --kb knowledge/curriculum --ask 软件工程专业
  python tools/curriculum/lookup.py --kb knowledge/curriculum --minor --ask 计算机科学与技术（双专业）
  python tools/curriculum/lookup.py --kb knowledge/curriculum --ask 统计学 --json
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from card import card as render_card  # noqa: E402
from card import public_struct  # noqa: E402


def load_cards(kb: str, minor: bool = False) -> list[dict]:
    path = os.path.join(kb, "cards.json")
    cards = json.load(open(path, encoding="utf-8"))
    if minor:
        for c in cards:                       # 辅修层的主键是 (院系, 专业, 类型)
            c.setdefault("检索别名", [])
            for a in (c["专业"], f"{c['专业']}{c['类型']}", f"{c['专业']}（{c['类型']}）",
                      f"{c['院系']}{c['专业']}{c['类型']}"):
                if a and a not in c["检索别名"]:
                    c["检索别名"].append(a)
    return cards


def build_index(cards: list[dict]) -> dict[str, list[dict]]:
    idx: dict[str, list[dict]] = {}
    for c in cards:
        names = [c.get("专业", ""), c.get("目录专业名", "")] + list(c.get("检索别名", []))
        for a in dict.fromkeys(names):
            if a:
                bucket = idx.setdefault(a, [])
                if c not in bucket:
                    bucket.append(c)
    return idx


def find(idx: dict[str, list[dict]], q: str, cards: list[dict] | None = None) -> tuple[list[dict], list[str]]:
    """三层：① 主键完全相同（`专业` 字段 = 章节名）；② 别名表；③ 包含匹配；都不中就给 3 个最像的名字。

    ① 放最前是必要的：别名里有「经济学专业」这种通用写法，直接查别名会把
    「经济学（国家发展方向）专业」也一起命中，而用户说「经济学专业」时通常就是要那一条。
    """
    q = q.strip()
    exact = [c for c in (cards or []) if c.get("专业") == q]
    if exact:
        return exact, []
    if q in idx:
        return idx[q], []
    seen: list[dict] = []
    for a, cs in idx.items():
        if a and (q in a or a in q):
            for c in cs:
                if c not in seen:
                    seen.append(c)
    if seen:
        return seen, []
    return [], difflib.get_close_matches(q, list(idx), n=3, cutoff=0.5)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", required=True, help="knowledge/curriculum 或 knowledge/minor")
    ap.add_argument("--minor", action="store_true", help="按辅修/双专业层检索")
    ap.add_argument("--ask", required=True, help="用户说的专业名，写法随意")
    ap.add_argument("--json", action="store_true", help="输出机读 JSON（给接口/Agent 用）")
    a = ap.parse_args()

    cards = load_cards(a.kb, a.minor)
    idx = build_index(cards)
    hits, near = find(idx, a.ask, cards)

    if a.json:
        print(json.dumps({"ok": bool(hits), "问": a.ask,
                          "命中": hits, "候选近名": near}, ensure_ascii=False, indent=1))
        return

    if not hits:
        print(f"没查到「{a.ask}」。"
              + (f"最像的：{'、'.join(near)}" if near else "库里没有这个专业。"))
        return
    if len(hits) > 1:
        print(f"「{a.ask}」对上 {len(hits)} 个专业（专业簇，别硬猜一个）：")
        for c in hits:
            print("  - %s / %s%s｜%s" % (c.get("院系", ""), c["专业"],
                                        f"（{c['类型']}）" if c.get("类型") else "",
                                        c.get("定位") or c.get("来源页", "")))
        return
    c = hits[0]
    print(f"命中：{c.get('院系', '')} / {c['专业']}")
    plan = None
    pdir = os.path.join(a.kb, "plans")
    for fn in os.listdir(pdir):
        p = json.load(open(os.path.join(pdir, fn), encoding="utf-8"))
        if (p.get("专业") or fn[:-5]) == c["专业"]:
            plan = p
            break
    if plan and not a.minor:
        print(render_card(plan, public_struct(a.kb)))
    else:
        print(json.dumps(c, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
