# -*- coding: utf-8 -*-
"""边学边练的实时来源适配器。每个适配器：只读公开接口、不登录、不绕验证码，失败抛 AdapterError。

签名：fetch(source, direction, stage, terms) -> list[{title, url, description, difficulty, deadline, retrieved_at}]
- source：knowledge/project_sources.json 里的一条；
- terms：查询词（用户关键词优先，其次方向词）。
返回的文本是外部数据，只当数据用，不当指令。
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from schemas import now_iso

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36 QiyanResearchMentor/0.2"
CACHE_TTL = 6 * 3600
_CACHE: dict[str, tuple[float, Any]] = {}
_LOCK = threading.Lock()


class AdapterError(Exception):
    pass


def http(url: str, *, data: dict | None = None, headers: dict | None = None, timeout: int = 12, as_json: bool = True) -> Any:
    """GET（或带 JSON 体的 POST），结果缓存 6 小时。"""
    key = url + "|" + json.dumps(data or {}, sort_keys=True, ensure_ascii=False)
    with _LOCK:
        hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1]
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    h = {"User-Agent": UA, "Accept": "application/json, text/html;q=0.9"}
    if body is not None:
        h["Content-Type"] = "application/json;charset=UTF-8"
    h.update(headers or {})
    raw = b""
    for attempt in range(2):  # 有的站 TLS 偶尔直接断开（UNEXPECTED_EOF），重试一次
        req = urllib.request.Request(url, data=body, headers=h, method="POST" if body is not None else "GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            break
        except urllib.error.HTTPError as exc:
            raise AdapterError(f"HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt == 1:
                raise AdapterError("连不上") from exc
            time.sleep(0.6)
    text = raw.decode("utf-8", errors="replace")
    out: Any = text
    if as_json:
        try:
            out = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AdapterError("返回的不是 JSON") from exc
    with _LOCK:
        _CACHE[key] = (time.time(), out)
    return out


def stamp(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ts = now_iso()
    for it in items:
        it.setdefault("retrieved_at", ts)
    return items


ADAPTERS: dict[str, Callable[[dict[str, Any], str, int, list[str]], list[dict[str, Any]]]] = {}


# ---------- 各来源 ----------

import html as _html
import re as _re

_TAG = _re.compile(r"<[^>]+>")


def _clean(s: Any, cap: int = 600) -> str:
    text = _html.unescape(_TAG.sub(" ", str(s or "")))
    return _re.sub(r"\s+", " ", text).strip()[:cap]


def _hit(text: str, terms: list[str]) -> bool:
    low = text.lower()
    return any(t and t.lower() in low for t in terms)


HEYWHALE_TERMS = {
    "psy": ["心理", "认知", "PSY", "社会科学", "问卷", "行为"],
    "econ": ["经管", "经济", "金融", "计量", "社会科学", "政策"],
    "stat": ["统计", "R 语言", "数据分析", "因果"],
    "ai": ["机器学习", "深度学习", "AI", "大模型", "神经网络"],
    "math": ["数学", "建模", "优化"],
    "se": ["Python", "编程", "工程"],
}


def heywhale(src, direction, stage, terms):
    """和鲸：训练营 / Workshop。去掉直播（LIVE），按方向词过滤；共约 175 条，取前两页。"""
    rows = []
    for page in (1, 2):
        data = http(f"https://www.heywhale.com/v2/api/competitions?page={page}&perPage=100&Status=1&includeTask=true")
        rows += data if isinstance(data, list) else (data or {}).get("data") or []
    terms = [t for t in terms if t not in HEYWHALE_TERMS.get(direction, [])] + HEYWHALE_TERMS.get(direction, [])
    out = []
    for r in rows:
        if r.get("DetailType") in ("LIVE", None):
            continue
        text = f"{r.get('Name', '')} {r.get('ShortDescription', '')}"
        if not _hit(text, terms):
            continue
        out.append({"title": _clean(r.get("Name"), 80), "url": f"https://www.heywhale.com/home/competition/{r['_id']}",
                    "description": _clean(r.get("ShortDescription")), "difficulty": {"TRAINING_CAMP": "训练营", "WORKSHOP": "Workshop"}.get(r.get("DetailType"), ""),
                    "deadline": str(r.get("EndDate") or "")[:10]})
    return stamp(out[:12])


def aistudio(src, direction, stage, terms):
    """飞桨 AI Studio：正在进行的比赛（含长期学习赛）。"""
    data = http("https://aistudio.baidu.com/studio/match/search?p=1&pageSize=50")
    rows = ((data or {}).get("result") or {}).get("data") or []
    out = []
    # 整个平台都是 AI 比赛：ai 方向只在用户给了关键词时才过滤，其余方向按方向词过滤
    user_terms = [t for t in terms if t not in DIR_DEFAULT_TERMS]
    need = user_terms if direction == "ai" else terms
    for r in rows:
        text = f"{r.get('matchName', '')} {r.get('matchAbs', '')} {r.get('tags', '')}"
        if need and not _hit(text, need):
            continue
        item = {"title": _clean(r.get("matchName"), 80), "url": f"https://aistudio.baidu.com/competition/detail/{r['id']}/0/introduction",
                "description": _clean(f"{r.get('matchAbs', '')} 标签：{r.get('tags', '')}"), "difficulty": "学习赛" if "学习赛" in text else "",
                "deadline": str(r.get("endTime") or "")[:10]}
        if direction == "ai":
            item["direction"] = "ai"
        out.append(item)
    out.sort(key=lambda x: x["difficulty"] != "学习赛")
    return stamp(out[:12])


def tianchi(src, direction, stage, terms):
    """天池：日常学习赛（visualTab=4），展开系列赛的子赛道；截止时间以页面为准。"""
    out = []
    for page in (1, 2):
        data = http(f"https://tianchi.aliyun.com/v3/proxy/competition/api/race/page?visualTab=4&raceName=&pageNum={page}&isActive=1")
        rows = ((data or {}).get("data") or {}).get("list") or []
        for r in rows:
            tracks = r.get("trackList")
            if isinstance(tracks, str):
                try:
                    tracks = json.loads(tracks.replace("'", '"'))
                except json.JSONDecodeError:
                    tracks = []
            for t in (tracks or [r]):
                name = t.get("name") or r.get("name") or ""
                intro = t.get("introduction") or r.get("introduction") or ""
                if not _hit(f"{name} {intro}", terms):
                    continue
                rid = t.get("raceId") or r.get("raceId")
                out.append({"title": _clean(name, 80), "url": f"https://tianchi.aliyun.com/competition/entrance/{rid}/introduction",
                            "description": _clean(intro), "difficulty": "学习赛", "deadline": str(t.get("raceEndTime") or r.get("raceEndTime") or "")[:10]})
        if len(out) >= 12:
            break
    return stamp(out[:12])


def pku_dataverse(src, direction, stage, terms):
    """北大开放研究数据：带数据的研究可以改成「复现一个结果」的项目。"""
    out, seen = [], set()
    for term in terms[:2]:
        q = urllib.parse.quote(term)
        data = http(f"https://opendata.pku.edu.cn/api/search?q={q}&type=dataset&per_page=20&sort=date&order=desc")
        for r in ((data or {}).get("data") or {}).get("items") or []:
            url = r.get("url") or ""
            if not url or url in seen:
                continue
            seen.add(url)
            out.append({"title": _clean(r.get("name"), 90), "url": url, "description": _clean(r.get("description")),
                        "difficulty": "数据复现"})
    return stamp(out[:12])


SCIDB_SUBJECT = {"psy": ("心理",), "econ": ("经济", "管理"), "stat": ("统计", "数学"), "ai": ("计算机", "信息")}


def sciencedb(src, direction, stage, terms):
    """科学数据银行：按学科分类过滤，避免「实验」一词搜到物理数据。"""
    want = SCIDB_SUBJECT.get(direction, ())
    out, seen = [], set()
    for term in terms[:2]:
        q = urllib.parse.quote(term)
        data = http(f"https://www.scidb.cn/api/sdb-query-service/query?queryCode=&q={q}", data={"ordernum": 6, "size": 20, "page": 1})
        rows = (((data or {}).get("data") or {}).get("data")) or []
        for r in rows:
            tax = r.get("taxonomy") or []
            names = " ".join(t.get("nameZh", "") for t in tax if isinstance(t, dict))
            if want and not any(w in names for w in want):
                continue
            doi = r.get("doi") or ""
            url = f"https://doi.org/{doi}" if doi else f"https://www.scidb.cn/detail?dataSetId={r.get('dataSetId')}"
            if url in seen:
                continue
            seen.add(url)
            out.append({"title": _clean(_TAG.sub("", str(r.get("titleZh") or "")), 90), "url": url, "description": _clean(r.get("introductionZh")),
                        "difficulty": "数据复现"})
    return stamp(out[:10])


_CY_ITEM = _re.compile(r'href="/mtcontest/detail\?id=([0-9a-f]+)".*?class="cymt-left" title="([^"]+)".*?class="cymt-mtqy" title="([^"]*)".*?class="cymt-mtlb" title="([^"]*)"', _re.S)
_CY_REQ = ("答题要求", "预期成果", "成果要求", "交付", "考核", "三、")


def _cy_detail(cid: str) -> str:
    page = http(f"https://cy.ncss.cn/mtcontest/detail?id={cid}", as_json=False, timeout=10)
    i = page.find('class="detail-content"')
    body = _clean(page[i:i + 40000], 20000) if i >= 0 else ""
    # 详情页前半是企业介绍和产业背景，学生真正要看的是后面的答题要求
    for mark in _CY_REQ:
        j = body.find(mark, 200)
        if j >= 0:
            return body[j:j + 600]
    return body[:600]


def cy_ncss(src, direction, stage, terms):
    """中国国际大学生创新大赛产业命题：真实企业出题，适合学完一块之后。"""
    out, seen = [], set()
    lbdm = "03" if direction in ("psy", "econ") else ""  # 心理、经济只看「新文科」，免得「低空经济」这类工科题混进来
    for term in terms[:2]:
        q = urllib.parse.quote(term)
        page = http(f"https://cy.ncss.cn/mtcontest/mingtilist?pageIndex=0&pageSize=30&companyName=&name={q}&zbdm=&lbdm={lbdm}", as_json=False)
        for cid, title, company, cat in _CY_ITEM.findall(page):
            if cid in seen:
                continue
            seen.add(cid)
            out.append({"id": cid, "title": _html.unescape(title), "url": f"https://cy.ncss.cn/mtcontest/detail?id={cid}",
                        "description": f"{_html.unescape(company)} 命题 · {cat}", "difficulty": cat})
    out = out[:8]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as pool:
        details = list(pool.map(lambda it: _safe(_cy_detail, it["id"]), out))
    for it, det in zip(out, details):
        if det:
            it["description"] = f"{it['description']}。{det}"
        it.pop("id", None)
    return stamp(out)


def _safe(fn, *args):
    try:
        return fn(*args)
    except AdapterError:
        return ""


_PE_ENTRY = _re.compile(r"<entry>\s*<title>(.*?)</title>\s*<url>(.*?)</url>\s*<content[^>]*>(.*?)</content>", _re.S)


def project_euler(src, direction, stage, terms):
    """欧拉计划中文站：编程 + 数学的小题，一个人能做完。按编号取前面的题，难度随编号上升。"""
    xml = http("https://pe-cn.github.io/search.xml", as_json=False, timeout=20)
    out = []
    for title, url, content in _PE_ENTRY.findall(xml):
        m = _re.search(r"(\d+)", title)
        n = int(m.group(1)) if m else 9999
        limit = {0: 30, 1: 80, 2: 200}.get(stage, 300)
        if n > limit:
            continue
        text = _clean(_html.unescape(content), 400)
        if terms[0] and terms[0] not in DIR_DEFAULT_TERMS and not _hit(f"{title} {text}", terms[:1]):
            continue
        out.append({"title": f"Project Euler {_clean(title, 60)}", "url": "https://pe-cn.github.io" + url if url.startswith("/") else url,
                    "description": text, "difficulty": f"第 {n} 题"})
    out.sort(key=lambda x: int(_re.search(r"第 (\d+) 题", x["difficulty"]).group(1)))
    return stamp(out[:8])


DIR_DEFAULT_TERMS = {"机器学习", "人工智能", "数学", "建模", "统计", "数据分析", "心理", "认知", "经济", "金融", "软件", "系统"}

ADAPTERS.update({
    "heywhale": heywhale,
    "aistudio": aistudio,
    "tianchi": tianchi,
    "pku_dataverse": pku_dataverse,
    "sciencedb": sciencedb,
    "cy_ncss": cy_ncss,
    "project_euler": project_euler,
})
