"""Immutable LLM request provenance and once-per-source business operations."""

from __future__ import annotations

import asyncio
import copy
import json
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any
from weakref import WeakKeyDictionary

from pipecat.frames.frames import (
    Frame,
    LLMContextFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection

from src.pipeline.response_revision import ResponseRevisions, ResponseVersion

Operation = Callable[[], Awaitable[dict[str, Any]]]


class ResponseScope:
    """One session's immutable inference scopes and settled operation results."""

    def __init__(
        self,
        owner: ResponseRevisions,
        evidence_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Share response ownership with TD without sharing mutable input provenance."""
        self.owner = owner
        self._contexts: WeakKeyDictionary[LLMContext, ResponseVersion] = WeakKeyDictionary()
        self._operations: dict[str, asyncio.Task[dict[str, Any]]] = {}
        self._lock = asyncio.Lock()
        self._closed = False
        self._sink = evidence_sink
        self.active: ContextVar[ResponseVersion | None] = ContextVar("td_response", default=None)
        self.enrich_context: Callable[[LLMContext, ResponseVersion], None] | None = None

    def record(self, kind: str, version: ResponseVersion | None, **fields: Any) -> None:
        """Emit safe operation evidence tied to its original user/response identity."""
        if self._sink:
            self._sink(
                {
                    "event": kind,
                    "turn_id": version.turn_id if version else None,
                    "response_id": version.response_id if version else None,
                    **fields,
                }
            )

    def bind(self, context: LLMContext, response_id: str | None = None) -> LLMContext:
        """Snapshot a request so a background tool cannot acquire a newer turn's authority.

        Raises:
            ValueError: If the requested response is no longer current.
        """
        version = self.owner.current
        if (
            self._closed
            or version is None
            or not self.owner.accepts_output(version.response_id)
            or (response_id is not None and response_id != version.response_id)
        ):
            raise ValueError("Response is no longer current")
        snapshot = LLMContext(
            messages=copy.deepcopy(context.get_messages()),
            tools=context.tools,
            tool_choice=context.tool_choice,
        )
        self._contexts[snapshot] = version
        if self.enrich_context is not None:
            self.enrich_context(snapshot, version)
        return snapshot

    def provenance(self, context: LLMContext) -> ResponseVersion | None:
        """Read the SDK runner's captured context, never the latest global text."""
        return self._contexts.get(context)

    async def execute(
        self,
        params: Any,
        operation: Operation,
        *,
        timeout: float = 5.0,
        validate: Callable[[], dict[str, Any] | None] | None = None,
    ) -> None:
        """Validate provenance and share one bounded operation across response revisions.

        Args:
            params: SDK FunctionCallParams carrying its immutable request context.
            operation: Deterministic validated business action returning its actual result.
            timeout: Upper bound in seconds for one operation to settle.
            validate: Optional current-input validation, run before consulting replay results.
        """
        version = self.provenance(params.context)
        if self._closed or version is None or not self.owner.accepts_output(version.response_id):
            self.record("tool_rejected", version, reason="stale_or_unbound_source")
            return
        if validate is not None:
            rejected = validate()
            if rejected is not None:
                self.record("tool_rejected", version, reason=rejected.get("status"))
                await params.result_callback(copy.deepcopy(rejected))
                return
        arguments = json.dumps(dict(params.arguments), sort_keys=True, allow_nan=False)
        identity = json.dumps(
            [version.turn_id, version.source_ids, params.function_name, arguments]
        )
        while True:
            async with self._lock:
                task = self._operations.get(identity)
                replay = task is not None
                if task is None:
                    task = asyncio.create_task(
                        self._operate(version, params.function_name, operation, timeout=timeout)
                    )
                    self._operations[identity] = task
            # Cancellation cannot prove that an already sent provider operation did
            # not apply. Keep its bounded settlement and result for the next version.
            result = await asyncio.shield(task)
            if not result.get("_td_not_started"):
                break
            async with self._lock:
                if self._operations.get(identity) is task:
                    self._operations.pop(identity)
            if self._closed or not self.owner.accepts_output(version.response_id):
                return
        if self.owner.accepts_output(version.response_id) and not self._closed:
            if validate is not None:
                rejected = validate()
                if rejected is not None:
                    self.record("tool_rejected", version, reason="state_changed_before_delivery")
                    await params.result_callback(copy.deepcopy(rejected))
                    return
            await params.result_callback(copy.deepcopy(result))
            self.record(
                "tool_callback_completed",
                version,
                function=params.function_name,
                replay=replay,
                operation_status=result.get("status"),
            )
        else:
            self.record("tool_result_discarded", version, reason="response_invalidated")

    async def _operate(
        self,
        version: ResponseVersion,
        function: str,
        operation: Operation,
        *,
        timeout: float,
    ) -> dict[str, Any]:
        """Settle a real attempt once; failures also cannot be silently replayed."""
        if not self.owner.accepts_output(version.response_id):
            return {"_td_not_started": True}
        self.record("tool_started", version, function=function)
        try:
            async with asyncio.timeout(timeout):
                result = await operation()
        except TimeoutError:
            result = {"status": "failed", "reason": "timeout"}
        except Exception as error:
            result = {"status": "failed", "reason": type(error).__name__}
        self.record("tool_settled", version, function=function, status=result.get("status"))
        return result

    async def close(self, *, timeout: float = 5.0) -> None:
        """Bound session cleanup and release immutable contexts without logging their contents."""
        self._closed = True
        tasks = list(self._operations.values())
        if tasks:
            _done, pending = await asyncio.wait(tasks, timeout=timeout)
            for task in pending:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        self._contexts.clear()
        self._operations.clear()


class ResponseScopedLLMMixin:
    """Bind actual SDK request contexts and fence late LLM output at its producer."""

    def __init__(self, *, response_scope: ResponseScope, **kwargs: Any) -> None:
        """Attach only to self-developed sessions; native service construction is unchanged."""
        self.response_scope = response_scope
        super().__init__(**kwargs)

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Give each inference, including tool continuations, its own immutable context."""
        if isinstance(frame, LLMContextFrame):
            try:
                snapshot = self.response_scope.bind(
                    frame.context, frame.metadata.get("td_response_id")
                )
            except ValueError:
                return
            version = self.response_scope.provenance(snapshot)
            replacement = LLMContextFrame(snapshot)
            replacement.metadata.update(frame.metadata)
            token = self.response_scope.active.set(version)
            try:
                await super().process_frame(replacement, direction)  # type: ignore[misc]
            finally:
                self.response_scope.active.reset(token)
        else:
            await super().process_frame(frame, direction)  # type: ignore[misc]

    async def push_frame(
        self,
        frame: Frame,
        direction: FrameDirection = FrameDirection.DOWNSTREAM,
    ) -> None:
        """Suppress old response tokens even when a provider ignores cancellation."""
        if isinstance(frame, (LLMTextFrame, LLMFullResponseStartFrame, LLMFullResponseEndFrame)):
            version = self.response_scope.active.get()
            if version is None or not self.response_scope.owner.accepts_output(version.response_id):
                return
            frame.metadata["td_response_id"] = version.response_id
            frame.metadata["td_turn_id"] = version.turn_id
        await super().push_frame(frame, direction)  # type: ignore[misc]

    async def _run_function_call(self, runner_item: Any) -> None:
        """Carry provenance through the SDK's separate sequential/background runner task."""
        version = self.response_scope.provenance(runner_item.context)
        if version is None or not self.response_scope.owner.accepts_output(version.response_id):
            self.response_scope.record("tool_runner_discarded", version, reason="stale")
            return
        token = self.response_scope.active.set(version)
        try:
            await super()._run_function_call(runner_item)  # type: ignore[misc]
        finally:
            self.response_scope.active.reset(token)

    async def broadcast_frame(self, frame_cls: type[Frame], **kwargs: Any) -> None:
        """Reject late tool lifecycle frames before they mutate the shared assistant context."""
        from pipecat.frames.frames import (
            FunctionCallInProgressFrame,
            FunctionCallResultFrame,
            FunctionCallsStartedFrame,
        )

        if issubclass(
            frame_cls,
            (FunctionCallInProgressFrame, FunctionCallResultFrame, FunctionCallsStartedFrame),
        ):
            version = self.response_scope.active.get()
            if version is None or not self.response_scope.owner.accepts_output(version.response_id):
                return
        await super().broadcast_frame(frame_cls, **kwargs)  # type: ignore[misc]
