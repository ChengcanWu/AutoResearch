# -*- coding: utf-8 -*-
"""引文定位：学生（或学生的 Agent）写的一句引文，是不是逐字出自原文、出自哪一节。

只做「规范化后的逐字匹配」，不做模糊匹配：差一个词就算找不到。
规范化只抹掉排版噪声：连字、弯引号、断行连字符、多余空白、全半角标点。
"""
from __future__ import annotations

import re
import threading
import unicodedata
from array import array
from collections import OrderedDict
from typing import Any

import arxiv
from singleflight import SingleFlight

_LIG = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}
_PUNCT = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "−": "-",
          " ": " ", "，": ",", "。": ".", "：": ":", "；": ";", "（": "(", "）": ")", "「": '"', "」": '"'}
MIN_LEN = 12


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    for a, b in {**_LIG, **_PUNCT}.items():
        s = s.replace(a, b)
    s = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", s)  # 断行连字符
    s = re.sub(r"\s+", " ", s)
    return "".join(c.lower() for c in s.strip())  # 逐字转小写，和 _index 的做法一致（整串转小写对希腊字母词尾 σ 有特例）


def _index(text: str) -> tuple[str, array]:
    """规范化全文，同时记下规范化后每个字符对应「原文」的位置，用来报告章节。
    原来先把整篇做 NFKC 再数位置：连字（ﬁ → fi）、全角字符会改变长度，位置整体错开，引言里的句子可能被报成局限段。
    现在按「一个字加上它后面的组合符号」一段段规范化，每段产出的字都记这段在原文里的起点。"""
    out, pos = [], array("I")
    n, i = len(text), 0
    while i < n:
        j = i + 1
        while j < n and not text[j].isascii() and unicodedata.combining(text[j]):
            j += 1
        chunk = text[i:j]
        for ch in (chunk if chunk.isascii() else unicodedata.normalize("NFKC", chunk)):
            ch = _LIG.get(ch, _PUNCT.get(ch, ch))
            for c in ch:
                if c.isspace():
                    if out and out[-1] == " ":
                        continue
                    c = " "
                out.append(c.lower())
                pos.append(i)
        i = j
    return "".join(out), pos


# 按总字数留，不按篇数：几篇不同的论文同时交卡时，提前建好的索引不能在评阅前就被挤掉；
# 每个字约占 6 字节（规范化文本两份加位置表），八百万字约 50 MB 封顶，最近用过的那篇总会留下
PREPARED_BUDGET = 8_000_000
_PREPARED: OrderedDict[str, tuple[str, array, str]] = OrderedDict()
_PREPARED_LOCK = threading.Lock()
_PREPARING = SingleFlight()  # 二十几张卡同时交同一篇论文：只建一次，其余等它（lru_cache 只缓存建好的，不合并正在建的）


def _prepared(text: str) -> tuple[str, array, str]:
    """一篇论文只规范化一次：一张卡要定位六七句，原来每句都把全文重做一遍。
    以全文字符串为键（Python 会缓存字符串的哈希）；总字数超过预算时先丢最久没用的。"""
    with _PREPARED_LOCK:
        hit = _PREPARED.get(text)
        if hit is not None:
            _PREPARED.move_to_end(text)
            return hit
    return _PREPARING.do(text, lambda: _prepare(text))


def _prepare(text: str) -> tuple[str, array, str]:
    with _PREPARED_LOCK:
        hit = _PREPARED.get(text)
    if hit is not None:  # 排在前面的那一个刚建好
        return hit
    hay, pos = _index(text)
    got = (hay, pos, re.sub(r"(\w)- (\w)", r"\1\2", hay))
    with _PREPARED_LOCK:
        _PREPARED[text] = got
        while len(_PREPARED) > 1 and sum(len(k) for k in _PREPARED) > PREPARED_BUDGET:
            _PREPARED.popitem(last=False)
    return got


def prepare(text: str) -> None:
    """提前建好索引（交卡入口在事件循环里共等这一步）。"""
    _prepared(text)


def clear_prepared() -> None:
    with _PREPARED_LOCK:
        _PREPARED.clear()


def locate(quote: str, paper: dict[str, Any]) -> dict[str, Any]:
    """返回 {found, section, where, reason}。paper 是 arxiv.fulltext() 的结果。"""
    q = norm(quote).strip(' "\'')
    if len(q) < MIN_LEN:
        return {"found": False, "reason": f"引文太短（至少 {MIN_LEN} 个字符），没法当证据"}
    hay, pos, hay2 = _prepared(paper.get("text") or "")
    i = hay.find(q)
    if i < 0 and hay2 != hay and q in hay2:
        i = -2
    if i == -1:
        return {"found": False, "reason": "原文里找不到这句" + ("（只拿到了摘要，正文核对不了）" if paper.get("source") == "abstract" else "")}
    if i == -2:
        return {"found": True, "section": "", "where": "正文", "reason": ""}
    src_pos = pos[i] if i < len(pos) else 0
    sec = arxiv.section_at(paper["text"], src_pos)
    where = arxiv.section_cn(sec) if sec else ("摘要" if paper.get("source") == "abstract" else "正文")
    return {"found": True, "section": sec, "where": where, "reason": ""}
