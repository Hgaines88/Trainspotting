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
            self._database_operations = Counter()
            self._database_latency_buckets = Counter()
            self._database_latency_sum_ms = Counter()
            self._transactions = Counter()
            self._transaction_duration_buckets = Counter()
            self._transaction_duration_sum_ms = Counter()
            self._pool = {}

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
            database_operations = [
                {
                    "backend": backend,
                    "operation": operation,
                    "outcome": outcome,
                    "count": count,
                }
                for (backend, operation, outcome), count in sorted(
                    self._database_operations.items()
                )
            ]
            database_latency = self._duration_snapshot(
                self._database_latency_sum_ms,
                self._database_latency_buckets,
                ("backend", "operation"),
            )
            transactions = [
                {"backend": backend, "outcome": outcome, "count": count}
                for (backend, outcome), count in sorted(self._transactions.items())
            ]
            transaction_latency = self._duration_snapshot(
                self._transaction_duration_sum_ms,
                self._transaction_duration_buckets,
                ("backend", "outcome"),
            )
            pool = dict(self._pool)
        return {
            "requests": requests,
            "request_latency_ms": latency,
            "database_operations": database_operations,
            "database_latency_ms": database_latency,
            "transactions": transactions,
            "transaction_duration_ms": transaction_latency,
            "connection_pool": pool,
        }

    @staticmethod
    def _duration_snapshot(sums, buckets, label_names) -> list[dict]:
        return [
            {
                **dict(zip(label_names, labels, strict=True)),
                "sum_ms": round(total, 3),
                "buckets": {
                    boundary: buckets[(*labels, boundary)]
                    for boundary in [
                        *(str(value) for value in LATENCY_BUCKETS_MS),
                        "+Inf",
                    ]
                },
            }
            for labels, total in sorted(sums.items())
        ]

    @staticmethod
    def _observe_duration(counter, labels, duration_ms) -> None:
        for boundary in LATENCY_BUCKETS_MS:
            if duration_ms <= boundary:
                counter[(*labels, str(boundary))] += 1
        counter[(*labels, "+Inf")] += 1

    def observe_database_operation(
        self,
        backend: str,
        operation: str,
        outcome: str,
        duration_ms: float,
    ) -> None:
        labels = (backend, operation)
        with self._lock:
            self._database_operations[(backend, operation, outcome)] += 1
            self._database_latency_sum_ms[labels] += duration_ms
            self._observe_duration(
                self._database_latency_buckets,
                labels,
                duration_ms,
            )

    def observe_transaction(
        self,
        backend: str,
        outcome: str,
        duration_ms: float,
    ) -> None:
        labels = (backend, outcome)
        with self._lock:
            self._transactions[labels] += 1
            self._transaction_duration_sum_ms[labels] += duration_ms
            self._observe_duration(
                self._transaction_duration_buckets,
                labels,
                duration_ms,
            )

    def set_connection_pool(
        self,
        *,
        backend: str,
        size: int,
        checked_out: int,
        overflow: int,
    ) -> None:
        with self._lock:
            self._pool = {
                "backend": backend,
                "size": size,
                "checked_out": checked_out,
                "overflow": overflow,
            }


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
