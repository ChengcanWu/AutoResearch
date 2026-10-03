# -*- coding: utf-8 -*-
"""pku-course-skill 适配层（SkillProtocol 的 W0 进程版实现）。

沿用 legacy discipline-map/server.py 验证过的做法：
- uv run --locked 子进程调用 skills/pku-course/scripts/pku.py；
- Windows 下强制 UTF-8，避免课程名乱码；
- 失败返回结构化错误 {ok: False, error}，绝不编造课程。

W1（陈浩文）：改为进程内 adapter（直接 import skill 的函数），子进程作为 fallback。
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import catalog
from limits import TTLCache
from singleflight import SingleFlight

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = (ROOT / "skills" / "pku-course").resolve()
PKU_PY = SKILL_DIR / "scripts" / "pku.py"
DEFAULT_TERM_FILE = Path(__file__).resolve().parent / "data" / "cached_term.txt"
TERM_MAX_AGE = 3 * 24 * 3600   # 学期缓存三天后重查，避免换学期后一直查旧学期
SEARCH_TTL = 10 * 60           # 同一查询十分钟内复用上次的真实结果（每次都起 uv 子进程要 1–3 秒）
_SEARCH_CACHE = TTLCache(SEARCH_TTL, 512)
_FLIGHT = SingleFlight()  # 同一查询并发时只起一个 uv 子进程


def _run_pku(args: list[str], timeout: int = 60) -> tuple[int, Any, str]:
    if not PKU_PY.exists():
        return 2, None, f"pku-course-skill not found at {SKILL_DIR}"
    cmd = ["uv", "run", "--locked", "--project", str(SKILL_DIR), str(PKU_PY), *args]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    try:
        proc = subprocess.run(cmd, capture_output=True, env=env, timeout=timeout, cwd=str(ROOT))
    except FileNotFoundError:
        return 2, None, "uv not found; install uv 0.10+ and retry"
    except subprocess.TimeoutExpired:
        return 2, None, "course search timed out"

    def decode(blob: bytes) -> str:
        if not blob:
            return ""
        for enc in ("utf-8", "gbk", "cp936"):
            try:
                return blob.decode(enc)
            except UnicodeDecodeError:
                continue
        return blob.decode("utf-8", errors="replace")

    stdout, stderr = decode(proc.stdout).strip(), decode(proc.stderr).strip()
    data = None
    if stdout:
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            stderr = (stderr + "\n" + stdout).strip()
    return proc.returncode, data, stderr


def _default_term() -> str | None:
    """默认学期：优先用缓存，拿不到就调 options 并缓存。"""
    if DEFAULT_TERM_FILE.exists() and time.time() - DEFAULT_TERM_FILE.stat().st_mtime < TERM_MAX_AGE:
        cached = DEFAULT_TERM_FILE.read_text(encoding="utf-8").strip()
        if cached:
            return cached
    code, data, _err = _FLIGHT.do(("options",), lambda: _run_pku(["options", "--limit", "1"]))
    if code == 0 and isinstance(data, dict) and data.get("items"):
        term = data["items"][0]["value"]
        try:
            DEFAULT_TERM_FILE.parent.mkdir(parents=True, exist_ok=True)
            DEFAULT_TERM_FILE.write_text(term, encoding="utf-8")
        except OSError:
            pass
        return term
    return None


def search_courses(query: str, limit: int = 5, term: str = "") -> dict[str, Any]:
    """先查本机学期快照；没有快照时再走教务实时检索。"""
    query = (query or "").strip()
    if not query:
        return {"ok": False, "error": "query is required"}
    if catalog.available():
        return catalog.search_courses(query, limit)
    term = term.strip() or (_default_term() or "")
    if not term:
        return {"ok": False, "error": "cannot resolve current term（教务接口不可达）"}
    limit = min(10, max(1, limit))
    key = (query, limit, term)
    hit, res = _SEARCH_CACHE.lookup(key)
    if hit:
        return {**res, "cached": True}
    return _FLIGHT.do(("search",) + key, lambda: _search_live(key))


def _search_live(key: tuple[str, int, str]) -> dict[str, Any]:
    query, limit, term = key
    hit, res = _SEARCH_CACHE.lookup(key)
    if hit:  # 排在前面的那一个刚查完
        return {**res, "cached": True}
    args = ["search", "--term", term, "--offset", "0", "--limit", str(limit), "--query", query]
    code, data, err = _run_pku(args, timeout=90)
    if not isinstance(data, dict):
        return {"ok": False, "error": err or "course search failed (live)"}
    items = data.get("items") or data.get("results") or []
    res = {"ok": code in (0, 1), "items": items, "term": term,
           "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "warning": None if code == 0 else (err or "partial retrieval")}
    if code == 0:  # 只缓存完整成功的结果；失败和部分结果下次照常重查
        _SEARCH_CACHE.set(key, res)
    return res
