"""Session-local serial playback authority with explicit client evidence (P01-P11)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

PlaybackKind = Literal["echo", "correction", "normal", "overflow", "incomplete"]


@dataclass(slots=True)
class PlaybackTask:
    """One prepared output; sending and confirmed playback are distinct facts."""

    playback_id: str
    kind: PlaybackKind
    generation: int
    source_id: str
    revision: int
    source_order: int
    final_segment: bool = False
    status: str = "queued"
    started: bool = False


class PlaybackArbiter:
    """Own playback sequencing while transport callbacks supply actual client evidence."""

    def __init__(self, evidence_sink: Callable[[dict[str, Any]], None] | None = None) -> None:
        """Create a session without a fabricated current output or playback acknowledgement."""
        self.generation = 0
        self.tasks: dict[str, PlaybackTask] = {}
        self.stop_requests: list[str] = []
        self._latest: dict[tuple[int, str, PlaybackKind], int] = {}
        self._active: PlaybackTask | None = None
        self._closed = False
        self._sink = evidence_sink

    def _record(self, task: PlaybackTask, event: str) -> None:
        """Preserve state transitions without leaking raw audio or user content."""
        if self._sink:
            self._sink(
                {
                    "event": event,
                    "playback_id": task.playback_id,
                    "collection_generation": task.generation,
                    "source_id": task.source_id,
                    "source_revision": task.revision,
                    "status": task.status,
                    "client_start_confirmed": task.started,
                    "output_kind": task.kind,
                }
            )

    def enqueue(
        self,
        *,
        playback_id: str,
        kind: PlaybackKind,
        generation: int,
        source_id: str,
        revision: int,
        source_order: int,
        final_segment: bool = False,
    ) -> PlaybackTask | None:
        """Accept prepared valid output, coalescing only definitely unplayed revisions.

        Returns:
            The task, or None for a stale generation/revision or duplicate identity.

        Raises:
            ValueError: If identity or sequence information is invalid.
        """
        if not playback_id or not source_id or revision < 1 or source_order < 0:
            raise ValueError("Playback identity and source order are required")
        if kind not in {"echo", "correction", "normal", "overflow", "incomplete"}:
            raise ValueError("Unknown playback kind")
        key = (generation, source_id, kind)
        if (
            self._closed
            or generation != self.generation
            or playback_id in self.tasks
            or revision <= self._latest.get(key, 0)
        ):
            return None
        self._latest[key] = revision
        for task in self.tasks.values():
            if task.status != "queued":
                continue
            same_source = task.generation == generation and task.source_id == source_id
            # A normal answer supersedes its unplayed final echo (P03=B).
            # Overflow takes precedence over all unplayed tail echoes (P01).
            superseded = (
                (same_source and task.kind == kind)
                or (kind == "normal" and task.final_segment and task.kind == "echo")
                or (kind == "overflow" and task.kind == "echo")
            )
            if superseded:
                self._cancel_unplayed(task)
        task = PlaybackTask(
            playback_id, kind, generation, source_id, revision, source_order, final_segment
        )
        self.tasks[playback_id] = task
        self._record(task, "playback_queued")
        if kind == "echo" and any(
            previous is not task
            and previous.generation == generation
            and previous.source_order >= source_order
            and previous.status != "cancelled_unplayed"
            and (previous.kind == "overflow" or (previous.kind == "normal" and final_segment))
            for previous in self.tasks.values()
        ):
            self._cancel_unplayed(task)
        return task

    def dispatch(self) -> PlaybackTask | None:
        """Reserve one output for sending; no next output until completion/stop evidence.

        The caller must send this exact identity with its audio. No client start
        evidence has been received yet, even when a send call returns success.
        """
        if self._closed or self._active is not None:
            return None
        queued = [task for task in self.tasks.values() if task.status == "queued"]
        if not queued:
            return None
        priority = {"overflow": 0, "correction": 1, "normal": 2, "incomplete": 2, "echo": 3}
        task = min(queued, key=lambda item: (priority[item.kind], item.source_order))
        task.status = "sent_unknown"
        self._active = task
        self._record(task, "playback_dispatched")
        return task

    def client_started(self, playback_id: str) -> bool:
        """Record only an acknowledgement matching the currently sent output identity."""
        task = self._active
        if task is None or task.playback_id != playback_id:
            return False
        task.started = True
        if task.status != "stop_requested":
            task.status = "playing"
        self._record(task, "playback_client_started")
        return True

    def client_finished(self, playback_id: str, *, event: str = "task_finished") -> bool:
        """Release the serial slot without inventing a missing start acknowledgement."""
        task = self._active
        if task is None or task.playback_id != playback_id:
            return False
        if event not in {"task_finished", "task_stopped", "task_failed"}:
            return False
        task.status = (
            "failed"
            if event == "task_failed"
            else "stopped"
            if event == "task_stopped" or task.status == "stop_requested"
            else "finished"
        )
        self._record(task, "playback_client_" + event.removeprefix("task_"))
        self._active = None
        return True

    def _cancel_unplayed(self, task: PlaybackTask) -> None:
        """Cancel only queued audio; in-flight audio must retain unknown/played evidence."""
        if task.status == "queued":
            task.status = "cancelled_unplayed"
            self._record(task, "playback_cancelled")

    def _request_stop(self, task: PlaybackTask) -> None:
        """Require the caller to propagate stop and await the client's drained/stopped reply."""
        if task.status != "stop_requested":
            task.status = "stop_requested"
            self.stop_requests.append(task.playback_id)
            self._record(task, "playback_stop_requested")

    def user_speech(self) -> None:
        """Preserve active echo during continuation; ordinary replies retain interruption."""
        active = self._active
        if active and active.kind in {"normal", "overflow", "incomplete"}:
            self._request_stop(active)
            for task in self.tasks.values():
                self._cancel_unplayed(task)

    def clear(self, generation: int) -> None:
        """Invalidate queued/cache work and request stop for old identifier audio.

        Raises:
            ValueError: If the supplied generation does not advance the collection.
        """
        if generation <= self.generation:
            raise ValueError("Collection generation must advance")
        self.generation = generation
        for task in self.tasks.values():
            if task.kind != "normal":
                self._cancel_unplayed(task)
        if self._active and self._active.kind in {"echo", "correction"}:
            self._request_stop(self._active)

    def close(self) -> None:
        """End a session while retaining missing playback acknowledgement as unknown."""
        self._closed = True
        for task in self.tasks.values():
            self._cancel_unplayed(task)
        if self._active:
            task = self._active
            task.status = "ended_started" if task.started else "ended_unknown"
            self._record(task, "playback_session_ended")
            self._active = None
