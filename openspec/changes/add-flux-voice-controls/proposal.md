# Change: Add Flux Voice Controls

## Why

Deepgram Flux voices currently use a fixed neutral delivery and the Bot editor exposes no provider-supported tuning, making some voices sound too flat.

## What Changes

- Expose Flux `expressivity` as five discrete values from Calm (`-2`) to Animated (`2`).
- Expose Flux `speed` with a conservative `0.85`–`1.15` UI range in `0.05` steps.
- Persist both values per Bot and pass them to the Flux streaming connection.
- Preserve existing Bot behavior with defaults `expressivity=0` and `speed=1.0`.

## Impact

- Affected specs: `bot-config`, `voice-pipeline`
- Affected code: Bot schemas/storage migration, session resolution, Flux factory, Bot editor and tests

