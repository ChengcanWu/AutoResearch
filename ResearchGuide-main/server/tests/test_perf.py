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
from limits import TTLCache  # noqa: E402
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
    monkeypatch.setattr(arxiv, "_META", TTLCache(60, 16))
    got = []
    feed = b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
    monkeypatch.setattr(arxiv, "_get", lambda url, timeout=20: got.append(url) or time.sleep(0.2) or feed)
    ts = [threading.Thread(target=arxiv.query, args=({"id_list": "2310.17623"},)) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(got) == 1

    monkeypatch.setattr(pku_adapter, "_SEARCH_CACHE", TTLCache(60, 16))
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


# ---------- 第二轮 ----------

def test_many_identical_paper_requests_share_one_fetch_without_holding_threads(monkeypatch):
    calls = []
    paper = {"id": "2310.17623", "title": "T", "source": "html", "url": "u", "text": "Abstract\nx\n6 Limitations\ny"}
    monkeypatch.setattr(arxiv, "fulltext", lambda aid: calls.append(aid) or time.sleep(0.4) or paper)

    async def go():
        async with _asgi() as c:
            papers = [asyncio.create_task(c.get("/api/papers/2310.17623")) for _ in range(40)]
            await asyncio.sleep(0.05)
            t0 = time.perf_counter()
            health = await c.get("/api/health")
            waited = time.perf_counter() - t0
            return [r.status_code for r in await asyncio.gather(*papers)], health.status_code, waited

    codes, health, waited = asyncio.run(go())
    assert set(codes) == {200} and health == 200 and len(calls) == 1 and waited < 0.3


def test_identical_searches_do_not_starve_other_sources(monkeypatch):
    slow_calls = []

    def slow(src, direction, stage, terms):
        slow_calls.append(1)
        time.sleep(0.8)
        return [{"title": "神经网络 慢", "url": "https://x/slow"}]

    def fast(src, direction, stage, terms):
        return [{"title": "神经网络 快", "url": "https://x/fast"}]

    sources = [{"id": "slow", "name": "慢", "directions": ["ai"], "adapter": "slow", "samples": []},
               {"id": "fast", "name": "快", "directions": ["ai"], "adapter": "fast", "samples": []}]
    monkeypatch.setattr(projects, "registry", lambda: {"sources": sources})
    monkeypatch.setattr(project_adapters, "ADAPTERS", {"slow": slow, "fast": fast})
    monkeypatch.setattr(projects, "SEARCH_BUDGET", 0.4)
    monkeypatch.setattr(store, "list_projects", lambda uid: [])
    results = []
    ts = [threading.Thread(target=lambda: results.append(projects.search("u", "ai", 1))) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    for r in results:
        st = {s["id"]: s for s in r["sources"]}
        assert st["fast"].get("live")  # 快来源没被八个相同的慢任务挤到超时
    assert len(slow_calls) == 1
    time.sleep(0.9)


class _Trickle(__import__("http.server").server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        size = 4096 if self.path == "/big" else 200
        for _ in range(size):
            self.wfile.write(b"x" * (256 if self.path == "/big" else 1))
            self.wfile.flush()
            if self.path != "/big":
                time.sleep(0.02)

    def log_message(self, *a):
        pass


@pytest.fixture()
def trickle():
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Trickle)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_external_reads_have_a_total_deadline_and_byte_cap(trickle, monkeypatch):
    t0 = time.perf_counter()
    with pytest.raises(project_adapters.AdapterError):
        project_adapters.http(trickle + "/slow", timeout=0.2, as_json=False)
    assert time.perf_counter() - t0 < 0.6  # 每 20 毫秒滴一个字节，单看 socket 超时永远不会触发

    monkeypatch.setattr(project_adapters, "MAX_BYTES", 10_000)
    with pytest.raises(project_adapters.AdapterError):
        project_adapters.http(trickle + "/big", timeout=5, as_json=False)

    monkeypatch.setattr(arxiv, "_LAST_CALL", [0.0])
    t0 = time.perf_counter()
    with pytest.raises(arxiv.ArxivError):
        arxiv._get(trickle + "/slow", timeout=0.2)
    assert time.perf_counter() - t0 < 0.6


def test_stalled_uploads_time_out_and_do_not_block_ready_ones(monkeypatch):
    monkeypatch.setattr(main, "_project_or_404", lambda uid, pid: {"id": pid})
    monkeypatch.setattr(main, "UPLOAD_SECONDS", 0.3)
    monkeypatch.setattr(submission, "review", lambda data, p: {"passed": 1})
    monkeypatch.setattr(projects, "record_review", lambda uid, p, r: None)

    async def stalled():
        yield b"PK"
        await asyncio.sleep(5)
        yield b"never"

    async def go():
        async with _asgi() as c:
            stuck = [asyncio.create_task(c.post("/api/projects/p/submit?uid=u", content=stalled())) for _ in range(6)]
            await asyncio.sleep(0.05)
            ready = await c.post("/api/projects/p/submit?uid=u", content=b"PK\x03\x04zip")
            return ready.status_code, [r.status_code for r in await asyncio.gather(*stuck)]

    t0 = time.perf_counter()
    ready, stuck = asyncio.run(go())
    assert ready == 200 and set(stuck) == {408} and time.perf_counter() - t0 < 2


def test_rarity_reads_peers_in_batches(monkeypatch):
    import json as _json
    now = "2026-10-03T00:00:00+00:00"
    with sqlite3.connect(store.DB_PATH) as c:
        c.executemany("INSERT INTO cards VALUES(?,?,?,?,?,?,?,?)",
                      [(f"c{i}", f"u{i}", "llm-eval", "2310.17623", 1, _json.dumps({}), "pass", now) for i in range(1000)])
        c.executemany("INSERT INTO facts VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                      [(f"f{i}", f"u{i}", "capability", "card:llm-eval:2310.17623", "v", 0.8, "behavior", "[]", "active", now, now) for i in range(1000)])
        c.executemany("INSERT INTO edges(id, user_id, kind, text, evidence_url, ref, created_at) VALUES(?,?,?,?,?,?,?)",
                      [(f"e{i}", f"u{i}", "language", "粤语母语", "", "", now) for i in range(0, 1000, 3)])
    me = store.create_user("me")["uid"]
    store.add_edge(me, "language", "粤语母语")
    store.add_edge(me, "course", "修过《数理统计》")
    opened = []
    real = store._conn
    monkeypatch.setattr(store, "_conn", lambda: opened.append(1) or real())
    import positioning
    t0 = time.perf_counter()
    r = positioning.combo_rarity(me, "llm-eval")
    assert r["status"] == "ok" and len(opened) < 20 and time.perf_counter() - t0 < 0.5


def test_quote_checks_prepare_each_paper_once(monkeypatch):
    import quotes
    import reading
    from test_reading import DIMS, GOOD, PAPER
    quotes._prepared.cache_clear()
    calls = []
    real = quotes._index
    monkeypatch.setattr(quotes, "_index", lambda text: calls.append(1) or real(text))
    review = reading.review_card(reading.kit("llm-eval"), PAPER, GOOD, DIMS, [])
    assert review["pass"] and len(calls) == 1


def test_ttl_cache_drops_expired_entries_and_caps_size():
    c = TTLCache(0.05, 1000)
    for i in range(200):
        c.set(i, i)
    time.sleep(0.06)
    assert c.lookup("other") == (False, None) and len(c) == 0
    small = TTLCache(60, 3)
    for i in range(10):
        small.set(i, [])
    assert len(small) == 3 and small.lookup(9) == (True, []) and small.lookup(0) == (False, None)


# ---------- 第三轮 ----------

def test_malformed_docx_xml_is_stripped_in_linear_time():
    t0 = time.perf_counter()
    assert submission._docx_text(_docx(b"<" * 66_000)) == ""
    assert submission._strip_xml("<w:p><w:t>a</w:t></w:p>x<y") == "a\nx"
    assert time.perf_counter() - t0 < 0.2


def test_zip_with_too_many_entries_is_rejected_before_parsing(monkeypatch):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i in range(submission.MAX_ENTRIES + 500):
            z.writestr(f"d{i}/", b"")
        z.writestr("README.md", "# 题目")
    data = buf.getvalue()
    opened = []
    real = zipfile.ZipFile
    monkeypatch.setattr(zipfile, "ZipFile", lambda *a, **k: opened.append(1) or real(*a, **k))
    with pytest.raises(submission.SubmissionError):
        submission.read_zip(data)
    assert opened == []  # 没等 zipfile 把几千个条目对象建出来就拒了


def test_daily_failure_is_shared_not_retried_per_request(monkeypatch):
    from limits import TTLCache as _T
    monkeypatch.setattr(main, "_DAILY_MISS", _T(30, 8))
    uid = store.create_user("t")["uid"]
    calls = []

    def down(*a, **k):
        calls.append(1)
        time.sleep(0.3)
        raise arxiv.ArxivError("连不上 arXiv")

    monkeypatch.setattr(arxiv, "recent", down)

    async def go():
        async with _asgi() as c:
            reqs = [asyncio.create_task(c.get(f"/api/daily?uid={uid}&kit=llm-eval")) for _ in range(40)]
            await asyncio.sleep(0.05)
            t0 = time.perf_counter()
            health = await c.get("/api/health")
            waited = time.perf_counter() - t0
            rs = await asyncio.gather(*reqs)
            again = await c.get(f"/api/daily?uid={uid}&kit=llm-eval")  # 三十秒内直接用失败结果
            return rs, health.status_code, waited, again

    rs, health, waited, again = asyncio.run(go())
    assert {r.status_code for r in rs} == {200} and all(r.json()["error"] for r in rs)
    assert health == 200 and waited < 0.3 and len(calls) == 1 and again.json()["error"]


class _SlowHead(__import__("http.server").server.BaseHTTPRequestHandler):
    def do_GET(self):
        for b in b"HTTP/1.0 200 OK\r\nX-Pad: " + b"a" * 200:
            self.wfile.write(bytes([b]))
            self.wfile.flush()
            time.sleep(0.02)

    def log_message(self, *a):
        pass


def test_deadline_covers_slow_response_headers(monkeypatch):
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _SlowHead)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/h"
    try:
        t0 = time.perf_counter()
        with pytest.raises(project_adapters.AdapterError):
            project_adapters.http(url, timeout=0.2, as_json=False)
        assert time.perf_counter() - t0 < 0.6
        monkeypatch.setattr(arxiv, "_LAST_CALL", [0.0])
        t0 = time.perf_counter()
        with pytest.raises(arxiv.ArxivError):
            arxiv._get(url, timeout=0.2)
        assert time.perf_counter() - t0 < 0.6  # 限速锁也只被占这么久
    finally:
        srv.shutdown()


def test_matrix_conflicts_are_grouped_not_paired():
    import json as _json
    import reading
    now = "2026-10-03T00:00:00+00:00"
    cards = []
    for i in range(500):
        aid = f"2401.{i:05d}"
        data = {"arxiv_id": aid, "title": f"P{i}", "version": 1, "status": "pass",
                "dims": {"metric": "准确率", "direction": "up" if i % 2 else "down", "models": "m", "task": "t", "language": "英文"}}
        cards.append((f"c{i}", "u", "llm-eval", aid, 1, _json.dumps(data), "pass", now))
    with sqlite3.connect(store.DB_PATH) as c:
        c.executemany("INSERT INTO cards VALUES(?,?,?,?,?,?,?,?)", cards)
    m = reading.matrix("u", "llm-eval")
    (g,) = m["flags"]["conflicts"]
    assert (g["up_total"], g["down_total"]) == (250, 250) and len(g["up"]) == reading.CONFLICT_SHOW
    assert len(_json.dumps(m["flags"]["conflicts"])) < 2000


def test_statement_refs_group_once():
    import json as _json
    rows = [(f"{u}-{v}", f"u{u}", "k", v, f"r{v}", _json.dumps({}), f"2026-09-{1 if v <= 5 else 21:02d}T00:00:00+00:00")
            for u in range(60) for v in range(1, 301)]
    with sqlite3.connect(store.DB_PATH) as c:
        c.executemany("INSERT INTO statements VALUES(?,?,?,?,?,?,?)", rows)
    t0 = time.perf_counter()
    refs = store.statement_refs("k", "2026-09-10T00:00:00+00:00")
    assert len(refs) == 60 and set(refs.values()) == {"r5"} and time.perf_counter() - t0 < 0.05


# ---------- 第四轮 ----------

class _SlowReply(__import__("http.server").server.BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.send_response(200)
        self.end_headers()
        for _ in range(100):
            self.wfile.write(b" ")
            self.wfile.flush()
            time.sleep(0.02)

    def log_message(self, *a):
        pass


def test_model_calls_have_a_total_deadline():
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _SlowReply)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        t0 = time.perf_counter()
        data, err = llm._post(f"http://127.0.0.1:{srv.server_address[1]}/chat/completions", "k", {"m": 1}, 0.2)
        assert data is None and err.startswith("limit") and time.perf_counter() - t0 < 0.6
    finally:
        srv.shutdown()


def test_slow_dns_counts_against_the_deadline(monkeypatch):
    import socket
    import urllib.request
    import limits
    real = socket.getaddrinfo
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: time.sleep(0.4) or real(*a, **k))
    t0 = time.perf_counter()
    with pytest.raises(limits.ReadLimitError):
        limits.fetch(urllib.request.Request("http://example.invalid/"), timeout=0.08, max_bytes=1000)
    assert time.perf_counter() - t0 < 0.3


def test_prefixed_zip64_is_checked_before_parsing(monkeypatch):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", allowZip64=True) as z:
        for i in range(70_000):  # 超过 65535 条，写成 zip64
            z.writestr(f"d{i}/", b"")
    data = b"JUNK" * 100 + buf.getvalue()
    opened = []
    real = zipfile.ZipFile
    monkeypatch.setattr(zipfile, "ZipFile", lambda *a, **k: opened.append(1) or real(*a, **k))
    with pytest.raises(submission.SubmissionError):
        submission.read_zip(data)
    assert opened == []
    with pytest.raises(submission.SubmissionError):  # 有目录尾、zip64 记录对不上的，不交给 zipfile 猜
        submission._directory_size(data[:-22 - 20 - 56] + b"\0" * 56 + data[-22 - 20:])


def test_competition_map_counts_demand_with_a_set(monkeypatch):
    import json as _json
    import positioning
    monkeypatch.setattr(positioning, "_cutoff", lambda: "9999")
    old = "2026-09-01T00:00:00+00:00"
    with sqlite3.connect(store.DB_PATH) as c:
        c.executemany("INSERT INTO cards VALUES(?,?,?,?,?,?,?,?)",
                      [(f"c{i}", f"u{i}", "llm-eval", "2310.17623", 1, _json.dumps({}), "pass", old) for i in range(10_000)])
        c.executemany("INSERT INTO statements VALUES(?,?,?,?,?,?,?)",
                      [(f"s{i}", f"u{i}", "llm-eval", 1, "multi-test" if i % 2 else "single-dup", _json.dumps({}), old) for i in range(10_000)])
    me = store.create_user("me")["uid"]
    t0 = time.perf_counter()
    rows = {r["id"]: r for r in positioning.competition_map(me, "llm-eval")["rows"]}
    assert rows["multi-test"]["demand"]["band"] == "热" and rows["shuffle"]["demand"]["band"] == "冷"
    assert time.perf_counter() - t0 < 1.5


def test_matrix_highlights_every_conflicting_row():
    import json as _json
    import reading
    now = "2026-10-03T00:00:00+00:00"
    with sqlite3.connect(store.DB_PATH) as c:
        c.executemany("INSERT INTO cards VALUES(?,?,?,?,?,?,?,?)", [
            (f"c{i}", "u", "llm-eval", f"2402.{i:05d}", 1,
             _json.dumps({"arxiv_id": f"2402.{i:05d}", "title": f"P{i}", "version": 1, "status": "pass",
                          "dims": {"metric": "胜率", "direction": "up" if i < 15 else "down"}}), "pass", now)
            for i in range(30)] + [
            ("c99", "u", "llm-eval", "2402.00099", 1,
             _json.dumps({"arxiv_id": "2402.00099", "title": "无关", "version": 1, "status": "pass",
                          "dims": {"metric": "准确率", "direction": "up"}}), "pass", now)])
    m = reading.matrix("u", "llm-eval")
    assert sum(r["conflict"] for r in m["rows"]) == 30 and len(m["flags"]["conflicts"][0]["up"]) == reading.CONFLICT_SHOW
