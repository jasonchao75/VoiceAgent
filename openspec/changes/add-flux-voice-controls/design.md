# Design: Flux Voice Controls

## Decisions

- `tts_speed` remains provider-neutral and is reused for Flux; no duplicate storage field is introduced.
- Add `tts_expressivity` as an integer enum `-2..2`, defaulting to `0`.
- The UI uses a discrete slider with named endpoints and shows both parameters only when Deepgram Flux is selected.
- The UI intentionally limits speed to `0.85..1.15` for predictable conversational quality even though the current Flux API accepts a wider range. Backend validation matches the exposed safe range.
- Existing rows migrate to `tts_expressivity=0`; existing `tts_speed=1.0` remains unchanged.

## Runtime Mapping

`Bot → SessionRequest → TTSConfig → DeepgramFluxTTSService.Settings(speed, expressivity)`.

Changing expressivity affects the next session because Flux fixes it when opening the connection. Speed is also established at connection creation for this product flow.

