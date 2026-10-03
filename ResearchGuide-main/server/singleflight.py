# -*- coding: utf-8 -*-
"""同一个 key 同时只做一次：并发的相同请求等第一个做完，共用它的结果（或异常）。

缓存只管「做完之后」；这里管「正在做的时候」——没有它，八个同时到的相同检索会各自打一次上游。
"""
from __future__ import annotations

import threading
from typing import Any, Callable, Hashable


class _Call:
    __slots__ = ("done", "value", "error")

    def __init__(self) -> None:
        self.done = threading.Event()
        self.value: Any = None
        self.error: BaseException | None = None


class SingleFlight:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: dict[Hashable, _Call] = {}

    def do(self, key: Hashable, fn: Callable[[], Any]) -> Any:
        with self._lock:
            call = self._calls.get(key)
            leader = call is None
            if leader:
                call = self._calls[key] = _Call()
        if not leader:
            call.done.wait()
            if call.error is not None:
                raise call.error
            return call.value
        try:
            call.value = fn()
        except BaseException as exc:
            call.error = exc
            raise
        finally:
            with self._lock:
                self._calls.pop(key, None)
            call.done.set()
        return call.value

    def in_flight(self) -> int:
        with self._lock:
            return len(self._calls)
