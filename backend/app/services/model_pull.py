"""Download-model jobs with live progress.

Pulling a model takes minutes, so the request cannot hold the download open. A
job runs in the background and any number of viewers subscribe to its progress;
late subscribers replay the history so the UI always shows the whole story.

The registry is in-process. That is sufficient for the single-worker deployment
this application targets; a multi-worker deployment would need the registry
moved to shared storage, which the single-flight check below would otherwise
silently under-enforce.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.services.model_service import record_event
from app.services.ollama_client import OllamaClient, OllamaError

logger = logging.getLogger(__name__)

#: Bounded so a stalled browser cannot grow the server's memory without limit.
SUBSCRIBER_QUEUE_SIZE = 256


class PullInProgress(RuntimeError):
    """Another pull for the same model is already running."""


class PullNotFound(RuntimeError):
    """No pull job exists for the requested model."""


@dataclass
class PullJob:
    model: str
    actor_id: uuid.UUID | None = None
    status: str = "running"  # running | success | error
    error: str | None = None
    completed: int = 0
    total: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    subscribers: set[asyncio.Queue] = field(default_factory=set)
    task: asyncio.Task | None = None

    @property
    def percent(self) -> float:
        if not self.total:
            return 0.0
        return round(min(self.completed / self.total, 1.0) * 100, 1)

    def snapshot(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "status": self.status,
            "error": self.error,
            "completed": self.completed,
            "total": self.total,
            "percent": self.percent,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }

    def publish(self, event: str, data: dict[str, Any]) -> None:
        self.history.append({"event": event, "data": data})
        for queue in list(self.subscribers):
            try:
                queue.put_nowait({"event": event, "data": data})
            except asyncio.QueueFull:
                # A viewer that cannot keep up loses intermediate progress but
                # still receives the terminal event, which is what matters.
                logger.debug("dropping progress for a slow subscriber of %s", self.model)

    def close_subscribers(self) -> None:
        for queue in list(self.subscribers):
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass


class PullManager:
    def __init__(self) -> None:
        self._jobs: dict[str, PullJob] = {}

    def get(self, model: str) -> PullJob | None:
        return self._jobs.get(model)

    def active(self) -> list[dict[str, Any]]:
        return [
            job.snapshot() for job in self._jobs.values() if job.status == "running"
        ]

    async def start(
        self,
        model: str,
        *,
        actor_id: uuid.UUID | None = None,
        session_factory,
    ) -> PullJob:
        existing = self._jobs.get(model)
        if existing is not None and existing.status == "running":
            raise PullInProgress(f"{model} 正在下载中")

        job = PullJob(model=model, actor_id=actor_id)
        self._jobs[model] = job
        job.task = asyncio.create_task(self._run(job, session_factory))
        return job

    async def _run(self, job: PullJob, session_factory) -> None:
        client = OllamaClient()
        job.publish("progress", {"status": "starting", **job.snapshot()})
        try:
            async for chunk in client.pull_model(job.model):
                status = str(chunk.get("status") or "")
                if chunk.get("total"):
                    job.total = int(chunk["total"])
                if chunk.get("completed"):
                    job.completed = int(chunk["completed"])
                job.publish(
                    "progress",
                    {
                        "status": status,
                        "digest": chunk.get("digest"),
                        "completed": job.completed,
                        "total": job.total,
                        "percent": job.percent,
                    },
                )
            job.status = "success"
        except OllamaError as exc:
            job.status = "error"
            job.error = str(exc)
            logger.warning("pull failed for %s: %s", job.model, exc)
        except asyncio.CancelledError:
            job.status = "error"
            job.error = "下载已取消"
            raise
        except Exception as exc:  # noqa: BLE001 - a failed job must report, not crash
            job.status = "error"
            job.error = str(exc)
            logger.exception("unexpected failure pulling %s", job.model)
        finally:
            job.finished_at = datetime.now(UTC)
            await self._finish(job, session_factory)

    async def _finish(self, job: PullJob, session_factory) -> None:
        job.publish("done", job.snapshot())
        job.close_subscribers()
        try:
            async with session_factory() as session:
                await record_event(
                    session,
                    model=job.model,
                    action="pull" if job.status == "success" else "pull-failed",
                    actor_id=job.actor_id,
                    detail={"error": job.error} if job.error else None,
                )
        except Exception:  # noqa: BLE001 - bookkeeping must not mask the job result
            logger.exception("could not record the pull outcome for %s", job.model)

    async def stream(self, model: str):
        """Yield a job's history, then follow it until it finishes."""
        job = self._jobs.get(model)
        if job is None:
            raise PullNotFound(f"没有 {model} 的下载任务")

        queue: asyncio.Queue = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_SIZE)
        # Replay before subscribing would race with a job that finishes in
        # between; subscribing first and slicing the history is safe.
        job.subscribers.add(queue)
        try:
            sent = 0
            while True:
                while sent < len(job.history):
                    item = job.history[sent]
                    sent += 1
                    yield item
                if job.status != "running":
                    return
                item = await queue.get()
                if item is None:
                    while sent < len(job.history):
                        yield job.history[sent]
                        sent += 1
                    return
                while sent < len(job.history):
                    yield job.history[sent]
                    sent += 1
        finally:
            job.subscribers.discard(queue)


pull_manager = PullManager()
