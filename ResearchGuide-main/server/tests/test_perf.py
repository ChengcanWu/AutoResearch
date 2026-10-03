# -*- coding: utf-8 -*-
"""性能与资源上限：评阅不阻塞事件循环、上传边收边限、.docx 套娃有上限、路径扫描线性、
并发相同请求只打一次上游、项目检索共用有上限的线程池、最新卡查询走索引。全部离线。"""
from __future__ import annotations

import asyncio
import io
import sqlite3
import sys
import threading
import time
import zipfile
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import arxiv  # noqa: E402
import llm  # noqa: E402
import main  # noqa: E402
import pku_adapter  # noqa: E402
import project_adapters  # noqa: E402
import projects  # noqa: E402
import store  # noqa: E402
import submission  # noqa: E402
from singleflight import SingleFlight  # noqa: E402


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "perf.db")
    store.init_db()
    monkeypatch.setattr(llm, "chat", lambda *a, **k: None)
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: None)


def _asgi():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://t")


def test_review_runs_off_the_event_loop(monkeypatch):
    monkeypatch.setattr(main, "_project_or_404", lambda uid, pid: {"id": pid})
    monkeypatch.setattr(submission, "review", lambda data, p: time.sleep(0.5) or {"passed": 0})
    monkeypatch.setattr(projects, "record_review", lambda uid, p, r: None)

    async def go():
        async with _asgi() as c:
            sub = asyncio.create_task(c.post("/api/projects/p/submit?uid=u", content=b"PK\x03\x04zip"))
            await asyncio.sleep(0.05)
            t0 = time.perf_counter()
            health = await c.get("/api/health")
            waited = time.perf_counter() - t0
            return (await sub).status_code, health.status_code, waited

    sub_code, health_code, waited = asyncio.run(go())
    assert sub_code == 200 and health_code == 200 and waited < 0.3


def test_upload_limit_stops_reading_early(monkeypatch):
    monkeypatch.setattr(main, "_project_or_404", lambda uid, pid: {"id": pid})
    monkeypatch.setattr(submission, "MAX_ZIP_BYTES", 1000)
    sent = []

    async def body():
        for _ in range(100):
            sent.append(1)
            yield b"x" * 100

    async def go():
        async with _asgi() as c:
            declared = await c.post("/api/projects/p/submit?uid=u", content=b"x" * 2000)
            streamed = await c.post("/api/projects/p/submit?uid=u", content=body())
            return declared.status_code, streamed.status_code

    assert asyncio.run(go()) == (413, 413)
    assert len(sent) < 20  # 超过 1000 字节就停，没有把 10 000 字节都读完


def test_review_queue_is_bounded(monkeypatch):
    monkeypatch.setattr(main, "_project_or_404", lambda uid, pid: {"id": pid})
    monkeypatch.setattr(main, "_review_pending", main.REVIEW_PENDING_MAX)

    async def go():
        async with _asgi() as c:
            return (await c.post("/api/projects/p/submit?uid=u", content=b"PK")).status_code

    assert asyncio.run(go()) == 503


def _docx(xml: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


def test_docx_inner_xml_is_bounded():
    assert "你好" in submission._docx_text(_docx("<w:p>你好</w:p>".encode()))
    bomb = _docx(b"<w:t>" + b"a" * (24 * 1024 * 1024) + b"</w:t>")
    assert len(bomb) < 100_000
    t0 = time.perf_counter()
    assert submission._docx_text(bomb) == ""
    assert time.perf_counter() - t0 < 0.5
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.md", "# 题目\n")
        z.writestr("报告.docx", bomb)
    bundle = submission.read_zip(outer.getvalue())
    assert bundle["texts"]["报告.docx"] == "" and any("报告.docx" in n for n in bundle["notes"])


def test_path_scan_is_linear_and_matches_old_behaviour():
    import re
    old = r"[\w\-./一-鿿]+\.(?:png|jpg|jpeg|svg|csv|xlsx|pdf|ipynb|py|txt|md|json|docx|r|m)"
    for text in ["见 results/fig1.png 和 data.csv。", "./a.PNG b/c.md.bak x.pngx 中文/图.jpg", "a.pngb.csv foo.r.m", "无"]:
        assert set(re.findall(old, text, flags=re.I)) == submission._path_tokens(text)
    t0 = time.perf_counter()
    submission._path_tokens("a" * 64 * 1024)
    assert time.perf_counter() - t0 < 0.1


def test_singleflight_shares_one_call():
    sf, calls = SingleFlight(), []

    def slow():
        calls.append(1)
        time.sleep(0.2)
        return 42

    out = []
    ts = [threading.Thread(target=lambda: out.append(sf.do("k", slow))) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert calls == [1] and out == [42] * 8 and sf.in_flight() == 0


def test_concurrent_identical_arxiv_and_course_lookups_hit_upstream_once(monkeypatch):
    monkeypatch.setattr(arxiv, "_META", {})
    got = []
    feed = b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
    monkeypatch.setattr(arxiv, "_get", lambda url, timeout=20: got.append(url) or time.sleep(0.2) or feed)
    ts = [threading.Thread(target=arxiv.query, args=({"id_list": "2310.17623"},)) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(got) == 1

    monkeypatch.setattr(pku_adapter, "_SEARCH_CACHE", {})
    monkeypatch.setattr(pku_adapter, "_default_term", lambda: "25-26-1")
    runs = []
    monkeypatch.setattr(pku_adapter, "_run_pku", lambda args, timeout=60: runs.append(args) or time.sleep(0.2) or (0, {"items": []}, ""))
    ts = [threading.Thread(target=pku_adapter.search_courses, args=("统计",)) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(runs) == 1


def test_project_searches_share_a_bounded_pool(monkeypatch):
    fetched = []

    def slow(src, direction, stage, terms):
        fetched.append(src["id"])
        time.sleep(0.6)
        return [{"title": "神经网络 实验", "url": f"https://x/{src['id']}"}]

    sources = [{"id": f"s{i}", "name": f"S{i}", "directions": ["ai"], "adapter": "slow", "samples": [{"title": "快照", "url": "https://x/s"}]}
               for i in range(6)]
    monkeypatch.setattr(projects, "registry", lambda: {"sources": sources})
    monkeypatch.setattr(project_adapters, "ADAPTERS", {"slow": slow})
    monkeypatch.setattr(projects, "SEARCH_BUDGET", 0.2)
    monkeypatch.setattr(store, "list_projects", lambda uid: [])
    peak = []

    def run():
        projects.search("u", "ai", 1)
        peak.append(sum(t.name.startswith("source") for t in threading.enumerate()))

    ts = [threading.Thread(target=run) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert max(peak) <= projects.SOURCE_WORKERS
    assert sorted(fetched) == sorted(set(fetched))  # 六次相同检索，每个来源只打一次上游
    time.sleep(0.7)


def test_latest_cards_uses_the_version_index():
    with sqlite3.connect(store.DB_PATH) as c:
        plan = c.execute(
            "EXPLAIN QUERY PLAN SELECT data FROM cards c WHERE user_id='u' AND kit_id='k' AND version = "
            "(SELECT MAX(version) FROM cards c2 WHERE c2.user_id=c.user_id AND c2.kit_id=c.kit_id AND c2.arxiv_id=c.arxiv_id)").fetchall()
    assert any("idx_cards_ver" in row[-1] for row in plan)
