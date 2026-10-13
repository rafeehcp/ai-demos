import math
import threading
import time
from collections import deque
from typing import Callable

from fastapi import Request

from app.core.errors import AppError

_SWEEP_THRESHOLD = 10_000


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    if first:
        return first
    return request.client.host if request.client else "unknown"


class RateLimiter:
    """Sliding window: at most `limit` hits per `window` seconds per key."""

    def __init__(
        self,
        limit: int,
        window: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window = window
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> None:
        with self._lock:
            now = self._clock()
            if len(self._hits) > _SWEEP_THRESHOLD:
                self._sweep(now)
            hits = self._hits.setdefault(key, deque())
            self._prune(hits, now)
            if len(hits) >= self._limit:
                retry_after = max(1, math.ceil(self._window - (now - hits[0])))
                raise AppError(
                    429,
                    "rate_limited",
                    f"Too many requests. Please wait {retry_after} seconds and try again.",
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)

    def _prune(self, hits: deque[float], now: float) -> None:
        while hits and now - hits[0] >= self._window:
            hits.popleft()

    def _sweep(self, now: float) -> None:
        for key in list(self._hits):
            self._prune(self._hits[key], now)
            if not self._hits[key]:
                del self._hits[key]
