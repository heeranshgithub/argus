"""Canonical Mongo collection names.

Centralized so route handlers and repositories never hardcode strings.
`SESSIONS` is used from Part 2; the rest land in Parts 3-5.
"""

SESSIONS = "sessions"
WORKFLOW_RUNS = "workflow_runs"
REPORTS = "reports"
CHAT_MESSAGES = "chat_messages"

ALL_COLLECTIONS = (SESSIONS, WORKFLOW_RUNS, REPORTS, CHAT_MESSAGES)
