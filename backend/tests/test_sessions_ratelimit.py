import pytest

from app.core.errors import AppError
from app.core.ratelimit import RateLimiter
from app.core.sessions import SessionStore


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def store(clock: Clock, max_sessions: int = 3, ttl: float = 60) -> SessionStore[list]:
    return SessionStore(list, max_sessions=max_sessions, ttl_seconds=ttl, clock=clock)


def assert_missing(s: SessionStore, session_id: str) -> None:
    with pytest.raises(AppError) as exc:
        s.get(session_id)
    assert (exc.value.status, exc.value.code) == (404, "session_not_found")


def test_session_expires_after_ttl_of_inactivity():
    clock = Clock()
    s = store(clock)
    session = s.create()

    clock.now += 59
    assert s.get(session.id) is session
    clock.now += 59  # still alive: the previous get refreshed it
    assert s.get(session.id) is session
    clock.now += 60
    assert_missing(s, session.id)


def test_lru_cap_evicts_least_recently_used():
    clock = Clock()
    s = store(clock, max_sessions=3)
    a, b, c = s.create(), s.create(), s.create()
    s.get(a.id)

    d = s.create()

    assert len(s) == 3
    assert_missing(s, b.id)
    for kept in (a, c, d):
        assert s.get(kept.id) is kept


def test_sessions_have_independent_state():
    s = store(Clock())
    a, b = s.create(), s.create()
    a.state.append("x")
    assert b.state == []


def test_rate_limit_slides_and_reports_retry_after():
    clock = Clock()
    limiter = RateLimiter(limit=2, window=60, clock=clock)
    limiter.hit("1.1.1.1")
    clock.now += 20
    limiter.hit("1.1.1.1")
    limiter.hit("2.2.2.2")

    with pytest.raises(AppError) as exc:
        limiter.hit("1.1.1.1")
    assert exc.value.status == 429
    assert exc.value.headers == {"Retry-After": "40"}

    clock.now += 40
    limiter.hit("1.1.1.1")
    with pytest.raises(AppError):
        limiter.hit("1.1.1.1")
