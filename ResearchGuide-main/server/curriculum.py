# -*- coding: utf-8 -*-
"""院系-专业知识库的查询层（给 FastAPI 用）。

数据在 `knowledge/curriculum/`（文理两卷合并）与 `knowledge/minor/`（辅修 / 双专业），
都是离线抽好的 JSON，这里只做「加载 + 查表」，**不联网、不调模型**：
用户说「我是经济学院的」，答案不该由模型回忆，而该由这些表算出来。

三件事：
  1. `find_major(q)`    —— 用户怎么说都能查到（章节名/专业目录名/口语 + 专业簇 + 按院系）
  2. `major_detail(n)`  —— 一个专业的卡片 + 学分结构 + 必修清单 + 兄弟专业
  3. `match(codes)`     —— 拿成绩单课号认院系/专业（F1、命中、还缺哪几门）

数值口径与 `tools/curriculum/validate.py` 的留一验证一致（院校级 100%、专业级 89–91%），
所以接口给的排名和文档里报的数字是同一套算法。
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "knowledge" / "curriculum"
MINOR = ROOT / "knowledge" / "minor"

# 出现在 ≥30% 专业必修结构里的课，视作公共/通用必修（高数 B、思政、大学英语这类），
# 认专业时要先剔掉，否则所有专业看起来都像。
COMMON_SHARE = 0.3
_cache: dict[str, tuple[float, object]] = {}
_cache_time: dict[str, float] = {}

# 没命中时必须一起交代的覆盖边界：宁可说「我没这份数据」，也不能让用户以为
# 「知识库里没有 = 北大没这个专业」。医学部/深研院/软微是北大真实存在的培养单位，
# 只是不在《本科培养方案（2026）》文理两卷里。
COVERAGE_NOTE = (
    "没查到。知识库覆盖《北京大学本科培养方案（2026）》文科卷 + 理科卷（198 份专业方案）"
    "与《本科辅修双专业培养方案（2025）》98 份；医学部、深圳研究生院、软件与微电子学院"
    "不在其中（不是北大没有，是这两卷里没有）。请如实说没查到，别用印象补一个名字。"
)

# 院系简称 → 官方院系名。用户嘴上说的是「信管」「数院」，库里存的是官方全名。
# 只登记能对上库内真实院系的简称（有 test 逐个核验）；对不上的（医学部、深研院、
# 软微、教育学院这类跨院/不在库里的）**故意不写**——写了就会给出一个像是查到了的答案。
DEPT_ALIAS: dict[str, str] = {
    "信管": "信息管理系", "信息管理": "信息管理系",
    "数院": "数学科学学院", "数学": "数学科学学院",
    "物院": "物理学院", "物理": "物理学院",
    "化院": "化学与分子工程学院", "化学": "化学与分子工程学院",
    "生科": "生命科学学院", "生科院": "生命科学学院", "生物": "生命科学学院",
    "信科": "信息科学技术学院", "信科院": "信息科学技术学院", "信息科学技术": "信息科学技术学院",
    "地空": "地球与空间科学学院", "城环": "城市与环境学院", "工院": "工学院", "工学": "工学院",
    "经院": "经济学院", "经济": "经济学院",
    "光华": "光华管理学院", "光管": "光华管理学院",
    "国发院": "国家发展研究院", "国发": "国家发展研究院",
    "法院": "法学院", "法学": "法学院",
    "国关": "国际关系学院", "政管": "政府管理学院", "政府管理": "政府管理学院",
    "新传": "新闻与传播学院", "新闻": "新闻与传播学院",
    "心院": "心理与认知科学学院", "心理": "心理与认知科学学院",
    "元培": "元培学院", "社会": "社会学系", "社会学": "社会学系",
    "中文系": "中国语言文学系", "中文": "中国语言文学系",
    "历史": "历史学系", "历史学": "历史学系", "哲学": "哲学系", "哲学系": "哲学系",
    "考古": "考古文博学院", "考古系": "考古文博学院",
    "艺术": "艺术学院", "艺术学院": "艺术学院", "马院": "马克思主义学院",
    "外院": "外国语学院", "外国语": "外国语学院",
}


# ---------------- 加载（按 mtime 失效：改了 JSON 不用重启服务） ----------------

def _load(path: Path):
    try:
        stamp = path.stat().st_mtime
    except OSError:
        return None
    hit = _cache.get(str(path))
    if hit and hit[0] == stamp:
        return hit[1]
    data = json.loads(path.read_text(encoding="utf-8"))
    _cache[str(path)] = (stamp, data)
    return data


def _load_dir(d: Path, by_stem: bool = False) -> dict:
    out = {}
    if not d.is_dir():
        return out
    for fn in sorted(d.iterdir()):
        if fn.suffix == ".json":
            p = _load(fn)
            if isinstance(p, dict):
                # 辅修层必须按文件名取键：`专业` 字段是「计算机科学与技术」，
                # 双专业和辅修各一份、还有同名不同院系的，按字段取键会把 98 条并成 56 条。
                out[fn.stem if by_stem else (p.get("专业") or fn.stem)] = p
    return out


def cards(minor: bool = False) -> list[dict]:
    data = _load((MINOR if minor else KB) / "cards.json")
    return data if isinstance(data, list) else []


def plans() -> dict:
    return _load_dir(KB / "plans")


def minor_plans() -> dict:
    return _load_dir(MINOR / "plans", by_stem=True)


def course_index() -> dict:
    return _load(KB / "course_index.json") or {}


def prefix_ownership() -> dict:
    return _load(KB / "prefix_ownership.json") or {}


# ---------------- 名字：别名与检索 ----------------

def aliases(cat_name: str, plan_name: str) -> list[str]:
    """章节名 / 专业目录名 / 去方向括号 / 去「专业」二字，四种写法都收。"""
    out: list[str] = []

    def add(x: str) -> None:
        x = (x or "").strip()
        if x and x not in out:
            out.append(x)

    for n in (plan_name, cat_name):
        if not n:
            continue
        plain = re.sub(r"（[^）]*）", "", n)
        for base in (n, plain):
            add(base)
            add(base.replace("专业", ""))
            if not base.endswith("专业"):
                add(base + "专业")
    return out


def _names(card: dict) -> list[str]:
    return [card.get("专业", ""), card.get("目录专业名", "")] + list(card.get("检索别名", []))


def _index(minor: bool) -> dict[str, list[dict]]:
    idx: dict[str, list[dict]] = {}
    for c in cards(minor):
        names = list(_names(c))
        if minor:                      # 辅修层主键是 (院系, 专业, 类型)
            for extra in (f"{c['专业']}{c['类型']}", f"{c['专业']}（{c['类型']}）",
                          f"{c['院系']}{c['专业']}{c['类型']}"):
                names.append(extra)
        for a in dict.fromkeys(names):
            if a:
                idx.setdefault(a, [])
                if c not in idx[a]:
                    idx[a].append(c)
    return idx


def _recent(idx_keys: list[str]) -> None:      # pragma: no cover - 仅为接口可读性
    pass


def known_names(minor: bool = False) -> list[str]:
    """库里所有「用户可能说出口的名字」：专业名 + 检索别名 + 院系名 + 院系简称。

    按长度从长到短排，长的先匹配（「大数据管理与应用专业」优先于「大数据」）。
    """
    names: set[str] = set()
    for c in cards(minor):
        names.update(n for n in _names(c) if n and len(n) >= 2)
        if c.get("院系"):
            names.add(c["院系"])
    for k, v in DEPT_ALIAS.items():
        if len(k) >= 2:
            names.add(k)
        names.add(v)
    return sorted(names, key=len, reverse=True)


def mentions(text: str, minor: bool = False, limit: int = 6) -> list[str]:
    """用户这句话里出现了哪些库内的专业/院系名字（长的优先）。

    给对话用：模型漏传 query、或者把整句「信管有哪些专业分流」当 query 传过来时，
    代码从原话里把「信管」抠出来再查——这叫代码裁决，不让模型自己缩写。
    只做「整名出现在原话里」的确定性匹配，不做模糊猜测。
    """
    t = str(text or "")
    if not t:
        return []
    return [n for n in known_names(minor) if n in t][:limit]


def _dept_of(q: str, pool: list[dict]) -> str:
    """用户这句话指的是哪个院系？认不出来返回空串。

    三层，都很保守（宁可认不出来，也别把「信息」硬套到某个院系上）：
    官方全名完全相同 → 简称表 → **唯一**一个院系名包含它。
    出现多个院系都包含（比如「学院」）就返回空，交给「最像的名字」那层。
    """
    depts = sorted({c.get("院系", "") for c in pool if c.get("院系")})
    if q in depts:
        return q
    alias = DEPT_ALIAS.get(q)
    if alias and alias in depts:
        return alias
    if len(q) < 2:
        return ""
    hit = [d for d in depts if q in d]
    return hit[0] if len(hit) == 1 else ""


def find_major(q: str, minor: bool = False, limit: int = 8) -> dict:
    """五层：主键完全相同 → 别名表 → 包含匹配 → 院系（列出该院全部专业）→ 最像的 3 个名字。

    一个名字对上多个专业时**返回全部候选**（专业簇）：低年级成绩单只能认到院系，
    兄弟方向本来就分不开，硬挑一个就是编。

    院系那层是给「信管有哪些专业分流」这类问题用的：用户问的是院系，
    回一张专业名单才是答案；在这之前它会被当成专业名去比，结果「未命中」。
    """
    q = (q or "").strip()
    if not q:
        return {"ok": False, "error": "q is required", "命中": []}
    pool = cards(minor)
    if not minor:
        exact = [c for c in pool if c.get("专业") == q]
        if exact:
            return {"ok": True, "query": q, "kind": "唯一", "命中": exact[:limit], "近名": []}
    idx = _index(minor)
    hits = idx.get(q)
    if not hits:
        seen: list[dict] = []
        for a, cs in idx.items():
            if a and (q in a or a in q):
                for c in cs:
                    if c not in seen:
                        seen.append(c)
        hits = seen
    if hits:
        kind = "唯一" if len(hits) == 1 else f"专业簇（{len(hits)} 个）"
        return {"ok": True, "query": q, "kind": kind, "命中": hits[:limit],
                "命中总数": len(hits), "近名": []}

    dept = _dept_of(q, pool)
    if dept:
        members = [c for c in pool if c.get("院系") == dept]
        kind = f"院系（{len(members)} 个专业）" if not minor else f"院系（辅修 {len(members)} 个）"
        return {"ok": True, "query": q, "kind": kind, "院系": dept,
                "命中": members[:limit], "命中总数": len(members), "近名": [],
                "说明": f"这是{dept}的全部专业/项目。**分流与名额以院系教务和当年培养方案为准**；"
                        f"这里给的是方案原文里的名单与学分要求。"}

    import difflib
    near = difflib.get_close_matches(q, list(idx), n=3, cutoff=0.5)
    return {"ok": True, "query": q, "kind": "未命中", "命中": [], "近名": near,
            "说明": COVERAGE_NOTE}


# ---------------- 单个专业详情 ----------------

# 与 tools/curriculum/extract_curriculum.py 的 is_public_module 同一口径：
# 模块号不是 1 的一律算专业自己的课；1.x 里只有名字含「专业/项目/核心/实践…」的才留。
PUBLIC_LABEL_RE = re.compile(
    r"公共必修|公共基础|全校必修|通识教育|大学英语|大学外语|信息科学课|军事理论|"
    r"国家安全|心理健康|思想政治|思政|大学成长课|体育课|劳动教育|与中国有关课程")
NON_PUBLIC_RE = re.compile(r"专业|项目|特设|核心|实践|实习|学科|讨论课")


def is_public_module(label: str) -> bool:
    lab = (label or "").strip()
    head = re.match(r"^(\d+)", lab)
    if head and head.group(1) != "1":
        return False
    if NON_PUBLIC_RE.search(lab):
        return False
    return bool(PUBLIC_LABEL_RE.search(lab))


def _must_courses(plan: dict, limit: int = 40) -> list[dict]:
    """专业必修课清单：拿掉公共基础课模块，再取课程性质写「必修」的课。

    模块名各院系写法不一（`2.1.1 数学类`、`2.2 专业核心课`），所以判据是
    「不是公共课模块」+「课程性质含必修」，跟 validate.py 的 core_must 同一口径；
    信科的 `1.1 公共必修课` 里其实放着计算概论A、数据结构这种本专业必修课，所以
    不能简单按「模块号是不是 1」一刀切（那条规则见 is_public_module）。
    """
    out = []
    for mod in plan.get("课程表", []):
        label = (mod.get("模块") or "").strip()
        if is_public_module(label):
            continue
        for c in mod.get("课程", []):
            if "必修" not in (c.get("课程性质") or ""):
                continue
            out.append({"课号": c.get("课号", ""), "课程名": c.get("课程名称", ""),
                        "学分": c.get("学分", ""), "学期": c.get("选课学期", ""),
                        "模块": label})
    return out[:limit]


def _siblings(name: str, dept: str, limit: int = 6) -> list[str]:
    """同院系的其他专业：低年级认不出细分专业时要一并给出（「换到本院任何专业都不用补课」）。"""
    out = []
    for c in cards():
        if c.get("院系") == dept and c.get("专业") != name and c.get("核心必修课"):
            out.append(c["专业"])
    return out[:limit]


def major_detail(name: str) -> dict:
    res = find_major(name, limit=1)
    if not res.get("命中"):
        # 没查到也要说清边界：不然模型很容易把「库里没有」说成「北大没这个专业」
        return {"ok": False, "error": "没查到", "近名": res.get("近名", []),
                "说明": COVERAGE_NOTE}
    card = res["命中"][0]
    plan = plans().get(card["专业"])
    payload = {"ok": True, "卡片": card}
    if plan:
        payload["学分结构"] = plan.get("学分结构", {})
        payload["必修课"] = _must_courses(plan)
        payload["课程数_去重"] = plan.get("课程数_去重")
        payload["页码"] = plan.get("页码")
        payload["卷"] = plan.get("卷")
    payload["兄弟专业"] = _siblings(card["专业"], card.get("院系", ""))
    return payload


# ---------------- 成绩单 → 院系 / 专业 ----------------

CODE_RE = re.compile(r"\b(\d{8})\b")


def _core_must(plan: dict, low_only: bool = False) -> set[str]:
    """认专业用的必修课号集合（与 validate.py 的 core_must 同口径）。"""
    out = set()
    for mod in plan.get("课程表", []):
        label = (mod.get("模块") or "").strip()
        if is_public_module(label):
            continue
        for c in mod.get("课程", []):
            if "必修" not in (c.get("课程性质") or ""):
                continue
            if low_only and not any(x in (c.get("选课学期") or "") for x in ("一", "二")):
                continue
            code = c.get("课号", "")
            if code:
                out.add(code)
    return out


def _common_set(profiles: dict[str, set[str]]) -> set[str]:
    counts: dict[str, int] = {}
    for must in profiles.values():
        for code in must:
            counts[code] = counts.get(code, 0) + 1
    n = max(1, len(profiles))
    return {c for c, cnt in counts.items() if cnt / n >= COMMON_SHARE}


def parse_codes(raw) -> list[str]:
    """成绩单可以是课号数组，也可以是整段文本（带课程名/学分），捞出 8 位课号即可。"""
    if isinstance(raw, str):
        raw = [raw]
    out = []
    for item in raw or []:
        for code in CODE_RE.findall(str(item)):
            if code not in out:
                out.append(code)
    return out


def match(codes, low_only: bool = False, top: int = 5) -> dict:
    tr = set(parse_codes(codes))
    if not tr:
        return {"ok": False, "error": "没识别出课号（要 8 位数字课号）", "专业排名": [], "院系排名": []}
    profs = {k: _core_must(p, low_only) for k, p in plans().items()
             if p.get("类别", "专业") in ("专业", "项目")}
    common = _common_set(profs)
    rows = []
    for key, must in profs.items():
        core = must - common
        if not core:
            continue
        hit = core & tr
        rec = len(hit) / len(core)
        pre = len(hit) / max(1, len(tr & (must | common)))
        f1 = 0.0 if rec + pre == 0 else 2 * rec * pre / (rec + pre)
        rows.append({"专业": key, "分": round(f1, 3), "命中数": len(hit), "必修数": len(core),
                     "命中": sorted(hit),
                     "还缺": sorted(core - tr)[:12],
                     "院系": (plans().get(key, {}).get("院系") or "")})
    rows.sort(key=lambda r: (-r["分"], -r["命中数"]))
    by_dept: dict[str, dict] = {}
    for r in rows:
        d = by_dept.setdefault(r["院系"], {"院系": r["院系"], "分": 0.0, "命中数": 0, "专业": []})
        d["分"] = max(d["分"], r["分"])
        d["命中数"] = max(d["命中数"], r["命中数"])
        if len(d["专业"]) < 4:
            d["专业"].append(r["专业"])
    depts = [d for d in sorted(by_dept.values(), key=lambda x: (-x["分"], -x["命中数"]))
             if d["命中数"] > 0][:top]
    return {"ok": True, "识别到课号": len(tr), "参评专业": len(rows),
            "院系排名": depts, "专业排名": rows[:top],
            "说明": "低年级成绩单只能认到院系：同院兄弟专业必修结构高度重合，"
                    "所以「院系」可信、「专业」请当作专业簇（本院任何专业都不需要补课）。"}


# ---------------- 辅修 / 双专业 ----------------

def find_minor(q: str = "", dept: str = "", top: int = 20) -> dict:
    if q:
        return find_major(q, minor=True, limit=top)
    items = [c for c in cards(True) if (not dept or dept in (c.get("院系") or ""))]
    return {"ok": True, "总数": len(items), "命中": items[:top]}


# ---------------- 课号反查 ----------------

def course_detail(code: str) -> dict:
    code = re.sub(r"\D", "", code or "")
    if len(code) != 8:
        return {"ok": False, "error": "课号要 8 位数字，例如 00130201"}
    hit = course_index().get(code) or {}
    own = prefix_ownership().get(code[:4]) or {}
    return {"ok": True, "课号": code,
            "课程名": hit.get("课程名称", "") or course_name(code),
            "必修它的专业": hit.get("必修该课的专业", []),
            "开课院系线索": own.get("专业样例", [])[:6],
            "同前缀有多少专业在必修": own.get("必修该前缀课程的专业数"),
            "同前缀课程名样例": own.get("课程名样例", [])[:4],
            "库内是否收录": bool(hit)}


def course_name(code: str) -> str:
    """课号 → 课程名：先看课程索引，索引里没有就从各专业课程表里找（名称都取自原文）。"""
    for plan in plans().values():
        for mod in plan.get("课程表", []):
            for c in mod.get("课程", []):
                if c.get("课号") == code and c.get("课程名称"):
                    return c["课程名称"]
    return ""


def _name_key(name: str) -> str:
    """课名归一：去掉书名号/括号/空格/连字符。成绩单上印的是「高等数学 (B)」，
    方案原文写的是「高等数学B」——不归一就一条都对不上。"""
    s = str(name or "")
    s = re.sub(r"[《》「」【】()（）\[\]·・,，.。:：;；\-—_\s]", "", s)
    return s


def codes_for_names(names: list[str]) -> dict:
    """课名 → 课号。给「已经录过成绩单」的画像用。

    北大成绩单打印件只有课名、没有课号（`transcript.parse_transcript` 抓的就是那个版式），
    而认院系/专业要的是课号。所以这里拿知识库的课程索引做一次**确定性反查**：
    归一后完全相同的才算命中，认不出来就如实列在 `未认出` 里，不做模糊猜测
    （猜错一门课，认出来的院系就是错的）。
    """
    by_key: dict[str, list[str]] = {}
    for code, v in course_index().items():
        k = _name_key((v or {}).get("课程名称", ""))
        if k:
            by_key.setdefault(k, []).append(code)
    # 索引里没有的，再从各专业课程表补一遍（同一门课在不同院系写法略有出入）
    for plan in plans().values():
        for mod in plan.get("课程表", []):
            for c in mod.get("课程", []):
                code, nm = c.get("课号"), _name_key(c.get("课程名称", ""))
                if code and nm and code not in by_key.get(nm, []):
                    by_key.setdefault(nm, []).append(code)

    codes: list[str] = []
    matched: dict[str, str] = {}
    missed: list[str] = []
    for n in names:
        hit = by_key.get(_name_key(n))
        if not hit:
            missed.append(str(n))
            continue
        matched[str(n)] = hit[0]
        for code in hit:
            if code not in codes:
                codes.append(code)
    return {"codes": codes, "matched": matched, "missed": missed}


def stats() -> dict:
    """给健康检查/前端用：知识库里现在有多少东西。"""
    t0 = time.time()
    return {"ok": True, "专业卡": len(cards()), "辅修双专业卡": len(cards(True)),
            "培养方案": len(plans()), "辅修方案": len(minor_plans()),
            "课程索引": len(course_index()), "课号前缀": len(prefix_ownership()),
            "加载耗时ms": int((time.time() - t0) * 1000)}
