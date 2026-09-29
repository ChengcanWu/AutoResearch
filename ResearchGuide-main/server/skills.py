# -*- coding: utf-8 -*-
"""读取 skills/<name>/SKILL.md，作为模型的工作说明（system prompt）。

何时写成 skill、何时写成代码，见 skills/README.md。改 SKILL.md 不用重启服务：按修改时间自动重读。
"""
from __future__ import annotations

from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"
_CACHE: dict[str, tuple[float, str]] = {}


def load(name: str) -> str:
    path = SKILLS_DIR / name / "SKILL.md"
    mtime = path.stat().st_mtime
    hit = _CACHE.get(name)
    if hit and hit[0] == mtime:
        return hit[1]
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:]
    text = text.strip()
    _CACHE[name] = (mtime, text)
    return text
