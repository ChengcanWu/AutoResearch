# -*- coding: utf-8 -*-
"""两个上限工具：读外部响应有总时限和字节上限；内存缓存有过期和条数上限。

- urlopen 的 timeout 只管「多久没收到数据」，一个慢慢滴数据的服务器能让连接、响应头、正文一直拖下去。
  fetch 给整个请求（域名解析、连接、TLS、响应头、正文）一个总截止时间：解析限时等，连接前就登记 socket，
  到点由看门狗关掉；正文另有字节上限。
- 原来的缓存是普通 dict：过期的只是不再命中，但一直留在内存里；TTLCache 过期即删，超过条数先删最旧的。
"""
from __future__ import annotations

import http.client
import socket
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
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


_DNS_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="dns")
# 同一主机正在解析就共用那一次：一个解析很慢的主机最多占一个解析线程，不会把四个都占满、连累别的主机
_DNS_INFLIGHT: dict[tuple[str, int], Future] = {}
_DNS_LOCK = threading.Lock()


def _resolve_shared(host: str, port: int) -> Future:
    key = (host, port)
    with _DNS_LOCK:
        fut = _DNS_INFLIGHT.get(key)
        created = fut is None
        if created:
            fut = _DNS_POOL.submit(socket.getaddrinfo, host, port, 0, socket.SOCK_STREAM)
            _DNS_INFLIGHT[key] = fut
    if created:  # 在锁外加回调：已完成的 future 会立刻在本线程回调，回调里要拿同一把锁
        fut.add_done_callback(lambda done, k=key: _forget_dns(k, done))
    return fut


def _forget_dns(key: tuple[str, int], done: Future) -> None:
    with _DNS_LOCK:
        if _DNS_INFLIGHT.get(key) is done:
            del _DNS_INFLIGHT[key]


class _Watch:
    """这次请求的截止时间和它用到的连接。DNS 解析在小线程池里限时等；socket 在连接之前就登记，
    到点 shutdown，卡在连接、TLS 握手、响应头、正文任何一步的线程都会立刻出错返回。"""

    def __init__(self, deadline: float) -> None:
        self.deadline = deadline
        self.killed = False
        self._dups: list[socket.socket] = []
        self._lock = threading.Lock()

    def left(self) -> float:
        return self.deadline - time.monotonic()

    def resolve(self, host: str, port: int) -> list:
        """getaddrinfo 没有超时参数，也打断不了：放进线程池，等到截止时间就放弃（解析线程自己会结束）。"""
        left = self.left()
        if left <= 0:
            raise ReadLimitError("超过总时限")
        fut = _resolve_shared(host, port)
        try:
            return fut.result(timeout=left)
        except FutureTimeout as exc:
            # 不取消：别的请求可能也在等这一次解析；它完成后自动从共享表里移除
            raise ReadLimitError("超过总时限（域名解析）") from exc

    def adopt(self, sock: socket.socket) -> None:
        """登记 socket 的副本：TLS 包装会摘走原对象，副本指向同一条连接，到点 shutdown 照样有效。"""
        dup = sock.dup()
        with self._lock:
            self._dups.append(dup)
            killed = self.killed
        if killed:
            _shut(dup)
        sock.settimeout(max(0.01, self.left()))

    def kill(self) -> None:
        with self._lock:
            self.killed = True
            dups = list(self._dups)
        for dup in dups:
            _shut(dup)

    def close(self) -> None:
        with self._lock:
            dups, self._dups = self._dups, []
        for dup in dups:
            dup.close()


def _shut(sock: socket.socket) -> None:
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass  # 连接已经断了


def _connect(watch: _Watch, address: tuple, timeout: Any = None, source_address: Any = None, **_: Any) -> socket.socket:
    """代替 socket.create_connection：解析限时；每个 socket 先登记再连接，连接本身受剩余时间约束。"""
    host, port = address
    err: OSError | None = None
    for family, socktype, proto, _canon, addr in watch.resolve(host, port):
        sock = socket.socket(family, socktype, proto)
        try:
            watch.adopt(sock)
            if source_address:
                sock.bind(source_address)
            sock.connect(addr)
            return sock
        except OSError as exc:
            err = exc
            sock.close()
            if watch.left() <= 0:
                break
    raise err or OSError("连不上")


def _watched(base: type, watch: _Watch) -> type:
    class Conn(base):  # type: ignore[misc, valid-type]
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._create_connection = lambda address, timeout=None, source_address=None, **kw: \
                _connect(watch, address, timeout, source_address)

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
        if isinstance(getattr(exc, "reason", None), ReadLimitError):
            raise exc.reason from exc  # urllib 把连接阶段的错误包成 URLError
        if watch.killed or time.monotonic() >= deadline:
            raise ReadLimitError("超过总时限") from exc
        if isinstance(exc, OSError):
            raise
        raise OSError(f"响应不完整（{type(exc).__name__}）") from exc
    finally:
        timer.cancel()
        watch.close()


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
