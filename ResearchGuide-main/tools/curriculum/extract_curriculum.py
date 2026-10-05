# -*- coding: utf-8 -*-
"""培养方案 PDF → 院系-专业结构化知识库。

输入：《北京大学本科培养方案》PDF（含专业目录表 + 各院系专业培养方案章节）
输出：
  catalog.json       院系 × 专业 骨架（专业代码 / 门类 / 专业类 / 学位 / 修业年限）
  sections.json      章节表：学部 → 院系 → 专业，带书内页码与 PDF 页码区间
  plans/*.json       单个专业：学分结构、按模块归类的课程表、课程结构指纹
  fingerprints.json  所有专业的课程结构指纹汇总（给检索/匹配用的小文件）
  course_index.json  课程 → 哪些专业必修它（反查用）

纪律：只抽原文；抽不到就留空，不补不猜。
用法：
  python extract_curriculum.py --pdf <pdf> --out <dir> [--only 经济学专业,...] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict

import pdfplumber

# ---------------- 文本清理 ----------------

def squeeze(s: str | None) -> str:
    return re.sub(r"\s+", "", s or "")


def clean_cell(s: str | None) -> str:
    if s is None:
        return ""
    return re.sub(r"[ \t\u00a0　]+", " ", s.replace("\n", "")).strip()


# ---------------- 页码 ----------------

PAGE_NO_RE = re.compile(r"[·•]\s*(\d{1,4})\s*[·•]")


def printed_page_no(page) -> int | None:
    """取书内页码（页眉/页脚里的 ·N·）。只看页眉页脚几行，避免正文数字干扰。"""
    lines = [l for l in (page.extract_text() or "").split("\n") if l.strip()]
    if not lines:
        return None
    zones = lines[:2] + lines[-2:]
    for line in zones:
        hits = PAGE_NO_RE.findall(line)
        if hits:
            return int(hits[0])
    return None


# ---------------- 一、专业目录骨架 ----------------

CATALOG_KEYS = ("所属院系", "专业代码", "专业名称")


def parse_catalog(pdf) -> tuple[list[dict], list[int]]:
    """专业目录是连续几页的同一张表：表头每页重复，院系名只在首行出现。"""
    rows: list[dict] = []
    pages: list[int] = []
    started = False
    for page in pdf.pages:
        text = page.extract_text() or ""
        if not started:
            if "本科专业目录" not in squeeze(text[:200]):
                continue
            started = True
        tables = [t for t in page.extract_tables()
                  if t and all(k in squeeze("".join(c or "" for c in t[0])) for k in CATALOG_KEYS)]
        if not tables and pages:
            break                                  # 目录表结束
        for table in tables:
            pages.append(page.page_number)
            dept = ""
            for row in table[1:]:
                cells = [clean_cell(c) for c in row]
                if len(cells) < 7:
                    continue
                if cells[0]:
                    dept = squeeze(cells[0])
                code = squeeze(cells[3])
                if not re.fullmatch(r"\d{6}[TK]?", code):
                    continue
                rows.append({
                    "院系": dept,
                    "门类": squeeze(cells[1]),
                    "专业类": squeeze(cells[2]),
                    "专业代码": code,
                    "专业名称": squeeze(cells[4]),
                    "修业年限": squeeze(cells[5]),
                    "学位授予门类": squeeze(cells[6]),
                    "来源页": page.page_number,
                })
    return rows, pages


# ---------------- 二、目录（章节表） ----------------

TOC_ENTRY_RE = re.compile(r"^(?P<name>.+?)[·.⋯\s]{3,}（(?P<page>\d{1,4})）\s*$")
FACULTY_GROUP_RE = re.compile(r"^[\u4e00-\u9fa5\s]{0,8}(学部|类)$")
GROUP_PREFIX_RE = re.compile(r"^[\u4e00-\u9fa5]{0,8}(?:学部|类)(?=北京大学)")


def parse_toc(pdf) -> list[dict]:
    """目录页 = 含「目 录」的那页起，到专业目录页前一页止。"""
    toc_pages: list[int] = []
    started = False
    for page in pdf.pages[:12]:
        text = page.extract_text() or ""
        head = squeeze((text.split("\n") or [""])[0])
        if not started and head.startswith("目录"):
            started = True
        elif not started:
            continue
        if toc_pages and "本科专业目录" in squeeze(text[:200]):
            break                                  # 目录页结束，进入专业目录表
        toc_pages.append(page.page_number)

    entries: list[dict] = []
    for pno in toc_pages:
        text = pdf.pages[pno - 1].extract_text() or ""
        pending = ""
        for raw in text.split("\n"):
            line = raw.strip()
            if not line:
                continue
            s = squeeze(line)
            if s.startswith("目录") or "北京大学本科培养方案" in s:
                continue                            # 页眉 / 「目 录」
            if FACULTY_GROUP_RE.match(s) and not re.search(r"\d", s):
                entries.append({"kind": "group", "name": s, "printed": None})
                pending = ""
                continue
            m = TOC_ENTRY_RE.match(line)
            if not m:
                pending += s                        # 折行的条目名，先攒着
                continue
            name = (pending + m.group("name")).strip()
            pending = ""
            # 目录里有的行把学部名和院系名连在一起印（「理学部北京大学数学科学学院」
            # 「工学部北京大学工学院」），不剥掉的话这种行会当成一个「专业」混进卡片里。
            name = GROUP_PREFIX_RE.sub("", name)
            kind = "dept" if name.startswith("北京大学") else "major"
            if kind == "dept":
                name = name[4:]                      # 跟专业目录表里的院系名对齐（不带校名）
            entries.append({"kind": kind, "name": name, "printed": int(m.group("page"))})
    return entries


# ---------------- 三、页码映射 ----------------

def build_page_map(pdf) -> tuple[dict[int, int], int]:
    """书内页码 → PDF 页码。偏移取众数，个别缺页用众数偏移补。"""
    pairs = {}
    for page in pdf.pages:
        n = printed_page_no(page)
        if n is not None and n not in pairs:
            pairs[n] = page.page_number
    if not pairs:
        return {}, 0
    offset = Counter(p - n for n, p in pairs.items()).most_common(1)[0][0]
    full = {n: (pairs.get(n) or n + offset) for n in range(1, max(pairs) + 1)}
    return full, offset


# ---------------- 四、单个专业章节 ----------------

HEADING_RE = re.compile(r"^[一二三四五六七八九十]+、\s*(.+)$")
MODULE_RE = re.compile(
    r"^(?P<code>\d+(?:[.\-]\d+)*)\s*[.．、]?\s*(?P<name>[^：:0-9]{2,24}?)"
    r"\s*[：:]?\s*(?P<credit>\d+(?:\.\d+)?(?:\s*[～~\-]\s*\d+(?:\.\d+)?)?)\s*(?P<unit>学分|学时)"
)
# 学分结构那一栏是两列排的，一行里可能同时出现「2．专业必修课程：51 学分」和「2-2 专业核心课：10 学分」，
# 所以这里不做行首锚定，改成在整行里全部找出。
CREDIT_ITEM_RE = re.compile(
    r"(?P<code>\d+(?:-\d+)*)\s*[.．、]?\s*(?P<name>[\u4e00-\u9fa5（）()A-Za-z·]{2,24}?)"
    r"\s*[：:]\s*(?P<credit>\d+(?:\.\d+)?(?:\s*[～~\-]\s*\d+(?:\.\d+)?)?)\s*(?P<unit>学分|学时)"
)
COURSE_CODE_RE = re.compile(r"^\d{8}$")


def table_is_course(table: list[list[str]]) -> bool:
    head = squeeze("".join(c or "" for c in table[0])) if table else ""
    return "课号" in head and "课程名称" in head


def course_rows(table: list[list[str]]) -> list[dict]:
    cols = [squeeze(c) for c in table[0]]
    idx = {name: i for i, name in enumerate(cols)}
    out: list[dict] = []
    for row in table[1:]:
        cells = [clean_cell(c) for c in row]
        code = squeeze(cells[idx["课号"]]) if idx.get("课号", 99) < len(cells) else ""
        if not COURSE_CODE_RE.match(code):
            continue
        item = {"课号": code, "课程名称": squeeze(cells[idx["课程名称"]]) if idx.get("课程名称", 99) < len(cells) else ""}
        for key in ("课程性质", "学分", "总学时", "实践总学时", "选课学期", "周学时"):
            i = idx.get(key)
            if i is not None and i < len(cells) and cells[i]:
                item[key] = squeeze(cells[i])
        out.append(item)
    return out


TOTAL_RE = re.compile(r"毕业总学分\s*[:：]\s*(.+)$")
TOTAL_FALLBACK_RE = re.compile(r"修满(?:培养方案规定的)?\s*([\d.]+(?:\s*[～~\-]\s*[\d.]+)?\s*学分)")
DEGREE_RE = re.compile(r"授予学位(?:类型|名称)?\s*[:：]\s*(.+)$")
DEGREE_FALLBACK_RE = re.compile(r"授予([\u4e00-\u9fa5]{2,10}?)学位")


def parse_credit_structure(text: str) -> dict:
    """只吃「四、毕业要求」到「五、课程设置」之间的学分结构。

    同一件事各院系写法不一（毕业总学分 / 须修满 N 学分方能毕业；授予学位类型 / 授予学位名称），
    按主表达式优先、兜底表达式补位；原文没写就留空。
    """
    lines = text.split("\n")
    buf, inside = [], False
    for raw in lines:
        s = squeeze(raw)
        m = HEADING_RE.match(s)
        if m:
            title = squeeze(m.group(1))
            if title.startswith("毕业要求"):
                inside = True
                continue
            if title.startswith("课程设置") or title.startswith("课程地图"):
                inside = False
        if inside:
            buf.append(s)

    structure: dict[str, str] = {}
    total = degree = None
    for s in buf:
        if total is None:
            m = TOTAL_RE.search(s) or TOTAL_FALLBACK_RE.search(s)
            if m:
                total = m.group(1)
        if degree is None and "符合学士学位授予条件" not in s:
            m = DEGREE_RE.search(s)
            if m and m.group(1).strip():
                degree = m.group(1).strip()
            else:
                m = DEGREE_FALLBACK_RE.search(s)
                if m and m.group(1) not in ("学士", "硕士", "博士"):
                    degree = f"{m.group(1)}学位"
        m = MODULE_RE.match(s)
        if m:
            structure[f"{m.group('code')} {m.group('name')}"] = f"{m.group('credit')}{m.group('unit')}"
        for m in CREDIT_ITEM_RE.finditer(s):
            structure[f"{m.group('code')} {m.group('name')}"] = f"{m.group('credit')}{m.group('unit')}"
    ordered = dict(sorted(structure.items(), key=lambda kv: _module_sort_key(kv[0])))
    # 有些院系把这两句写成散文，而且被排版断行（「达到学位要求者授 / 予法学学士学位。」），
    # 所以行内匹配失败时，再在整段里去换行找一次。先删掉那句全校统一的套话，否则会抽出「学士学位」。
    joined = "".join(buf)
    for boiler in ("符合学士学位授予条件的，授予学士学位。", "符合学士学位授予条件的,授予学士学位。",
                   "符合学士学位授予条件的，授予学士学位", "授予学士学位。"):
        joined = joined.replace(boiler, "")
    if total is None:
        m = TOTAL_FALLBACK_RE.search(joined)
        if m:
            total = m.group(1)
    if degree is None:
        # 只在这个字段和「毕业总学分」之间找，避免把后面的「毕业总学分」当成学位名
        tail = joined.split("毕业总学分")[0]
        m = re.search(r"授予学位(?:类型|名称)?\s*[:：]\s*([\u4e00-\u9fa5]{2,12})", tail)
        if m and m.group(1) not in ("学士", "硕士", "博士"):
            degree = m.group(1)
        else:
            m = DEGREE_FALLBACK_RE.search(tail)
            if m and m.group(1) not in ("学士", "硕士", "博士"):
                degree = f"{m.group(1)}学位"
    return {"毕业总学分": total, "授予学位": degree, "学分结构": ordered}


def _module_sort_key(label: str) -> tuple:
    """「1-2 思政选择性必修课」→ (1, 2)：让学分结构按培养方案的编号顺序排。"""
    head = label.split(" ", 1)[0]
    parts = re.split(r"[.\-]", head)
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return (99,)


def extract_section(pdf, start: int, end: int) -> dict:
    """按 PDF 页码区间抽一个专业：学分结构 + 按模块归类的课程表。

    模块按页内纵向顺序推进：表归到它上面最近的模块标题；跨页续表沿用上一页的模块。
    """
    modules: list[dict] = []
    current = "未归类"
    for pno in range(start, min(end, len(pdf.pages)) + 1):
        page = pdf.pages[pno - 1]
        current = _consume_page(page, current, modules)
    texts = "\n".join((pdf.pages[p - 1].extract_text() or "")
                      for p in range(start, min(end, len(pdf.pages)) + 1))
    struct = parse_credit_structure(texts)

    all_courses, seen = [], set()
    for m in modules:
        for c in m["课程"]:
            key = (c["课号"], c["课程名称"])
            if key in seen:
                continue
            seen.add(key)
            all_courses.append(c)
    return {"学分结构": struct, "课程表": modules, "课程数_去重": len(all_courses),
            "文字统计": text_stats(texts)}


# 公共基础课程（思政 / 体育 / 英语 / 信息科学 / 通识…）全校所有专业一样，
# 每个专业存一遍纯属重复，单独抽出来存一份。
#
# 只按「1 开头 + 明说公共」认，不能只看关键词：各章节编号体系不一样，项目类章节把自己的核心课
# 也从 1 开始编（古典语文学项目的「1-1 古希腊语拉丁语课程」、政治法律与社会项目的
# 「1-1 项目特设核心必修课」都是专业自己的课），而「2-4 实习/实践/劳动教育课」「3 体育课」
# 是专业必修/选修里带「劳动教育」「体育」字样的课，都不是公共基础课程。
PUBLIC_LABEL_RE = re.compile(
    r"公共必修|公共基础|全校必修|通识教育|大学英语|大学外语|信息科学课|军事理论|"
    r"国家安全|心理健康|思想政治|思政|大学成长课|体育课|劳动教育|与中国有关课程")
NON_PUBLIC_RE = re.compile(r"专业|项目|特设|核心|实践|实习|学科|讨论课")


def is_public_module(label: str) -> bool:
    lab = (label or "").strip()
    head = re.match(r"^(\d+)", lab)
    if head and head.group(1) != "1":                  # 2-x / 3-x 一律属于专业自己的课
        return False
    if NON_PUBLIC_RE.search(lab):
        return False
    return bool(PUBLIC_LABEL_RE.search(lab))


def own_prefixes(plan: dict, cover: float = 0.6) -> set[str]:
    """这个专业自己的课号前缀（覆盖 ≥60% 课程的那几个）。

    用课号自证归属：培养方案里既有「人文学部与其他院系的专业必修课」这种跨院系菜单，
    也有把本系课表错标到「1.2 通识教育课」下面的排版（历史学专业古典语文学项目就是这样），
    靠前缀分布才能判断一张表到底是谁的课。
    """
    cnt: Counter = Counter()
    for mod in plan.get("课程表", []):
        for c in mod.get("课程", []):
            if c.get("课号"):
                cnt[c["课号"][:4]] += 1
    total = sum(cnt.values())
    out, acc = set(), 0
    for p, n in cnt.most_common():
        out.add(p)
        acc += n
        if total and acc / total >= cover:
            break
    return out or set(cnt)


def module_is_public(mod: dict, own: set[str]) -> bool:
    """标签说是公共课，而且课号也确实不是本系开的，才当公共课摘走。"""
    if not is_public_module(mod.get("模块", "")):
        return False
    codes = [c.get("课号", "") for c in mod.get("课程", []) if c.get("课号")]
    if not codes or not own:
        return True
    share = sum(1 for c in codes if c[:4] in own) / len(codes)
    return share < 0.5


def plan_courses(plan: dict) -> list[dict]:
    """把模块化的课程表摊平成去重后的课程列表（原来单独存了一份 课程_去重，体积翻倍）。"""
    out, seen = [], set()
    for mod in plan.get("课程表", []):
        for c in mod.get("课程", []):
            k = (c.get("课号"), c.get("课程名称"))
            if k in seen:
                continue
            seen.add(k)
            out.append(c)
    return out


def professional_courses(plan: dict) -> list[dict]:
    """只要专业自己的课（去掉公共基础课程）。"""
    out, seen = [], set()
    for mod in plan.get("课程表", []):
        if is_public_module(mod.get("模块", "")):
            continue
        for c in mod.get("课程", []):
            k = (c.get("课号"), c.get("课程名称"))
            if k in seen:
                continue
            seen.add(k)
            out.append(c)
    return out


def split_public(plans: dict[str, dict], previous: dict | None = None) -> dict:
    """把 1.x 公共课模块从各专业里摘出来，合成一份全校共用的 public_courses.json。

    这些课每个专业都一样（思政 12 + 选择性必修 2 + 军事 2 + 国安 1 + 体育 4 + 心理 2 +
    劳动 32 学时 + 英语 2～8 + 信息科学 6 + 通识 12），存 100 遍没有任何信息增益。

    注意：`类别 == 公共课` 的章节（思政/体育/英语/信息科学/通识…）是这份共享数据的**来源**，
    原样保留，只把它们的学分结构登记进去。这个函数必须幂等：重复跑（--refingerprint）不能再动
    已经摘过一遍的 plans，也不能把已有的共享课表覆盖成空。

    所以重算时要传 `previous`（上一次的 public_courses.json）：已经摘过的 plans 里再也找不到
    「哪门课属于哪个专业」的证据了，只能从旧文件把 `出现于` 继承下来，否则重算一次就等于把
    归属信息全删了（实跑踩过：重算后 15 门共享课只剩 2 门，check_split 全线报错）。
    """
    shared: dict[str, dict] = {}
    struct_majors: dict[str, str] = {}
    struct_sections: dict[str, dict] = {}
    if previous:
        for v in previous.values():
            if not isinstance(v, dict) or "课号" not in v:
                continue
            shared[v["课号"]] = {"课号": v["课号"], "课程名称": v["课程名称"],
                                 "学分": v.get("学分", ""), "出现于": list(v.get("出现于") or [])}
        struct_majors.update(previous.get("_学分结构_各专业公共课") or {})
        struct_sections.update(previous.get("_公共课章节学分结构") or {})

    def add(mods: list[dict], owner: str) -> None:
        for mod in mods:
            for c in mod.get("课程", []):
                node = shared.setdefault(c["课号"], {"课号": c["课号"], "课程名称": c["课程名称"],
                                                     "学分": c.get("学分", ""), "出现于": []})
                node["出现于"].append(owner)

    for key, plan in plans.items():
        if plan.get("类别") == "公共课":
            add(plan.get("课程表", []), key)
            struct_sections[key] = plan.get("学分结构", {}).get("学分结构", {})
            continue
        kept, moved = [], []
        own = own_prefixes(plan)
        for mod in plan.get("课程表", []):
            (moved if module_is_public(mod, own) else kept).append(mod)
        struct = plan.get("学分结构", {}).get("学分结构", {})
        pub_keys = [k for k in struct if is_public_module(k)]
        for k in pub_keys:                             # 1-x 公共课小项（思政 12 / 体育 4 …）人人一份
            struct_majors.setdefault(k, struct[k])
            struct.pop(k, None)
        if not moved:
            continue
        plan["课程表"] = kept
        plan["公共基础课程_见"] = "public_courses.json"
        add(moved, key)

    for v in shared.values():
        owners = sorted(set(v.pop("出现于")))
        v["出现于专业数"] = len(owners)
        v["出现于"] = owners
        v["出现于样例"] = owners[:6]
    out: dict = dict(sorted(shared.items()))
    if struct_majors:
        out["_学分结构_各专业公共课"] = dict(sorted(struct_majors.items()))
    if struct_sections:
        out["_公共课章节学分结构"] = struct_sections
    return out


PROSE_HEADS = ("专业简介", "培养目标", "培养要求", "专业历史", "师资")
DATA_HEADS = ("毕业要求", "课程设置", "课程地图", "学分要求", "选课要求")


def text_stats(text: str) -> dict:
    """描述性文字（简介/目标/要求）与硬数据（学分结构/课程表）的字数比。

    这就是「挤水分」的量化口径：水分率 = 描述性字数 ÷ 全章字数。
    """
    prose = data = other = 0
    bucket = "other"
    for raw in text.split("\n"):
        s = squeeze(raw)
        if not s:
            continue
        m = HEADING_RE.match(s)
        if m:
            title = squeeze(m.group(1))
            if any(title.startswith(h) for h in DATA_HEADS):
                bucket = "data"
            elif any(title.startswith(h) for h in PROSE_HEADS):
                bucket = "prose"
            else:
                bucket = "other"
        n = len(s)
        if bucket == "prose":
            prose += n
        elif bucket == "data":
            data += n
        else:
            other += n
    total = prose + data + other
    return {"描述性字数": prose, "硬数据字数": data, "其他字数": other,
            "水分率": round(prose / total, 3) if total else None}


PLAIN_HEADING_RE = re.compile(r"^[\u4e00-\u9fa5（）()A-Za-z0-9]{2,18}(课程|课|组)\s*[：:]?$")
# 无编号的模块标题（辅修卷里写成「专业必修课：31学分」），名字里得有「课/组」才认，
# 免得把「辅修专业要求的总学分：31学分」这种行也当成模块标题。
PLAIN_CREDIT_HEAD_RE = re.compile(r"^(?P<name>[\u4e00-\u9fa5]{2,16})\s*[：:]\s*[\d.]+\s*学分$")


def _heading_label(text: str) -> str | None:
    """一行是不是模块标题？编号标题优先，其次「信息科学课程见下表」这类无编号标题。"""
    s = squeeze(text)
    if not s or len(s) > 40:
        return None
    m = MODULE_RE.match(s)
    if m and ("学分" in s or "学时" in s):
        return f"{m.group('code')} {m.group('name')}"
    m = PLAIN_CREDIT_HEAD_RE.match(s)
    if m and ("课" in m.group("name") or "组" in m.group("name")):
        return m.group("name")
    if s.endswith(("：", ":")) and PLAIN_HEADING_RE.match(s.rstrip("：:")):
        return s.rstrip("：:")
    if PLAIN_HEADING_RE.match(s) and ("见下表" in s or "如下" in s):
        return s.rstrip("：:")
    return None


def _consume_page(page, current: str, modules: list[dict]) -> str:
    """把一页里的标题与课程表按纵向顺序串起来，返回页末的当前模块。"""
    items: list[tuple[float, str, object]] = []
    for line in page.extract_text_lines() or []:
        label = _heading_label(line["text"])
        if label:
            items.append((line["top"], "heading", label))
    for table in page.find_tables():
        rows = table.extract()
        if not rows or not table_is_course(rows):
            continue
        items.append((table.bbox[1], "table", rows))
    for _, kind, payload in sorted(items, key=lambda x: x[0]):
        if kind == "heading":
            current = payload                       # type: ignore[assignment]
            continue
        courses = course_rows(payload)              # type: ignore[arg-type]
        if not courses:
            continue
        modules.append({"模块": current, "来源页": page.page_number,
                        "列": [clean_cell(c) for c in payload[0]],  # type: ignore[index]
                        "课程": courses})
    return current


# ---------------- 五、课程结构指纹 ----------------

TAGS: dict[str, tuple[str, ...]] = {
    "数学": ("高等数学", "数学分析", "线性代数", "概率", "统计", "微积分", "离散数学",
             "常微分", "数理", "代数", "几何", "运筹", "计量", "数学"),
    # 注意别放「信息」「数据」这种太宽的词：信息计量学、信息资源管理会被误判成计算课。
    "计算": ("计算概论", "程序设计", "程序", "数据结构", "算法", "人工智能", "机器学习",
             "数据库", "计算机", "软件", "编程", "数据分析", "数据科学", "智能计算"),
    "语言": ("英语", "日语", "德语", "法语", "俄语", "西班牙语", "葡萄牙语", "阿拉伯语",
             "朝鲜语", "泰语", "语言", "写作"),
    "实验实践": ("实验", "实习", "实践", "调查", "毕业论文", "毕业设计", "田野", "社会调查"),
}


def _credit_of(course: dict) -> float:
    m = re.match(r"(\d+(?:\.\d+)?)", course.get("学分", ""))
    return float(m.group(1)) if m else 0.0


def _prefix(code: str) -> str:
    return code[:4]


CREDIT_CAP_RE = re.compile(r"([\d.]+)(?:\s*[～~\-]\s*([\d.]+))?\s*学分")


def _module_cap(struct: dict, label: str) -> float | None:
    """模块的学分上限 = 培养方案自己给这个模块写的学分（区间取上限）。

    没有对应条目、或者写的是「至少 N 学分」「N 学时」时不封顶。
    """
    if not label:
        return None
    items = struct.get("学分结构", {})
    key = label.replace(".", "-", 1).split(" ")[0]
    for scope in (key, key.split("-")[0]):
        for k, v in items.items():
            if k.split(" ")[0] != scope:
                continue
            if "至少" in v or "学时" in v:
                return None
            m = CREDIT_CAP_RE.search(v)
            if m:
                return float(m.group(2) or m.group(1))
    return None


def _planned_must_credit(struct: dict) -> str | None:
    """培养方案自己写的「2 专业必修课程」学分——照抄，不推算，这是最不含糊的那个数。"""
    for k, v in struct.get("学分结构", {}).items():
        if k.split(" ")[0] == "2" and "必修" in k:
            return v
    return None


def fingerprint(modules: list[dict], struct: dict) -> dict:
    """课程结构指纹：只用必修课（选修是菜单，不是这个专业真正的底子）。

    - 必修课学分 / 门数 / 学期分布
    - 按课程名的能力标签（数学 / 计算 / 语言 / 实验实践）
    - 按课号前 4 位的开课单位分布（北大课号前几位对应开课院系，用数据自己学出来）

    **备选课要按模块封顶**：有的专业一个位置给一串可选课（「数学分析 / 数学分析（I） /
    高等数学 A / …」全标成专业必修），直接求和会得出「必修 147 学分」这种大于毕业总学分的数。
    所以逐模块按培养方案写的模块学分等比压缩，并置 `必修_含备选` 标记。
    """
    groups: dict[str, list[dict]] = {}
    for mod in modules:
        groups.setdefault(mod.get("模块") or "未归类", []).extend(mod.get("课程", []))

    # 有的专业课程表压根没有「课程性质」列——那张表列的就全是必修课，按全部课程计。
    any_must = any("必修" in c.get("课程性质", "")
                   for cs in groups.values() for c in cs)
    must_selector = (lambda c: "必修" in c.get("课程性质", "")) if any_must else (lambda c: True)

    must: list[dict] = []
    seen: set = set()
    tags: dict[str, float] = {t: 0.0 for t in TAGS}
    names: dict[str, list[str]] = {t: [] for t in TAGS}
    prefixes: dict[str, float] = {}
    raw_total = capped_total = 0.0
    has_alt = False

    for label, cs in groups.items():
        uniq = []
        for c in cs:
            k = (c["课号"], c["课程名称"])
            if k not in seen:
                seen.add(k)
                uniq.append(c)
        m = [c for c in uniq if must_selector(c)]
        if not m:
            continue
        raw = sum(_credit_of(c) for c in m)
        cap = _module_cap(struct, label)
        factor = 1.0
        if cap is not None and raw > cap + 0.05:
            factor = cap / raw
            has_alt = True
        raw_total += raw
        capped_total += raw * factor
        must.extend(m)
        for c in m:
            credit = _credit_of(c) * factor
            p = _prefix(c["课号"])
            prefixes[p] = round(prefixes.get(p, 0.0) + credit, 1)
            for tag, kws in TAGS.items():
                if any(k in c["课程名称"] for k in kws):
                    tags[tag] += credit
                    if len(names[tag]) < 8:
                        names[tag].append(c["课程名称"])

    base = must
    terms = Counter(c.get("选课学期", "") for c in base if c.get("选课学期"))
    return {
        "毕业总学分": struct.get("毕业总学分"),
        "专业必修学分_方案原文": _planned_must_credit(struct),
        "必修学分合计": round(capped_total, 1),
        "必修_课程学分和": round(raw_total, 1),
        "必修_含备选": has_alt,
        "必修_无性质列": not any_must,
        "必修门数": len(must),
        "必修_数学学分": round(tags["数学"], 1),
        "必修_计算学分": round(tags["计算"], 1),
        "必修_语言学分": round(tags["语言"], 1),
        "必修_实践学分": round(tags["实验实践"], 1),
        "必修_课号前缀学分": dict(sorted(prefixes.items(), key=lambda kv: -kv[1])),
        "必修_学期分布": dict(sorted(terms.items(), key=lambda kv: -kv[1])),
        "必修_能力课程名": names,
        "学分结构": struct.get("学分结构", {}),
    }


# ---------------- 六、课程反查（从课程结构认院系） ----------------

def build_course_index(plans: dict[str, dict]) -> dict:
    """课号 → 哪些专业把它列为必修/核心；顺带给出课号前缀 → 院系归属的自证。"""
    index: dict[str, dict] = defaultdict(lambda: {"课程名称": "", "专业": []})
    for key, plan in plans.items():
        for c in professional_courses(plan):
            nature = c.get("课程性质", "")
            if "必修" not in nature:
                continue
            node = index[c["课号"]]
            node["课程名称"] = node["课程名称"] or c["课程名称"]
            node["专业"].append(key)
    return {k: {"课程名称": v["课程名称"], "必修该课的专业": sorted(set(v["专业"]))}
            for k, v in index.items()}


def prefix_ownership(plans: dict[str, dict]) -> dict:
    """课号前 4 位 → 谁在必修它（用数据自证「课号能认院系」，也顺便给出该前缀的课程名样例）。"""
    names: dict[str, Counter] = defaultdict(Counter)
    majors: dict[str, set] = defaultdict(set)
    for key, plan in plans.items():
        for c in professional_courses(plan):
            if "必修" not in c.get("课程性质", ""):
                continue
            p = _prefix(c["课号"])
            names[p][c["课程名称"]] += 1
            majors[p].add(key)
    return {p: {"课程名样例": [n for n, _ in names[p].most_common(6)],
                "必修该前缀课程的专业数": len(majors[p]),
                "专业样例": sorted(majors[p])[:6]}
            for p in sorted(names)}


def infer_major(course_codes: list[str], plans: dict[str, dict],
                drop_common: float = 0.3) -> list[dict]:
    """给定课号集合，按「命中该专业必修课的比例」排序。

    公共课（出现在 drop_common 比例以上专业的必修课里）先剔除，否则所有专业都会被思政课拉平。
    """
    profiles = {}
    for key, plan in plans.items():
        profiles[key] = {c["课号"] for c in professional_courses(plan)
                         if "必修" in c.get("课程性质", "")}
    if not profiles:
        return []
    counter: Counter = Counter()
    for must in profiles.values():
        counter.update(must)
    n = len(profiles)
    common = {code for code, cnt in counter.items() if cnt / n >= drop_common}
    scores = []
    for key, must in profiles.items():
        core = must - common
        if not core:
            continue
        hit = core & set(course_codes)
        scores.append({
            "专业": key,
            "命中核心必修": len(hit),
            "该专业核心必修数": len(core),
            "覆盖率": round(len(hit) / len(core), 3),
        })
    return sorted(scores, key=lambda x: (-x["覆盖率"], -x["命中核心必修"]))


# ---------------- 主流程 ----------------

def slug(s: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]", "_", s)


def classify(name: str) -> str:
    """目录里的条目不都是专业：院系章节、公共课、项目、附录、说明要分开标，下游才好筛。"""
    if name.startswith(("附", "附表")) or "目录" in name:
        return "附录"
    if any(k in name for k in ("细则", "办法", "规定", "一览", "评定", "荣誉学位", "导引",
                               "介绍", "名单", "问答", "申请表")):
        return "说明"
    if "说明" in name or name.endswith("要求"):
        return "说明"
    if name.endswith(("学院", "学系", "系", "中心", "研究院", "学部")):
        return "院系"
    if name.startswith("公共与基础") or ("培养方案" in name and "专业" not in name):
        return "公共课"
    if "项目" in name or "实验班" in name:
        return "项目"
    return "专业"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default="", help="培养方案 PDF（用 --refingerprint 时不需要）")
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="", help="只抽这些专业（逗号分隔，名称可部分匹配）")
    ap.add_argument("--limit", type=int, default=0, help="最多抽多少个专业（0 = 全部）")
    ap.add_argument("--refingerprint", action="store_true",
                    help="不动 PDF，只按现有 plans/*.json 重算指纹（改了指纹规则时用，几秒钟）")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    os.makedirs(os.path.join(args.out, "plans"), exist_ok=True)
    log = lambda *a: print(*a, flush=True)

    if args.refingerprint:
        plans: dict[str, dict] = {}
        pdir = os.path.join(args.out, "plans")
        for fn in sorted(os.listdir(pdir)):
            if fn.endswith(".json"):
                plan = json.load(open(os.path.join(pdir, fn), encoding="utf-8"))
                plans[plan["专业"]] = plan
        write_derived(args.out, plans, reuse_public=True)
        log(f"[重算] {len(plans)} 个专业的指纹已更新")
        return

    with pdfplumber.open(args.pdf) as pdf:
        catalog, cat_pages = parse_catalog(pdf)
        json.dump(catalog, open(os.path.join(args.out, "catalog.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        log(f"[骨架] {len(catalog)} 条专业记录，来自 PDF 页 {cat_pages}")

        toc = parse_toc(pdf)
        json.dump(toc, open(os.path.join(args.out, "sections_raw.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        log(f"[目录] {len(toc)} 条（院系 {sum(1 for e in toc if e['kind']=='dept')}，"
            f"专业/项目 {sum(1 for e in toc if e['kind']=='major')}）")
        odd = [e["name"] for e in toc if len(e["name"]) > 40 or "培养方案" in e["name"]]
        if odd:
            log(f"[目录] 可疑条目 {len(odd)}：{odd[:5]}")

        pmap, offset = build_page_map(pdf)
        log(f"[页码] 偏移 {offset}，覆盖 {len(pmap)} 个书内页")

        # 章节表：把目录里的专业条目按书内页码排序，配 PDF 页码区间
        majors = [e for e in toc if e["kind"] in ("major", "dept") and e["printed"]]
        majors.sort(key=lambda e: e["printed"])
        for i, e in enumerate(majors):
            e["pdf_start"] = pmap.get(e["printed"])
            # 「下一个」要取页码严格更大的那一条：理科卷把地质学与地球化学印在同一章里、
            # 目录给的是同一个页码，直接取 i+1 会算出 start>end 的空区间，把整章丢掉。
            nxt = next((m["printed"] for m in majors[i + 1:] if m["printed"] > e["printed"]), None)
            e["pdf_end"] = (pmap.get(nxt) - 1) if nxt and pmap.get(nxt) else (e["pdf_start"] or 0) + 3
        # 同一页开始的专业 = 合章（共用一份培养方案），标出来，下游才知道两份计划为什么一模一样
        same_page: dict[int, list[str]] = {}
        for e in majors:
            if e["kind"] == "major":
                same_page.setdefault(e["printed"], []).append(e["name"])
        # 院系 / 学部归属：专业挂在「书内页码在它之前、且最靠后的那个院系」下。
        # 早先是按目录排版顺序挂的，遇到目录把专业按别的次序排（理科卷就有）会挂错院系，
        # 所以改成按页码区间判定；学部没有页码，仍按目录里院系前最近的那个学部/跨学科类。
        cur_group = ""
        depts: list[dict] = []
        for e in toc:
            if e["kind"] == "group":
                cur_group = e["name"]
            elif e["kind"] == "dept":
                e["学部"] = cur_group
                if e["printed"]:
                    depts.append(e)
        depts.sort(key=lambda e: e["printed"])
        for e in majors:
            if e["kind"] != "major":
                continue
            before = [d for d in depts if d["printed"] <= (e["printed"] or 0)]
            e["院系"] = before[-1]["name"] if before else ""
            e["学部"] = before[-1].get("学部", cur_group) if before else cur_group
        json.dump(majors, open(os.path.join(args.out, "sections.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

        # 只抽培养方案章节：专业/项目条目 + 公共课培养方案（思政/体育/英语/通识…，全校共用）
        targets = [e for e in majors
                   if e["kind"] == "major" or classify(e["name"]) == "公共课"]
        if args.only:
            keys = [s.strip() for s in args.only.split(",") if s.strip()]
            targets = [e for e in targets if any(k in e["name"] for k in keys)]
        if args.limit:
            targets = targets[: args.limit]
        log(f"[抽取] 目标 {len(targets)} 个专业")

        plans: dict[str, dict] = {}
        for i, e in enumerate(targets, 1):
            start, end = e["pdf_start"], e["pdf_end"]
            if not start:
                log(f"  - 跳过 {e['name']}（无页码）")
                continue
            sec = extract_section(pdf, start, end)
            key = e["name"]
            plan = {**sec, "专业": key, "类别": classify(key),
                    "院系": e.get("院系", ""), "学部": e.get("学部", ""),
                    "页码": {"pdf": [start, end], "书内": e["printed"]}}
            sib = [n for n in same_page.get(e["printed"], []) if n != key]
            if sib:
                plan["合章"] = sib
            plans[key] = plan
            log(f"  [{i}/{len(targets)}] {key} p{start}-{end} 课程 {sec['课程数_去重']}")

        write_derived(args.out, plans)
        log(f"[完成] {len(plans)} 个专业 → {args.out}")


def write_derived(out: str, plans: dict[str, dict], reuse_public: bool = False) -> None:
    """公共课拆分 + 指纹 / 课程反查 / 前缀归属 —— 全部从 plans 推导，可随时重算。"""
    ppath = os.path.join(out, "public_courses.json")
    previous = None
    if reuse_public and os.path.exists(ppath):
        previous = json.load(open(ppath, encoding="utf-8"))
    shared = split_public(plans, previous)
    if shared:
        json.dump(shared, open(ppath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    elif not os.path.exists(ppath):
        print("[警告] 没抽到公共基础课程，请带 --pdf 重跑全量抽取")
    for key, plan in plans.items():
        plan["指纹"] = fingerprint(plan["课程表"], plan["学分结构"])
        plan["课程数_去重"] = len(plan_courses(plan))
        plan.pop("课程_去重", None)                  # 可由 课程表 摊平得到，不再存第二份
        json.dump(plan, open(os.path.join(out, "plans", slug(key) + ".json"), "w",
                             encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({k: v["指纹"] for k, v in plans.items()},
              open(os.path.join(out, "fingerprints.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(build_course_index(plans),
              open(os.path.join(out, "course_index.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(prefix_ownership(plans),
              open(os.path.join(out, "prefix_ownership.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
