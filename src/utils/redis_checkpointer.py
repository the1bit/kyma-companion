"""Implementation of a langgraph checkpoint saver using Redis."""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import redis
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint import BaseCheckpointSaver
from langgraph.checkpoint.base import Checkpoint, CheckpointMetadata, CheckpointTuple
from langgraph.serde.jsonplus import JsonPlusSerializer
from redis.asyncio import ConnectionPool as AsyncConnectionPool
from redis.asyncio import Redis as AsyncRedis

from utils import logging

logger = logging.get_logger(__name__)


class JsonAndBinarySerializer(JsonPlusSerializer):
    """A JSON serializer that can handle binary data."""

    def _default(self, obj: Any) -> Any:
        if isinstance(obj, bytes | bytearray):
            return self._encode_constructor_args(obj.__class__, method="fromhex", args=[obj.hex()])
        return super()._default(obj)

    def dumps(self, obj: Any) -> bytes | str:
        """Serialize an object to a string."""
        try:
            if isinstance(obj, bytes | bytearray):
                return obj.hex()
            return super().dumps(obj)
        except Exception as e:
            logger.error(f"Serialization error: {e}")
            raise

    def loads(self, s: str | bytes, is_binary: bool = False) -> Any:
        """Deserialize a string to an object."""
        try:
            if is_binary:
                return bytes.fromhex(s)
            return super().loads(s)
        except Exception as e:
            logger.error(f"Deserialization error: {e}")
            raise


def initialize_async_pool(url: str = "redis://localhost", **kwargs: Any) -> AsyncConnectionPool:
    """Initialize an asynchronous Redis connection pool."""
    try:
        pool = AsyncConnectionPool.from_url(url, **kwargs)
        logger.info(f"Asynchronous Redis pool initialized with url={url}")
        return pool
    except Exception as e:
        logger.error(f"Error initializing async pool: {e}")
        raise


@asynccontextmanager
async def _get_async_connection(connection: AsyncRedis | AsyncConnectionPool | None) -> (
        AsyncGenerator)[AsyncRedis, None]:
    conn = None
    try:
        if isinstance(connection, AsyncRedis):
            yield connection
        elif isinstance(connection, AsyncConnectionPool):
            conn = AsyncRedis(connection_pool=connection)
            yield conn
        else:
            raise ValueError("Invalid async connection object.")
    except redis.ConnectionError as e:
        logger.error(f"Async connection error: {e}")
        raise
    finally:
        if conn:
            await conn.aclose()


class RedisSaver(BaseCheckpointSaver):
    """Implementation of a langgraph checkpoint saver using Redis."""
    async_connection: AsyncRedis | AsyncConnectionPool | None = None

    def __init__(self, async_connection: AsyncRedis | AsyncConnectionPool | None = None):
        super().__init__(serde=JsonAndBinarySerializer())
        self.async_connection = async_connection

    async def aput(self, config: RunnableConfig, checkpoint: Checkpoint,
                   metadata: CheckpointMetadata) -> RunnableConfig:
        """Saves a checkpoint."""
        thread_id = config["configurable"]["thread_id"]
        parent_ts = config["configurable"].get("thread_ts")
        key = f"checkpoint:{thread_id}:{checkpoint['ts']}"
        try:
            async with _get_async_connection(self.async_connection) as conn:
                await conn.hset(key, mapping={
                    "checkpoint": self.serde.dumps(checkpoint),
                    "metadata": self.serde.dumps(metadata),
                    "parent_ts": parent_ts if parent_ts else ""
                })
                logger.info(f"Checkpoint stored successfully for thread_id: {thread_id}, "
                            f"ts: {checkpoint['ts']}")
        except Exception as e:
            logger.error(f"Failed to aput checkpoint: {e}")
            raise
        return {
            "configurable": {
                "thread_id": thread_id,
                "thread_ts": checkpoint["ts"],
            },
        }

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """Gets a checkpoint tuple."""
        thread_id = config["configurable"]["thread_id"]
        thread_ts = config["configurable"].get("thread_ts", None)
        try:
            async with _get_async_connection(self.async_connection) as conn:
                if thread_ts:
                    key = f"checkpoint:{thread_id}:{thread_ts}"
                else:
                    all_keys = await conn.keys(f"checkpoint:{thread_id}:*")
                    if not all_keys:
                        logger.info(f"No checkpoints found for thread_id: {thread_id}")
                        return None
                    # convert all_keys to list and sort and get the latest key
                    all_keys.sort(key=lambda k: k.decode())
                    key = all_keys[-1]
                checkpoint_data = await conn.hgetall(key)
                if not checkpoint_data:
                    logger.info(f"No valid checkpoint data found for key: {key}")
                    return None
                checkpoint = self.serde.loads(checkpoint_data[b"checkpoint"].decode())
                metadata = self.serde.loads(checkpoint_data[b"metadata"].decode())
                parent_ts = checkpoint_data.get(b"parent_ts", b"").decode()
                parent_config = {
                    "configurable": {
                        "thread_id": thread_id,
                        "thread_ts": parent_ts}} if parent_ts else None
                logger.info(f"Checkpoint retrieved successfully for thread_id: {thread_id}, "
                            f"ts: {thread_ts}")
                return CheckpointTuple(config=config, checkpoint=checkpoint, metadata=metadata,
                                       parent_config=parent_config)
        except Exception as e:
            logger.error(f"Failed to get checkpoint tuple: {e}")
            raise

    async def alist(self, config: RunnableConfig | None, *, filter: dict[str, Any] | None = None,
                    before: RunnableConfig | None = None, limit: int | None = None) -> (
            AsyncGenerator)[CheckpointTuple, None]:
        """List checkpoints."""
        thread_id = config["configurable"]["thread_id"] if config else "*"
        pattern = f"checkpoint:{thread_id}:*"
        try:
            async with _get_async_connection(self.async_connection) as conn:
                keys = await conn.keys(pattern)
                if before:
                    keys = [k for k in keys if k.decode().split(":")[-1]
                            < before["configurable"]["thread_ts"]]
                keys = sorted(keys, key=lambda k: k.decode().split(":")[-1], reverse=True)
                if limit:
                    keys = keys[:limit]
                for key in keys:
                    data = await conn.hgetall(key)
                    if data and "checkpoint" in data and "metadata" in data:
                        thread_ts = key.decode().split(":")[-1]
                        yield CheckpointTuple(
                            config={"configurable": {"thread_id": thread_id,
                                                     "thread_ts": thread_ts}},
                            checkpoint=self.serde.loads(data["checkpoint"].decode()),
                            metadata=self.serde.loads(data["metadata"].decode()),
                            parent_config={"configurable": {
                                "thread_id": thread_id,
                                "thread_ts": data.get("parent_ts", b"").decode()
                            }} if data.get(
                                "parent_ts") else None,
                        )
                        logger.info(f"Checkpoint listed for thread_id: {thread_id}, "
                                    f"ts: {thread_ts}")
        except Exception as e:
            logger.error(f"Failed to list checkpoints: {e}")
            raise
