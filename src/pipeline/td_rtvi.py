"""Keep private TD submissions out of the public ASR caption stream."""

from typing import Any

from pipecat.observers.base_observer import FramePushed
from pipecat.processors.frameworks.rtvi import RTVIObserver, RTVIObserverParams, RTVIProcessor

from src.pipeline.td_strategies import TDSubmissionFrame


class TDTranscriptObserver(RTVIObserver):
    """Publish provider captions without echoing internal LLM submission frames."""

    async def on_push_frame(self, data: FramePushed) -> None:
        """Filter only the private duplicate, preserving identical real utterances."""
        if isinstance(data.frame, TDSubmissionFrame):
            return
        await super().on_push_frame(data)


class TDRTVIProcessor(RTVIProcessor):
    """Use the SDK's standard RTVI wiring with the custom TD caption observer."""

    def create_rtvi_observer(
        self, *, params: RTVIObserverParams | None = None, **kwargs: Any
    ) -> RTVIObserver:
        """Keep all standard messages and options except the private TD echo."""
        return TDTranscriptObserver(self, params=params, **kwargs)
