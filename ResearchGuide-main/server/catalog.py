# -*- coding: utf-8 -*-
"""读 knowledge/catalog/ 快照，给节点做关键词检索。"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import json

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "knowledge" / "catalog"


@lru_cache(maxsize=1)
def loaded() -> dict[str, Any]:
    meta_p = CATALOG / "meta.json"
    courses_p = CATALOG / "courses.json"
    teachers_p = CATALOG / "teachers.json"
    if not (meta_p.exists() and courses_p.exists()):
        return {}
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    courses = json.loads(courses_p.read_text(encoding="utf-8"))
    teachers = json.loads(teachers_p.read_text(encoding="utf-8")) if teachers_p.exists() else []
    by_name = {t["name"]: t for t in teachers if t.get("name")}
    return {"meta": meta, "courses": courses, "teachers": teachers, "by_name": by_name}


def available() -> bool:
    return bool(loaded())


def _hay(course: dict[str, Any]) -> str:
    bits = [
        course.get("name") or "",
        course.get("teachers") or "",
        course.get("department") or "",
        course.get("category") or "",
        " ".join(course.get("teacher_names") or []),
    ]
    return " ".join(bits).lower()


def search_courses(query: str, limit: int = 5) -> dict[str, Any]:
    pack = loaded()
    query = (query or "").strip()
    if not pack:
        return {"ok": False, "error": "local catalog missing"}
    if not query:
        return {"ok": False, "error": "query is required"}
    q = query.lower()
    scored: list[tuple[int, dict[str, Any]]] = []
    for c in pack["courses"]:
        name = (c.get("name") or "").lower()
        hay = _hay(c)
        if q not in hay:
            continue
        score = 0
        if q == name:
            score += 80
        elif name.startswith(q):
            score += 50
        elif q in name:
            score += 30
        if q in (c.get("teachers") or "").lower():
            score += 12
        if q in (c.get("department") or "").lower():
            score += 6
        scored.append((score, c))
    scored.sort(key=lambda x: (-x[0], x[1].get("name") or ""))
    items = []
    for _s, c in scored[: max(1, min(20, limit))]:
        items.append({
            "ref": c.get("ref"),
            "name": c.get("name"),
            "teachers": c.get("teachers") or "",
            "teacher_names": c.get("teacher_names") or [],
            "department": c.get("department") or "",
            "credits": c.get("credits") or "",
            "term": c.get("term"),
        })
    meta = pack["meta"]
    return {
        "ok": True,
        "items": items,
        "term": meta.get("term"),
        "source": "catalog",
        "retrieved_at": meta.get("retrieved_at") or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": len(scored),
    }


def get_teacher(name: str) -> dict[str, Any] | None:
    pack = loaded()
    if not pack:
        return None
    return pack["by_name"].get((name or "").strip())


def teacher_payload(name: str) -> dict[str, Any]:
    rec = get_teacher(name)
    if not rec:
        return {"ok": False, "error": "teacher not in this term snapshot"}
    return {
        "ok": True,
        "name": rec["name"],
        "departments": rec.get("departments") or [],
        "bio": rec.get("bio"),
        "bio_source": rec.get("bio_source"),
        "courses": rec.get("courses") or [],
        "term": loaded()["meta"].get("term"),
        "note": "简介只在对上北京大学的 OpenAlex 记录时才写；对不上就空着。同名可能被合在一条里。",
    }
