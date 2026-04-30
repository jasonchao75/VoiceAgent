# Speechmatics Realtime (Streaming) API

## 1. 核心信息
- **接口协议**: WebSocket (`wss://eu.rt.speechmatics.com/v2/` 默认为 EU 节点，或者对应区域的节点)
- **鉴权方式**: HTTP Handshake 阶段携带 Header: `Authorization: Bearer YOUR_API_KEY`
- **基础流程**: 
  1. 建立 WebSocket 连接。
  2. 发送 `StartRecognition` JSON 消息配置音频和语言。
  3. 接收 `RecognitionStarted` JSON 消息确认。
  4. 持续发送二进制音频数据 (`AddAudio`)。
  5. 接收转写结果 (`AddPartialTranscript`, `AddTranscript` 等)。
  6. 发送 `EndOfStream` JSON 消息。
  7. 接收 `EndOfTranscript` 消息，随后关闭连接。

## 2. 关键请求消息 (Client -> Server)

### 2.1 `StartRecognition`
这是建立连接后的首个消息，必填。用于配置音频格式和转写参数。
```json
{
  "message": "StartRecognition",
  "audio_format": {
    "type": "raw",
    "encoding": "pcm_s16le",
    "sample_rate": 8000
  },
  "transcription_config": {
    "language": "en",
    "enable_partials": true,
    "max_delay": 4
  }
}
```

#### `audio_format` 参数详情
- `type`: 必填。实时音频流传 `raw`。
- `encoding`: 必填。通常为 `pcm_f32le`, `pcm_s16le`, `mulaw`。**电话场景固定为 `pcm_s16le`**。
- `sample_rate`: 必填。采样率，例如 `8000` 或 `16000`。**电话场景固定为 `8000`**。

#### `transcription_config` 核心参数详情
- `language`: 必填。符合 ISO 语言代码（如 "en", "zh"）。
- `enable_partials`: 是否发送中间结果(`AddPartialTranscript`)，流式场景通常设置为 `true`，默认为 `false`。
- `max_delay`: 最终结果(Final transcript)返回的最大延迟（秒），可取 `0.7` 到 `4`，默认为 `4`。延迟越高上下文理解越好。
- `operating_point`: 模型选择，`standard` 或 `enhanced`，默认为 `standard`。
- `diarization`: 说话人分离。可设为 `none`, `speaker`, `channel`, `channel_and_speaker`。开启后结果中会带有 `speaker` 标签。
- `domain`: 指定领域模型，如 `finance` 或 `medical`（可选）。
- `additional_vocab`: 自定义词典/热词（可选数组），可以通过 `content` 和 `sounds_like` 提升专有词汇识别率。注意：使用热词可能会在会话初始化时带来最长15秒的延迟。
- `punctuation_overrides`: 控制标点符号输出的配置。
- `enable_entities`: 是否开启实体格式化（如日期、金钱、数字转写格式化），默认为 `true`。
- `conversation_config.end_of_utterance_silence_trigger`: 设置非说话静音时长（0-2秒），触发后会发送 `EndOfUtterance` 消息。
- `translation_config`: 如果需要边转写边翻译，可配置 `target_languages` 数组（需注意有些端点可能不支持）。

### 2.2 `AddAudio`
发送二进制音频块。注意：此消息**没有**外层 JSON 包装，直接发送 binary buffer 即可。

### 2.3 `EndOfStream`
音频发送完毕时调用。
```json
{
  "message": "EndOfStream",
  "last_seq_no": 123
}
```
`last_seq_no` 是你发送的音频包的计数（可选填入正确的数值，以便服务器进行校验）。

### 2.4 `SetRecognitionConfig`
允许客户端在会话进行中重新配置转写参数（无需断开重连）。
```json
{
  "message": "SetRecognitionConfig",
  "transcription_config": {
    "language": "en",
    "max_delay": 2,
    "enable_partials": true
  }
}
```
> **注意**：
> - 可以在这里指定 `language`，但必须与 `StartRecognition` 初始握手时配置的语言一致（不能用于语种切换）。
> - 主要用于动态调整 `max_delay`, `audio_filtering_config` 或 `conversation_config`。
> - 试图修改不允许热更新的参数将导致服务端报错。

## 3. 关键接收消息 (Server -> Client)

### 3.1 `AddPartialTranscript`
中间转写结果（如果 `enable_partials: true`）。
```json
{
  "message": "AddPartialTranscript",
  "metadata": {
    "start_time": 0.5,
    "end_time": 1.2,
    "transcript": "Hello wo"
  },
  "results": [...]
}
```
- **注意**：大段文本通常拼接 `metadata.transcript`。

### 3.2 `AddTranscript`
最终确定的转写片段。
```json
{
  "message": "AddTranscript",
  "metadata": {
    "start_time": 1.2,
    "end_time": 2.5,
    "transcript": "Hello world."
  },
  "results": [...]
}
```

## 4. 常见问题与异常处理
- **WebSocket 报错 4001 Not Authorised**: Token 格式错误或未放置在握手 Header 中。
- **WebSocket 报错 4004 Invalid Model / Invalid Language**: 语言不支持。
- **4005 Quota Exceeded / 4013 Job Error**: 需要在客户端实现 5-10 秒的重试逻辑。
- **Idle Timeout (1008)**: 若 1 小时内没有音频发送，会被断开连接，服务端会提前发送 `Warning` (type=`idle_timeout`)。
- **强制要求**: 发送完音频后必须发 `EndOfStream` 否则服务端不知道何时结束转写。

---

## 5. Reference: Official API Spec
> **防幻觉红线**: 以下为官方原始 API 规范文档备份。当上方精简版参数无法满足需求或出现争议时，请**绝对以本段下方的官方原始定义为准**。

# Realtime API Reference

```
GET
wss://eu.rt.speechmatics.com/v2/
```

## Protocol overview

A basic Realtime session will have the following message exchanges:



#### Browser based transcription

When starting a Realtime transcription session **in the browser**, [temporary keys](/get-started/authentication.md#temporary-keys) should be used to avoid exposing your long-lived API key.

To do so, you must provide the temporary key as a part of a query parameter. This is due to a browser limitation. For example:

```
 wss://eu.rt.speechmatics.com/v2?jwt=<temporary-key>
```

### Handshake responses

**Successful Response**

* `101 Switching Protocols` - Switch to WebSocket protocol

Here is an example for a successful WebSocket handshake:

```
GET /v2/ HTTP/1.1
Host: eu.rt.speechmatics.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: ujRTbIaQsXO/0uCbjjkSZQ==
Sec-WebSocket-Version: 13
Sec-WebSocket-Extensions: permessage-deflate; client_max_window_bits
Authorization: Bearer wmz9fkLJM6U5NdyaG3HLHybGZj65PXp
User-Agent: Python/3.8 websockets/8.1
```

A successful response should look like:

```
HTTP/1.1 101 Switching Protocols
Server: nginx/1.17.8
Date: Wed, 06 Jan 2021 11:01:05 GMT
Connection: upgrade
Upgrade: WebSocket
Sec-WebSocket-Accept: 87kiC/LI5WgXG52nSylnfXdz260=
```

**Malformed request**

A malformed handshake request will result in one of the following HTTP responses:

* `400 Bad Request`
* `401 Unauthorized` - when the API key is not valid
* `405 Method Not Allowed` - when the request method is not GET

**Client Retry**

Following a successful handshake and switch to the WebSocket protocol, the client could receive an immediate error message and WebSocket close handshake from the server. For the following errors only, we recommend adding a client retry interval of at least 5-10 seconds:

* `4005 quota_exceeded`
* `4013 job_error`
* `1011 internal_error`

## Message handling

Each message that the **Server** accepts is a stringified JSON object with the following fields:

* `message` (String): The name of the message we are sending. Any other fields depend on the value of the `message` and are described below.

The messages sent by the **Server** to a **Client** are stringified JSON objects as well.

The only exception is a binary message sent from the **Client** to the **Server** containing a chunk of audio which will be referred to as `AddAudio`.

The following values of the `message` field are supported:

## Sent messages

### StartRecognition

See example

Initiates a new recognition session.

**message**required

Constant value: `StartRecognition`

**audio\_format** objectrequired

oneOf

* Raw
* File

Raw audio samples, described by the following additional mandatory fields:

**type**required

Constant value: `raw`

**encoding**stringrequired

Possible values: \[`pcm_f32le`, `pcm_s16le`, `mulaw`]

**sample\_rate**integerrequired

The sample rate of the audio in Hz.

**Example**: `{"type":"raw","encoding":"pcm_s16le","sample_rate":44100}`

Choose this option to send audio encoded in a recognized format. The AddAudio messages have to provide all the file contents, including any headers. The file is usually not accepted all at once, but segmented into reasonably sized messages.

Note: Only the following formats are supported: `wav`, `mp3`, `aac`, `ogg`, `mpeg`, `amr`, `m4a`, `mp4`, `flac`

**type**required

Constant value: `file`

**transcription\_config** objectrequired

Contains configuration for this recognition session.

**language**stringrequired

Language model to process the audio input, normally specified as an ISO language code. The value must be consistent with the language code used in the API endpoint URL.

**Example:&#x20;**`en`

**domain**string

Request a specialized model based on 'language' but optimized for a particular field, e.g. `finance` or `medical`.

**output\_locale**string

Configure locale for outputted transcription. See [output formatting](https://docs.speechmatics.com/speech-to-text/formatting#output-locale).

Possible values: `non-empty`

**additional\_vocab** object\[]

Configure [custom dictionary](https://docs.speechmatics.com/speech-to-text/features/custom-dictionary). Default is an empty list. You should be aware that there is a performance penalty (latency degradation and memory increase) from using `additional_vocab`, especially if you use a large word list. When initializing a session that uses `additional_vocab` in the config, you should expect a delay of up to 15 seconds (depending on the size of the list).

* Array \[

oneOf

* String
* Object

Pass a non-empty string to add a single word to the dictionary.

****string

Pass a non-empty string to add a single word to the dictionary.

Possible values: `non-empty`

Pass an object to add a single word to the dictionary, with an array of words which it sounds like.

**content**stringrequired

Possible values: `non-empty`

**sounds\_like**string\[]

Possible values: `>= 1`

* ]

**diarization**string

Set to `speaker` to apply [Speaker Diarization](https://docs.speechmatics.com/speech-to-text/features/diarization) to the audio.

Possible values: \[`none`, `speaker`, `channel`, `channel_and_speaker`]

**Default value:&#x20;**`none`

**max\_delay**number

This is the delay in seconds between the end of a spoken word and returning the Final transcript results. See [Latency](https://docs.speechmatics.com/speech-to-text/realtime/output#latency) for more details

Possible values: `>= 0.7` and `<= 4`

**Default value:&#x20;**`4`

**max\_delay\_mode**string

This allows some additional time for [Smart Formatting](https://docs.speechmatics.com/speech-to-text/formatting#smart-formatting).

Possible values: \[`flexible`, `fixed`]

**Default value:&#x20;**`flexible`

**speaker\_diarization\_config** object

**max\_speakers**integer

Configure the maximum number of speakers to detect. See [Max Speakers](http://docs.speechmatics.com/speech-to-text/features/diarization#max-speakers).

Possible values: `>= 2`

**prefer\_current\_speaker**boolean

When set to `true`, reduces the likelihood of incorrectly switching between similar sounding speakers. See [Prefer Current Speaker](https://docs.speechmatics.com/speech-to-text/features/diarization#prefer-current-speaker).

**Default value:&#x20;**`false`

**speaker\_sensitivity**float

Possible values: `>= 0` and `<= 1`

**get\_speakers**boolean

If true, speaker identifiers will be returned at the end of transcript.

**speakers** object\[]

Use this option to provide speaker labels linked to their speaker identifiers. When passed, the transcription system will tag spoken words in the transcript with the provided speaker labels whenever any of the specified speakers is detected in the audio. A maximum of 50 speakers identifiers across all speakers can be provided.

* Array \[

**label**stringrequired

Speaker label, which must not match the format used internally (e.g. S1, S2, etc)

Possible values: `non-empty`

**speaker\_identifiers**bytes\[]required

Possible values: `>= 1`

* ]

**audio\_filtering\_config** object

Puts a lower limit on the volume of processed audio by using the `volume_threshold` setting. See [Audio Filtering](https://docs.speechmatics.com/speech-to-text/features/audio-filtering).

**volume\_threshold**float

Possible values: `>= 0` and `<= 100`

**transcript\_filtering\_config** object

**remove\_disfluencies**boolean

When set to `true`, removes disfluencies from the transcript. See [Removing disfluencies](https://docs.speechmatics.com/speech-to-text/formatting#removing-disfluencies)

**replacements** object\[]

A list of replacement rules to apply to the transcript. Each rule consists of a pattern to match and a replacement string. See [Word replacement](https://docs.speechmatics.com/speech-to-text/formatting#word-replacement)

* Array \[

**from**stringrequired

**to**stringrequired

* ]

**enable\_partials**boolean

Whether or not to send Partials (i.e. `AddPartialTranslation` messages) as well as Finals (i.e. `AddTranslation` messages) See [Partial transcripts](https://docs.speechmatics.com/speech-to-text/realtime/output#partial-transcripts).

**Default value:&#x20;**`false`

**enable\_entities**boolean

**Default value:&#x20;**`true`

**operating\_point**string

Which model you wish to use. See [Operating points](http://docs.speechmatics.com/speech-to-text/#operating-points) for more details.

Possible values: \[`standard`, `enhanced`]

**Default value:&#x20;**`standard`

**punctuation\_overrides** object

Options for controlling punctuation in the output transcripts. See [Punctuation Settings](https://docs.speechmatics.com/speech-to-text/formatting#punctuation)

**permitted\_marks**string\[]

The punctuation marks which the client is prepared to accept in transcription output, or the special value 'all' (the default). Unsupported marks are ignored. This value is used to guide the transcription process.

Possible values: Value must match regular expression `^(.|all)$`

**sensitivity**float

Ranges between zero and one. Higher values will produce more punctuation. The default is 0.5.

Possible values: `>= 0` and `<= 1`

**conversation\_config** object

This mode will detect when a speaker has stopped talking. The `end_of_utterance_silence_trigger` is the time in seconds after which the server will assume that the speaker has finished speaking, and will emit an `EndOfUtterance` message. A value of 0 disables the feature.

**end\_of\_utterance\_silence\_trigger**float

Possible values: `>= 0` and `<= 2`

**Default value:&#x20;**`0`

**channel\_diarization\_labels**string\[]

**translation\_config** object

Specifies various configuration values for translation. All fields except `target_languages` are optional, using default values when omitted.

**target\_languages**string\[]required

List of languages to translate to from the source transcription `language`. Specified as an [ISO Language Code](https://docs.speechmatics.com/speech-to-text/languages).

**enable\_partials**boolean

Whether or not to send Partials (i.e. `AddPartialTranslation` messages) as well as Finals (i.e. `AddTranslation` messages).

**Default value:&#x20;**`false`

**audio\_events\_config** object

Contains configuration for [Audio Events](https://docs.speechmatics.com/speech-to-text/features/audio-events)

**types**string\[]

List of [Audio Event types](https://docs.speechmatics.com/speech-to-text/features/audio-events#supported-audio-events) to enable.

### AddAudio

A binary chunk of audio. The server confirms receipt by sending an AudioAdded message.

**string**binary

### AddChannelAudio

Audio belonging to a specific channel.

**message**required

Constant value: `AddChannelAudio`

**channel**stringrequired

The channel identifier to which the audio belongs.

**data**stringrequired

The audio data in base64 format.

### EndOfStream

Declares that the client has no more audio to send.

**message**required

Constant value: `EndOfStream`

**last\_seq\_no**integerrequired

### EndOfChannel

Declares that the channel has no more audio to send.

**message**required

Constant value: `EndOfChannel`

**channel**stringrequired

The channel identifier to which the audio belongs.

**last\_seq\_no**integerrequired

### ForceEndOfUtterance

Requests a finalized transcript.

**message**required

Constant value: `ForceEndOfUtterance`

**channel**string

The channel to request finalized transcript from. This field is only seen in multichannel.

**timestamp**float

Timestamp of the audio data that corresponds to the force end of utterance request. It's the number of seconds since the beginning of the audio.

Possible values: `>= 0`

### SetRecognitionConfig

Allows the client to re-configure the recognition session.

The language field can be included in SetRecognitionConfig, but its value must match the language specified in the initial StartRecognition message. Attempting to change the language or any other transcription configuration parameter not listed below will result in an error.

**message**required

Constant value: `SetRecognitionConfig`

**transcription\_config** objectrequired

Contains configuration for this recognition session.

**language**string

Language model to process the audio input, normally specified as an ISO language code. The value must be consistent with the language code used in the API endpoint URL.

**Example:&#x20;**`en`

**max\_delay**number

This is the delay in seconds between the end of a spoken word and returning the Final transcript results. See [Latency](https://docs.speechmatics.com/speech-to-text/realtime/output#latency) for more details

Possible values: `>= 0.7` and `<= 4`

**Default value:&#x20;**`4`

**max\_delay\_mode**string

This allows some additional time for [Smart Formatting](https://docs.speechmatics.com/speech-to-text/formatting#smart-formatting).

Possible values: \[`flexible`, `fixed`]

**Default value:&#x20;**`flexible`

**audio\_filtering\_config** object

Puts a lower limit on the volume of processed audio by using the `volume_threshold` setting. See [Audio Filtering](https://docs.speechmatics.com/speech-to-text/features/audio-filtering).

**volume\_threshold**float

Possible values: `>= 0` and `<= 100`

**enable\_partials**boolean

Whether or not to send Partials (i.e. `AddPartialTranslation` messages) as well as Finals (i.e. `AddTranslation` messages) See [Partial transcripts](https://docs.speechmatics.com/speech-to-text/realtime/output#partial-transcripts).

**Default value:&#x20;**`false`

**conversation\_config** object

This mode will detect when a speaker has stopped talking. The `end_of_utterance_silence_trigger` is the time in seconds after which the server will assume that the speaker has finished speaking, and will emit an `EndOfUtterance` message. A value of 0 disables the feature.

**end\_of\_utterance\_silence\_trigger**float

Possible values: `>= 0` and `<= 2`

**Default value:&#x20;**`0`

### GetSpeakers

Requests any detected speaker identifiers to be returned.

**message**required

Constant value: `GetSpeakers`

**final**boolean

Optional. This flag controls when speaker identifiers are returned. Defaults to false if omitted. When false, multiple GetSpeakers requests can be sent during transcription, each returning the speaker identifiers generated so far. To reduce the chance of empty results, send requests after at least one TranscriptAdded message is received to make sure that the server has processed some audio. When true, speaker identifiers are returned only once at the end of the transcription, regardless of how many final: true requests are sent. Even with final: true requests, you can still send final: false requests to receive intermediate speaker identifier updates.

## Received messages

### RecognitionStarted

See example

Server response to StartRecognition, acknowledging that a recognition session has started.

**message**required

Constant value: `RecognitionStarted`

**orchestrator\_version**string

**id**string

**language\_pack\_info** object

Properties of the language pack.

**language\_description**string

Full descriptive name of the language, e.g. 'Japanese'.

**word\_delimiter**stringrequired

The character to use to separate words.

**writing\_direction**string

The direction that words in the language should be written and read in.

Possible values: \[`left-to-right`, `right-to-left`]

**itn**boolean

Whether or not ITN (inverse text normalization) is available for the language pack.

**adapted**boolean

Whether or not language model adaptation has been applied to the language pack.

**channel\_ids**string\[]

### AudioAdded

Server response to AddAudio, indicating that audio has been added successfully.

When clients send audio faster than real-time, the server may read data slower than it's sent. If binary `AddAudio` messages exceed the server's internal buffer, the server will process other WebSocket messages until buffer space is available. Clients receive `AudioAdded` responses only after binary data is read. This can fill TCP buffers, potentially causing WebSocket write failures and connection closure [with prejudice](https://websockets.spec.whatwg.org#the-closeevent-interface). Clients can monitor the WebSocket's [`bufferedAmount`](https://www.w3.org/TR/websockets#dom-websocket-bufferedamount) attribute to prevent this.

**message**required

Constant value: `AudioAdded`

**seq\_no**integerrequired

### ChannelAudioAdded

Server response to AddChannelAudio, indicating that audio has been added successfully.

**message**required

Constant value: `ChannelAudioAdded`

**seq\_no**integerrequired

**channel**stringrequired

### AddPartialTranscript

A partial transcript is a transcript that can be changed in a future `AddPartialTranscript` as more words are spoken until the `AddTranscript` **Final** message is sent for that audio.

Partials will only be sent if `transcription_config.enable_partials` is set to `true` in the `StartRecognition` message.

The message structure is the same as `AddTranscript`, with a few [limitations](https://docs.speechmatics.com/speech-to-text/realtime/output#partial-transcripts).

For `AddPartialTranscript` messages the `confidence` field for `alternatives` has no meaning and should not be relied on.

**message**required

Constant value: `AddPartialTranscript`

**format**string

Speechmatics JSON output format version number.

**Example:&#x20;**`2.1`

**metadata** objectrequired

**start\_time**floatrequired

**end\_time**floatrequired

**transcript**stringrequired

The entire transcript contained in the segment in text format. Providing the entire transcript here is designed for ease of consumption; we have taken care of all the necessary formatting required to concatenate the transcription results into a block of text. This transcript lacks the detailed information however which is contained in the `results` field of the message - such as the timings and confidences for each word.

**results** object\[]required

* Array \[

**type**stringrequired

Possible values: \[`word`, `punctuation`, `entity`]

**start\_time**floatrequired

**end\_time**floatrequired

**attaches\_to**string

Possible values: \[`next`, `previous`, `none`, `both`]

**is\_eos**boolean

**alternatives** object\[]

* Array \[

**content**stringrequired

A word or punctuation mark.

**confidence**floatrequired

A confidence score assigned to the alternative. Ranges from 0.0 (least confident) to 1.0 (most confident).

**language**string

The language that the alternative word is assumed to be spoken in. Currently, this will always be equal to the language that was requested in the initial `StartRecognition` message.

**display** object

Information about how the word/symbol should be displayed.

**direction**stringrequired

Either `ltr` for words that should be displayed left-to-right, or `rtl` vice versa.

Possible values: \[`ltr`, `rtl`]

**speaker**string

Label indicating who said that word. Only set if [diarization](https://docs.speechmatics.com/speech-to-text/features/diarization) is enabled.

**tags**string\[]

This is a set list of profanities and disfluencies respectively that cannot be altered by the end user. `[disfluency]` is only present in English, and `[profanity]` is present in English, Spanish, and Italian

Possible values: \[`disfluency`, `profanity`]

* ]

**volume**float

Possible values: `>= 0` and `<= 100`

**entity\_class**string

For 'entity' results only, the class the entity has been formatted as. Examples: 'date', 'money', 'number'

**spoken\_form** object\[]

For 'entity' results only, the spoken\_form is the transcript of the individual words directly spoken.

* Array \[

**alternatives** object\[]required

* Array \[

**content**stringrequired

A word or punctuation mark.

**confidence**floatrequired

A confidence score assigned to the alternative. Ranges from 0.0 (least confident) to 1.0 (most confident).

**language**string

The language that the alternative word is assumed to be spoken in. Currently, this will always be equal to the language that was requested in the initial `StartRecognition` message.

**display** object

Information about how the word/symbol should be displayed.

**direction**stringrequired

Either `ltr` for words that should be displayed left-to-right, or `rtl` vice versa.

Possible values: \[`ltr`, `rtl`]

**speaker**string

Label indicating who said that word. Only set if [diarization](https://docs.speechmatics.com/speech-to-text/features/diarization) is enabled.

**tags**string\[]

This is a set list of profanities and disfluencies respectively that cannot be altered by the end user. `[disfluency]` is only present in English, and `[profanity]` is present in English, Spanish, and Italian

Possible values: \[`disfluency`, `profanity`]

* ]

**end\_time**floatrequired

**start\_time**floatrequired

**type**stringrequired

Possible values: \[`word`, `punctuation`]

* ]

**written\_form** object\[]

For 'entity' results only, the written\_form is a standardized form of the spoken words. It contains the formatted entity split into individual words.

* Array \[

**alternatives** object\[]required

* Array \[

**content**stringrequired

A word or punctuation mark.

**confidence**floatrequired

A confidence score assigned to the alternative. Ranges from 0.0 (least confident) to 1.0 (most confident).

**language**string

The language that the alternative word is assumed to be spoken in. Currently, this will always be equal to the language that was requested in the initial `StartRecognition` message.

**display** object

Information about how the word/symbol should be displayed.

**direction**stringrequired

Either `ltr` for words that should be displayed left-to-right, or `rtl` vice versa.

Possible values: \[`ltr`, `rtl`]

**speaker**string

Label indicating who said that word. Only set if [diarization](https://docs.speechmatics.com/speech-to-text/features/diarization) is enabled.

**tags**string\[]

This is a set list of profanities and disfluencies respectively that cannot be altered by the end user. `[disfluency]` is only present in English, and `[profanity]` is present in English, Spanish, and Italian

Possible values: \[`disfluency`, `profanity`]

* ]

**end\_time**floatrequired

**start\_time**floatrequired

**type**stringrequired

Possible values: \[`word`]

* ]

* ]

**channel**string

The channel identifier to which the audio belongs. This field is only seen in multichannel.

### AddTranscript

Contains the final transcript of a part of the audio that the client has sent.

**message**required

Constant value: `AddTranscript`

**format**string

Speechmatics JSON output format version number.

**Example:&#x20;**`2.1`

**metadata** objectrequired

**start\_time**floatrequired

**end\_time**floatrequired

**transcript**stringrequired

The entire transcript contained in the segment in text format. Providing the entire transcript here is designed for ease of consumption; we have taken care of all the necessary formatting required to concatenate the transcription results into a block of text. This transcript lacks the detailed information however which is contained in the `results` field of the message - such as the timings and confidences for each word.

**results** object\[]required

* Array \[

**type**stringrequired

Possible values: \[`word`, `punctuation`, `entity`]

**start\_time**floatrequired

**end\_time**floatrequired

**attaches\_to**string

Possible values: \[`next`, `previous`, `none`, `both`]

**is\_eos**boolean

**alternatives** object\[]

* Array \[

**content**stringrequired

A word or punctuation mark.

**confidence**floatrequired

A confidence score assigned to the alternative. Ranges from 0.0 (least confident) to 1.0 (most confident).

**language**string

The language that the alternative word is assumed to be spoken in. Currently, this will always be equal to the language that was requested in the initial `StartRecognition` message.

**display** object

Information about how the word/symbol should be displayed.

**direction**stringrequired

Either `ltr` for words that should be displayed left-to-right, or `rtl` vice versa.

Possible values: \[`ltr`, `rtl`]

**speaker**string

Label indicating who said that word. Only set if [diarization](https://docs.speechmatics.com/speech-to-text/features/diarization) is enabled.

**tags**string\[]

This is a set list of profanities and disfluencies respectively that cannot be altered by the end user. `[disfluency]` is only present in English, and `[profanity]` is present in English, Spanish, and Italian

Possible values: \[`disfluency`, `profanity`]

* ]

**volume**float

Possible values: `>= 0` and `<= 100`

**entity\_class**string

For 'entity' results only, the class the entity has been formatted as. Examples: 'date', 'money', 'number'

**spoken\_form** object\[]

For 'entity' results only, the spoken\_form is the transcript of the individual words directly spoken.

* Array \[

**alternatives** object\[]required

* Array \[

**content**stringrequired

A word or punctuation mark.

**confidence**floatrequired

A confidence score assigned to the alternative. Ranges from 0.0 (least confident) to 1.0 (most confident).

**language**string

The language that the alternative word is assumed to be spoken in. Currently, this will always be equal to the language that was requested in the initial `StartRecognition` message.

**display** object

Information about how the word/symbol should be displayed.

**direction**stringrequired

Either `ltr` for words that should be displayed left-to-right, or `rtl` vice versa.

Possible values: \[`ltr`, `rtl`]

**speaker**string

Label indicating who said that word. Only set if [diarization](https://docs.speechmatics.com/speech-to-text/features/diarization) is enabled.

**tags**string\[]

This is a set list of profanities and disfluencies respectively that cannot be altered by the end user. `[disfluency]` is only present in English, and `[profanity]` is present in English, Spanish, and Italian

Possible values: \[`disfluency`, `profanity`]

* ]

**end\_time**floatrequired

**start\_time**floatrequired

**type**stringrequired

Possible values: \[`word`, `punctuation`]

* ]

**written\_form** object\[]

For 'entity' results only, the written\_form is a standardized form of the spoken words. It contains the formatted entity split into individual words.

* Array \[

**alternatives** object\[]required

* Array \[

**content**stringrequired

A word or punctuation mark.

**confidence**floatrequired

A confidence score assigned to the alternative. Ranges from 0.0 (least confident) to 1.0 (most confident).

**language**string

The language that the alternative word is assumed to be spoken in. Currently, this will always be equal to the language that was requested in the initial `StartRecognition` message.

**display** object

Information about how the word/symbol should be displayed.

**direction**stringrequired

Either `ltr` for words that should be displayed left-to-right, or `rtl` vice versa.

Possible values: \[`ltr`, `rtl`]

**speaker**string

Label indicating who said that word. Only set if [diarization](https://docs.speechmatics.com/speech-to-text/features/diarization) is enabled.

**tags**string\[]

This is a set list of profanities and disfluencies respectively that cannot be altered by the end user. `[disfluency]` is only present in English, and `[profanity]` is present in English, Spanish, and Italian

Possible values: \[`disfluency`, `profanity`]

* ]

**end\_time**floatrequired

**start\_time**floatrequired

**type**stringrequired

Possible values: \[`word`]

* ]

* ]

**channel**string

The channel identifier to which the audio belongs. This field is only seen in multichannel.

### AddPartialTranslation

Contains a work-in-progress translation of a part of the audio that the client has sent.

**message**required

Constant value: `AddPartialTranslation`

**format**string

Speechmatics JSON output format version number.

**Example:&#x20;**`2.1`

**language**stringrequired

Language translation relates to given as an ISO language code.

**results** object\[]required

* Array \[

**content**stringrequired

**start\_time**floatrequired

The start time (in seconds) of the original transcribed audio segment

**end\_time**floatrequired

The end time (in seconds) of the original transcribed audio segment

**speaker**string

The speaker that uttered the speech if speaker diarization is enabled

* ]

### AddTranslation

Contains the final translation of a part of the audio that the client has sent.

**message**required

Constant value: `AddTranslation`

**format**string

Speechmatics JSON output format version number.

**Example:&#x20;**`2.1`

**language**stringrequired

Language translation relates to given as an ISO language code.

**results** object\[]required

* Array \[

**content**stringrequired

**start\_time**floatrequired

The start time (in seconds) of the original transcribed audio segment

**end\_time**floatrequired

The end time (in seconds) of the original transcribed audio segment

**speaker**string

The speaker that uttered the speech if speaker diarization is enabled

* ]

### EndOfTranscript

Server response to `EndOfStream`, after the server has finished sending all AddTranscript messages.

**message**required

Constant value: `EndOfTranscript`

### AudioEventStarted

Start of an audio event detected.

**message**required

Constant value: `AudioEventStarted`

**event** objectrequired

**type**stringrequired

The type of audio event that has started or ended. See our list of [supported Audio Event types](https://docs.speechmatics.com/speech-to-text/features/audio-events#supported-audio-events).

**start\_time**floatrequired

The time (in seconds) of the audio corresponding to the beginning of the audio event.

**confidence**floatrequired

A confidence score assigned to the audio event. Ranges from 0.0 (least confident) to 1.0 (most confident).

Possible values: `>= 0` and `<= 1`

**channel**string

The channel identifier to which the audio belongs. This field is only seen in multichannel.

### AudioEventEnded

End of an audio event detected.

**message**required

Constant value: `AudioEventEnded`

**event** objectrequired

**type**stringrequired

The type of audio event that has started or ended. See our list of [supported Audio Event types](https://docs.speechmatics.com/speech-to-text/features/audio-events#supported-audio-events).

**end\_time**floatrequired

**channel**string

The channel identifier to which the audio belongs. This field is only seen in multichannel.

### EndOfUtterance

Indicates the end of an utterance, triggered by a configurable period of non-speech. The message is sent when no speech has been detected for a short period of time, configurable by the `end_of_utterance_silence_trigger` parameter in `conversation_config` (see [End Of Utterance](https://docs.speechmatics.com/speech-to-text/realtime/turn-detection#configuration)).

Like punctuation, an `EndOfUtterance` has zero duration.

**message**required

Constant value: `EndOfUtterance`

**metadata** objectrequired

**start\_time**float

The time (in seconds) that the end of utterance was detected.

**end\_time**float

The time (in seconds) that the end of utterance was detected.

**channel**string

The channel identifier to which the EndOfUtterance message belongs. This field is only seen in multichannel.

### Info

Additional information sent from the server to the client.

**message**required

Constant value: `Info`

**type**stringrequired

The following are the possible info types:

| Info Type | Description |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `recognition_quality`      | Informs the client what particular quality-based model is used to handle the recognition. Sent to the client immediately after the WebSocket handshake is completed.    |
| `concurrent_session_usage` | Informs the client of their quota for concurrent sessions and how much of it they are using. Sent to the client immediately after the WebSocket handshake is completed. |

Possible values: \[`recognition_quality`, `concurrent_session_usage`]

**reason**stringrequired

**code**integer

**seq\_no**integer

**quality**string

Only set when `type` is `recognition_quality`. Quality-based model name. It is one of "telephony", "broadcast". The model is selected automatically, for high-quality audio (12kHz+) the broadcast model is used, for lower quality audio the telephony model is used.

**usage**number

Only set when `type` is `concurrent_session_usage`. Indicates the current usage (number of active concurrent sessions).

**quota**number

Only set when `type` is `concurrent_session_usage`. Indicates the current quota (maximum number of concurrent sessions allowed).

**last\_updated**string

Only set when `type` is `concurrent_session_usage`. Indicates the timestamp of the most recent usage update, in the format `YYYY-MM-DDTHH:MM:SSZ` (UTC). This value is updated even when usage exceeds the quota, as it represents the most recent known data. In some cases, it may be empty or outdated due to internal errors preventing successful update.

**Example:&#x20;**`2025-03-25T08:45:31Z`

### Warning

Warning messages sent from the server to the client.

**message**required

Constant value: `Warning`

**type**stringrequired

The following are the possible warning types:

| Warning Type | Description |
| --- | --- |
| `duration_limit_exceeded` | The maximum allowed duration of a single utterance to process has been exceeded. Any `AddAudio` messages received that exceed this limit are confirmed with `AudioAdded`, but are ignored by the transcription engine. Exceeding the limit triggers the same mechanism as receiving an `EndOfStream` message, so the Server will eventually send an `EndOfTranscript` message and suspend. |
| `unsupported_translation_pair` | One of the requested translation target languages is unsupported (given the source audio language). The error message specifies the unsupported language pair. |
| `idle_timeout` | Informs that the session is approaching the idle duration limit (no audio data sent within the last hour), with a `reason` of the form:`Session will timeout in {time_remaining}m due to inactivity, no audio sent within the last {time_elapsed}m`Currently the server will send messages at 15, 10 and 5m prior to timeout, and will send a final error message on timeout, before closing the connection with the code 1008. (see [Realtime limits](https://docs.speechmatics.com/speech-to-text/realtime/limits) for more information). |
| `session_timeout` | Informs that the session is approaching the max session duration limit (maximum session duration of 48 hours), with a `reason` of the form:`Session will timeout in {time_remaining}m due to max duration, session has been active for {time_elapsed}m`Currently the server will send messages at 45, 30 and 15m prior to timeout, and will send a final error message on timeout, before closing the connection with the code 1008. (see [Realtime limits](https://docs.speechmatics.com/speech-to-text/realtime/limits) for more information). |
| `empty_translation_target_list` | No supported translation target languages specified. Translation will not run. |
| `add_audio_after_eos` | Protocol specification doesn't allow adding audio after `EndOfStream` has been received. Any \`AddAudio messages after this, will be ignored. |
| `speaker_id` | Informs the client about any speaker ID related issues. |

Possible values: \[`duration_limit_exceeded`, `unsupported_translation_pair`, `idle_timeout`, `session_timeout`, `empty_translation_target_list`, `add_audio_after_eos`, `speaker_id`]

**reason**stringrequired

**code**integer

**seq\_no**integer

**duration\_limit**number

Only set when `type` is `duration_limit_exceeded`. Indicates the limit that was exceeded (in seconds).

### Error

Error messages sent from the server to the client. After any error, the transcription is terminated and the connection is closed.

**message**required

Constant value: `Error`

**type**stringrequired

The following are the possible error types:

| Error Type | Description |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `invalid_message` | The message received was not understood. |
| `invalid_model` | Unable to use the model for the recognition. This can happen if the language is not supported at all, or is not available for the user. |
| `invalid_language` | The requested language is not valid or is not supported. |
| `invalid_config` | The config received contains some wrong or unsupported fields, or too many translation target languages were requested. |
| `invalid_audio_type` | Audio type is not supported, is deprecated, or the `audio_type` is malformed. |
| `invalid_output_format` | Output format is not supported, is deprecated, or the `output_format` is malformed. |
| `not_authorised` | User was not recognised, or the API key provided is not valid. |
| `not_allowed` | User is not allowed to use this message (is not allowed to perform the action the message would invoke). |
| `job_error` | Unable to do any work on this job, the server might have timed out etc. |
| `protocol_error`        | Message received was syntactically correct, but could not be accepted due to protocol limitations. This is usually caused by messages sent in the wrong order. |
| `quota_exceeded` | Maximum number of concurrent connections allowed for the contract has been reached |
| `timelimit_exceeded` | Usage quota for the contract has been reached |
| `idle_timeout` | Idle duration limit was reached (no audio data sent within the last hour), a closing handshake with code 1008 follows this in-band error. |
| `session_timeout` | Max session duration was reached (maximum session duration of 48 hours), a closing handshake with code 1008 follows this in-band error. |
| `unknown_error` | An error that did not fit any of the types above. |

`invalid_message`, `protocol_error` and `unknown_error` can be triggered as a response to any type of messages.

Possible values: \[`invalid_message`, `invalid_model`, `invalid_language`, `invalid_config`, `invalid_audio_type`, `invalid_output_format`, `not_authorised`, `not_allowed`, `job_error`, `protocol_error`, `quota_exceeded`, `timelimit_exceeded`, `idle_timeout`, `session_timeout`, `unknown_error`]

**reason**stringrequired

**code**integer

**seq\_no**integer

### SpeakersResult

Server response to GetSpeakers request returning any detected speaker identifiers.

**message**required

Constant value: `SpeakersResult`

**speakers** object\[]required

* Array \[

**label**stringrequired

Speaker label.

Possible values: `non-empty`

**speaker\_identifiers**bytes\[]required

Possible values: `>= 1`

* ]

## Websocket errors

In the Realtime SaaS, an in-band error message can be followed by a WebSocket close message. The table below shows the possible WebSocket close codes and associated error types. The error types are provided in the payload of the close message.

| WebSocket Close Code | WebSocket Close Payload |
| -------------------- | ----------------------- |
| 1003 | `protocol_error` |
| 1008 | `policy_violation` |
| 1011 | `internal_error` |
| 4001 | `not_authorised` |
| 4003 | `not_allowed` |
| 4004 | `invalid_model` |
| 4005 | `quota_exceeded` |
| 4006 | `timelimit_exceeded` |
| 4013 | `job_error` |
