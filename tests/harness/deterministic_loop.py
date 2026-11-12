"""Socket-free deterministic virtual-clock asyncio event loop for Windows sandbox test runs."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
import heapq
from typing import Any


class DeterministicEventLoop(asyncio.AbstractEventLoop):
    """Pure-Python virtual-clock event loop for offline unit tests (zero TCP loopback sockets)."""

    def __init__(self) -> None:
        self._ready: deque[asyncio.Handle] = deque()
        self._scheduled: list[asyncio.TimerHandle] = []
        self._clock: float = 0.0
        self._closed: bool = False
        self._running: bool = False
        self._task_factory: Any = None
        self._exception_handler: Any = None

    def get_debug(self) -> bool:
        return False

    def set_debug(self, enabled: bool) -> None:
        _ = enabled

    def time(self) -> float:
        return self._clock

    def is_running(self) -> bool:
        return self._running

    def is_closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        self._ready.clear()
        self._scheduled.clear()
        self._closed = True

    def _timer_handle_cancelled(self, handle: asyncio.TimerHandle) -> None:
        _ = handle

    def create_future(self) -> asyncio.Future[Any]:
        return asyncio.Future(loop=self)

    def create_task(self, coro: Any, *, name: str | None = None, context: Any = None) -> asyncio.Task[Any]:
        if self._task_factory is not None:
            return self._task_factory(self, coro, name=name, context=context)
        return asyncio.Task(coro, loop=self, name=name, context=context)

    def set_task_factory(self, factory: Any) -> None:
        self._task_factory = factory

    def get_task_factory(self) -> Any:
        return self._task_factory

    def set_exception_handler(self, handler: Any) -> None:
        self._exception_handler = handler

    def get_exception_handler(self) -> Any:
        return self._exception_handler

    def default_exception_handler(self, context: dict[str, Any]) -> None:
        _ = context

    def call_exception_handler(self, context: dict[str, Any]) -> None:
        if self._exception_handler is not None:
            self._exception_handler(self, context)

    def call_soon(self, callback_fn: Callable[..., Any], *args: Any, context: Any = None) -> asyncio.Handle:
        h = asyncio.Handle(callback_fn, args, self, context)
        self._ready.append(h)
        return h

    def call_soon_threadsafe(self, callback_fn: Callable[..., Any], *args: Any, context: Any = None) -> asyncio.Handle:
        return self.call_soon(callback_fn, *args, context=context)

    def call_at(self, when: float, callback_fn: Callable[..., Any], *args: Any, context: Any = None) -> asyncio.TimerHandle:
        h = asyncio.TimerHandle(float(when), callback_fn, args, self, context)
        heapq.heappush(self._scheduled, h)
        return h

    def call_later(self, delay: float, callback_fn: Callable[..., Any], *args: Any, context: Any = None) -> asyncio.TimerHandle:
        return self.call_at(self._clock + max(0.0, float(delay)), callback_fn, *args, context=context)

    async def shutdown_asyncgens(self) -> None:
        return None

    async def shutdown_default_executor(self, *args: Any, **kwargs: Any) -> None:
        _ = (args, kwargs)

    def run_until_complete(self, future: Any) -> Any:
        fut = asyncio.ensure_future(future, loop=self)
        self._running = True
        asyncio.events._set_running_loop(self)
        try:
            steps = 0
            while not fut.done():
                steps += 1
                if steps > 100000:
                    raise RuntimeError("Deterministic event loop exceeded step budget")
                while self._scheduled and self._scheduled[0]._when <= self._clock:
                    th = heapq.heappop(self._scheduled)
                    if not th._cancelled:
                        self._ready.append(th)
                if not self._ready and self._scheduled:
                    while self._scheduled and self._scheduled[0]._cancelled:
                        heapq.heappop(self._scheduled)
                    if self._scheduled:
                        self._clock = self._scheduled[0]._when
                        continue
                if not self._ready:
                    break
                batch = len(self._ready)
                for _ in range(batch):
                    h = self._ready.popleft()
                    if not h._cancelled:
                        h._run()
            return fut.result()
        finally:
            self._running = False
            asyncio.events._set_running_loop(None)
