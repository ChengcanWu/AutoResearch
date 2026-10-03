# -*- coding: utf-8 -*-
"""两个上限工具：读外部响应有总时限和字节上限；内存缓存有过期和条数上限。

- urlopen 的 timeout 只管「多久没收到数据」，一个慢慢滴数据的服务器能让 read() 一直读下去；
  read_limited 按总截止时间和字节数读，超了就停。
- 原来的缓存是普通 dict：过期的只是不再命中，但一直留在内存里；TTLCache 过期即删，超过条数先删最旧的。
"""
from __future__ import annotations

import threading
import time
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
