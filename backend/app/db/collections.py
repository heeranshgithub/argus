"""Canonical Mongo collection names.

Centralized so route handlers and repositories never hardcode strings.
`SESSIONS` is used from Part 2; the rest land in Parts 3-5.
"""

SESSIONS = "sessions"
WORKFLOW_RUNS = "workflow_runs"
REPORTS = "reports"
CHAT_MESSAGES = "chat_messages"

# LangGraph checkpointer storage (see app.workflow.checkpointer). Blobs and
# writes live in their own collections because LangGraph addresses channel
# blobs by (thread, ns, channel, version) independently of any one checkpoint.
WORKFLOW_CHECKPOINTS = "workflow_checkpoints"
WORKFLOW_CHECKPOINT_BLOBS = "workflow_checkpoint_blobs"
WORKFLOW_CHECKPOINT_WRITES = "workflow_checkpoint_writes"

ALL_COLLECTIONS = (
    SESSIONS,
    WORKFLOW_RUNS,
    REPORTS,
    CHAT_MESSAGES,
    WORKFLOW_CHECKPOINTS,
    WORKFLOW_CHECKPOINT_BLOBS,
    WORKFLOW_CHECKPOINT_WRITES,
)
