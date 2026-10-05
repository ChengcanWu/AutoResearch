# -*- coding: utf-8 -*-
"""院系认知卡：把某个专业的培养方案压成一段可以塞进模型上下文的确定事实。

这是「AI 怎么用这份知识库」的最小实现：结构化查表 → 固定模板 → 每句话都能指回 PDF 页码。
用法: python card.py --kb <知识库目录> [--major 经济学专业] [--list] [--context]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_curriculum import plan_courses  # noqa: E402

MODULE_ALIAS = {
    "数学": "必修_数学学分",
    "计算": "必修_计算学分",
    "语言": "必修_语言学分",
    "实践": "必修_实践学分",
}


def load(kb: str) -> dict:
    plans = {}
    pdir = os.path.join(kb, "plans")
    for fn in sorted(os.listdir(pdir)):
        if fn.endswith(".json"):
            plan = json.load(open(os.path.join(pdir, fn), encoding="utf-8"))
            plans[plan.get("专业") or fn[:-5]] = plan
    return plans


def pick(plans: dict, query: str) -> list[str]:
    exact = [k for k in plans if k == query]
    if exact:
        return exact
    return [k for k in plans if query in k]


def public_struct(kb: str) -> str:
    """全校统一的公共基础课程大类（plans 里已摘走，这里补一句，免得卡上看不出公共课那几十学分）。"""
    path = os.path.join(kb, "public_courses.json")
    if not os.path.exists(path):
        return ""
    pub = json.load(open(path, encoding="utf-8"))
    for k, v in (pub.get("_学分结构_各专业公共课") or {}).items():
        if re.match(r"^\d+[\.\s]?公共", k):
            return f"{k.split(' ')[-1]} {v}"
    return ""


def card(plan: dict, pub: str = "") -> str:
    fp = plan["指纹"]
    st = plan["学分结构"]
    terms = fp.get("必修_学期分布", {})
    early = [c for c in plan_courses(plan)
             if "必修" in c.get("课程性质", "")
             and any(x in c.get("选课学期", "") for x in ("一上", "一下", "大一"))]
    early.sort(key=lambda c: c.get("选课学期", ""))
    pre = list(fp.get("必修_课号前缀学分", {}).items())[:3]

    lines = [
        f"【院系-专业】{plan.get('院系', '?')} / {plan['专业']}",
        f"【学位与总学分】{st.get('授予学位') or '?'} · 毕业总学分 {st.get('毕业总学分') or '?'}",
    ]
    if st.get("学分结构"):
        struct = "｜".join(f"{k} {v}" for k, v in st["学分结构"].items() if "-" not in k.split(" ")[0])
        lines.append(f"【学分结构（大类）】{struct}")
        sub = "｜".join(f"{k} {v}" for k, v in st["学分结构"].items() if "-" in k.split(" ")[0])
        if sub:
            lines.append(f"【学分结构（细分）】{sub}")
    if pub:
        lines.append(f"【公共基础课程】全校统一 {pub}（明细见 public_courses.json，"
                     "plans 里已摘走，不在上面的专业必修里）")
    lines.append(f"【必修分量】方案要求 「{fp.get('专业必修学分_方案原文') or '?'}」；"
                 f"课程表内必修课 {fp.get('必修_课程学分和') if fp.get('必修_含备选') else fp.get('必修学分合计')}"
                 f" 学分 / {fp.get('必修门数')} 门"
                 f"（数学 {fp.get('必修_数学学分')} · 计算 {fp.get('必修_计算学分')} · "
                 f"语言 {fp.get('必修_语言学分')} · 实践 {fp.get('必修_实践学分')}）")
    if fp.get("必修_含备选"):
        lines.append("【注意】本专业课程表里一个位置给了多门备选课（课程学分和 "
                     f"{fp.get('必修_课程学分和')} 已按模块学分压到 {fp.get('必修学分合计')}）；"
                     "下面课程名并列时是「任选其一」，不要当成都要修。")
    if fp.get("必修_无性质列"):
        lines.append("【注意】该专业的课程表没有「课程性质」列，指纹是按全部课程算的，"
                     "只能用来看画像，不能当必修清单。")
    if pre:
        lines.append("【开课院系线索（课号前 4 位：学分）】" +
                     "、".join(f"{p}→{v}" for p, v in pre))
    if early:
        lines.append("【大一就会出现】" + "、".join(
            f"{c['课程名称']}{c.get('学分', '')}（{c.get('选课学期', '')}）" for c in early[:8]))
    if terms:
        lines.append("【必修课学期分布】" + "、".join(f"{k}×{v}" for k, v in list(terms.items())[:6]))
    names = fp.get("必修_能力课程名", {})
    for tag in ("数学", "计算"):
        if names.get(tag):
            lines.append(f"【{tag}底子（必修）】" + "、".join(names[tag]))
    pg = plan.get("页码", {})
    vol = plan.get("卷") or "文科卷"
    lines.append(f"【来源】《北京大学本科培养方案（2026）{vol}》书内 p{pg.get('书内')}"
                 f"（PDF p{pg.get('pdf', ['?', '?'])[0]}–{pg.get('pdf', ['?', '?'])[1]}）")
    if plan.get("合章"):
        lines.append("【合章】与 " + "、".join(plan["合章"]) + " 印在同一章，课程表相同（原文就没分开印）")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", required=True)
    ap.add_argument("--major", default="经济学专业")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default="", help="写到文件（Windows 控制台重定向会把中文写坏，建议用它）")
    args = ap.parse_args()

    plans = load(args.kb)
    pub = public_struct(args.kb)
    buf: list[str] = []
    if args.list:
        for k in sorted(plans):
            buf.append(f"{plans[k].get('院系', '')}\t{k}")
    else:
        hits = pick(plans, args.major)
        if not hits:
            buf.append(f"知识库里没有「{args.major}」")
        for h in hits:
            if args.json:
                buf.append(json.dumps({k: v for k, v in plans[h].items() if k != "课程表"},
                                      ensure_ascii=False, indent=1))
            else:
                buf.append(card(plans[h], pub))
                buf.append("")
    text = "\n".join(buf)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(text)
        print("->", args.out)
    else:
        print(text)


if __name__ == "__main__":
    main()
