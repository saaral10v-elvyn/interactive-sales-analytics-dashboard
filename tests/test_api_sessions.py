"""Unit tests for the in-memory session store."""

from __future__ import annotations

import pytest

from sales_api.sessions import SessionNotFoundError, SessionStore
from sales_dashboard.loading import load_demo_dataset


class FakeClock:
    """A monotonic clock the tests can move by hand."""

    def __init__(self, start: float = 1_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def store(clock: FakeClock) -> SessionStore:
    return SessionStore(ttl_seconds=60, max_sessions=2, clock=clock)


def test_create_returns_distinct_live_sessions(store: SessionStore) -> None:
    first = store.create()
    second = store.create()

    assert first.id != second.id
    assert len(store) == 2
    assert set(store.ids()) == {first.id, second.id}


def test_get_refreshes_the_idle_timer(store: SessionStore, clock: FakeClock) -> None:
    session = store.create()

    clock.advance(30)
    assert store.get(session.id) is session

    # 40s since creation, but only 10s since the last read.
    clock.advance(40)
    assert store.get(session.id) is session

    clock.advance(59)
    assert store.get(session.id) is session

    clock.advance(60)
    with pytest.raises(SessionNotFoundError):
        store.get(session.id)


def test_expired_session_is_dropped_on_read(store: SessionStore, clock: FakeClock) -> None:
    session = store.create()
    clock.advance(60)

    with pytest.raises(SessionNotFoundError):
        store.get(session.id)

    assert len(store) == 0


def test_unknown_session_raises(store: SessionStore) -> None:
    with pytest.raises(SessionNotFoundError):
        store.get("not-a-real-session")


def test_purge_expired_keeps_recent_sessions(
    store: SessionStore,
    clock: FakeClock,
) -> None:
    old = store.create()
    clock.advance(30)
    fresh = store.create()
    clock.advance(31)

    assert store.purge_expired() == 1
    assert len(store) == 1
    assert store.get(fresh.id) is fresh
    with pytest.raises(SessionNotFoundError):
        store.get(old.id)


def test_capacity_evicts_the_least_recently_used(
    store: SessionStore,
    clock: FakeClock,
) -> None:
    first = store.create()
    clock.advance(1)
    second = store.create()
    clock.advance(1)

    # Touch the older session so the second one becomes the least recent.
    store.get(first.id)
    clock.advance(1)
    third = store.create()

    assert len(store) == 2
    assert set(store.ids()) == {first.id, third.id}
    with pytest.raises(SessionNotFoundError):
        store.get(second.id)


def test_expired_sessions_are_swept_before_eviction(
    store: SessionStore,
    clock: FakeClock,
) -> None:
    store.create()
    clock.advance(60)
    fresh = store.create()

    assert len(store) == 1
    assert store.get(fresh.id) is fresh


def test_delete_reports_whether_the_session_existed(store: SessionStore) -> None:
    session = store.create()

    assert store.delete(session.id) is True
    assert store.delete(session.id) is False
    assert len(store) == 0


def test_clear_removes_everything(store: SessionStore) -> None:
    store.create()
    store.create()
    store.clear()

    assert len(store) == 0
    assert store.ids() == ()


def test_ids_are_ordered_by_last_access(
    store: SessionStore,
    clock: FakeClock,
) -> None:
    first = store.create()
    clock.advance(1)
    second = store.create()
    clock.advance(1)
    store.get(first.id)

    assert store.ids() == (second.id, first.id)


def test_store_owns_the_loaded_dataset(store: SessionStore) -> None:
    loaded = load_demo_dataset()
    session = store.create(loaded=loaded)

    assert session.loaded is loaded
    assert session.cleaned is None
    assert session.mapping_override == {}
    assert session.revision == 0


def test_configuration_is_exposed(store: SessionStore) -> None:
    assert store.ttl_seconds == 60
    assert store.max_sessions == 2


@pytest.mark.parametrize(
    ("ttl_seconds", "max_sessions"),
    [(0, 1), (-1, 1), (60, 0), (60, -5)],
)
def test_invalid_configuration_is_rejected(ttl_seconds: int, max_sessions: int) -> None:
    with pytest.raises(ValueError):
        SessionStore(ttl_seconds=ttl_seconds, max_sessions=max_sessions)
