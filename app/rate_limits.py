"""Small, identity-keyed abuse controls for authenticated mutation routes."""

from __future__ import annotations

import math
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import HTTPException, status


ACCOUNT_SYNC_LIMIT = 12
SUBMISSION_WRITE_LIMIT = 10
MODERATION_WRITE_LIMIT = 30
ADMIN_WRITE_LIMIT = 30
RATE_LIMIT_WINDOW_SECONDS = 60


@dataclass
class BucketState:
    tokens: float
    updated_at: float


class IdentityRateLimiter:
    """Thread-safe token buckets with bounded process-local state."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        max_identities: int = 10_000,
    ) -> None:
        self.clock = clock
        self.max_identities = max_identities
        self._buckets: OrderedDict[tuple[str, str], BucketState] = OrderedDict()
        self._lock = threading.Lock()

    def consume(
        self,
        bucket: str,
        identity: str,
        *,
        limit: int,
        window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
    ) -> None:
        if limit < 1 or window_seconds < 1:
            raise ValueError("Rate-limit configuration must be positive.")

        key = (bucket, identity)
        now = self.clock()
        refill_rate = limit / window_seconds

        with self._lock:
            state = self._buckets.pop(key, None)
            if state is None:
                state = BucketState(tokens=float(limit), updated_at=now)
            else:
                elapsed = max(0.0, now - state.updated_at)
                state.tokens = min(float(limit), state.tokens + elapsed * refill_rate)
                state.updated_at = now

            if state.tokens < 1:
                self._buckets[key] = state
                retry_after = max(1, math.ceil((1 - state.tokens) / refill_rate))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again shortly.",
                    headers={"Retry-After": str(retry_after)},
                )

            state.tokens -= 1
            self._buckets[key] = state
            while len(self._buckets) > self.max_identities:
                self._buckets.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()


identity_rate_limiter = IdentityRateLimiter()


def enforce_identity_rate_limit(
    bucket: str,
    identity: str,
    *,
    limit: int,
) -> None:
    identity_rate_limiter.consume(bucket, identity, limit=limit)
