from __future__ import annotations

import base64
import json
import random
from collections.abc import AsyncIterator, Iterator, Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import anyio
import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    WRITES_IDX_MAP,
    get_checkpoint_id,
    get_checkpoint_metadata,
)
from redis.exceptions import RedisError

from app.core.redis import RedisManager
from app.pipeline.state import ApplyIQState


logger = structlog.get_logger(__name__)


class PipelineCheckpointer(BaseCheckpointSaver[str]):
    def __init__(self, redis_manager: RedisManager, *, ttl_seconds: int) -> None:
        super().__init__()
        self._redis_manager = redis_manager
        self._ttl_seconds = ttl_seconds

    async def save(self, run_id: str, state: ApplyIQState) -> None:
        payload = json.dumps(
            {
                "version": 1,
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "state": state,
            },
            default=_json_default,
        )
        try:
            await self._redis_manager.client.set(self._snapshot_key(run_id), payload, ex=self._ttl_seconds)
        except RedisError as error:
            logger.warning("pipeline.checkpoint.redis_save_failed", run_id=run_id, error=str(error))

    async def load(self, run_id: str) -> ApplyIQState | None:
        try:
            payload = await self._redis_manager.client.get(self._snapshot_key(run_id))
            if not payload:
                return None
            parsed = json.loads(payload)
            if isinstance(parsed, dict) and "state" in parsed:
                return parsed["state"]
            return parsed
        except RedisError as error:
            logger.warning("pipeline.checkpoint.redis_load_failed", run_id=run_id, error=str(error))
            return None

    async def delete(self, run_id: str) -> None:
        try:
            await self._redis_manager.client.delete(self._snapshot_key(run_id), self._checkpoint_key(run_id))
        except RedisError as error:
            logger.warning("pipeline.checkpoint.redis_delete_failed", run_id=run_id, error=str(error))

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        try:
            return anyio.run(self.aget_tuple, config)
        except RuntimeError as error:
            raise RuntimeError("pipeline checkpointer get_tuple() cannot run inside an active event loop") from error

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        thread_id, checkpoint_ns = self._thread_and_ns(config)
        bucket = await self._load_checkpoint_bucket(thread_id)
        checkpoint_id = get_checkpoint_id(config)
        namespace_bucket = bucket.get("namespaces", {}).get(checkpoint_ns, {})
        if checkpoint_id is None:
            order = namespace_bucket.get("order", [])
            if not order:
                return None
            checkpoint_id = order[-1]

        entry = namespace_bucket.get("checkpoints", {}).get(checkpoint_id)
        if entry is None:
            return None
        return self._entry_to_tuple(thread_id, checkpoint_ns, checkpoint_id, entry)

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        try:
            return iter(anyio.run(self._alist_collect, config, filter, before, limit))
        except RuntimeError as error:
            raise RuntimeError("pipeline checkpointer list() cannot run inside an active event loop") from error

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        for item in await self._alist_collect(config, filter, before, limit):
            yield item

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        try:
            return anyio.run(self.aput, config, checkpoint, metadata, new_versions)
        except RuntimeError as error:
            raise RuntimeError("pipeline checkpointer put() cannot run inside an active event loop") from error

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        thread_id, checkpoint_ns = self._thread_and_ns(config)
        bucket = await self._load_checkpoint_bucket(thread_id)
        namespaces = bucket.setdefault("namespaces", {})
        namespace_bucket = namespaces.setdefault(checkpoint_ns, {"order": [], "checkpoints": {}})

        checkpoint_id = str(checkpoint["id"])
        existing_entry = namespace_bucket["checkpoints"].get(checkpoint_id, {})
        namespace_bucket["checkpoints"][checkpoint_id] = {
            "checkpoint_ns": checkpoint_ns,
            "checkpoint": self._encode_typed(checkpoint),
            "metadata": self._encode_typed(get_checkpoint_metadata(config, metadata)),
            "parent_checkpoint_id": config["configurable"].get("checkpoint_id"),
            "pending_writes": existing_entry.get("pending_writes", {}),
        }
        if checkpoint_id not in namespace_bucket["order"]:
            namespace_bucket["order"].append(checkpoint_id)

        await self._save_checkpoint_bucket(thread_id, bucket)
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        try:
            anyio.run(self.aput_writes, config, writes, task_id, task_path)
        except RuntimeError as error:
            raise RuntimeError("pipeline checkpointer put_writes() cannot run inside an active event loop") from error

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id, checkpoint_ns = self._thread_and_ns(config)
        checkpoint_id = get_checkpoint_id(config)
        if checkpoint_id is None:
            return

        bucket = await self._load_checkpoint_bucket(thread_id)
        namespace_bucket = bucket.get("namespaces", {}).get(checkpoint_ns)
        if namespace_bucket is None:
            return

        checkpoint_entry = namespace_bucket["checkpoints"].get(checkpoint_id)
        if checkpoint_entry is None:
            return

        pending_writes = checkpoint_entry.setdefault("pending_writes", {})
        for idx, (channel, value) in enumerate(writes):
            write_idx = WRITES_IDX_MAP.get(channel, idx)
            inner_key = f"{task_id}:{write_idx}"
            if inner_key in pending_writes:
                continue
            pending_writes[inner_key] = {
                "task_id": task_id,
                "channel": channel,
                "value": self._encode_typed(value),
                "task_path": task_path,
                "idx": write_idx,
            }

        await self._save_checkpoint_bucket(thread_id, bucket)

    def delete_thread(self, thread_id: str) -> None:
        try:
            anyio.run(self.adelete_thread, thread_id)
        except RuntimeError as error:
            raise RuntimeError("pipeline checkpointer delete_thread() cannot run inside an active event loop") from error

    async def adelete_thread(self, thread_id: str) -> None:
        try:
            await self._redis_manager.client.delete(self._checkpoint_key(thread_id))
        except RedisError as error:
            logger.warning("pipeline.checkpoint.redis_delete_thread_failed", thread_id=thread_id, error=str(error))

    def delete_for_runs(self, run_ids: Sequence[str]) -> None:
        for run_id in run_ids:
            self.delete_thread(run_id)

    def copy_thread(self, source_thread_id: str, target_thread_id: str) -> None:
        try:
            anyio.run(self.acopy_thread, source_thread_id, target_thread_id)
        except RuntimeError as error:
            raise RuntimeError("pipeline checkpointer copy_thread() cannot run inside an active event loop") from error

    async def acopy_thread(self, source_thread_id: str, target_thread_id: str) -> None:
        bucket = await self._load_checkpoint_bucket(source_thread_id)
        if not bucket:
            return
        await self._save_checkpoint_bucket(target_thread_id, bucket)

    def prune(self, thread_ids: Sequence[str], *, strategy: str = "keep_latest") -> None:
        try:
            anyio.run(self.aprune, thread_ids, strategy=strategy)
        except RuntimeError as error:
            raise RuntimeError("pipeline checkpointer prune() cannot run inside an active event loop") from error

    async def aprune(self, thread_ids: Sequence[str], *, strategy: str = "keep_latest") -> None:
        for thread_id in thread_ids:
            bucket = await self._load_checkpoint_bucket(thread_id)
            if not bucket:
                continue
            if strategy == "delete":
                await self.adelete_thread(thread_id)
                continue

            namespaces = bucket.get("namespaces", {})
            for namespace_bucket in namespaces.values():
                order = namespace_bucket.get("order", [])
                checkpoints = namespace_bucket.get("checkpoints", {})
                if not order:
                    continue
                latest_checkpoint_id = order[-1]
                latest_entry = checkpoints.get(latest_checkpoint_id)
                namespace_bucket["order"] = [latest_checkpoint_id]
                namespace_bucket["checkpoints"] = {latest_checkpoint_id: latest_entry} if latest_entry else {}
            await self._save_checkpoint_bucket(thread_id, bucket)

    def get_next_version(self, current: str | None, channel: None) -> str:
        if current is None:
            current_version = 0
        elif isinstance(current, int):
            current_version = current
        else:
            current_version = int(current.split(".")[0])
        next_version = current_version + 1
        next_hash = random.random()
        return f"{next_version:032}.{next_hash:016}"

    async def _alist_collect(
        self,
        config: RunnableConfig | None,
        filter: dict[str, Any] | None,
        before: RunnableConfig | None,
        limit: int | None,
    ) -> list[CheckpointTuple]:
        if config is None:
            buckets = await self._load_all_checkpoint_buckets()
            results: list[CheckpointTuple] = []
            for thread_id, bucket in buckets.items():
                results.extend(self._list_from_bucket(thread_id, bucket, None, filter, before, limit))
            return results

        thread_id, checkpoint_ns = self._thread_and_ns(config)
        bucket = await self._load_checkpoint_bucket(thread_id)
        return self._list_from_bucket(thread_id, bucket, checkpoint_ns, filter, before, limit)

    def _list_from_bucket(
        self,
        thread_id: str,
        bucket: dict[str, Any],
        checkpoint_ns: str | None,
        filter: dict[str, Any] | None,
        before: RunnableConfig | None,
        limit: int | None,
    ) -> list[CheckpointTuple]:
        results: list[CheckpointTuple] = []
        namespaces = bucket.get("namespaces", {}) if isinstance(bucket, dict) else {}
        namespaces_to_scan = [checkpoint_ns] if checkpoint_ns is not None else list(namespaces.keys())
        before_checkpoint_id = before["configurable"].get("checkpoint_id") if before else None

        for namespace in namespaces_to_scan:
            namespace_bucket = namespaces.get(namespace, {})
            order = namespace_bucket.get("order", [])
            checkpoints = namespace_bucket.get("checkpoints", {})
            cutoff_index = len(order)
            if before_checkpoint_id in order:
                cutoff_index = order.index(before_checkpoint_id)

            for checkpoint_id in reversed(order[:cutoff_index]):
                entry = checkpoints.get(checkpoint_id)
                if entry is None:
                    continue
                checkpoint_tuple = self._entry_to_tuple(thread_id, namespace, checkpoint_id, entry)
                if checkpoint_tuple is None:
                    continue
                if filter and not self._metadata_matches(checkpoint_tuple.metadata, filter):
                    continue
                results.append(checkpoint_tuple)
                if limit is not None and len(results) >= limit:
                    return results

        return results

    def _entry_to_tuple(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        entry: dict[str, Any],
    ) -> CheckpointTuple | None:
        checkpoint = self._decode_typed(entry["checkpoint"])
        metadata = self._decode_typed(entry["metadata"])
        pending_writes_payload = entry.get("pending_writes", {})
        pending_writes: list[tuple[str, str, Any]] = []
        if isinstance(pending_writes_payload, dict):
            sorted_writes = sorted(
                pending_writes_payload.values(),
                key=lambda item: (str(item.get("task_id", "")), int(item.get("idx", 0))),
            )
            for write in sorted_writes:
                pending_writes.append(
                    (
                        str(write["task_id"]),
                        str(write["channel"]),
                        self._decode_typed(write["value"]),
                    )
                )

        parent_checkpoint_id = entry.get("parent_checkpoint_id")
        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_id,
                }
            },
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=(
                {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": str(parent_checkpoint_id),
                    }
                }
                if parent_checkpoint_id
                else None
            ),
            pending_writes=pending_writes,
        )

    def _metadata_matches(self, metadata: dict[str, Any], filter_values: dict[str, Any]) -> bool:
        for key, expected in filter_values.items():
            if metadata.get(key) != expected:
                return False
        return True

    def _encode_typed(self, value: Any) -> dict[str, str]:
        type_name, payload = self.serde.dumps_typed(value)
        return {
            "type": type_name,
            "data": base64.b64encode(payload).decode("ascii"),
        }

    def _decode_typed(self, payload: dict[str, str]) -> Any:
        return self.serde.loads_typed((payload["type"], base64.b64decode(payload["data"])))

    def _thread_and_ns(self, config: RunnableConfig) -> tuple[str, str]:
        configurable = config["configurable"]
        return str(configurable["thread_id"]), str(configurable.get("checkpoint_ns", ""))

    def _snapshot_key(self, run_id: str) -> str:
        return f"pipeline_run_state:{run_id}"

    def _checkpoint_key(self, thread_id: str) -> str:
        return f"pipeline_run_checkpoint:{thread_id}"

    async def _load_checkpoint_bucket(self, thread_id: str) -> dict[str, Any]:
        try:
            payload = await self._redis_manager.client.get(self._checkpoint_key(thread_id))
            if not payload:
                return {"namespaces": {}}
            parsed = json.loads(payload)
            if isinstance(parsed, dict) and "namespaces" in parsed:
                return parsed
            return {"namespaces": {}}
        except RedisError as error:
            logger.warning("pipeline.checkpoint.redis_load_failed", thread_id=thread_id, error=str(error))
            return {"namespaces": {}}

    async def _load_all_checkpoint_buckets(self) -> dict[str, dict[str, Any]]:
        try:
            buckets: dict[str, dict[str, Any]] = {}
            async for key in self._redis_manager.client.scan_iter(match="pipeline_run_checkpoint:*"):
                if not isinstance(key, str) or not key.startswith("pipeline_run_checkpoint:"):
                    continue
                thread_id = key.rsplit(":", 1)[-1]
                buckets[thread_id] = await self._load_checkpoint_bucket(thread_id)
            return buckets
        except RedisError as error:
            logger.warning("pipeline.checkpoint.redis_list_failed", error=str(error))
            return {}

    async def _save_checkpoint_bucket(self, thread_id: str, bucket: dict[str, Any]) -> None:
        try:
            await self._redis_manager.client.set(
                self._checkpoint_key(thread_id),
                json.dumps(bucket, default=_json_default),
                ex=self._ttl_seconds,
            )
        except RedisError as error:
            logger.warning("pipeline.checkpoint.redis_save_failed", thread_id=thread_id, error=str(error))


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(f"Type {type(value)!r} is not JSON serializable")
    raise TypeError(f"Type {type(value)!r} is not JSON serializable")
