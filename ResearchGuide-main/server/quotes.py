# -*- coding: utf-8 -*-
"""引文定位：学生（或学生的 Agent）写的一句引文，是不是逐字出自原文、出自哪一节。

只做「规范化后的逐字匹配」，不做模糊匹配：差一个词就算找不到。
规范化只抹掉排版噪声：连字、弯引号、断行连字符、多余空白、全半角标点。
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

import arxiv

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
    return s.strip().lower()


def _index(text: str) -> tuple[str, list[int]]:
    """规范化全文，同时记下规范化后每个字符对应原文的位置，用来报告章节。"""
    out, pos = [], []
    for i, ch in enumerate(unicodedata.normalize("NFKC", text)):
        ch = _LIG.get(ch, _PUNCT.get(ch, ch))
        for c in ch:
            if c.isspace():
                if out and out[-1] == " ":
                    continue
                c = " "
            out.append(c.lower())
            pos.append(i)
    return "".join(out), pos


def locate(quote: str, paper: dict[str, Any]) -> dict[str, Any]:
    """返回 {found, section, where, reason}。paper 是 arxiv.fulltext() 的结果。"""
    q = norm(quote).strip(' "\'')
    if len(q) < MIN_LEN:
        return {"found": False, "reason": f"引文太短（至少 {MIN_LEN} 个字符），没法当证据"}
    hay, pos = _index(paper.get("text") or "")
    hay2 = re.sub(r"(\w)- (\w)", r"\1\2", hay)
    i = hay.find(q)
    if i < 0 and hay2 != hay and q in hay2:
        i = -2
    if i == -1:
        return {"found": False, "reason": "原文里找不到这句" + ("（只拿到了摘要，正文核对不了）" if paper.get("source") == "abstract" else "")}
    if i == -2:
        return {"found": True, "section": "", "where": "正文", "reason": ""}
    src_pos = pos[i] if i < len(pos) else 0
    sec = arxiv.section_at(paper["text"], src_pos)
    return {"found": True, "section": sec, "where": sec or ("摘要" if paper.get("source") == "abstract" else "正文"), "reason": ""}
