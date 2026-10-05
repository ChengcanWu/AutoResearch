# -*- coding: utf-8 -*-
"""只留「AI 知道你是谁、这个专业是干什么的」那一层——紧凑专业卡。

相比 plans/*.json（把整个课程表都存下来，3.2 MB），这一层只回答两类问题：
  1. 用户在哪个院系-专业？这个专业属于什么门类、读几年、拿什么学位？（catalog + plans 的字段）
  2. 这个专业到底在干什么？——用「学分结构骨架 + 代表性必修课 + 数学/计算底子」回答，
     而不是抄一段招生宣传；可选再补一句培养目标原文（--pdf）。

用法:
  python compact.py --kb knowledge/curriculum [--pdf "<文科卷.pdf>"] --out knowledge/curriculum
产出:
  cards.json  紧凑专业卡（全部 150 条专业记录 + 98 个章节的画像）
  CARDS.md    同样内容的人读版
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_curriculum import HEADING_RE, own_prefixes, squeeze  # noqa: E402

PROSE_STOP = ("培养目标", "培养要求", "毕业要求", "课程设置", "课程地图", "师资")
CORE_MODULES = ("专业基础课", "专业核心课", "专业必修")


def load_plans(kb: str) -> dict[str, dict]:
    plans = {}
    pdir = os.path.join(kb, "plans")
    for fn in sorted(os.listdir(pdir)):
        if fn.endswith(".json"):
            plan = json.load(open(os.path.join(pdir, fn), encoding="utf-8"))
            plans[plan.get("专业") or fn[:-5]] = plan
    return plans


def big_struct(plan: dict) -> str:
    """学分结构只留大类：公共基础 / 专业必修 / 选修。"""
    out = []
    for k, v in plan.get("学分结构", {}).get("学分结构", {}).items():
        if re.match(r"^\d+[\.\s]", k) and "-" not in k.split(" ")[0].replace(".", "-"):
            out.append(f"{k.split(' ')[-1]} {v}")
    return "｜".join(out)


def is_must_module(label: str) -> bool:
    """必修区 = 模块编号 2.x，或者标题里写着专业必修/基础/核心（子模块如「2.1.1 数学组」也算）。"""
    label = label or ""
    if re.match(r"^2([\.\-]|$)", label.strip()):
        return True
    return any(k in label for k in ("专业必修", "专业基础", "专业核心"))


def core_courses(plan: dict, limit: int = 10) -> list[str]:
    """代表性必修课：本系课优先，跨院系菜单课只在不够时补位；滤掉数学/英语这类全校公共课。"""
    skip = ("高等数学", "大学英语", "思想政治", "军事理论", "体育", "心理健康",
            "劳动教育", "通识", "计算概论", "国家安全", "计算机实习", "习近平")
    no_nature = plan.get("指纹", {}).get("必修_无性质列", False)
    own = own_prefixes(plan)
    primary: list[str] = []
    secondary: list[str] = []
    for mod in plan.get("课程表", []):
        if not is_must_module(mod.get("模块", "")):
            continue
        for c in mod.get("课程", []):
            name = c.get("课程名称", "")
            if not no_nature and "必修" not in c.get("课程性质", ""):
                continue
            if any(s in name for s in skip):
                continue
            bucket = primary if (c.get("课号") or "")[:4] in own else secondary
            if name not in bucket:
                bucket.append(name)
    picked = primary[:limit]
    if len(picked) < 4:                               # 本系课太少（如方向性项目）才补跨院系课
        picked += [n for n in secondary if n not in picked][:4 - len(picked)]
    return picked


def ability(plan: dict, tag: str, limit: int = 4) -> str:
    names = (plan.get("指纹", {}).get("必修_能力课程名") or {}).get(tag) or []
    return "、".join(names[:limit])


FLUFF_RE = re.compile(r"师资|教师|教授|沿革|学院现有|教职工|人数|荣誉|奖励|排名|学科评估|招生"
                      r"|历年来|培养了大量|大师辈出|我系|本系")


def first_sentence(text: str, cap: int = 80) -> str:
    """从培养目标/专业简介里取一句「这个专业在干什么」。

    培养方案这部分水很多（师资、沿革、荣誉）——把明显是水分的句子整句丢掉，
    剩下的才留；一句话都剩不下就返回空（宁可没有，也不要放宣传语）。
    """
    text = squeeze(text)
    if not text:
        return ""
    out = ""
    for p in re.split(r"(?<=[。；])", text):
        if not p or FLUFF_RE.search(p) or len(p) < 12:
            continue
        if len(out) + len(p) > cap:
            break
        out += p
    return out.strip()


def intro_from_pdf(pdf_path: str, sections: list[dict], only: set[str]) -> dict[str, str]:
    import pdfplumber

    intros: dict[str, str] = {}
    with pdfplumber.open(pdf_path) as pdf:
        for e in sections:
            name = e["name"]
            if name not in only or not e.get("pdf_start"):
                continue
            text = "\n".join((pdf.pages[p - 1].extract_text() or "")
                             for p in range(e["pdf_start"], min(e["pdf_start"] + 2, len(pdf.pages)) + 1))
            lines, buf, inside = text.split("\n"), [], False
            for raw in lines:
                s = squeeze(raw)
                m = HEADING_RE.match(s)
                if m:
                    title = squeeze(m.group(1))
                    if title.startswith(("专业简介", "培养目标", "专业概况", "学科简介")):
                        inside = True
                        continue
                    if inside and title.startswith("培养目标"):
                        break                           # 培养目标之后再要一次（见下）
                    if inside and any(title.startswith(x) for x in PROSE_STOP):
                        break
                if inside and s and "北京大学本科培养方案" not in s:
                    buf.append(s)
            # 优先用「培养目标」那段（比「专业简介」少讲师资沿革）
            goal = ""
            cur, bucket = [], {}
            for raw in text.split("\n"):
                s = squeeze(raw)
                m = HEADING_RE.match(s)
                if m:
                    t = squeeze(m.group(1))
                    cur = (["简介"] if t.startswith(("专业简介", "专业概况", "学科简介"))
                           else ["目标"] if t.startswith("培养目标")
                           else ["其他"] if any(t.startswith(x) for x in PROSE_STOP)
                           else cur)
                    continue
                if cur and s and "北京大学本科培养方案" not in s:
                    bucket.setdefault(cur[0], []).append(s)
            goal = first_sentence("".join(bucket.get("目标", [])))
            if buf:
                intros[name] = goal or first_sentence("".join(buf))
    return intros


def norm_name(s: str) -> str:
    """把「专业目录表的名字」和「培养方案章节名」对齐：只去掉「专业」二字，方向括号保留。"""
    return re.sub(r"\s", "", s).replace("专业", "")


def merge_same_chapter(cards: list[dict]) -> list[dict]:
    """一份培养方案覆盖多个专业目录条目时，卡片只留一张。

    例子：物理学院 p112 那一章同时是「物理学 / 物理学（大气物理方向）/ 物理学（天体物理方向）」，
    化学与分子工程学院 p168 一章同时是「化学（材料化学方向）080403… 不对，是 070301 与材料化学 080403」。
    这些条目在专业目录里是**不同的专业代码**，但培养方案只有一份、课程表完全一样——
    按条目各出一张卡就是把同一份内容存 N 遍（AI 还会重复读到）。
    合并后把被覆盖的目录条目收进 `目录条目`，专业代码用「、」连起来，别名取并集。
    """
    out: list[dict] = []
    seat: dict[tuple[str, str], dict] = {}
    for c in cards:
        k = (c.get("院系", ""), c["专业"])
        if k not in seat:
            seat[k] = c
            out.append(c)
            continue
        keep = seat[k]
        entry = {"专业代码": c.get("专业代码", ""), "目录专业名": c.get("目录专业名", c["专业"]),
                 "学位门类": c.get("学位门类", ""), "来源页": c.get("来源页", "")}
        if entry not in keep.setdefault("目录条目", []):
            keep["目录条目"].append(entry)
        head = {"专业代码": keep.get("专业代码", ""),
                "目录专业名": keep.get("目录专业名", keep["专业"]),
                "学位门类": keep.get("学位门类", ""), "来源页": keep.get("来源页", "")}
        if head not in keep["目录条目"]:
            keep["目录条目"].insert(0, head)
        codes = list(dict.fromkeys(e["专业代码"] for e in keep["目录条目"] if e["专业代码"]))
        keep["专业代码"] = "、".join(codes)
        for a in c.get("检索别名", []):
            if a not in keep["检索别名"]:
                keep["检索别名"].append(a)
    return out


def aliases(cat_name: str, plan_name: str) -> list[str]:
    """同一件事在库里有两个写法（专业目录的「汉语言文学」、章节名的「汉语言文学专业」），
    两种都当检索别名收着，AI/接口按哪个名字问都能命中同一条。
    还要补上「去掉方向括号」和「加/去『专业』二字」两种口语写法——用户会说
    「软件工程专业」，而章节名是「软件工程（软件工程方向）专业」。"""
    out: list[str] = []

    def add(x: str) -> None:
        x = (x or "").strip()
        if x and x not in out:
            out.append(x)

    for n in (plan_name, cat_name):
        if not n:
            continue
        plain = re.sub(r"（[^）]*）", "", n)          # 去掉方向括号
        for base in (n, plain):
            add(base)
            add(base.replace("专业", ""))
            if not base.endswith("专业"):
                add(base + "专业")                   # 目录名补一个「专业」后缀
    return out


def match_plan(cat_name: str, plans: dict[str, dict]) -> str | None:
    """先精确（去掉「专业」后完全一致），再退到包含关系，避免「经济学」吃掉「经济学（国家发展方向）」。"""
    n = norm_name(cat_name)
    exact = [k for k in plans if norm_name(k) == n]
    if exact:
        return min(exact, key=len)
    sub = [k for k in plans if n and n in norm_name(k)]
    if sub:
        return min(sub, key=len)
    pre = [k for k in plans if norm_name(k) and norm_name(k) in n]
    return min(pre, key=len) if pre else None


def public_struct(kb: str) -> str:
    """全校统一的公共基础课程大类（43～49 学分）。plans 里已经被摘掉了，卡片补一句免得看着少一截。"""
    path = os.path.join(kb, "public_courses.json")
    if not os.path.exists(path):
        return ""
    pub = json.load(open(path, encoding="utf-8"))
    for k, v in (pub.get("_学分结构_各专业公共课") or {}).items():
        if re.match(r"^\d+[\.\s]?公共", k):
            return f"{k.split(' ')[-1]} {v}"
    return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pdf", default="")
    args = ap.parse_args()

    catalog = json.load(open(os.path.join(args.kb, "catalog.json"), encoding="utf-8"))
    plans = load_plans(args.kb)
    sections = json.load(open(os.path.join(args.kb, "sections.json"), encoding="utf-8"))
    intros: dict[str, str] = {}
    cache = os.path.join(args.out, "intros.json")
    if os.path.exists(cache):
        intros = json.load(open(cache, encoding="utf-8"))
    elif args.pdf:
        want = {k for k, p in plans.items() if p.get("类别") in ("专业", "项目")}
        intros = intro_from_pdf(args.pdf, sections, want)
        json.dump(intros, open(cache, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    used: set[str] = set()
    pub_struct = public_struct(args.kb)
    cards = []
    for row in catalog:
        card = {"院系": row["院系"], "专业": row["专业名称"], "专业代码": row["专业代码"],
                "门类": row["门类"], "专业类": row["专业类"], "修业年限": row["修业年限"],
                "学位门类": row["学位授予门类"], "类别": "专业",
                "来源页": f"专业目录 p{row['来源页']}"}
        key = match_plan(row["专业名称"], plans)
        if key:
            used.add(key)
            plan = plans[key]
            fp = plan["指纹"]
            # `专业` 用**章节名**（= plans/*.json 的键、intros.json 的键），目录上的写法另存，
            # 否则 150 条卡片的名字（「汉语言文学」）和章节名（「汉语言文学专业」）对不上，
            # 按名字查表就得靠模糊匹配。两种写法都进 `检索别名`。
            card["专业"] = key
            card["目录专业名"] = row["专业名称"]
            card["检索别名"] = aliases(row["专业名称"], key)
            card.update({
                "类别": plan.get("类别", "专业"),
                "毕业总学分": plan["学分结构"].get("毕业总学分"),
                "专业必修_方案原文": fp.get("专业必修学分_方案原文"),
                "学分结构": big_struct(plan),
                "核心必修课": core_courses(plan),
                "数学底子": ability(plan, "数学"),
                "计算底子": ability(plan, "计算"),
                "公共基础课程": pub_struct,
                "来源页": f"培养方案 书内 p{plan['页码']['书内']}（PDF p{plan['页码']['pdf'][0]}–{plan['页码']['pdf'][1]}）",
                "定位": intros.get(key, ""),
                "卷": plan.get("卷", ""),
            })
            if plan.get("合章"):
                card["合章"] = plan["合章"]
        else:
            card["检索别名"] = aliases(row["专业名称"], "")
        cards.append(card)

    # 有培养方案但不在专业目录表里的：只留「项目」，公共课/说明/附录/院系章节不进卡片层
    # （卡片是给 AI 认「用户在哪个院系-专业」用的，塞进院系章节和评定细则只会干扰判断）
    for name, plan in plans.items():
        if name in used or plan.get("类别") not in ("专业", "项目"):
            continue
        fp = plan["指纹"]
        card = {"院系": plan.get("院系", ""), "专业": name, "类别": plan.get("类别", ""),
                "检索别名": aliases(name, name),
                "卷": plan.get("卷", ""),
                "毕业总学分": plan["学分结构"].get("毕业总学分"),
                "专业必修_方案原文": fp.get("专业必修学分_方案原文"),
                "学分结构": big_struct(plan), "核心必修课": core_courses(plan),
                "数学底子": ability(plan, "数学"), "计算底子": ability(plan, "计算"),
                "公共基础课程": pub_struct,
                "来源页": f"书内 p{plan['页码']['书内']}（PDF p{plan['页码']['pdf'][0]}–{plan['页码']['pdf'][1]}）",
                "定位": intros.get(name, "")}
        if plan.get("合章"):
            card["合章"] = plan["合章"]
        cards.append(card)

    cards = merge_same_chapter(cards)

    jpath = os.path.join(args.out, "cards.json")
    json.dump(cards, open(jpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    lines = ["# 专业卡（紧凑层）", "",
             f"共 {len(cards)} 条；有培养方案画像的 {sum(1 for c in cards if c.get('核心必修课'))} 条；"
             f"带定位句的 {sum(1 for c in cards if c.get('定位'))} 条。", ""]
    for c in cards:
        head = f"### {c['院系']} / {c['专业']}"
        lines.append(head)
        meta = [f"{c.get('专业代码', '')}", f"{c.get('门类', '')}{c.get('专业类', '')}".strip(),
                f"学制 {c.get('修业年限', '?')} 年", f"{c.get('学位门类', '')}学士",
                f"类别 {c.get('类别', '')}", f"卷 {c.get('卷', '')}".strip()]
        lines.append("｜".join(x for x in meta if x.strip()))
        if c.get("目录专业名") and c["目录专业名"] != c["专业"]:
            lines.append(f"- 专业目录写作：{c['目录专业名']}；检索别名：{'、'.join(c.get('检索别名', []))}")
        if c.get("目录条目"):
            lines.append("- 这一份培养方案覆盖 %d 个专业目录条目：%s" % (
                len(c["目录条目"]),
                "；".join(f"{e['目录专业名']}（{e['专业代码']}）" for e in c["目录条目"])))
        if c.get("定位"):
            lines.append(f"- 定位：{c['定位']}")
        if c.get("合章"):
            lines.append(f"- 合章：与 {'、'.join(c['合章'])} 印在同一章、共用一份培养方案（课程表相同）")
        if c.get("毕业总学分"):
            lines.append(f"- 毕业总学分：{c['毕业总学分']}；专业必修（方案原文）：{c.get('专业必修_方案原文')}")
        if c.get("学分结构"):
            lines.append(f"- 学分结构：{c['学分结构']}")
        if c.get("公共基础课程"):
            lines.append(f"- 公共基础课程（全校统一，明细见 public_courses.json）：{c['公共基础课程']}")
        if c.get("核心必修课"):
            lines.append(f"- 代表性必修课：{'、'.join(c['核心必修课'])}")
        if c.get("数学底子"):
            lines.append(f"- 数学底子：{c['数学底子']}")
        if c.get("计算底子"):
            lines.append(f"- 计算底子：{c['计算底子']}")
        lines.append(f"- 来源：{c.get('来源页')}")
        lines.append("")
    mpath = os.path.join(args.out, "CARDS.md")
    open(mpath, "w", encoding="utf-8").write("\n".join(lines))

    print(f"cards={len(cards)} intros={len(intros)}")
    print(f"cards.json {os.path.getsize(jpath)/1024:.0f} KB, CARDS.md {os.path.getsize(mpath)/1024:.0f} KB")


if __name__ == "__main__":
    main()
