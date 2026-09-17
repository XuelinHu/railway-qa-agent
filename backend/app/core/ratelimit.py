"""A small in-process login throttle.

Deliberately simple: no Redis, no background sweeper. The window is short and
the entry count is bounded by the number of distinct (username, ip) pairs seen
within the lockout period. Note that this is per-process — running uvicorn with
more than one worker multiplies the allowance.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class _Attempts:
    count: int = 0
    first_at: float = field(default_factory=time.monotonic)


class LoginThrottle:
    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._entries: dict[str, _Attempts] = {}

    def _key(self, username: str, ip: str | None) -> str:
        return f"{username.lower()}@{ip or '-'}"

    def _prune(self, key: str, now: float) -> _Attempts:
        entry = self._entries.get(key)
        if entry is None or now - entry.first_at > self.window_seconds:
            entry = _Attempts(first_at=now)
            self._entries[key] = entry
        return entry

    def retry_after(self, username: str, ip: str | None) -> int:
        """Seconds until the caller may try again; 0 when not locked out."""
        now = time.monotonic()
        entry = self._entries.get(self._key(username, ip))
        if entry is None or now - entry.first_at > self.window_seconds:
            return 0
        if entry.count < self.max_attempts:
            return 0
        return max(1, int(self.window_seconds - (now - entry.first_at)))

    def record_failure(self, username: str, ip: str | None) -> None:
        now = time.monotonic()
        entry = self._prune(self._key(username, ip), now)
        entry.count += 1
        if len(self._entries) > 10_000:
            self._sweep(now)

    def reset(self, username: str, ip: str | None) -> None:
        self._entries.pop(self._key(username, ip), None)

    def _sweep(self, now: float) -> None:
        expired = [
            key
            for key, entry in self._entries.items()
            if now - entry.first_at > self.window_seconds
        ]
        for key in expired:
            self._entries.pop(key, None)
