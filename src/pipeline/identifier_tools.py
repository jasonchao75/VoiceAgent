"""Conversation LLM tools using captured source evidence and shared identifier state."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from typing import Any

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import FunctionCallResultProperties
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.services.llm_service import FunctionCallParams

from src.asr.transcript import TranscriptView
from src.pipeline.identifier import IdentifierCollection, IdentifierSource
from src.pipeline.response_revision import ResponseVersion
from src.pipeline.response_scope import ResponseScope


class IdentifierTools:
    """Expose business operations without giving the LLM authority over source identities."""

    def __init__(
        self,
        scope: ResponseScope,
        collection: IdentifierCollection,
        *,
        keywords: tuple[str, ...] | None = None,
        new_collection_allowed: Callable[[], bool] | None = None,
    ) -> None:
        """Use the same collection as the local strict-format path."""
        self.scope = scope
        self.collection = collection
        self._sources: dict[str, IdentifierSource] = {}
        self._turn_generations: dict[str, int] = {}
        self._turn_gates: dict[str, bool] = {}
        self._evidence: dict[str, TranscriptView] = {}
        self.keywords = keywords
        self._new_collection_allowed = new_collection_allowed
        self._new_turns: dict[str, bool] = {}

    def bind_snapshot(
        self,
        version: ResponseVersion,
        snapshot: TranscriptView,
        assistant: str,
    ) -> None:
        """Bind coordinator-owned audio groups only when the actual keyword gate matches."""
        matched = self.keywords is None or any(
            keyword.casefold() in assistant.casefold() for keyword in self.keywords
        )
        if not self._turn_gates.setdefault(version.turn_id, matched):
            return
        if snapshot.text != version.text:
            raise ValueError("Response text must equal the effective source snapshot")
        self._new_turns.setdefault(
            version.turn_id,
            self._new_collection_allowed()
            if self._new_collection_allowed
            else self.collection.successful,
        )
        self.bind_response(version, self.collection.bind_snapshot(snapshot))
        if version.response_id in self._sources:
            self._evidence[version.response_id] = snapshot
            if version.final:
                self.collection.confirm_equivalent_final(self._sources[version.response_id])

    def _record_result(
        self,
        params: FunctionCallParams,
        operation: str,
        result: dict[str, Any],
    ) -> None:
        """Record actual state transitions once; replay never invents another applied event."""
        version = self.scope.provenance(params.context)
        snapshot = self._evidence.get(version.response_id) if version else None
        self.scope.record(
            "identifier_tool_result",
            version,
            operation=operation,
            **result,
            source_ranges=[
                {
                    "epoch": s.epoch,
                    "source_id": s.source_id,
                    "source_revision": s.revision,
                    "start_ms": s.start_ms,
                    "end_ms": s.end_ms,
                }
                for s in snapshot.segments
            ]
            if snapshot
            else None,
        )

    def enrich_context(self, context: LLMContext, version: ResponseVersion) -> None:
        """Attach current server truth to this inference snapshot, never fake a user turn."""
        source = self._sources.get(version.response_id)
        already_collected = source is not None and self.collection.locally_collected(source)
        if already_collected and isinstance(context.tools, ToolsSchema):
            context.set_tools(
                ToolsSchema(
                    standard_tools=[
                        tool
                        for tool in context.tools.standard_tools
                        if tool.name not in {"submit_identifier", "clear_identifier"}
                    ],
                    custom_tools=context.tools.custom_tools,
                )
            )
        state = {
            "value": self.collection.value,
            "count": len(self.collection.value),
            "target_length": self.collection.target_length,
            "generation": self.collection.generation,
            "current_input_authorized": source is not None
            and source.generation == self.collection.generation,
            "current_input_already_collected": already_collected,
            "new_collection_on_submit": self._new_turns.get(version.turn_id, False),
        }
        context.add_message(
            {
                "role": "system",
                "content": (
                    "Server-verified identifier collection state: "
                    + json.dumps(state, ensure_ascii=False)
                    + ". Use these values for count/repetition questions. "
                    "Modify only through the tools; never report a successful change "
                    "without a successful tool result. Corrections clear the entire identifier "
                    "and require a complete reread. If current_input_authorized is false, "
                    "do not attempt to submit or clear from this input."
                ),
            }
        )

    def bind_response(self, version: ResponseVersion, source: IdentifierSource) -> None:
        """Capture coordinator-proven input before starting its corresponding inference.

        Args:
            version: Immutable request authority created by the TD owner.
            source: Exact effective collection input, never an LLM-provided identity.

        Raises:
            ValueError: If source text or connection identity differs from the request.
        """
        if (
            source.text != version.text
            or (source.evidence_ids or ((source.epoch, source.source_id),)) != version.source_ids
        ):
            raise ValueError("Identifier tool source must match the original request")
        generation = self._turn_generations.setdefault(version.turn_id, source.generation)
        # Final reanswer cannot acquire authority over data created after its
        # original clear, even if the LLM chooses different arguments this time.
        if generation == source.generation:
            self._sources[version.response_id] = source

    def schemas(self) -> list[FunctionSchema]:
        """Return existing SDK tool schemas with real handlers and constrained arguments."""
        return [
            FunctionSchema(
                name="submit_identifier",
                description=(
                    "Submit an identifier explicitly provided in the current user input. "
                    "Do not use for corrections or extract digits from unrelated requests. "
                    "Only report success when the tool returns submitted or duplicate."
                ),
                properties={"identifier": {"type": "string", "minLength": 1}},
                required=["identifier"],
                handler=self.submit,
            ),
            FunctionSchema(
                name="clear_identifier",
                description=(
                    "Clear the current identifier when the user explicitly requests clearing "
                    "or correction, including editing any position. After a cleared result, "
                    "ask for the complete identifier again; do not append correction digits."
                ),
                properties={},
                required=[],
                handler=self.clear,
            ),
        ]

    def _source(self, params: FunctionCallParams) -> IdentifierSource | None:
        """Resolve only the SDK's original context and previously captured coordinator evidence."""
        version = self.scope.provenance(params.context)
        return self._sources.get(version.response_id) if version else None

    def _rejected(self, reason: str) -> dict[str, Any]:
        """Include current collection truth without claiming a state transition."""
        return {
            "status": reason,
            "value": self.collection.value,
            "count": len(self.collection.value),
            "generation": self.collection.generation,
        }

    def _result_params(
        self,
        params: FunctionCallParams,
        confirm: Callable[[], None] | None = None,
    ) -> FunctionCallParams:
        """Report state at delivery, without rewriting the cached operation or another call."""
        scoped = copy.copy(params)

        async def deliver(
            result: Any,
            *,
            properties: FunctionCallResultProperties | None = None,
        ) -> None:
            """A parallel clear/replacement may have superseded a legitimately applied action."""
            result = dict(result)
            if confirm and result.get("status") in {"submitted", "duplicate"}:
                confirm()
            if result.get("value") != self.collection.value and result.get("status") in {
                "submitted",
                "duplicate",
                "cleared",
            }:
                result["status"] = "superseded"
            result.update(
                value=self.collection.value,
                count=len(self.collection.value),
                generation=self.collection.generation,
            )
            self.scope.record(
                "identifier_tool_result_offered", self.scope.provenance(params.context), **result
            )
            if properties is None:
                await params.result_callback(result)
            else:
                await params.result_callback(result, properties=properties)

        scoped.result_callback = deliver
        return scoped

    async def submit(self, params: FunctionCallParams) -> None:
        """Validate actual source and return the committed state through the SDK callback."""
        source = self._source(params)

        def validate() -> dict[str, Any] | None:
            """A previous success cannot authorize a number absent from the new Final."""
            if source is None:
                return self._rejected("stale")
            identifier = params.arguments.get("identifier")
            if not isinstance(identifier, str) or set(params.arguments) != {"identifier"}:
                return self._rejected("invalid")
            reason = self.collection.validate_submission(source, identifier)
            return self._rejected(reason) if reason else None

        async def apply() -> dict[str, Any]:
            """Keep validation inside the atomic scoped business operation."""
            nonlocal source
            rejected = validate()
            if rejected is not None:
                return rejected
            if source is None:
                return self._rejected("stale")
            identifier = params.arguments.get("identifier")
            if not isinstance(identifier, str) or set(params.arguments) != {"identifier"}:
                return self._rejected("invalid")
            version = self.scope.provenance(params.context)
            if version is not None and self._new_turns.get(version.turn_id, False):
                snapshot = self._evidence.get(version.response_id)
                if snapshot is None:
                    return self._rejected("stale")
                old_generation = self.collection.generation
                self.collection.begin_collection()
                self._new_turns[version.turn_id] = False
                if self.collection.generation != old_generation:
                    source = self.collection.bind_snapshot(snapshot)
                    self._turn_generations[version.turn_id] = self.collection.generation
                    self.bind_response(version, source)
                    self.scope.record(
                        "identifier_collection_started",
                        version,
                        generation=self.collection.generation,
                    )
            result = self.collection.submit_tool(source, identifier)
            self._record_result(params, "submit", result)
            return result

        def confirm() -> None:
            """Refresh accepted Final proof before triggering any tool continuation."""
            identifier = params.arguments.get("identifier")
            if source is not None and isinstance(identifier, str) and validate() is None:
                self.collection.confirm_submission(source, identifier)

        await self.scope.execute(self._result_params(params, confirm), apply, validate=validate)

    async def clear(self, params: FunctionCallParams) -> None:
        """Invalidate the collection once and fence all old generation operations."""
        source = self._source(params)

        async def apply() -> dict[str, Any]:
            """Never let a model select or override the target collection generation."""
            if source is None:
                return self._rejected("stale")
            if params.arguments:
                return self._rejected("invalid")
            result = self.collection.clear_tool(source)
            self._record_result(params, "clear", result)
            return result

        await self.scope.execute(self._result_params(params), apply)

    def close(self) -> None:
        """Release session input provenance after the owning pipeline shuts down."""
        self._sources.clear()
        self._turn_generations.clear()
        self._turn_gates.clear()
        self._evidence.clear()
        self._new_turns.clear()
