"""In-process metrics counters (PLAN_PART_5 §2.3).

A dependency-free counter registry surfaced at ``GET /api/metrics`` as JSON —
documented as "scrape with curl/cron". Real Prometheus/OpenTelemetry export is
listed as deferred work in ``docs/engineering-decisions.md``. Counters are
process-local, so they reset on restart and don't survive multi-replica deploys
(another reason the in-process event bus needs Redis at scale).
"""

from __future__ import annotations

import threading
from collections import defaultdict


class Metrics:
    """Thread-safe monotonic counters grouped by dimension."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.requests_total: dict[str, int] = defaultdict(int)
        self.workflow_runs_total: dict[str, int] = defaultdict(int)
        self.chat_messages_total: dict[str, int] = defaultdict(int)
        self.llm_tokens_total: dict[str, int] = defaultdict(int)

    def incr_request(self, method: str, route: str, status_code: int) -> None:
        with self._lock:
            self.requests_total[f"{method} {route} {status_code}"] += 1

    def incr_workflow_run(self, status: str) -> None:
        with self._lock:
            self.workflow_runs_total[status] += 1

    def incr_chat_message(self, role: str) -> None:
        with self._lock:
            self.chat_messages_total[role] += 1

    def add_llm_tokens(self, prompt: int | None, completion: int | None) -> None:
        with self._lock:
            self.llm_tokens_total["prompt"] += prompt or 0
            self.llm_tokens_total["completion"] += completion or 0

    def snapshot(self) -> dict[str, dict[str, int]]:
        """Return a plain-dict copy of all counters for JSON serialization."""
        with self._lock:
            return {
                "requestsTotal": dict(self.requests_total),
                "workflowRunsTotal": dict(self.workflow_runs_total),
                "chatMessagesTotal": dict(self.chat_messages_total),
                "llmTokensTotal": dict(self.llm_tokens_total),
            }

    def reset(self) -> None:
        """Clear all counters (used in tests)."""
        with self._lock:
            self.requests_total.clear()
            self.workflow_runs_total.clear()
            self.chat_messages_total.clear()
            self.llm_tokens_total.clear()


# Process-wide registry shared by the middleware, runner, and chat service.
metrics = Metrics()
