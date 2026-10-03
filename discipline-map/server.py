# -*- coding: utf-8 -*-
"""学科瞭望本地服务：静态站点 + 北大公开课检索 API（包装 pku-course-skill）。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
SKILL_DIR = (ROOT.parent / "pku-course-skill-main").resolve()
PKU_PY = SKILL_DIR / "scripts" / "pku.py"
HOST = "127.0.0.1"
PORT = int(os.environ.get("DISCIPLINE_MAP_PORT", "8765"))


def run_pku(args: list[str], timeout: int = 60) -> tuple[int, dict | list | None, str]:
    if not PKU_PY.exists():
        return 2, None, f"pku-course-skill not found at {SKILL_DIR}"
    cmd = [
        "uv", "run", "--locked",
        "--project", str(SKILL_DIR),
        str(PKU_PY),
        *args,
    ]
    env = os.environ.copy()
    # Windows 下子进程默认常为 GBK；强制 UTF-8，避免课程名变成乱码
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            env=env,
            timeout=timeout,
            cwd=str(ROOT),
        )
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

    stderr = decode(proc.stderr).strip()
    stdout = decode(proc.stdout).strip()
    data = None
    if stdout:
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            stderr = (stderr + "\n" + stdout).strip()
    return proc.returncode, data, stderr


CACHE_TTL = 10 * 60   # 同样的参数十分钟内复用上次的完整结果（每次起 uv 子进程要 1–3 秒）
CACHE_MAX = 512
_cache: dict[tuple[str, ...], tuple[float, tuple]] = {}
_inflight: dict[tuple[str, ...], list] = {}
_lock = threading.Lock()


def run_pku_cached(args: list[str], timeout: int = 60) -> tuple[int, dict | list | None, str]:
    """缓存 + 并发去重：相同参数同时到的请求只起一个子进程，其余等它的结果。只缓存完整成功的结果。"""
    key = tuple(args)
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < CACHE_TTL:
            return hit[1]
        call = _inflight.get(key)
        leader = call is None
        if leader:
            call = _inflight[key] = [threading.Event(), (2, None, "course search failed")]
    if not leader:
        call[0].wait()
        return call[1]
    try:
        call[1] = run_pku(args, timeout)
        if call[1][0] == 0:
            with _lock:
                now = time.time()
                if len(_cache) >= CACHE_MAX:
                    for k in [k for k, (t, _) in _cache.items() if now - t >= CACHE_TTL]:
                        del _cache[k]
                    while len(_cache) >= CACHE_MAX:
                        del _cache[min(_cache, key=lambda k: _cache[k][0])]
                _cache[key] = (now, call[1])
        return call[1]
    finally:
        with _lock:
            _inflight.pop(key, None)
        call[0].set()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/terms":
            self._api_terms()
            return
        if parsed.path == "/api/courses":
            self._api_courses(parse_qs(parsed.query))
            return
        if parsed.path == "/api/health":
            self._json(200, {"ok": True, "skill": str(SKILL_DIR), "skillExists": PKU_PY.exists()})
            return
        super().do_GET()

    def _json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _api_terms(self):
        code, data, err = run_pku_cached(["options", "--limit", "10"])
        if code != 0 or not isinstance(data, dict):
            self._json(502, {"error": err or "failed to list terms", "code": code})
            return
        self._json(200, data)

    def _api_courses(self, qs: dict):
        query = (qs.get("query") or qs.get("q") or [""])[0].strip()
        term = (qs.get("term") or [""])[0].strip()
        teacher = (qs.get("teacher") or [""])[0].strip()
        department = (qs.get("department") or ["0"])[0].strip() or "0"
        try:
            offset = max(0, int((qs.get("offset") or ["0"])[0]))
            limit = min(10, max(1, int((qs.get("limit") or ["10"])[0])))
        except ValueError:
            self._json(400, {"error": "offset/limit must be integers"})
            return
        if not query and not teacher:
            self._json(400, {"error": "query or teacher is required"})
            return
        if not term:
            # 默认取 options 的第一条学期
            tcode, tdata, terr = run_pku_cached(["options", "--limit", "1"])
            if tcode != 0 or not isinstance(tdata, dict) or not tdata.get("items"):
                self._json(502, {"error": terr or "cannot resolve default term"})
                return
            term = tdata["items"][0]["value"]

        args = ["search", "--term", term, "--offset", str(offset), "--limit", str(limit)]
        if query:
            args.extend(["--query", query])
        if teacher:
            args.extend(["--teacher", teacher])
        if department and department != "0":
            args.extend(["--department", department])

        code, data, err = run_pku_cached(args, timeout=90)
        if not isinstance(data, dict):
            self._json(502, {"error": err or "invalid search response", "code": code})
            return
        data = dict(data)
        data["term"] = term
        data["query"] = query
        data["warning"] = None if code == 0 else (err or "partial/failed retrieval")
        status = 200 if code in (0, 1) else 502
        self._json(status, data)

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))


def main():
    if not PKU_PY.exists():
        print(f"warning: pku skill missing at {SKILL_DIR}", file=sys.stderr)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"学科瞭望: http://{HOST}:{PORT}/")
    print(f"API:      http://{HOST}:{PORT}/api/health")
    print(f"skill:    {SKILL_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
