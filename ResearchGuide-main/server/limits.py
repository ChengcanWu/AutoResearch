# -*- coding: utf-8 -*-
"""两个上限工具：读外部响应有总时限和字节上限；内存缓存有过期和条数上限。

- urlopen 的 timeout 只管「多久没收到数据」，一个慢慢滴数据的服务器能让连接、响应头、正文一直拖下去。
  fetch 给整个请求（连接、TLS、响应头、正文）一个总截止时间：到点由看门狗关掉 socket；正文另有字节上限。
- 原来的缓存是普通 dict：过期的只是不再命中，但一直留在内存里；TTLCache 过期即删，超过条数先删最旧的。
"""
from __future__ import annotations

import http.client
import socket
import threading
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from typing import Any, Hashable

CHUNK = 64 * 1024


class ReadLimitError(OSError):
    """超过总时限或字节上限。继承 OSError，调用方原有的网络错误处理照样接得住。"""


def _socket_of(resp: Any) -> Any:
    try:
        return resp.fp.raw._sock  # CPython http.client 的底层 socket；拿不到就只靠两次读之间检查
    except AttributeError:
        return None


def read_limited(resp: Any, max_bytes: int, deadline: float) -> bytes:
    """deadline 是 time.monotonic() 的绝对时刻。每次读之前把 socket 超时收紧到剩余时间。"""
    buf = bytearray()
    sock = _socket_of(resp)
    read = getattr(resp, "read1", None) or resp.read
    while True:
        left = deadline - time.monotonic()
        if left <= 0:
            raise ReadLimitError("超过总时限")
        if sock is not None:
            try:
                sock.settimeout(left)
            except OSError:
                pass
        try:
            chunk = read(CHUNK)
        except TimeoutError as exc:
            raise ReadLimitError("超过总时限") from exc
        if not chunk:
            return bytes(buf)
        buf += chunk
        if len(buf) > max_bytes:
            raise ReadLimitError(f"响应超过 {max_bytes // 1024 // 1024} MB")


class _Watch:
    """记下这次请求用到的 socket；到截止时间就把它们全部 shutdown，阻塞在读响应头上的线程会立刻出错返回。"""

    def __init__(self, deadline: float) -> None:
        self.deadline = deadline
        self.killed = False
        self._socks: list[socket.socket] = []
        self._lock = threading.Lock()

    def adopt(self, sock: socket.socket) -> socket.socket:
        with self._lock:
            if self.killed:
                _shut(sock)
            self._socks.append(sock)
        try:
            sock.settimeout(max(0.01, self.deadline - time.monotonic()))
        except OSError:
            pass
        return sock

    def kill(self) -> None:
        with self._lock:
            self.killed = True
            socks = list(self._socks)
        for sock in socks:
            _shut(sock)


def _shut(sock: socket.socket) -> None:
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass  # 已经关了，或是 TLS 包装后被摘走的原始 socket


def _watched(base: type, watch: _Watch) -> type:
    class Conn(base):  # type: ignore[misc, valid-type]
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # 刚建好 TCP 连接就登记：TLS 握手慢也在看门狗范围内
            self._create_connection = lambda *a, **k: watch.adopt(socket.create_connection(*a, **k))

        def connect(self):
            super().connect()
            watch.adopt(self.sock)  # TLS 包装后的 socket

    return Conn


class _HTTP(urllib.request.HTTPHandler):
    def __init__(self, watch: _Watch) -> None:
        super().__init__()
        self.watch = watch

    def http_open(self, req):
        return self.do_open(_watched(http.client.HTTPConnection, self.watch), req)


class _HTTPS(urllib.request.HTTPSHandler):
    def __init__(self, watch: _Watch) -> None:
        super().__init__()
        self.watch = watch

    def https_open(self, req):
        return self.do_open(_watched(http.client.HTTPSConnection, self.watch), req, context=self._context)


def fetch(req: urllib.request.Request, *, timeout: float, max_bytes: int) -> bytes:
    """整个请求的总时限是 timeout 秒。HTTPError 原样抛出；超时或超大抛 ReadLimitError；其他网络错误抛 OSError。"""
    deadline = time.monotonic() + timeout
    watch = _Watch(deadline)
    opener = urllib.request.build_opener(_HTTP(watch), _HTTPS(watch))
    timer = threading.Timer(timeout, watch.kill)
    timer.daemon = True
    timer.start()
    try:
        with opener.open(req, timeout=timeout) as resp:
            return read_limited(resp, max_bytes, deadline)
    except (urllib.error.HTTPError, ReadLimitError):
        raise
    except (OSError, http.client.HTTPException) as exc:
        if watch.killed or time.monotonic() >= deadline:
            raise ReadLimitError("超过总时限") from exc
        if isinstance(exc, OSError):
            raise
        raise OSError(f"响应不完整（{type(exc).__name__}）") from exc
    finally:
        timer.cancel()


class TTLCache:
    """线程安全。lookup 返回 (命中?, 值)，值可以是空列表这类假值。"""

    def __init__(self, ttl: float, maxsize: int) -> None:
        self.ttl, self.maxsize = ttl, maxsize
        self._data: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def _sweep(self, now: float) -> None:
        # 按写入时间排序（set 时移到末尾），过期的都在最前面：从头删到第一个没过期的为止
        while self._data:
            first = next(iter(self._data.values()))
            if now - first[0] < self.ttl:
                break
            self._data.popitem(last=False)

    def lookup(self, key: Hashable) -> tuple[bool, Any]:
        with self._lock:
            self._sweep(time.monotonic())
            item = self._data.get(key)
            return (True, item[1]) if item is not None else (False, None)

    def set(self, key: Hashable, value: Any) -> None:
        with self._lock:
            now = time.monotonic()
            self._sweep(now)
            self._data[key] = (now, value)
            self._data.move_to_end(key)
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)
