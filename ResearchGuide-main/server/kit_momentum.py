# -*- coding: utf-8 -*-
"""给工具包的每个开放问题算「势头」：近 12 个月 vs 前 12 个月，arXiv 上相关论文数。

arXiv 整体每年都在涨，所以趋势按「比所在分类整体涨得快还是慢」算（相对增长 = 子领域增长 ÷ 分类增长）。

离线跑，结果写回 knowledge/kits/<id>.json 的 open_problems[].momentum，带核对日期；
竞争地图只读这个字段，不在页面加载时打 arXiv。势头只作修正，不单独决定拥挤度（DESIGN_PROPOSAL §1D.3）。

用法：uv run --no-project python server/kit_momentum.py llm-eval
"""
from __future__ import annotations

import datetime as dt
import json
import sys

import arxiv
import reading

UP, DOWN = 1.25, 0.8


def _window(end: dt.date, months: int) -> str:
    start = end.replace(year=end.year - months // 12)
    return f"[{start:%Y%m%d}0000 TO {end:%Y%m%d}2359]"


def _counts(query: str, today: dt.date) -> tuple[int, int]:
    year_ago = today.replace(year=today.year - 1)
    last = arxiv.count(f"{query} AND submittedDate:{_window(today, 12)}")
    prev = arxiv.count(f"{query} AND submittedDate:{_window(year_ago - dt.timedelta(days=1), 12)}")
    return last, prev


def momentum(cats: str, keywords: list[str], base: float, today: dt.date) -> dict:
    kws = " OR ".join(f'abs:"{k}"' for k in keywords)
    last, prev = _counts(f"({cats}) AND ({kws})", today)
    rel = (last / prev) / base if prev and base else None
    trend = "flat" if rel is None or last < 10 else "up" if rel >= UP else "down" if rel <= DOWN else "flat"
    return {"last12": last, "prev12": prev, "relative": round(rel, 2) if rel else None, "trend": trend,
            "checked_at": today.isoformat(), "query": f"({cats}) AND ({kws})"}


def main(kit_id: str) -> None:
    path = reading.KITS / f"{kit_id}.json"
    k = json.loads(path.read_text(encoding="utf-8"))
    today = dt.date.today()
    cats = " OR ".join(f"cat:{c}" for c in k["daily"]["categories"])
    b_last, b_prev = _counts(f"({cats})", today)
    base = b_last / b_prev
    print(f"{'(分类整体)':<20} {b_prev:>6} → {b_last:>6}  ×{base:.2f}", flush=True)
    for o in k["open_problems"]:
        o["momentum"] = momentum(cats, o["keywords"], base, today)
        m = o["momentum"]
        print(f"{o['id']:<20} {m['prev12']:>6} → {m['last12']:>6}  相对 ×{m['relative']}  {m['trend']}", flush=True)
    k["momentum_base"] = {"last12": b_last, "prev12": b_prev, "growth": round(base, 2), "checked_at": today.isoformat()}
    path.write_text(json.dumps(k, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "llm-eval")
