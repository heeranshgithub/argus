"""``MongoCheckpointer`` — a Mongo-backed LangGraph ``BaseCheckpointSaver``.

Persisting every super-step's state snapshot is what makes a crashed run
resumable: on restart we reload the latest checkpoint for ``thread_id ==
session_id`` and LangGraph continues from the last completed node instead of
re-running the workflow from scratch.

Storage mirrors LangGraph's own savers (Postgres/SQLite) and is split across
three collections because channel *blobs* are addressed by
``(thread, ns, channel, version)`` independently of any single checkpoint — an
older checkpoint's blob is reused by later checkpoints that didn't rewrite that
channel:

* ``workflow_checkpoints``        — one doc per checkpoint (+ its metadata)
* ``workflow_checkpoint_blobs``   — one doc per channel value, keyed by version
* ``workflow_checkpoint_writes``  — pending writes (intermediate task outputs)

Values are serialized with LangGraph's own ``serde`` (msgpack → ``bytes``) and
stored as BSON ``Binary`` so ``ObjectId``/Pydantic quirks never enter the picture.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from bson.binary import Binary
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
    get_checkpoint_metadata,
)

from app.db.collections import (
    WORKFLOW_CHECKPOINT_BLOBS,
    WORKFLOW_CHECKPOINT_WRITES,
    WORKFLOW_CHECKPOINTS,
)

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig
    from motor.motor_asyncio import AsyncIOMotorDatabase


def _now() -> datetime:
    return datetime.now(UTC)


class MongoCheckpointer(BaseCheckpointSaver[str]):
    """Async LangGraph checkpoint saver backed by MongoDB (Motor)."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__()
        self.db = db

    # --- serialization helpers -------------------------------------------------

    def _dump(self, value: Any) -> tuple[str, Binary]:
        """Serialize a value to ``(type, BSON Binary)`` via LangGraph's serde."""
        type_, blob = self.serde.dumps_typed(value)
        return type_, Binary(blob)

    def _load(self, type_: str, blob: Any) -> Any:
        """Deserialize a ``(type, bytes)`` pair stored in Mongo."""
        return self.serde.loads_typed((type_, bytes(blob)))

    async def _load_blobs(
        self, thread_id: str, checkpoint_ns: str, versions: ChannelVersions
    ) -> dict[str, Any]:
        """Load channel values for the given per-channel versions."""
        result: dict[str, Any] = {}
        for channel, version in versions.items():
            doc = await self.db[WORKFLOW_CHECKPOINT_BLOBS].find_one(
                {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "channel": channel,
                    "version": version,
                }
            )
            if doc is None or doc["type"] == "empty":
                continue
            result[channel] = self._load(doc["type"], doc["blob"])
        return result

    async def _load_writes(
        self, thread_id: str, checkpoint_ns: str, checkpoint_id: str
    ) -> list[tuple[str, str, Any]]:
        """Load pending writes (task_id, channel, value) for a checkpoint."""
        cursor = self.db[WORKFLOW_CHECKPOINT_WRITES].find(
            {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        ).sort([("task_id", 1), ("idx", 1)])
        return [
            (doc["task_id"], doc["channel"], self._load(doc["type"], doc["blob"]))
            async for doc in cursor
        ]

    def _tuple_from_doc(
        self, doc: dict[str, Any], channel_values: dict[str, Any], writes: list
    ) -> CheckpointTuple:
        """Assemble a :class:`CheckpointTuple` from a checkpoint document."""
        thread_id = doc["thread_id"]
        checkpoint_ns = doc["checkpoint_ns"]
        checkpoint: Checkpoint = self._load(doc["type"], doc["checkpoint"])
        parent_id = doc.get("parent_checkpoint_id")
        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": doc["checkpoint_id"],
                }
            },
            checkpoint={**checkpoint, "channel_values": channel_values},
            metadata=self._load(doc["metadata_type"], doc["metadata"]),
            parent_config=(
                {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": parent_id,
                    }
                }
                if parent_id
                else None
            ),
            pending_writes=writes,
        )

    # --- async API (used by the graph) -----------------------------------------

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        query: dict[str, Any] = {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
        }
        checkpoint_id = get_checkpoint_id(config)
        if checkpoint_id:
            query["checkpoint_id"] = checkpoint_id
            doc = await self.db[WORKFLOW_CHECKPOINTS].find_one(query)
        else:
            # Latest checkpoint for the thread (ids are monotonic + sortable).
            doc = await self.db[WORKFLOW_CHECKPOINTS].find_one(
                query, sort=[("checkpoint_id", -1)]
            )
        if doc is None:
            return None

        checkpoint: Checkpoint = self._load(doc["type"], doc["checkpoint"])
        channel_values = await self._load_blobs(
            thread_id, checkpoint_ns, checkpoint["channel_versions"]
        )
        writes = await self._load_writes(thread_id, checkpoint_ns, doc["checkpoint_id"])
        return self._tuple_from_doc(doc, channel_values, writes)

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        query: dict[str, Any] = {}
        if config is not None:
            query["thread_id"] = config["configurable"]["thread_id"]
            ns = config["configurable"].get("checkpoint_ns")
            if ns is not None:
                query["checkpoint_ns"] = ns
        if before is not None and (before_id := get_checkpoint_id(before)):
            query["checkpoint_id"] = {"$lt": before_id}

        cursor = self.db[WORKFLOW_CHECKPOINTS].find(query).sort([("checkpoint_id", -1)])
        if limit is not None:
            cursor = cursor.limit(limit)

        async for doc in cursor:
            checkpoint: Checkpoint = self._load(doc["type"], doc["checkpoint"])
            metadata = self._load(doc["metadata_type"], doc["metadata"])
            if filter and not all(metadata.get(k) == v for k, v in filter.items()):
                continue
            channel_values = await self._load_blobs(
                doc["thread_id"], doc["checkpoint_ns"], checkpoint["channel_versions"]
            )
            writes = await self._load_writes(
                doc["thread_id"], doc["checkpoint_ns"], doc["checkpoint_id"]
            )
            yield self._tuple_from_doc(doc, channel_values, writes)

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"]["checkpoint_ns"]
        checkpoint_id = checkpoint["id"]

        copy = checkpoint.copy()
        channel_values: dict[str, Any] = copy.pop("channel_values")  # type: ignore[misc]

        # Persist each newly-versioned channel value as its own blob doc.
        for channel, version in new_versions.items():
            if channel in channel_values:
                type_, blob = self._dump(channel_values[channel])
            else:
                type_, blob = "empty", Binary(b"")
            await self.db[WORKFLOW_CHECKPOINT_BLOBS].update_one(
                {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "channel": channel,
                    "version": version,
                },
                {"$set": {"type": type_, "blob": blob}},
                upsert=True,
            )

        ckpt_type, ckpt_blob = self._dump(copy)
        meta_type, meta_blob = self._dump(get_checkpoint_metadata(config, metadata))
        await self.db[WORKFLOW_CHECKPOINTS].update_one(
            {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            },
            {
                "$set": {
                    "parent_checkpoint_id": config["configurable"].get("checkpoint_id"),
                    "type": ckpt_type,
                    "checkpoint": ckpt_blob,
                    "metadata_type": meta_type,
                    "metadata": meta_blob,
                    "ts": _now(),
                }
            },
            upsert=True,
        )
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]

        for idx, (channel, value) in enumerate(writes):
            write_idx = WRITES_IDX_MAP.get(channel, idx)
            type_, blob = self._dump(value)
            await self.db[WORKFLOW_CHECKPOINT_WRITES].update_one(
                {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_id,
                    "task_id": task_id,
                    "idx": write_idx,
                },
                {
                    "$set": {
                        "channel": channel,
                        "type": type_,
                        "blob": blob,
                        "task_path": task_path,
                    }
                },
                upsert=True,
            )

    async def adelete_thread(self, thread_id: str) -> None:
        """Delete all checkpoints, blobs and writes for a thread."""
        for collection in (
            WORKFLOW_CHECKPOINTS,
            WORKFLOW_CHECKPOINT_BLOBS,
            WORKFLOW_CHECKPOINT_WRITES,
        ):
            await self.db[collection].delete_many({"thread_id": thread_id})

    # --- sync API (unused; the graph runs async) -------------------------------

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        raise NotImplementedError("MongoCheckpointer is async-only; use aget_tuple.")

    def put(self, *args: Any, **kwargs: Any) -> RunnableConfig:
        raise NotImplementedError("MongoCheckpointer is async-only; use aput.")

    def put_writes(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError("MongoCheckpointer is async-only; use aput_writes.")

    def list(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("MongoCheckpointer is async-only; use alist.")
