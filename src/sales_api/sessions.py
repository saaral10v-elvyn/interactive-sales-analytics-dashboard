"""In-memory, idle-expiring sessions for uploaded datasets.

A session owns the loaded and cleaned DataFrames so they never cross the HTTP
boundary. The store is process-local by design: one API instance holds its own
sessions and a restart invalidates them. That is the expected trade-off for a
single-container deployment with no user accounts.
"""

from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from sales_dashboard.models import CleanedDataset, LoadedDataset

SESSION_ID_BYTES = 24
SESSION_NOT_FOUND_MESSAGE = "This dataset session no longer exists. Upload the file again."


class SessionNotFoundError(KeyError):
    """Raised when a session id is unknown or has expired."""

    def __init__(self, session_id: str) -> None:
        super().__init__(session_id)
        self.session_id = session_id


@dataclass
class Session:
    """Everything the API keeps between requests for one browser session."""

    id: str
    created_at: float
    last_accessed: float
    loaded: LoadedDataset | None = None
    cleaned: CleanedDataset | None = None
    mapping_override: dict[str, str] = field(default_factory=dict)
    revision: int = 0


class SessionStore:
    """Thread-safe session storage with an idle timeout and a hard cap.

    Expiry is lazy: sessions are checked when they are read and swept on every
    create, so an idle server holds no more than ``max_sessions`` entries. The
    clock is injectable so tests do not need to sleep.
    """

    def __init__(
        self,
        ttl_seconds: int,
        max_sessions: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        if max_sessions <= 0:
            raise ValueError("max_sessions must be greater than zero")
        self._ttl_seconds = ttl_seconds
        self._max_sessions = max_sessions
        self._clock = clock
        self._lock = threading.RLock()
        self._sessions: dict[str, Session] = {}

    @property
    def ttl_seconds(self) -> int:
        """Return how long a session may sit idle before it expires."""
        return self._ttl_seconds

    @property
    def max_sessions(self) -> int:
        """Return the maximum number of live sessions."""
        return self._max_sessions

    def create(self, loaded: LoadedDataset | None = None) -> Session:
        """Create a session, evicting expired and then least-recently-used entries."""
        now = self._clock()
        with self._lock:
            self._purge_locked(now)
            while len(self._sessions) >= self._max_sessions:
                self._evict_oldest_locked()

            session_id = self._new_id_locked()
            session = Session(
                id=session_id,
                created_at=now,
                last_accessed=now,
                loaded=loaded,
            )
            self._sessions[session_id] = session
            return session

    def get(self, session_id: str) -> Session:
        """Return a live session and refresh its idle timer."""
        now = self._clock()
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionNotFoundError(session_id)
            if now - session.last_accessed >= self._ttl_seconds:
                del self._sessions[session_id]
                raise SessionNotFoundError(session_id)
            session.last_accessed = now
            return session

    def delete(self, session_id: str) -> bool:
        """Remove a session, returning whether it existed."""
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def purge_expired(self) -> int:
        """Drop every expired session and return how many were removed."""
        with self._lock:
            return self._purge_locked(self._clock())

    def clear(self) -> None:
        """Remove every session. Intended for tests and shutdown hooks."""
        with self._lock:
            self._sessions.clear()

    def ids(self) -> tuple[str, ...]:
        """Return the live session ids, oldest access first."""
        with self._lock:
            ordered = sorted(
                self._sessions.values(),
                key=lambda session: (session.last_accessed, session.id),
            )
            return tuple(session.id for session in ordered)

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)

    def _new_id_locked(self) -> str:
        while True:
            candidate = secrets.token_urlsafe(SESSION_ID_BYTES)
            if candidate not in self._sessions:
                return candidate

    def _purge_locked(self, now: float) -> int:
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if now - session.last_accessed >= self._ttl_seconds
        ]
        for session_id in expired:
            del self._sessions[session_id]
        return len(expired)

    def _evict_oldest_locked(self) -> None:
        oldest = min(
            self._sessions.values(),
            key=lambda session: (session.last_accessed, session.created_at, session.id),
        )
        del self._sessions[oldest.id]
