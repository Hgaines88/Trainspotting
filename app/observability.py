"""Privacy-safe request logging and bounded in-process service metrics."""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from collections import Counter


REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
LATENCY_BUCKETS_MS = (50, 100, 250, 500, 1_000, 2_500, 5_000)
logger = logging.getLogger("trainspotting.operations")
logger.setLevel(logging.INFO)


def request_id(value: str | None) -> str:
    if value and REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return uuid.uuid4().hex


def route_template(scope: dict) -> str:
    route = scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path.startswith("/"):
        return path
    return "unmatched"


class ServiceMetrics:
    """Aggregate low-cardinality counters without retaining request records."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.clear()

    def clear(self) -> None:
        with getattr(self, "_lock", threading.Lock()):
            self._requests = Counter()
            self._latency_buckets = Counter()
            self._latency_sum_ms = Counter()

    def observe_request(
        self,
        method: str,
        route: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        key = (method, route, str(status_code))
        with self._lock:
            self._requests[key] += 1
            self._latency_sum_ms[(method, route)] += duration_ms
            for boundary in LATENCY_BUCKETS_MS:
                if duration_ms <= boundary:
                    self._latency_buckets[(method, route, str(boundary))] += 1
            self._latency_buckets[(method, route, "+Inf")] += 1

    def snapshot(self) -> dict:
        with self._lock:
            requests = [
                {
                    "method": method,
                    "route": route,
                    "status_code": int(status_code),
                    "count": count,
                }
                for (method, route, status_code), count in sorted(
                    self._requests.items()
                )
            ]
            latency = [
                {
                    "method": method,
                    "route": route,
                    "sum_ms": round(total, 3),
                    "buckets": {
                        boundary: self._latency_buckets[(method, route, boundary)]
                        for boundary in [
                            *(str(value) for value in LATENCY_BUCKETS_MS),
                            "+Inf",
                        ]
                    },
                }
                for (method, route), total in sorted(self._latency_sum_ms.items())
            ]
        return {"requests": requests, "request_latency_ms": latency}


service_metrics = ServiceMetrics()


def log_request(
    *,
    request_id_value: str,
    method: str,
    route: str,
    status_code: int,
    duration_ms: float,
) -> None:
    # Some server/library logging configurations disable loggers that existed
    # before their dictConfig was applied. Re-enable this named child while
    # continuing to use the process handler rather than adding a duplicate one.
    logger.disabled = False
    logger.propagate = True
    logger.info(
        json.dumps(
            {
                "event": "http_request",
                "request_id": request_id_value,
                "method": method,
                "route": route,
                "status_code": status_code,
                "duration_ms": round(duration_ms, 3),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def monotonic_time() -> float:
    return time.monotonic()
