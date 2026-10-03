# -*- coding: utf-8 -*-
"""arXiv：元数据、最新论文、全文（HTML 版），给研读层用。

- 只用 arXiv 官方公开接口和 arxiv.org/html 页面；不抓需要登录的东西。
- 官方要求连续请求间隔约 3 秒，这里串行加锁并缓存：元数据 6 小时，全文落盘长期复用。
- 全文取不到（老论文没有 HTML 版）就退回摘要，并在结果里写明 `source`，引文核对据此如实说明。
"""
from __future__ import annotations

import html
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from singleflight import SingleFlight

API = "https://export.arxiv.org/api/query"
ATOM = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
UA = "QiyanResearchMentor/0.3 (education; contact via repo)"
CACHE_DIR = Path(__file__).resolve().parent / "data" / "papers"
META_TTL = 6 * 3600
_LOCK = threading.Lock()
_LAST_CALL = [0.0]
_META: dict[str, tuple[float, Any]] = {}
_FLIGHT = SingleFlight()  # 同一 URL / 同一篇论文并发只取一次（限速锁下，重复请求每个都要排 3 秒）
ID_RE = re.compile(r"^\d{4}\.\d{4,5}$")


class ArxivError(Exception):
    pass


def clean_id(raw: str) -> str:
    """接受 2310.17623、2310.17623v2、arxiv.org/abs/… 等写法，返回不带版本号的 id。"""
    s = (raw or "").strip()
    s = re.sub(r"^https?://(www\.)?arxiv\.org/(abs|pdf|html)/", "", s)
    s = re.sub(r"\.pdf$", "", s)
    s = re.sub(r"v\d+$", "", s)
    if not ID_RE.match(s):
        raise ArxivError("不是有效的 arXiv 编号（形如 2310.17623）")
    return s


def _get(url: str, timeout: int = 20) -> bytes:
    with _LOCK:  # 官方要求慢一点：同一时间只发一个请求，间隔 ≥3 秒
        wait = 3.0 - (time.time() - _LAST_CALL[0])
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
        except urllib.error.HTTPError as exc:
            raise ArxivError(f"arXiv 返回 HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ArxivError("连不上 arXiv") from exc
        finally:
            _LAST_CALL[0] = time.time()
    return body


def _entries(xml_bytes: bytes) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_bytes)
    out = []
    for e in root.findall("a:entry", ATOM):
        raw_id = (e.findtext("a:id", "", ATOM) or "").rsplit("/", 1)[-1]
        title = re.sub(r"\s+", " ", e.findtext("a:title", "", ATOM)).strip()
        if not raw_id or title == "Error":
            continue
        out.append({
            "id": re.sub(r"v\d+$", "", raw_id),
            "title": title,
            "summary": re.sub(r"\s+", " ", e.findtext("a:summary", "", ATOM)).strip(),
            "authors": [a.findtext("a:name", "", ATOM) for a in e.findall("a:author", ATOM)],
            "published": (e.findtext("a:published", "", ATOM) or "")[:10],
            "updated": (e.findtext("a:updated", "", ATOM) or "")[:10],
            "categories": [c.get("term") for c in e.findall("a:category", ATOM)],
            "url": f"https://arxiv.org/abs/{re.sub(r'v\\d+$', '', raw_id)}",
        })
    return out


def query(params: dict[str, Any]) -> list[dict[str, Any]]:
    url = API + "?" + urllib.parse.urlencode(params)

    def fetch() -> list[dict[str, Any]]:
        hit = _META.get(url)
        if hit and time.time() - hit[0] < META_TTL:
            return hit[1]
        try:
            data = _entries(_get(url))
        except ET.ParseError as exc:
            raise ArxivError("arXiv 返回的不是 Atom") from exc
        _META[url] = (time.time(), data)
        return data

    hit = _META.get(url)
    if hit and time.time() - hit[0] < META_TTL:
        return hit[1]
    return _FLIGHT.do(("query", url), fetch)


def count(search_query: str) -> int:
    """命中总数（opensearch:totalResults），不取条目。给「势头」用。"""
    # max_results=0 会让 arXiv 返回 500，取 1 条
    url = API + "?" + urllib.parse.urlencode({"search_query": search_query, "max_results": 1})
    try:
        root = ET.fromstring(_FLIGHT.do(("count", url), lambda: _get(url)))
    except ET.ParseError as exc:
        raise ArxivError("arXiv 返回的不是 Atom") from exc
    total = root.findtext("{http://a9.com/-/spec/opensearch/1.1/}totalResults")
    if total is None:
        raise ArxivError("arXiv 没有返回总数")
    return int(total)


def papers(ids: list[str]) -> list[dict[str, Any]]:
    ids = [clean_id(i) for i in ids]
    return query({"id_list": ",".join(ids), "max_results": len(ids)}) if ids else []


def recent(categories: list[str], keywords: list[str], max_results: int = 30) -> list[dict[str, Any]]:
    """某些分类下最近提交、标题或摘要命中关键词的论文，按提交时间倒序。"""
    cats = " OR ".join(f"cat:{c}" for c in categories)
    kws = " OR ".join(f'abs:"{k}"' if " " in k else f"abs:{k}" for k in keywords)
    q = f"({cats}) AND ({kws})" if kws else cats
    return query({"search_query": q, "sortBy": "submittedDate", "sortOrder": "descending", "max_results": max_results})


# ---------- 全文 ----------

_DROP = re.compile(r"<(script|style|math|svg|nav|header|footer)[^>]*>.*?</\1>", re.S | re.I)
_BLOCK = re.compile(r"</?(p|div|section|h[1-6]|li|tr|br|figcaption|caption|table)[^>]*>", re.I)
_TAG = re.compile(r"<[^>]+>")


def _html_to_text(page: str) -> str:
    # 正文在 <article> 里；前面是 arXiv 的横幅、反馈弹窗等页面杂项
    start = page.find("<article")
    if start >= 0:
        page = page[start:]
    # LaTeXML 把公式的 TeX 原文放在 alttext 里；先换成 TeX，免得句子断开
    page = re.sub(r"<math[^>]*alttext=\"([^\"]*)\"[^>]*>.*?</math>", lambda m: f" {html.unescape(m.group(1))} ", page, flags=re.S)
    page = _DROP.sub(" ", page)
    page = _BLOCK.sub("\n", page)
    text = html.unescape(_TAG.sub(" ", page))
    lines = [re.sub(r"[ \t ]+", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def fulltext(arxiv_id: str) -> dict[str, Any]:
    """{id, source: 'html' | 'abstract', text, title}；全文落盘缓存。"""
    aid = clean_id(arxiv_id)
    cached = CACHE_DIR / f"{aid}.json"
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    return _FLIGHT.do(("fulltext", aid), lambda: _fetch_fulltext(aid))


def _fetch_fulltext(aid: str) -> dict[str, Any]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = CACHE_DIR / f"{aid}.json"
    if cached.exists():  # 排在前面的那一个刚写好
        return json.loads(cached.read_text(encoding="utf-8"))
    meta = papers([aid])
    if not meta:
        raise ArxivError(f"arXiv 上没有 {aid}")
    m = meta[0]
    result = {"id": aid, "title": m["title"], "source": "abstract", "text": m["summary"], "url": m["url"]}
    try:
        page = _get(f"https://arxiv.org/html/{aid}", timeout=30).decode("utf-8", errors="replace")
        text = _html_to_text(page)
        if len(text) > 2000:
            result.update(source="html", text=text)
    except ArxivError:
        pass  # 没有 HTML 版就只用摘要，调用方会看到 source=abstract
    cached.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result


def sections(text: str) -> list[tuple[str, int]]:
    """粗分节：返回 [(标题, 起始位置)]。用来判断一句引文在不在 Limitations / Future work 里。"""
    out = []
    for m in re.finditer(r"^(?:\d+(?:\.\d+)*\s+)?(Abstract|Introduction|Related Work|Background|Method[s]?|Approach|Experiments?|Results?|Discussion|Analysis|Limitations?|Future Work|Conclusions?|Broader Impact|Ethics Statement|Acknowledg(?:e)?ments?|References|Appendix)\b.*$", text, re.M | re.I):
        out.append((m.group(1).lower(), m.start()))
    return out


SECTION_CN = {"abstract": "摘要", "introduction": "引言", "related work": "相关工作", "background": "背景",
              "method": "方法", "methods": "方法", "approach": "方法", "experiment": "实验", "experiments": "实验",
              "result": "结果", "results": "结果", "discussion": "讨论", "analysis": "分析", "limitation": "局限",
              "limitations": "局限", "future work": "未来工作", "conclusion": "结论", "conclusions": "结论",
              "broader impact": "更广的影响", "ethics statement": "伦理声明", "references": "参考文献", "appendix": "附录"}


def section_cn(name: str) -> str:
    return SECTION_CN.get(name, "致谢" if name.startswith("acknowledg") else name)


def section_at(text: str, pos: int) -> str:
    name = ""
    for title, start in sections(text):
        if start <= pos:
            name = title
        else:
            break
    return name
