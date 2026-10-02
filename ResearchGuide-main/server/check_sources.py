# -*- coding: utf-8 -*-
"""一条命令复测「项目」的全部来源：主页能不能打开、实时接口能不能取到项目、各要多久。

用法（在 ResearchGuide-main 目录）：
    uv run --no-project python server/check_sources.py
请在大陆网络下跑一次，把最后的表格贴到群里或 PR 里。
只发 GET（和鲸、开源之夏这类本来就是 POST 查询的接口除外），不登录、不提交任何东西。
结果另存一份到 server/data/source_check.json（不入库）。
"""
from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import project_adapters  # noqa: E402
import projects  # noqa: E402

OUT = Path(__file__).resolve().parent / "data" / "source_check.json"


def _w(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    """按显示宽度补空格（中文占两格），表格才对得齐。"""
    while _w(text) > width:
        text = text[:-1]
    return text + " " * (width - _w(text))


def _where() -> str:
    """只取出口所在地区，不打印 IP（结果会被贴到群里）。"""
    try:
        req = urllib.request.Request("https://myip.ipip.net", headers={"User-Agent": project_adapters.UA})
        with urllib.request.urlopen(req, timeout=8) as r:
            text = r.read().decode("utf-8", errors="replace")
        m = re.search(r"来自于[：:]\s*(.+)", text)
        return m.group(1).strip() if m else "未知"
    except Exception:
        return "未知（查询失败）"


def _home(src: dict) -> dict:
    url = src.get("home_url") or ""
    if not url:
        return {"ok": False, "code": "-", "ms": 0}
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": project_adapters.UA, "Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=12) as r:
            code = r.status
        return {"ok": 200 <= code < 400, "code": code, "ms": int((time.time() - t0) * 1000)}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "code": exc.code, "ms": int((time.time() - t0) * 1000)}
    except Exception as exc:
        return {"ok": False, "code": type(exc).__name__, "ms": int((time.time() - t0) * 1000)}


def _live(src: dict) -> dict:
    fetch = project_adapters.ADAPTERS.get(src.get("adapter") or "")
    if not fetch:
        return {}
    direction = (src.get("directions") or ["ai"])[0]
    t0 = time.time()
    try:
        items = fetch(src, direction, 1, projects.DIR_TERMS.get(direction, [])[:2])
        return {"ok": bool(items), "count": len(items), "ms": int((time.time() - t0) * 1000), "direction": direction,
                "first": items[0]["title"][:40] if items else "", "error": "" if items else "接口通了，但没有取到项目"}
    except project_adapters.AdapterError as exc:
        return {"ok": False, "count": 0, "ms": int((time.time() - t0) * 1000), "direction": direction, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "count": 0, "ms": int((time.time() - t0) * 1000), "direction": direction, "error": type(exc).__name__}


def main() -> int:
    reg = projects.registry()
    sources = reg["sources"]
    where = _where()
    print(f"出口地区：{where}；共 {len(sources)} 个来源，其中 {sum(1 for s in sources if s.get('adapter'))} 个走实时接口。检查中…\n", flush=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        homes = list(pool.map(_home, sources))
        lives = list(pool.map(_live, sources))
    rows = []
    for src, home, live in zip(sources, homes, lives):
        rows.append({"id": src["id"], "name": src["name"], "home": home, "live": live})
    print(f"{_pad('来源', 34)}  {_pad('主页', 22)}  实时接口")
    for r in rows:
        h = r["home"]
        home = f"{'✓' if h['ok'] else '✕'} {h['code']} {h['ms']}ms"
        lv = r["live"]
        live = "—（快照 + 路线）" if not lv else (f"✓ {lv['count']} 条 {lv['ms']}ms" if lv["ok"] else f"✕ {lv['error']} {lv['ms']}ms")
        print(f"{_pad(r['name'], 34)}  {_pad(home, 22)}  {live}")
    live_rows = [r for r in rows if r["live"]]
    ok_live = sum(1 for r in live_rows if r["live"]["ok"])
    ok_home = sum(1 for r in rows if r["home"]["ok"])
    print(f"\n小结：实时接口 {ok_live}/{len(live_rows)} 能取到项目，主页 {ok_home}/{len(rows)} 能打开。出口地区：{where}。")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"checked_at": projects.now_iso(), "where": where, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"明细已存到 {OUT.relative_to(Path.cwd()) if OUT.is_relative_to(Path.cwd()) else OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
