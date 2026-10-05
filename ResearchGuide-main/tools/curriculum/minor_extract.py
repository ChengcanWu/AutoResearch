# -*- coding: utf-8 -*-
"""辅修 / 双专业培养方案（2025）→ 知识层。

和主修卷的区别（所以单独一个工具）：
  · 一个章节 = 一个「XX专业双专业」或「XX专业辅修」，同一专业两个身份各一章；
  · 没有「毕业总学分」，只有「双专业要求的总学分」「辅修专业总学分」+ 必修/选修学分；
  · 课程表只有 专业必修课 / 专业选修课 两类，外加「说明」后面跟的**替代课程表**
    （主修已修过必修课时改修这些），替代课不能算进必修学分；
  · 页眉左边是「院系名 + 书内页码」，直接给出院系归属与页码偏移。

用法:
  python tools/curriculum/minor_extract.py --pdf "<辅修双专业.pdf>" --out knowledge/minor
  python tools/curriculum/minor_extract.py --out knowledge/minor --batches 4 --batch-dir .work/minor_distill
  python tools/curriculum/minor_extract.py --out knowledge/minor --cards [--intros <intros.json>]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_curriculum import (  # noqa: E402
    _heading_label, clean_cell, course_rows, squeeze, table_is_course, slug,
)

FACULTY_HEAD_RE = re.compile(
    r"^([\u4e00-\u9fa5]{1,20}?(?:学院|学系|系|中心|研究院|学部|教研部)"
    r"(?:[\u4e00-\u9fa5]{2,20}?(?:系|学院|中心))?)(\d{1,4})$")
PAGE_HEAD_RE = re.compile(r"^(\d{1,4})北京大学")
SECTION_RE = re.compile(r"([\u4e00-\u9fa5A-Za-z0-9（）()、·+～\-\s]{2,60}?专[业]?)(双专业|辅修)")
TOTAL_RE = re.compile(
    r"(?:要求的总学分|总学分)\s*[：:]\s*([≥≤><=]{0,2}\s*[\d.]+(?:\s*[～~\-]\s*[\d.]+)?)\s*学分")
MUST_RE = re.compile(
    r"必修(?:课程|课)?\s*[：:]?\s*([≥≤><=]{0,2}\s*[\d.]+(?:\s*[～~\-]\s*[\d.]+)?)\s*学分")
ELECT_RE = re.compile(
    r"选修(?:课程|课)?\s*[：:]?\s*([≥≤><=]{0,2}\s*[\d.]+(?:\s*[～~\-]\s*[\d.]+)?)\s*学分")
DEGREE_RE = re.compile(r"授予([\u4e00-\u9fa5]{2,14}?学位)")
PROSE_HEADS = ("专业简介", "培养目标", "培养要求", "修业要求", "获得双专业要求",
               "获得辅修专业毕业要求", "获得辅修证书要求", "获得双学位要求", "修读要求")
BAD_NAME_PREFIX = ("获得", "不能", "可以", "须", "未", "若", "需", "如", "该", "本", "其",
                   "以上", "学生", "第", "同时", "并", "从")
TOC_ROW_RE = re.compile(r"^([\u4e00-\u9fa5]{2,20}?)[·•\s]{3,}[（(](\d{1,4})[）)]$")
# 只有这些行才是在引出替代表（正文里叙述「…修读其他课程替代。」不算）
ALT_HEAD_RE = re.compile(r"^(说明|附[：:]|注[：:]|可替代课程|替代课程|替代课列表)")


def norm_major(name: str) -> str:
    """掐掉标题里可能带上的院系前缀，再抹掉名字末尾多出来的「专」「专业」。"""
    s = re.sub(r"^北京大学[\u4e00-\u9fa5]{0,12}?(?:学院|学系|系|中心|研究院|学部)?", "", name.strip())
    s = re.sub(r"\s+", " ", s)
    return re.sub(r"专(业)?$", "", s).strip()


def usable_name(name: str) -> bool:
    return len(name) >= 2 and not name.startswith(BAD_NAME_PREFIX)


def headings_of(line: str) -> list[tuple[str, str]]:
    """整行必须是「XX专业双专业」这类标题（可以一行两个，也可以跟一句括号说明）。

    只要求「匹配处出现在行首或标点之后」是不够的：说明段落里出现「…汉语言文学专业双专业…」
    会凭空多切出一个章节，把后面的内容全抢走。所以这里要求标题铺满整行。
    """
    s = squeeze(line)
    if not s or len(s) > 60:
        return []
    hits: list[tuple[str, str]] = []
    pos = 0
    for sm in SECTION_RE.finditer(s):
        if sm.start() != pos:
            return []
        name = norm_major(sm.group(1))
        if not usable_name(name):
            return []
        hits.append((name, sm.group(2)))
        pos = sm.end()
    if not hits:
        return []
    rest = s[pos:]
    if rest and not rest.startswith("（"):
        return []
    return hits


def parse_minor_toc(pdf, pages: range) -> list[tuple[str, int]]:
    """辅修卷目录：院系名 + 书内起始页。用来给章节定院系（页眉只印在奇数页上，不可靠）。"""
    rows: list[tuple[str, int]] = []
    for pno in pages:
        for line in pdf.pages[pno - 1].extract_text_lines() or []:
            s = squeeze(line["text"])
            m = TOC_ROW_RE.match(s)
            if m and not m.group(1).endswith("部"):
                rows.append((m.group(1), int(m.group(2))))
    return rows


MAYBE_EMPTY = ("实践总学时", "总学时", "选课学期")


def _collapse(row: list) -> list[str]:
    """一行里空的（None 与 ''）全丢掉。

    这本 PDF 的表格列是合并单元格，而**表头行和数据行的空法不一样**：
    数据行里被合并的格子是 None，表头行里则是一堆 ''，另外表头还常常多一个行首空格子。
    只有把 None 和 '' 都丢掉，表头与数据行才会落到同一个列序上（否则课程名会取到学分那一列）。
    """
    out: list[str] = []
    for x in row:
        if x is None:
            continue
        c = str(x).replace("\n", " ").strip()
        if c and c != "nan":
            out.append(c)
    return out


def _align(cells: list[str], head: list[str]) -> list[str]:
    """数据行比表头短，说明丢的是「实践总学时 / 选课学期」这种可以空着的列，补回占位。"""
    miss = len(head) - len(cells)
    if miss <= 0:
        return cells
    out = list(cells)
    for name in reversed(MAYBE_EMPTY):
        if miss <= 0 or name not in head:
            continue
        i = head.index(name)
        if i <= len(out):
            out.insert(i, "")
            miss -= 1
    while len(out) < len(head):
        out.append("")
    return out


def loose_courses(rows: list[list]) -> list[dict]:
    """合并单元格表格 → 课程列表。

    再把「一行塞两门课」（课号 A\\nB + 名称 A\\nB + 学分 4\\n4）拆成两行。
    """
    if not rows:
        return []
    head = _collapse(rows[0])
    idx = {squeeze(h): i for i, h in enumerate(head)}
    ci, ni = idx.get("课号"), idx.get("课程名称")
    body: list[list[str]] = []
    for r in rows[1:]:
        cells = _align(_collapse(r), head)
        code = cells[ci] if ci is not None and ci < len(cells) else ""
        codes = code.split()
        names = (cells[ni] if ni is not None and ni < len(cells) else "").split()
        if len(codes) > 1 and len(names) == len(codes):
            for k, (c_, n_) in enumerate(zip(codes, names)):
                rr = list(cells)
                rr[ci], rr[ni] = c_, n_
                for col, i in idx.items():
                    if col in ("学分", "周学时", "实践总学时", "总学时") and i < len(rr):
                        vals = rr[i].split()
                        if len(vals) == len(codes):
                            rr[i] = vals[k]
                body.append(rr)
        else:
            body.append(cells)
    return course_rows([head] + body)


def scan(pdf) -> list[dict]:
    """把整本 PDF 摊成有序条目流（标题/表格/正文按纵向顺序），顺路切出章节。

    页眉有两种写法：奇数页「院 系 名 + 书内页码」（字间常带空格：物 理 学 院 7），
    偶数页「书内页码 + 书名」。章节首页干脆没有页眉，所以页码偏移量取观测值的众数来推。
    """
    # 第一遍：只为拿页眉信息（院系归属 + 页码偏移）。院系名只印在奇数页页眉上，
    # 而章节首页没有页眉，所以院系要用「它之后最近的已知页眉」倒推，
    # 否则会把上一章的院系带过去（生物科学专业就被算成了化学与分子工程学院）。
    known: dict[int, str] = {}
    obs: list[int] = []
    n = len(pdf.pages)
    for pno in range(1, n + 1):
        for line in pdf.pages[pno - 1].extract_text_lines() or []:
            if line["top"] >= 80:
                continue
            flat = re.sub(r"\s+", "", squeeze(line["text"]))
            m = FACULTY_HEAD_RE.match(flat)
            if m and pno > 12:
                known[pno] = m.group(1)
                obs.append(pno - int(m.group(2)))
                break
            m = PAGE_HEAD_RE.match(flat)
            if m and pno > 12:
                obs.append(pno - int(m.group(1)))
                break
    kp = sorted(known)
    fac_of: dict[int, str] = {}
    for pno in range(1, n + 1):
        nxt = [p for p in kp if p >= pno]
        fac_of[pno] = known[nxt[0]] if nxt else (known[kp[-1]] if kp else "")
    off = Counter(obs).most_common(1)[0][0] if obs else 0

    # 目录更权威：院系 = 目录里起始页 ≤ 本章节书内页 的最后一个院系。
    toc = parse_minor_toc(pdf, range(11, 13))

    def faculty_for(printed: int, pno: int) -> str:
        best, best_start = "", -1
        for name, start in toc:
            if start <= printed and start > best_start:
                best, best_start = name, start
        return best or fac_of.get(pno, "")

    sections: list[dict] = []
    cur: dict | None = None
    alt = False                      # 「说明」后面的替代课程表
    mod = ""                         # 当前模块名，跨页要留着（续表的页面上没有标题）
    for pno in range(1, len(pdf.pages) + 1):
        page = pdf.pages[pno - 1]
        items: list[tuple[float, str, object]] = []
        for line in page.extract_text_lines() or []:
            s = squeeze(line["text"])
            if not s:
                continue
            flat = re.sub(r"\s+", "", s)
            if line["top"] < 80 and pno > 12 and (
                    FACULTY_HEAD_RE.match(flat) or PAGE_HEAD_RE.match(flat)):
                continue
            secs = headings_of(s)
            if secs:
                # 「国际政治专业双专业 外交学专业双专业」这种一行两章共用一套课程表，
                # 拆成两章只会让后一章把课程全抢走（国际政治就变成空章节消失了），
                # 所以并成一章，名字用顿号连起来，跟主修卷的处理一致。
                name = "、".join(n for n, _ in secs)
                kindname = secs[0][1]
                items.append((line["top"], "section", (name, kindname)))
            else:
                items.append((line["top"], "text", s))
        for table in page.find_tables():
            rows = table.extract()
            if rows and table_is_course(rows):
                items.append((table.bbox[1], "table", rows))

        for _, kind, payload in sorted(items, key=lambda x: x[0]):
            if kind == "section":
                name, kindname = payload                        # type: ignore[misc]
                cur = {"院系": faculty_for(pno - off, pno), "专业": name, "类型": kindname,
                       "课程表": [], "替代课程": [], "说明": [], "文本": [], "页": [pno, pno]}
                sections.append(cur)
                alt, mod = False, ""
                continue
            if cur is None:
                continue
            cur["页"][1] = pno
            if kind == "table":
                courses = loose_courses(payload)                  # type: ignore[arg-type]
                if not courses:
                    continue
                if alt:
                    cur["替代课程"].extend(courses)
                elif cur["课程表"] and cur["课程表"][-1]["模块"] == (mod or "课程"):
                    cur["课程表"][-1]["课程"].extend(courses)
                else:
                    cur["课程表"].append({"模块": mod or "课程", "课程": courses})
                continue
            s = str(payload)
            label = _heading_label(s)
            if label:
                mod, alt = label, False
            # 「主修修过同名课就不要重复修，须从选修里挑别的替代」这种正文里也有「替代」二字，
            # 一律当替代表开关的话，紧随其后的必修表会被整张搬进替代课里去。
            if ALT_HEAD_RE.match(s):
                alt = True
            if s.startswith("说明"):
                cur["说明"].append(s)
            cur["文本"].append(s)

    for s in sections:
        s["书内"] = [s["页"][0] - off, s["页"][1] - off]
        s["pdf"] = list(s["页"])
        del s["页"]
    return sections


def parse_credits(section: dict) -> None:
    text = "\n".join(section["文本"])
    m = TOTAL_RE.search(text)
    section["总学分"] = (m.group(1) + "学分") if m else None
    m = MUST_RE.search(text)
    section["必修学分"] = (m.group(1) + "学分") if m else None
    m = ELECT_RE.search(text)
    section["选修学分"] = (m.group(1) + "学分") if m else None
    m = DEGREE_RE.search(text)
    section["授予学位"] = m.group(1) if m else None
    # 修读要求：四、获得双专业要求 / 获得辅修专业毕业要求 / 修业要求 那一段
    buf, inside = [], False
    for s in section["文本"]:
        mm = re.match(r"^[一二三四五六七八九十]+、\s*(.+)$", s)
        if mm:
            title = squeeze(mm.group(1))
            inside = any(title.startswith(h) for h in ("获得", "修业要求", "修读要求"))
            if inside:
                continue
            if title.startswith(("课程设置", "授予学位")):
                break
        if inside:
            buf.append(s)
    section["获得要求"] = squeeze("".join(buf))[:400]
    # 简介 / 培养目标 / 培养要求 原文（只给蒸馏用）
    for head, key in (("专业简介", "简介原文"), ("培养目标", "培养目标原文"), ("培养要求", "培养要求原文")):
        buf, inside = [], False
        for s in section["文本"]:
            mm = re.match(r"^[一二三四五六七八九十]+、\s*(.+)$", s)
            if mm:
                title = squeeze(mm.group(1))
                inside = title.startswith(head)
                if inside:
                    continue
                if any(title.startswith(h) for h in PROSE_HEADS) and inside is False and buf:
                    break
            if inside:
                buf.append(s)
        section[key] = squeeze("".join(buf))[:700]


def core_courses(section: dict, limit: int = 10) -> list[str]:
    """核心课程 = 必修区（模块编号 1.x，或标题里写着「必修」）的课。

    只按「必修」两个字找会漏：历史学系把必修拆成「1.1 专业核心课练习课组」这种子模块；
    反过来，辅修卷里有的章节（法学、社会学…）压根没有模块标题，整张表都是必修，那就全收。
    """
    skip = ("思想政治", "大学英语", "军事理论", "体育", "心理健康", "通识", "劳动教育")

    def is_must(label: str) -> bool:
        return "必修" in label or bool(re.match(r"^1([.\-]|$)", label.strip()))

    mods = section["课程表"]
    must = [m for m in mods if is_must(m["模块"])]
    if not must and section.get("类型") == "辅修":
        must = mods                                  # 辅修没标模块，整表就是必修
    out: list[str] = []
    for mod in must:
        for c in mod["课程"]:
            name = c.get("课程名称", "")
            if any(s in name for s in skip) or name in out:
                continue
            out.append(name)
            if len(out) >= limit:
                return out
    return out


def dup_keys(sections: list[dict]) -> set[tuple[str, str]]:
    """同名专业在不同院系各有一份方案（环境科学在城环和工学院都有）——这些 key 要带院系。"""
    c = Counter((s["专业"], s["类型"]) for s in sections)
    return {k for k, v in c.items() if v > 1}


def card_key(s: dict, dups: set[tuple[str, str]]) -> str:
    base = f"{s['专业']}（{s['类型']}）"
    return f"{s['院系']} {base}" if (s["专业"], s["类型"]) in dups else base


def write_layer(out: str, sections: list[dict]) -> None:
    os.makedirs(os.path.join(out, "plans"), exist_ok=True)
    catalog = []
    for s in sections:
        s["核心课程"] = core_courses(s)
        # 文件名带上院系：光用「专业+类型」两个院系同名时会互相覆盖，白白丢方案
        fn = slug(f"{s['院系']}-{s['专业']}专业{s['类型']}") + ".json"
        json.dump(s, open(os.path.join(out, "plans", fn), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        catalog.append({"院系": s["院系"], "专业": s["专业"], "类型": s["类型"],
                        "总学分": s["总学分"], "必修学分": s["必修学分"], "选修学分": s["选修学分"],
                        "授予学位": s["授予学位"], "课程数": sum(len(m["课程"]) for m in s["课程表"]),
                        "替代课程数": len(s["替代课程"]),
                        "来源页": "书内 p%s–%s（PDF p%s–%s）" % (s["书内"][0], s["书内"][1],
                                                                s["pdf"][0], s["pdf"][1])})
    catalog.sort(key=lambda r: (r["院系"], r["专业"], r["类型"]))
    json.dump(catalog, open(os.path.join(out, "catalog.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("章节 %d：双专业 %d · 辅修 %d；院系 %d" % (
        len(sections),
        sum(1 for s in sections if s["类型"] == "双专业"),
        sum(1 for s in sections if s["类型"] == "辅修"),
        len({s["院系"] for s in sections})))


def load_sections(out: str) -> list[dict]:
    return [json.load(open(os.path.join(out, "plans", fn), encoding="utf-8"))
            for fn in sorted(os.listdir(os.path.join(out, "plans"))) if fn.endswith(".json")]


def write_batches(out: str, batch_dir: str, n: int) -> None:
    os.makedirs(batch_dir, exist_ok=True)
    secs = load_sections(out)
    dups = dup_keys(secs)
    items = [(card_key(s, dups), {
        "院系": s["院系"], "类型": s["类型"], "总学分": s["总学分"],
        "简介原文": s.get("简介原文", ""), "培养目标原文": s.get("培养目标原文", ""),
        "核心课程": s.get("核心课程", []),
    }) for s in secs]
    size = (len(items) + n - 1) // n
    for i in range(n):
        chunk = dict(items[i * size:(i + 1) * size])
        if chunk:
            json.dump(chunk, open(os.path.join(batch_dir, f"batch_{i + 1}.json"), "w",
                                  encoding="utf-8"), ensure_ascii=False, indent=1)
            print("batch_%d.json: %d 条" % (i + 1, len(chunk)))


def write_cards(out: str, intros: dict) -> None:
    secs = load_sections(out)
    dups = dup_keys(secs)
    rows = []
    for s in secs:
        rows.append({
            "院系": s["院系"], "专业": s["专业"], "类型": s["类型"],
            "总学分": s["总学分"], "必修学分": s["必修学分"], "选修学分": s["选修学分"],
            "授予学位": s["授予学位"],
            "定位": intros.get(card_key(s, dups), ""),
            "核心课程": s.get("核心课程", []),
            "替代课程": [c["课程名称"] for c in s.get("替代课程", [])][:10],
            "修读要求": (s.get("获得要求") or "")[:200],
            "来源页": "书内 p%s（PDF p%s–%s）" % (s["书内"][0], s["pdf"][0], s["pdf"][1]),
        })
    rows.sort(key=lambda r: (r["院系"], r["专业"], r["类型"]))
    json.dump(rows, open(os.path.join(out, "cards.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    lines = ["# 辅修 / 双专业卡", "",
             f"共 {len(rows)} 条（双专业 {sum(1 for r in rows if r['类型'] == '双专业')} · "
             f"辅修 {sum(1 for r in rows if r['类型'] == '辅修')}）", ""]
    for r in rows:
        lines.append(f"### {r['院系']} / {r['专业']}（{r['类型']}）")
        lines.append("｜".join(x for x in [f"总学分 {r['总学分'] or '?'}",
                                           f"必修 {r['必修学分'] or '?'}",
                                           f"选修 {r['选修学分'] or '?'}",
                                           r["授予学位"] or ""] if x))
        if r["定位"]:
            lines.append(f"- 定位：{r['定位']}")
        if r["核心课程"]:
            lines.append(f"- 核心课程：{'、'.join(r['核心课程'])}")
        if r["替代课程"]:
            lines.append(f"- 替代课程（主修已修过必修课时改修）：{'、'.join(r['替代课程'])}")
        if r["修读要求"]:
            lines.append(f"- 修读要求：{r['修读要求']}")
        lines.append(f"- 来源：{r['来源页']}")
        lines.append("")
    open(os.path.join(out, "CARDS.md"), "w", encoding="utf-8").write("\n".join(lines))
    print("cards.json %d 条（带定位 %d）" % (len(rows), sum(1 for r in rows if r["定位"])))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--batches", type=int, default=0)
    ap.add_argument("--batch-dir", default="")
    ap.add_argument("--cards", action="store_true")
    ap.add_argument("--intros", default="")
    a = ap.parse_args()

    if a.pdf:
        import pdfplumber
        with pdfplumber.open(a.pdf) as pdf:
            sections = scan(pdf)
        for s in sections:
            parse_credits(s)
        sections = [s for s in sections if s["课程表"] or s["总学分"]]
        write_layer(a.out, sections)
    if a.batches and a.batch_dir:
        write_batches(a.out, a.batch_dir, a.batches)
    if a.cards:
        intros = json.load(open(a.intros, encoding="utf-8")) if a.intros else {}
        write_cards(a.out, intros)


if __name__ == "__main__":
    main()
