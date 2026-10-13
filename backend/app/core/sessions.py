import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

from app.core.errors import AppError

T = TypeVar("T")


@dataclass
class Session(Generic[T]):
    id: str
    last_used: float
    state: T


class SessionStore(Generic[T]):
    """In-memory sessions. Kept in least-recently-used order, so expired
    sessions are always at the front and the LRU victim is the first entry."""

    def __init__(
        self,
        new_state: Callable[[], T],
        *,
        max_sessions: int,
        ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._new_state = new_state
        self._max_sessions = max_sessions
        self._ttl = ttl_seconds
        self._clock = clock
        self._sessions: OrderedDict[str, Session[T]] = OrderedDict()
        self._lock = threading.Lock()

    def create(self) -> Session[T]:
        with self._lock:
            now = self._clock()
            self._evict_expired(now)
            while len(self._sessions) >= self._max_sessions:
                self._sessions.popitem(last=False)
            session = Session(id=f"s_{secrets.token_urlsafe(16)}", last_used=now, state=self._new_state())
            self._sessions[session.id] = session
            return session

    def get(self, session_id: str) -> Session[T]:
        with self._lock:
            now = self._clock()
            self._evict_expired(now)
            session = self._sessions.get(session_id)
            if session is None:
                raise AppError(
                    404,
                    "session_not_found",
                    "Your session expired. Reload the page to start a new one.",
                )
            session.last_used = now
            self._sessions.move_to_end(session_id)
            return session

    def __len__(self) -> int:
        return len(self._sessions)

    def _evict_expired(self, now: float) -> None:
        while self._sessions:
            oldest = next(iter(self._sessions.values()))
            if now - oldest.last_used < self._ttl:
                break
            self._sessions.popitem(last=False)
