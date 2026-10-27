"""Concrete existing providers with optional custom-TD response fencing."""

from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

from src.tts.confirmed_flux import ConfirmedDeepgramFluxTTSService
from src.tts.response_scope import ResponseScopedTTSMixin


class ScopedDeepgramFluxTTSService(ResponseScopedTTSMixin, ConfirmedDeepgramFluxTTSService):
    """Preserve confirmed Flux configuration and original response audio provenance."""


class ScopedElevenLabsTTSService(ResponseScopedTTSMixin, ElevenLabsTTSService):
    """Keep ElevenLabs provider context identity across Final cancellation."""
