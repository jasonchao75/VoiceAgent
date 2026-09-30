# Small WebRTC Compatibility Evidence

## Evidence status

- Evidence level: `local-real` for backend offer/answer and PATCH; frontend data-message remains pending
- Reviewed environment: repository virtual environment and installed locked frontend manifests
- Reviewed on: 2026-09-29
- Approved dependencies were installed locally. No external or paid provider call was made.

## Confirmed locally

- Backend pins `pipecat-ai[webrtc]==1.8.1` and `aiortc==1.15.0`.
- Frontend pins `@pipecat-ai/client-js@1.13.0`, `@pipecat-ai/small-webrtc-transport@1.10.7` and `qr@0.7.0`.
- Pipecat 1.8.1 exposes `SmallWebRTCRequestHandler`, POST-style offer handling, PATCH candidate handling, `SmallWebRTCConnection` and `SmallWebRTCTransport`. Runtime import verification confirms there is no `SmallWebRTCParams`; the transport constructor uses the shared `TransportParams` class.
- The transport converts WebRTC media into the pipeline's raw audio frames, so ASR/TTS contracts can remain behind the shared transport boundary.
- A real in-process aiortc peer completed offer/answer, applied an RFC 8840 end-of-candidates PATCH, and closed cleanly through the project adapter.
- The adapter tests prove single-use capability claim, capability-to-`pc_id` binding, callback-registration failure rejection, lease release and shutdown cleanup.

## Risks found in upstream behavior

### Callback failure can be masked

`SmallWebRTCRequestHandler.handle_web_request()` catches an exception raised by the connection callback, logs it and continues constructing the answer response. A browser could therefore receive an SDP answer even though the Bot pipeline was not started.

Required mitigation: wrap the handler with a project-owned session boundary, require successful pipeline task registration before declaring the offer successful, and close the connection/release the lease on failure.

### Signaling details can enter debug logs

The reviewed source contains debug paths for the full Small WebRTC request, signaling messages and remote ICE candidates. Those values can include SDP and network addresses.

Required mitigation: filter or raise the log level for the affected upstream loggers in production, avoid copying these values into application logs, and add a regression test using sentinel SDP/IP/candidate strings.

### PATCH needs project-level authorization

The upstream PATCH handler resolves a connection by `pc_id`. The public product contract requires stronger binding than a client-provided connection identifier.

Required mitigation: validate the short-lived session capability first, resolve its registered connection server-side, and reject any mismatched `pc_id` before calling the upstream handler.

## Still unverified

- Browser-side offer/PATCH/data-message compatibility for client-js 1.13.0 plus Small WebRTC transport 1.10.7.
- Real non-empty trickle candidate, media flow, reconnect and ICE-failure behavior.
- UDP/ICE reachability from the current DigitalOcean deployment without TURN.

## Dependency metadata checked

- `@pipecat-ai/small-webrtc-transport@1.10.7` declares `@pipecat-ai/client-js ~1.13.0`, matching the repository's pinned client-js 1.13.0 range. It is BSD-2-Clause, has an unpacked package size of 732,191 bytes, and brings `@daily-co/daily-js`, `dequal` and `lodash` dependencies. Metadata compatibility does not replace the required local-real offer/PATCH/data-message test.
- `qr@0.7.0` has no runtime dependencies in npm metadata, is dual licensed MIT or Apache-2.0, and has an unpacked package size of 485,788 bytes. The official package documentation reports about 6 KB gzipped for the encoding-only entry point and supports SVG plus browser PNG conversion.
- The user approved dependency option A on 2026-09-29; the lockfile is installed and `npm audit` reports zero known vulnerabilities.

## Required next evidence

Checkpoint B must complete the remaining browser-side data-message/audio path and non-empty trickle candidate test on the production route. DigitalOcean UDP/ICE remains a deployment verification item and must not be inferred from the local in-process result.
