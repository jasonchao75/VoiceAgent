# Deepgram Flux v2 Streaming API Docs (Conversational STT)

> Flux is Deepgram's Conversational STT model family, designed specifically for Voice Agents and interactive assistants with built-in turn detection.

## 1. 核心接入差异速览 (Agent 必读)
- **Endpoint**: WebSocket API Endpoint 必须使用 `wss://api.deepgram.com/v2/listen` (注意是 **v2**，不同于 Nova 的 v1)。
- **Authentication**: 必须放在 WebSocket headers 中: `Authorization: Token YOUR_DEEPGRAM_API_KEY`
- **Core Parameters**:
  - `model`: 必须使用 `flux-general-en` (英文) 或 `flux-general-multi` (多语种)。
  - `encoding`: 如 `linear16` (PCM数据)。
  - `sample_rate`: 如 `8000` 或 `16000`。
- **Turn Detection (核心差异)**: Flux **没有** `endpointing` 参数。相反，它通过 WebSocket 返回不同的 Event 来控制对话流（如 `StartOfTurn`, `EagerEndOfTurn`, `EndOfTurn`）。请严格参考下方规范中的 `ChannelsListenV2MessagesListenV2TurnInfoEvent` 定义。

---

## 2. AsyncAPI 完整规范参考

```yaml
asyncapi: 2.6.0
info:
  title: listen.v2
  version: subpackage_listen/v2.listen.v2
  description: |
    Real-time conversational speech recognition with contextual turn detection
    for natural voice conversations
channels:
  /v2/listen:
    description: |
      Real-time conversational speech recognition with contextual turn detection
      for natural voice conversations
    bindings:
      ws:
        query:
          type: object
          properties:
            model:
              $ref: '#/components/schemas/ListenV2Model'
            encoding:
              $ref: '#/components/schemas/ListenV2Encoding'
            sample_rate:
              $ref: '#/components/schemas/ListenV2SampleRate'
            eager_eot_threshold:
              $ref: '#/components/schemas/ListenV2EagerEotThreshold'
            eot_threshold:
              $ref: '#/components/schemas/ListenV2EotThreshold'
            eot_timeout_ms:
              $ref: '#/components/schemas/ListenV2EotTimeoutMs'
            keyterm:
              $ref: '#/components/schemas/ListenV2Keyterm'
            mip_opt_out:
              $ref: '#/components/schemas/ListenV2MipOptOut'
            tag:
              $ref: '#/components/schemas/ListenV2Tag'
        headers:
          type: object
          properties:
            Authorization:
              type: string
    publish:
      operationId: listen-v-2-publish
      summary: Server messages
      message:
        oneOf:
          - $ref: >-
              #/components/messages/subpackage_listen/v2.listen.v2-server-0-ListenV2Connected
          - $ref: >-
              #/components/messages/subpackage_listen/v2.listen.v2-server-1-ListenV2TurnInfo
          - $ref: >-
              #/components/messages/subpackage_listen/v2.listen.v2-server-2-ListenV2ConfigureSuccess
          - $ref: >-
              #/components/messages/subpackage_listen/v2.listen.v2-server-3-ListenV2ConfigureFailure
          - $ref: >-
              #/components/messages/subpackage_listen/v2.listen.v2-server-4-ListenV2FatalError
    subscribe:
      operationId: listen-v-2-subscribe
      summary: Client messages
      message:
        oneOf:
          - $ref: >-
              #/components/messages/subpackage_listen/v2.listen.v2-client-0-ListenV2Media
          - $ref: >-
              #/components/messages/subpackage_listen/v2.listen.v2-client-1-ListenV2CloseStream
          - $ref: >-
              #/components/messages/subpackage_listen/v2.listen.v2-client-2-ListenV2Configure
servers:
  Production:
    url: wss://api.deepgram.com/
    protocol: wss
    x-default: true
  Agent:
    url: wss://api.deepgram.com/
    protocol: wss
components:
  messages:
    subpackage_listen/v2.listen.v2-server-0-ListenV2Connected:
      name: ListenV2Connected
      title: ListenV2Connected
      description: Receive a connected message
      payload:
        $ref: '#/components/schemas/ListenV2_ListenV2Connected'
    subpackage_listen/v2.listen.v2-server-1-ListenV2TurnInfo:
      name: ListenV2TurnInfo
      title: ListenV2TurnInfo
      description: Receive a turn info message
      payload:
        $ref: '#/components/schemas/ListenV2_ListenV2TurnInfo'
    subpackage_listen/v2.listen.v2-server-2-ListenV2ConfigureSuccess:
      name: ListenV2ConfigureSuccess
      title: ListenV2ConfigureSuccess
      description: >-
        Sent when a `Configure` message was successfully applied. Returns the
        current, up-to-date values that were applied.
      payload:
        $ref: '#/components/schemas/ListenV2_ListenV2ConfigureSuccess'
    subpackage_listen/v2.listen.v2-server-3-ListenV2ConfigureFailure:
      name: ListenV2ConfigureFailure
      title: ListenV2ConfigureFailure
      description: Indicates that a Configure message was rejected
      payload:
        $ref: '#/components/schemas/ListenV2_ListenV2ConfigureFailure'
    subpackage_listen/v2.listen.v2-server-4-ListenV2FatalError:
      name: ListenV2FatalError
      title: ListenV2FatalError
      description: Receive a fatal error message
      payload:
        $ref: '#/components/schemas/ListenV2_ListenV2FatalError'
    subpackage_listen/v2.listen.v2-client-0-ListenV2Media:
      name: ListenV2Media
      title: ListenV2Media
      description: Send audio or video data to be transcribed
      payload:
        $ref: '#/components/schemas/ListenV2_ListenV2Media'
    subpackage_listen/v2.listen.v2-client-1-ListenV2CloseStream:
      name: ListenV2CloseStream
      title: ListenV2CloseStream
      description: Send a CloseStream message to close the WebSocket stream
      payload:
        $ref: '#/components/schemas/ListenV2_ListenV2CloseStream'
    subpackage_listen/v2.listen.v2-client-2-ListenV2Configure:
      name: ListenV2Configure
      title: ListenV2Configure
      description: Send a Configure message to update Flux settings
      payload:
        $ref: '#/components/schemas/ListenV2_ListenV2Configure'
  schemas:
    ListenV2Model:
      type: string
      enum:
        - flux-general-en
        - flux-general-multi
      description: Defines the AI model used to process submitted audio.
      title: ListenV2Model
    ListenV2Encoding:
      type: string
      enum:
        - linear16
        - linear32
        - mulaw
        - alaw
        - opus
        - ogg-opus
      description: >-
        Encoding of the audio stream. Required if sending non-containerized/raw
        audio. If sending containerized audio, this parameter should be omitted.
      title: ListenV2Encoding
    ListenV2SampleRate:
      description: Any type
      title: ListenV2SampleRate
    ListenV2EagerEotThreshold:
      description: Any type
      title: ListenV2EagerEotThreshold
    ListenV2EotThreshold:
      description: Any type
      title: ListenV2EotThreshold
    ListenV2EotTimeoutMs:
      description: Any type
      title: ListenV2EotTimeoutMs
    ListenV2Keyterm:
      oneOf:
        - type: string
        - type: array
          items:
            type: string
      description: |
        Keyterm prompting can improve recognition of specialized terminology.
        Pass multiple keyterm query parameters to boost multiple keyterms.
      title: ListenV2Keyterm
    ListenV2MipOptOut:
      description: Any type
      title: ListenV2MipOptOut
    ListenV2Tag:
      description: Any type
      title: ListenV2Tag
    ChannelsListenV2MessagesListenV2ConnectedType:
      type: string
      enum:
        - Connected
      description: Message type identifier
      title: ChannelsListenV2MessagesListenV2ConnectedType
    ListenV2_ListenV2Connected:
      type: object
      properties:
        type:
          $ref: '#/components/schemas/ChannelsListenV2MessagesListenV2ConnectedType'
          description: Message type identifier
        request_id:
          type: string
          format: uuid
          description: The unique identifier of the request
        sequence_id:
          type: integer
          description: |
            Starts at `0` and increments for each message the server sends
            to the client.  This includes messages of other types, like
            `TurnInfo` messages.
      required:
        - type
        - request_id
        - sequence_id
      title: ListenV2_ListenV2Connected
    ChannelsListenV2MessagesListenV2TurnInfoEvent:
      type: string
      enum:
        - Update
        - StartOfTurn
        - EagerEndOfTurn
        - TurnResumed
        - EndOfTurn
      description: >
        The type of event being reported.


        - **Update** - Additional audio has been transcribed, but the turn state
        hasn't changed

        - **StartOfTurn** - The user has begun speaking for the first time in
        the turn

        - **EagerEndOfTurn** - The system has moderate confidence that the user
        has finished speaking for the turn. This is an opportunity to begin
        preparing an agent reply

        - **TurnResumed** - The system detected that speech had ended and
        therefore sent an **EagerEndOfTurn** event, but speech is actually
        continuing for this turn

        - **EndOfTurn** - The user has finished speaking for the turn
      title: ChannelsListenV2MessagesListenV2TurnInfoEvent
    ChannelsListenV2MessagesListenV2TurnInfoWordsItems:
      type: object
      properties:
        word:
          type: string
          description: The individual punctuated, properly-cased word from the transcript
        confidence:
          type: number
          format: double
          description: Confidence that this word was transcribed correctly
      required:
        - word
        - confidence
      title: ChannelsListenV2MessagesListenV2TurnInfoWordsItems
    ListenV2_ListenV2TurnInfo:
      type: object
      properties:
        type:
          type: string
          enum:
            - TurnInfo
        request_id:
          type: string
          format: uuid
          description: The unique identifier of the request
        sequence_id:
          type: integer
          description: >
            Starts at `0` and increments for each message the server sends to
            the client.  This includes messages of other types, like `Connected`
            messages.
        event:
          $ref: '#/components/schemas/ChannelsListenV2MessagesListenV2TurnInfoEvent'
          description: >
            The type of event being reported.


            - **Update** - Additional audio has been transcribed, but the turn
            state hasn't changed

            - **StartOfTurn** - The user has begun speaking for the first time
            in the turn

            - **EagerEndOfTurn** - The system has moderate confidence that the
            user has finished speaking for the turn. This is an opportunity to
            begin preparing an agent reply

            - **TurnResumed** - The system detected that speech had ended and
            therefore sent an **EagerEndOfTurn** event, but speech is actually
            continuing for this turn

            - **EndOfTurn** - The user has finished speaking for the turn
        turn_index:
          type: integer
          description: The index of the current turn
        audio_window_start:
          type: number
          format: double
          description: Start time in seconds of the audio range that was transcribed
        audio_window_end:
          type: number
          format: double
          description: End time in seconds of the audio range that was transcribed
        transcript:
          type: string
          description: Text that was said over the course of the current turn
        words:
          type: array
          items:
            $ref: >-
              #/components/schemas/ChannelsListenV2MessagesListenV2TurnInfoWordsItems
          description: The words in the `transcript`
        end_of_turn_confidence:
          type: number
          format: double
          description: Confidence that no more speech is coming in this turn
        languages:
          type: array
          items:
            type: string
          description: |
            Detected languages sorted by descending frequency in the
            transcript. Only present when the flux-general-multi model
            detects languages in the audio.
        languages_hinted:
          type: array
          items:
            type: string
          description: |
            The language hints that were supplied for this turn. Only
            present when language hints are configured.
      required:
        - type
        - request_id
        - sequence_id
        - event
        - turn_index
        - audio_window_start
        - audio_window_end
        - transcript
        - words
        - end_of_turn_confidence
      description: Describes the current turn and latest state of the turn
      title: ListenV2_ListenV2TurnInfo
```