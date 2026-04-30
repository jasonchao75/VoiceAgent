# Soniox Async Batch API 规范

> **协议**: HTTP REST API
> **Base URL**: `https://api.soniox.com`
> **鉴权**: 请求头 `Authorization: Bearer ${SONIOX_API_KEY}`

## 1. 核心流程与鉴权

使用 Soniox 离线批量接口主要包含两种模式：
- **公共 URL 模式**: 音频通过可公开访问的 URL 提供 (`audio_url`)。
- **本地文件上传模式**: 将音频通过 API 提交到服务器存储后获取 `file_id`，再提交转写任务。

所有请求均需通过 HTTP Header `Authorization: Bearer <API_KEY>` 进行身份校验。

支持的音频格式（使用此接口时自动检测）：
`aac, aiff, amr, asf, flac, mp3, ogg, wav, webm, m4a, mp4`

---

## 2. 第一步：上传音频文件 (可选)
如果需要处理本地音频文件，首先将其上传到 Soniox 服务器，获取 `file_id`。

**上传接口 (`POST /v1/files`)**
```bash
curl -X POST "https://api.soniox.com/v1/files" \
     -H "Authorization: Bearer YOUR_SONIOX_API_KEY" \
     -F "file=@/path/to/your/audio.mp3"
```
**响应示例**:
```json
{
  "id": "file_abc123",
  "created_at": "2026-04-27T08:00:00Z"
}
```

---

## 3. 第二步：创建转写任务
将 `file_id` 或直接可访问的 `audio_url` 传入以开启异步转写任务。你还可以配置 Webhook 用于在任务完成时接收回调。

**转写接口 (`POST /v1/transcriptions`)**
```bash
curl -X POST "https://api.soniox.com/v1/transcriptions" \
     -H "Authorization: Bearer YOUR_SONIOX_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "stt-async-v4",
       "file_id": "file_abc123", 
       "language_hints": ["en", "zh"],
       "enable_language_identification": true,
       "enable_speaker_diarization": true,
       "client_reference_id": "MySystemID_001",
       "webhook_url": "https://your-domain.com/webhook",
       "webhook_auth_header_name": "X-Custom-Auth",
       "webhook_auth_header_value": "secret123"
     }'
```
> **注**: `file_id` 与 `audio_url` 互斥，只能同时提供一个。

**响应示例**:
```json
{
  "id": "txn_xyz789",
  "status": "processing"
}
```

---

## 4. 第三步：轮询状态与获取结果

**状态查询 (`GET /v1/transcriptions/{id}`)**
任务状态 (`status`) 可能为 `processing`, `completed`, `error`。

**获取详细 Token 结果 (`GET /v1/transcriptions/{id}/transcript`)**
只有在任务转为 `completed` 后才能调用。

```bash
curl "https://api.soniox.com/v1/transcriptions/txn_xyz789/transcript" \
     -H "Authorization: Bearer YOUR_SONIOX_API_KEY"
```

**响应结构 (Token 流汇总)**:
```json
{
  "tokens": [
    {
      "text": "Hello",
      "speaker": 1,
      "language": "en"
    },
    {
      "text": " ",
      "speaker": 1,
      "language": "en"
    },
    {
      "text": "world",
      "speaker": 1,
      "language": "en"
    }
  ]
}
```

---

## 5. 垃圾回收机制
为保护数据隐私并节省配额，使用完毕后必须删除记录和源文件。

- 删除转写任务: `DELETE /v1/transcriptions/{id}`
- 删除音频文件: `DELETE /v1/files/{file_id}`

---

## 6. Reference: Official API Spec
> **防幻觉红线**: 以下为官方原始 API 规范文档备份。当上方精简版参数无法满足需求或出现争议时，请**绝对以本段下方的官方原始定义为准**。

# Async transcription
URL: /stt/async/async-transcription

Learn about async transcription for audio files.

## Overview

Soniox supports **asynchronous transcription** for audio files. This allows you to
transcribe recordings without maintaining a live connection or streaming
pipeline.

You can submit audio from:

* A **public URL** (`audio_url`).
* A **local file** uploaded via the **Soniox Files API** (`file_id`).

Once submitted, jobs are processed in the background. You can poll for
status/results, or use **webhooks** to get notified when transcription is complete.

***

## Audio input options

### Transcribe from public URL

If your audio is publicly accessible via HTTP, use the `audio_url` parameter:

```json
{"audio_url": "https://example.com/audio.mp3"}
```

### Transcribe from local file

For local files, upload to Soniox using the **Files API**. Then reference the
returned `file_id` when creating the transcription request:

```json
{"file_id": "your_file_id"}
```

***

## Audio formats

Soniox automatically detects audio formats for file transcription — no configuration required.

Supported formats:

```text
aac, aiff, amr, asf, flac, mp3, ogg, wav, webm, m4a, mp4
```

***

## Tracking requests

Optionally, add a client-defined identifier to track requests:

```json
{"client_reference_id": "MyReferenceId"}
```

***

## Code examples

**Prerequisite:** Complete the steps in [Get started](/stt/get-started).

  
    
      
        See on GitHub: [soniox\_sdk\_async.py](https://github.com/soniox/soniox_examples/blob/master/speech_to_text/python_sdk/soniox_sdk_async.py).

        
          ```
          import os
          import argparse
          from typing import Optional

          from soniox import SonioxClient
          from soniox.types import (
              CreateTranscriptionConfig,
              StructuredContext,
              TranslationConfig,
              StructuredContextGeneralItem,
              StructuredContextTranslationTerm,
          )
          from soniox.utils import render_tokens

          def get_config(translation: Optional[str]) -> CreateTranscriptionConfig:
              config = CreateTranscriptionConfig(
                  # Select the model to use.
                  # See: soniox.com/docs/stt/models
                  model="stt-async-v4",
                  #
                  # Set language hints when possible to significantly improve accuracy.
                  # See: soniox.com/docs/stt/concepts/language-hints
                  language_hints=["en", "es"],
                  #
                  # Enable language identification. Each token will include a "language" field.
                  # See: soniox.com/docs/stt/concepts/language-identification
                  enable_language_identification=True,
                  #
                  # Enable speaker diarization. Each token will include a "speaker" field.
                  # See: soniox.com/docs/stt/concepts/speaker-diarization
                  enable_speaker_diarization=True,
                  #
                  # Set context to help the model understand your domain, recognize important terms,
                  # and apply custom vocabulary and translation preferences.
                  # See: soniox.com/docs/stt/concepts/context
                  context=StructuredContext(
                      general=[
                          StructuredContextGeneralItem(key="domain", value="Healthcare"),
                          StructuredContextGeneralItem(
                              key="topic", value="Diabetes management consultation"
                          ),
                          StructuredContextGeneralItem(key="doctor", value="Dr. Martha Smith"),
                          StructuredContextGeneralItem(key="patient", value="Mr. David Miller"),
                          StructuredContextGeneralItem(
                              key="organization", value="St John's Hospital"
                          ),
                      ],
                      text="Mr. David Miller visited his healthcare provider last month for a routine follow-up related to diabetes care. The clinician reviewed his recent test results, noted improved glucose levels, and adjusted his medication schedule accordingly. They also discussed meal planning strategies and scheduled the next check-up for early spring.",
                      terms=[
                          "Celebrex",
                          "Zyrtec",
                          "Xanax",
                          "Prilosec",
                          "Amoxicillin Clavulanate Potassium",
                      ],
                      translation_terms=[
                          StructuredContextTranslationTerm(
                              source="Mr. Smith", target="Sr. Smith"
                          ),
                          StructuredContextTranslationTerm(
                              source="St John's", target="St John's"
                          ),
                          StructuredContextTranslationTerm(source="stroke", target="ictus"),
                      ],
                  ),
                  #
                  # Optional identifier to track this request (client-defined).
                  # See: https://soniox.com/docs/stt/api-reference/transcriptions/create_transcription#request
                  client_reference_id="MyReferenceId",
              )

              # Webhook.
              # You can set a webhook to get notified when the transcription finishes or fails.
              # See: https://soniox.com/docs/stt/api-reference/transcriptions/create_transcription#request
              # In SDK you can set the following fields:
              # - config.webhook_url
              # - config.webhook_auth_header_name
              # - config.webhook_auth_header_value

              # Translation options.
              # See: soniox.com/docs/stt/rt/real-time-translation#translation-modes
              if translation == "none":
                  pass
              elif translation == "one_way":
                  # Translates all languages into the target language.
                  config.translation = TranslationConfig(
                      type="one_way",
                      target_language="es",
                  )
              elif translation == "two_way":
                  # Translates from language_a to language_b and back from language_b to language_a.
                  config.translation = TranslationConfig(
                      type="two_way",
                      language_a="en",
                      language_b="es",
                  )
              else:
                  raise ValueError(f"Unsupported translation: {translation}")

              return config

          def transcribe_file(
              client: SonioxClient,
              audio_url: Optional[str],
              audio_path: Optional[str],
              translation: Optional[str],
          ) -> None:
              if audio_url is not None:
                  # Public URL of the audio file to transcribe.
                  assert audio_path is None
                  file = None
              elif audio_path is not None:
                  # Local file to be uploaded to obtain file id.
                  assert audio_url is None
                  file = client.files.upload(audio_path)
              else:
                  raise ValueError("Missing audio: audio_url or audio_path must be specified.")

              config = get_config(translation)

              print("Creating transcription...")
              transcription = client.stt.create(
                  config=config, file_id=file.id if file else None, audio_url=audio_url
              )
              print("Waiting for transcription...")
              client.stt.wait(transcription.id)

              result = client.stt.get_transcript(transcription.id)

              print(render_tokens(result.tokens, []))

              client.stt.delete(transcription.id)

              if file is not None:
                  client.files.delete(file.id)

          def main():
              parser = argparse.ArgumentParser()
              parser.add_argument(
                  "--audio_url", help="Public URL of the audio file to transcribe."
              )
              parser.add_argument(
                  "--audio_path", help="Path to a local audio file to transcribe."
              )
              parser.add_argument("--delete_all_files", action="store_true")
              parser.add_argument("--delete_all_transcriptions", action="store_true")
              parser.add_argument("--translation", default="none")
              args = parser.parse_args()

              api_key = os.environ.get("SONIOX_API_KEY")
              if not api_key:
                  raise RuntimeError(
                      "Missing SONIOX_API_KEY.\n"
                      "1. Get your API key at https://console.soniox.com\n"
                      "2. Run: export SONIOX_API_KEY=<YOUR_API_KEY>"
                  )

              client = SonioxClient()

              # Delete all uploaded files.
              if args.delete_all_files:
                  print("Deleting all files...")
                  client.files.delete_all()
                  return

              # Delete all transcriptions.
              if args.delete_all_transcriptions:
                  print("Deleting all transcriptions...")
                  client.stt.delete_all()
                  return

              # If not deleting, require one audio source.
              if not (args.audio_url or args.audio_path):
                  parser.error("Provide --audio_url or --audio_path (or use a delete flag).")

              transcribe_file(client, args.audio_url, args.audio_path, args.translation)

          if __name__ == "__main__":
              main()

          ```
        
      

      
        ```sh title="Terminal"
        # Transcribe file from URL
        python soniox_sdk_async.py --audio_url "https://soniox.com/media/examples/coffee_shop.mp3"

        # Transcribe from local file
        python soniox_sdk_async.py --audio_path ../assets/coffee_shop.mp3

        # Delete all uploaded files
        python soniox_sdk_async.py --delete_all_files

        # Delete all transcriptions
        python soniox_sdk_async.py --delete_all_transcriptions
        ```
      
    
  

  
    
      
        See on GitHub: [soniox\_sdk\_async.js](https://github.com/soniox/soniox_examples/blob/master/speech_to_text/nodejs_sdk/soniox_sdk_async.js).

        
          ```
          import { SonioxNodeClient } from "@soniox/node";
          import fs from "fs";
          import { parseArgs } from "node:util";
          import process from "process";

          // Initialize the client.
          // The API key is read from the SONIOX_API_KEY environment variable.
          const client = new SonioxNodeClient();

          // Convert transcript into a readable output.
          function renderTranscript(transcript) {
            return transcript
              .segments()
              .map((s) => {
                const speaker = s.speaker ? `Speaker ${s.speaker}` : "";
                const isTranslation = s.tokens[0]?.translation_status === "translation";
                const lang = isTranslation
                  ? `[Translation][${s.language}]`
                  : `[${s.language}]`;
                return `${speaker} ${lang}: ${s.text.trim()}`;
              })
              .join("\n");
          }

          // Build transcription options.
          function getTranscriptionOptions(audioUrl, audioPath, translation) {
            if (!audioUrl && !audioPath) {
              throw new Error(
                "Missing audio: audio_url or audio_path must be specified.",
              );
            }

            const options = {
              // Select the model to use.
              // See: soniox.com/docs/stt/models
              model: "stt-async-v4",

              // Set language hints when possible to significantly improve accuracy.
              // See: soniox.com/docs/stt/concepts/language-hints
              language_hints: ["en", "es"],

              // Enable language identification. Each token will include a "language" field.
              // See: soniox.com/docs/stt/concepts/language-identification
              enable_language_identification: true,

              // Enable speaker diarization. Each token will include a "speaker" field.
              // See: soniox.com/docs/stt/concepts/speaker-diarization
              enable_speaker_diarization: true,

              // Set context to help the model understand your domain, recognize important terms,
              // and apply custom vocabulary and translation preferences.
              // See: soniox.com/docs/stt/concepts/context
              context: {
                general: [
                  { key: "domain", value: "Healthcare" },
                  { key: "topic", value: "Diabetes management consultation" },
                  { key: "doctor", value: "Dr. Martha Smith" },
                  { key: "patient", value: "Mr. David Miller" },
                  { key: "organization", value: "St John's Hospital" },
                ],
                text: "Mr. David Miller visited his healthcare provider last month for a routine follow-up related to diabetes care. The clinician reviewed his recent test results, noted improved glucose levels, and adjusted his medication schedule accordingly. They also discussed meal planning strategies and scheduled the next check-up for early spring.",
                terms: [
                  "Celebrex",
                  "Zyrtec",
                  "Xanax",
                  "Prilosec",
                  "Amoxicillin Clavulanate Potassium",
                ],
                translation_terms: [
                  { source: "Mr. Smith", target: "Sr. Smith" },
                  { source: "St John's", target: "St John's" },
                  { source: "stroke", target: "ictus" },
                ],
              },

              // Optional identifier to track this request (client-defined).
              client_reference_id: "MyReferenceId",

              // Wait for transcription to complete and fetch the transcript.
              wait: true,

              // Automatically clean up the file and transcription after we're done.
              cleanup: ["file", "transcription"],
            };

            // Audio source: either a local file or a public URL.
            if (audioPath) {
              options.file = fs.readFileSync(audioPath);
              options.filename = audioPath;
            } else {
              options.audio_url = audioUrl;
            }

            // Translation options.
            // See: soniox.com/docs/stt/rt/real-time-translation#translation-modes
            if (translation === "one_way") {
              options.translation = { type: "one_way", target_language: "es" };
            } else if (translation === "two_way") {
              options.translation = {
                type: "two_way",
                language_a: "en",
                language_b: "es",
              };
            } else if (translation !== "none") {
              throw new Error(`Unsupported translation: ${translation}`);
            }

            return options;
          }

          async function transcribeFile(audioUrl, audioPath, translation) {
            console.log("Starting transcription...");
            const transcription = await client.stt.transcribe(
              getTranscriptionOptions(audioUrl, audioPath, translation),
            );
            console.log(renderTranscript(transcription.transcript));
          }

          async function deleteAllFiles() {
            const { deleted } = await client.files.delete_all();
            console.log(
              deleted === 0 ? "No files to delete." : `Deleted ${deleted} files.`,
            );
          }

          async function deleteAllTranscriptions() {
            const { deleted } = await client.stt.delete_all();
            console.log(
              deleted === 0
                ? "No transcriptions to delete."
                : `Deleted ${deleted} transcriptions.`,
            );
          }

          async function main() {
            const { values: argv } = parseArgs({
              options: {
                audio_url: {
                  type: "string",
                  description: "Public URL of the audio file to transcribe",
                },
                audio_path: {
                  type: "string",
                  description: "Path to a local audio file to transcribe",
                },
                delete_all_files: {
                  type: "boolean",
                  description: "Delete all uploaded files",
                },
                delete_all_transcriptions: {
                  type: "boolean",
                  description: "Delete all transcriptions",
                },
                translation: { type: "string", default: "none" },
              },
            });

            if (argv.delete_all_files) {
              await deleteAllFiles();
              return;
            }

            if (argv.delete_all_transcriptions) {
              await deleteAllTranscriptions();
              return;
            }

            await transcribeFile(argv.audio_url, argv.audio_path, argv.translation);
          }

          main().catch((err) => {
            console.error("Error:", err.message);
            process.exit(1);
          });

          ```
        
      

      
        ```sh title="Terminal"
        # Transcribe file from URL
        node soniox_sdk_async.js --audio_url "https://soniox.com/media/examples/coffee_shop.mp3"

        # Transcribe from local file
        node soniox_sdk_async.js --audio_path ../assets/coffee_shop.mp3

        # Delete all uploaded files
        node soniox_sdk_async.js --delete_all_files

        # Delete all transcriptions
        node soniox_sdk_async.js --delete_all_transcriptions
        ```
      
    
  

  
    
      
        See on GitHub: [soniox\_async.py](https://github.com/soniox/soniox_examples/blob/master/speech_to_text/python/soniox_async.py).

        
          ```
          import os
          import time
          import argparse
          from typing import Optional
          import requests
          from requests import Session

          SONIOX_API_BASE_URL = "https://api.soniox.com"

          # Get Soniox STT config.
          def get_config(
              audio_url: Optional[str], file_id: Optional[str], translation: Optional[str]
          ) -> dict:
              config = {
                  # Select the model to use.
                  # See: soniox.com/docs/stt/models
                  "model": "stt-async-v4",
                  #
                  # Set language hints when possible to significantly improve accuracy.
                  # See: soniox.com/docs/stt/concepts/language-hints
                  "language_hints": ["en", "es"],
                  #
                  # Enable language identification. Each token will include a "language" field.
                  # See: soniox.com/docs/stt/concepts/language-identification
                  "enable_language_identification": True,
                  #
                  # Enable speaker diarization. Each token will include a "speaker" field.
                  # See: soniox.com/docs/stt/concepts/speaker-diarization
                  "enable_speaker_diarization": True,
                  #
                  # Set context to help the model understand your domain, recognize important terms,
                  # and apply custom vocabulary and translation preferences.
                  # See: soniox.com/docs/stt/concepts/context
                  "context": {
                      "general": [
                          {"key": "domain", "value": "Healthcare"},
                          {"key": "topic", "value": "Diabetes management consultation"},
                          {"key": "doctor", "value": "Dr. Martha Smith"},
                          {"key": "patient", "value": "Mr. David Miller"},
                          {"key": "organization", "value": "St John's Hospital"},
                      ],
                      "text": "Mr. David Miller visited his healthcare provider last month for a routine follow-up related to diabetes care. The clinician reviewed his recent test results, noted improved glucose levels, and adjusted his medication schedule accordingly. They also discussed meal planning strategies and scheduled the next check-up for early spring.",
                      "terms": [
                          "Celebrex",
                          "Zyrtec",
                          "Xanax",
                          "Prilosec",
                          "Amoxicillin Clavulanate Potassium",
                      ],
                      "translation_terms": [
                          {"source": "Mr. Smith", "target": "Sr. Smith"},
                          {"source": "St John's", "target": "St John's"},
                          {"source": "stroke", "target": "ictus"},
                      ],
                  },
                  #
                  # Optional identifier to track this request (client-defined).
                  # See: https://soniox.com/docs/stt/api-reference/transcriptions/create_transcription#request
                  "client_reference_id": "MyReferenceId",
                  #
                  # Audio source (only one can specified):
                  # - Public URL of the audio file.
                  # - File ID of a previously uploaded file
                  # See: https://soniox.com/docs/stt/api-reference/transcriptions/create_transcription#request
                  "audio_url": audio_url,
                  "file_id": file_id,
              }

              # Webhook.
              # You can set a webhook to get notified when the transcription finishes or fails.
              # See: https://soniox.com/docs/stt/api-reference/transcriptions/create_transcription#request

              # Translation options.
              # See: soniox.com/docs/stt/rt/real-time-translation#translation-modes
              if translation == "none":
                  pass
              elif translation == "one_way":
                  # Translates all languages into the target language.
                  config["translation"] = {
                      "type": "one_way",
                      "target_language": "es",
                  }
              elif translation == "two_way":
                  # Translates from language_a to language_b and back from language_b to language_a.
                  config["translation"] = {
                      "type": "two_way",
                      "language_a": "en",
                      "language_b": "es",
                  }
              else:
                  raise ValueError(f"Unsupported translation: {translation}")

              return config

          def upload_audio(session: Session, audio_path: str) -> str:
              print("Starting file upload...")
              res = session.post(
                  f"{SONIOX_API_BASE_URL}/v1/files",
                  files={"file": open(audio_path, "rb")},
              )
              file_id = res.json()["id"]
              print(f"File ID: {file_id}")
              return file_id

          def create_transcription(session: Session, config: dict) -> str:
              print("Creating transcription...")
              try:
                  res = session.post(
                      f"{SONIOX_API_BASE_URL}/v1/transcriptions",
                      json=config,
                  )
                  res.raise_for_status()
                  transcription_id = res.json()["id"]
                  print(f"Transcription ID: {transcription_id}")
                  return transcription_id
              except Exception as e:
                  print("error here:", e)

          def wait_until_completed(session: Session, transcription_id: str) -> None:
              print("Waiting for transcription...")
              while True:
                  res = session.get(f"{SONIOX_API_BASE_URL}/v1/transcriptions/{transcription_id}")
                  res.raise_for_status()
                  data = res.json()
                  if data["status"] == "completed":
                      return
                  elif data["status"] == "error":
                      raise Exception(f"Error: {data.get('error_message', 'Unknown error')}")
                  time.sleep(1)

          def get_transcription(session: Session, transcription_id: str) -> dict:
              res = session.get(
                  f"{SONIOX_API_BASE_URL}/v1/transcriptions/{transcription_id}/transcript"
              )
              res.raise_for_status()
              return res.json()

          def delete_transcription(session: Session, transcription_id: str) -> dict:
              res = session.delete(f"{SONIOX_API_BASE_URL}/v1/transcriptions/{transcription_id}")
              res.raise_for_status()

          def delete_file(session: Session, file_id: str) -> dict:
              res = session.delete(f"{SONIOX_API_BASE_URL}/v1/files/{file_id}")
              res.raise_for_status()

          def delete_all_files(session: Session) -> None:
              files: list[dict] = []
              cursor: str = ""

              while True:
                  print("Getting files...")
                  res = session.get(f"{SONIOX_API_BASE_URL}/v1/files?cursor={cursor}")
                  res.raise_for_status()
                  res_json = res.json()
                  files.extend(res_json["files"])
                  cursor = res_json["next_page_cursor"]
                  if cursor is None:
                      break

              total = len(files)
              if total == 0:
                  print("No files to delete.")
                  return

              print(f"Deleting {total} files...")
              for idx, file in enumerate(files):
                  file_id = file["id"]
                  print(f"Deleting file: {file_id} ({idx + 1}/{total})")
                  delete_file(session, file_id)

          def delete_all_transcriptions(session: Session) -> None:
              transcriptions: list[dict] = []
              cursor: str = ""

              while True:
                  print("Getting transcriptions...")
                  res = session.get(f"{SONIOX_API_BASE_URL}/v1/transcriptions?cursor={cursor}")
                  res.raise_for_status()
                  res_json = res.json()
                  for transcription in res_json["transcriptions"]:
                      status = transcription["status"]
                      # Delete only transcriptions with completed or error status.
                      if status in ("completed", "error"):
                          transcriptions.append(transcription)
                  cursor = res_json["next_page_cursor"]
                  if cursor is None:
                      break

              total = len(transcriptions)
              if total == 0:
                  print("No transcriptions to delete.")
                  return

              print(f"Deleting {total} transcriptions...")
              for idx, transcription in enumerate(transcriptions):
                  transcription_id = transcription["id"]
                  print(f"Deleting transcription: {transcription_id} ({idx + 1}/{total})")
                  delete_transcription(session, transcription_id)

          # Convert tokens into a readable transcript.
          def render_tokens(final_tokens: list[dict]) -> str:
              text_parts: list[str] = []
              current_speaker: Optional[str] = None
              current_language: Optional[str] = None

              # Process all tokens in order.
              for token in final_tokens:
                  text = token["text"]
                  speaker = token.get("speaker")
                  language = token.get("language")
                  is_translation = token.get("translation_status") == "translation"

                  # Speaker changed -> add a speaker tag.
                  if speaker is not None and speaker != current_speaker:
                      if current_speaker is not None:
                          text_parts.append("\n\n")
                      current_speaker = speaker
                      current_language = None  # Reset language on speaker changes.
                      text_parts.append(f"Speaker {current_speaker}:")

                  # Language changed -> add a language or translation tag.
                  if language is not None and language != current_language:
                      current_language = language
                      prefix = "[Translation] " if is_translation else ""
                      text_parts.append(f"\n{prefix}[{current_language}] ")
                      text = text.lstrip()

                  text_parts.append(text)

              return "".join(text_parts)

          def transcribe_file(
              session: Session,
              audio_url: Optional[str],
              audio_path: Optional[str],
              translation: Optional[str],
          ) -> None:
              if audio_url is not None:
                  # Public URL of the audio file to transcribe.
                  assert audio_path is None
                  file_id = None
              elif audio_path is not None:
                  # Local file to be uploaded to obtain file id.
                  assert audio_url is None
                  file_id = upload_audio(session, audio_path)
              else:
                  raise ValueError("Missing audio: audio_url or audio_path must be specified.")

              config = get_config(audio_url, file_id, translation)

              transcription_id = create_transcription(session, config)

              wait_until_completed(session, transcription_id)

              result = get_transcription(session, transcription_id)

              text = render_tokens(result["tokens"])
              print(text)

              delete_transcription(session, transcription_id)

              if file_id is not None:
                  delete_file(session, file_id)

          def main():
              parser = argparse.ArgumentParser()
              parser.add_argument(
                  "--audio_url", help="Public URL of the audio file to transcribe."
              )
              parser.add_argument(
                  "--audio_path", help="Path to a local audio file to transcribe."
              )
              parser.add_argument("--delete_all_files", action="store_true")
              parser.add_argument("--delete_all_transcriptions", action="store_true")
              parser.add_argument("--translation", default="none")
              args = parser.parse_args()

              api_key = os.environ.get("SONIOX_API_KEY")
              if not api_key:
                  raise RuntimeError(
                      "Missing SONIOX_API_KEY.\n"
                      "1. Get your API key at https://console.soniox.com\n"
                      "2. Run: export SONIOX_API_KEY=<YOUR_API_KEY>"
                  )

              # Create an authenticated session.
              session = requests.Session()
              session.headers["Authorization"] = f"Bearer {api_key}"

              # Delete all uploaded files.
              if args.delete_all_files:
                  delete_all_files(session)
                  return

              # Delete all transcriptions.
              if args.delete_all_transcriptions:
                  delete_all_transcriptions(session)
                  return

              # If not deleting, require one audio source.
              if not (args.audio_url or args.audio_path):
                  parser.error("Provide --audio_url or --audio_path (or use a delete flag).")

              transcribe_file(session, args.audio_url, args.audio_path, args.translation)

          if __name__ == "__main__":
              main()

          ```
        
      

      
        ```sh title="Terminal"
        # Transcribe file from URL
        python soniox_async.py --audio_url "https://soniox.com/media/examples/coffee_shop.mp3"

        # Transcribe from local file
        python soniox_async.py --audio_path ../assets/coffee_shop.mp3

        # Delete all uploaded files
        python soniox_async.py --delete_all_files

        # Delete all transcriptions
        python soniox_async.py --delete_all_transcriptions
        ```
      
    
  

  
    
      
        See on GitHub: [soniox\_async.js](https://github.com/soniox/soniox_examples/blob/master/speech_to_text/nodejs/soniox_async.js).

        
          ```
          import fs from "fs";
          import { parseArgs } from "node:util";
          import process from "process";

          const SONIOX_API_BASE_URL = "https://api.soniox.com";

          // Get Soniox STT config.
          function getConfig(audioUrl, fileId, translation) {
            const config = {
              // Select the model to use.
              // See: soniox.com/docs/stt/models
              model: "stt-async-v4",

              // Set language hints when possible to significantly improve accuracy.
              // See: soniox.com/docs/stt/concepts/language-hints
              language_hints: ["en", "es"],

              // Enable language identification. Each token will include a "language" field.
              // See: soniox.com/docs/stt/concepts/language-identification
              enable_language_identification: true,

              // Enable speaker diarization. Each token will include a "speaker" field.
              // See: soniox.com/docs/stt/concepts/speaker-diarization
              enable_speaker_diarization: true,

              // Set context to help the model understand your domain, recognize important terms,
              // and apply custom vocabulary and translation preferences.
              // See: soniox.com/docs/stt/concepts/context
              context: {
                general: [
                  { key: "domain", value: "Healthcare" },
                  { key: "topic", value: "Diabetes management consultation" },
                  { key: "doctor", value: "Dr. Martha Smith" },
                  { key: "patient", value: "Mr. David Miller" },
                  { key: "organization", value: "St John's Hospital" },
                ],
                text: "Mr. David Miller visited his healthcare provider last month for a routine follow-up related to diabetes care. The clinician reviewed his recent test results, noted improved glucose levels, and adjusted his medication schedule accordingly. They also discussed meal planning strategies and scheduled the next check-up for early spring.",
                terms: [
                  "Celebrex",
                  "Zyrtec",
                  "Xanax",
                  "Prilosec",
                  "Amoxicillin Clavulanate Potassium",
                ],
                translation_terms: [
                  { source: "Mr. Smith", target: "Sr. Smith" },
                  { source: "St John's", target: "St John's" },
                  { source: "stroke", target: "ictus" },
                ],
              },

              // Optional identifier to track this request (client-defined).
              // See: https://soniox.com/docs/stt/api-reference/transcriptions/create_transcription#request
              client_reference_id: "MyReferenceId",

              // Audio source (only one can specified):
              // - Public URL of the audio file.
              // - File ID of a previously uploaded file
              // See: https://soniox.com/docs/stt/api-reference/transcriptions/create_transcription#request
              audio_url: audioUrl,
              file_id: fileId,
            };

            // Webhook.
            // You can set a webhook to get notified when the transcription finishes or fails.
            // See: https://soniox.com/docs/stt/api-reference/transcriptions/create_transcription#request

            // Translation options.
            // See: soniox.com/docs/stt/rt/real-time-translation#translation-modes
            if (translation === "one_way") {
              // Translates all languages into the target language.
              config.translation = { type: "one_way", target_language: "es" };
            } else if (translation === "two_way") {
              // Translates from language_a to language_b and back from language_b to language_a.
              config.translation = {
                type: "two_way",
                language_a: "en",
                language_b: "es",
              };
            } else if (translation !== "none") {
              throw new Error(`Unsupported translation: ${translation}`);
            }

            return config;
          }

          // Adds Soniox API_KEY to each request.
          async function apiFetch(endpoint, { method = "GET", body, headers = {} } = {}) {
            const apiKey = process.env.SONIOX_API_KEY;
            if (!apiKey) {
              throw new Error(
                "Missing SONIOX_API_KEY.\n" +
                  "1. Get your API key at https://console.soniox.com\n" +
                  "2. Run: export SONIOX_API_KEY=<YOUR_API_KEY>",
              );
            }

            const res = await fetch(`${SONIOX_API_BASE_URL}${endpoint}`, {
              method,
              headers: {
                Authorization: `Bearer ${apiKey}`,
                ...headers,
              },
              body,
            });

            if (!res.ok) {
              const msg = await res.text();
              console.log(msg);
              throw new Error(`HTTP ${res.status} ${res.statusText}: ${msg}`);
            }

            return method !== "DELETE" ? res.json() : null;
          }

          async function uploadAudio(audioPath) {
            console.log("Starting file upload...");

            const form = new FormData();
            form.append("file", new Blob([fs.readFileSync(audioPath)]), audioPath);

            const res = await apiFetch("/v1/files", {
              method: "POST",
              body: form,
            });

            console.log(`File ID: ${res.id}`);
            return res.id;
          }

          async function createTranscription(config) {
            console.log("Creating transcription...");
            const res = await apiFetch("/v1/transcriptions", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(config),
            });
            console.log(`Transcription ID: ${res.id}`);
            return res.id;
          }

          async function waitUntilCompleted(transcriptionId) {
            console.log("Waiting for transcription...");
            while (true) {
              const res = await apiFetch(`/v1/transcriptions/${transcriptionId}`);
              if (res.status === "completed") return;
              if (res.status === "error") throw new Error(`Error: ${res.error_message}`);
              await new Promise((r) => setTimeout(r, 1000));
            }
          }

          async function getTranscription(transcriptionId) {
            return apiFetch(`/v1/transcriptions/${transcriptionId}/transcript`);
          }

          async function deleteTranscription(transcriptionId) {
            await apiFetch(`/v1/transcriptions/${transcriptionId}`, { method: "DELETE" });
          }

          async function deleteFile(fileId) {
            await apiFetch(`/v1/files/${fileId}`, { method: "DELETE" });
          }

          async function deleteAllFiles() {
            let files = [];
            let cursor = "";

            while (true) {
              const res = await apiFetch(`/v1/files?cursor=${cursor}`);
              files = files.concat(res.files);
              cursor = res.next_page_cursor;
              if (!cursor) break;
            }

            if (files.length === 0) {
              console.log("No files to delete.");
              return;
            }

            console.log(`Deleting ${files.length} files...`);
            for (let i = 0; i < files.length; i++) {
              console.log(`Deleting file: ${files[i].id} (${i + 1}/${files.length})`);
              await deleteFile(files[i].id);
            }
          }

          async function deleteAllTranscriptions() {
            let transcriptions = [];
            let cursor = "";

            while (true) {
              const res = await apiFetch(`/v1/transcriptions?cursor=${cursor}`);
              // Delete only transcriptions with completed or error status.
              transcriptions = transcriptions.concat(
                res.transcriptions.filter(
                  (t) => t.status === "completed" || t.status === "error",
                ),
              );
              cursor = res.next_page_cursor;
              if (!cursor) break;
            }

            if (transcriptions.length === 0) {
              console.log("No transcriptions to delete.");
              return;
            }

            console.log(`Deleting ${transcriptions.length} transcriptions...`);
            for (let i = 0; i < transcriptions.length; i++) {
              console.log(
                `Deleting transcription: ${transcriptions[i].id} (${i + 1}/${transcriptions.length})`,
              );
              await deleteTranscription(transcriptions[i].id);
            }
          }

          // Convert tokens into a readable transcript.
          function renderTokens(finalTokens) {
            const textParts = [];
            let currentSpeaker = null;
            let currentLanguage = null;

            // Process all tokens in order.
            for (const token of finalTokens) {
              let { text, speaker, language } = token;
              const isTranslation = token.translation_status === "translation";

              // Speaker changed -> add a speaker tag.
              if (speaker !== undefined && speaker !== currentSpeaker) {
                if (currentSpeaker !== null) textParts.push("\n\n");
                currentSpeaker = speaker;
                currentLanguage = null; // Reset language on speaker changes.
                textParts.push(`Speaker ${currentSpeaker}:`);
              }

              // Language changed -> add a language or translation tag.
              if (language !== undefined && language !== currentLanguage) {
                currentLanguage = language;
                const prefix = isTranslation ? "[Translation] " : "";
                textParts.push(`\n${prefix}[${currentLanguage}] `);
                text = text.trimStart();
              }

              textParts.push(text);
            }
            return textParts.join("");
          }

          async function transcribeFile(audioUrl, audioPath, translation) {
            let fileId = null;

            if (!audioUrl && !audioPath) {
              throw new Error(
                "Missing audio: audio_url or audio_path must be specified.",
              );
            }
            if (audioPath) {
              fileId = await uploadAudio(audioPath);
            }

            const config = getConfig(audioUrl, fileId, translation);
            const transcriptionId = await createTranscription(config);
            await waitUntilCompleted(transcriptionId);

            const result = await getTranscription(transcriptionId);
            const text = renderTokens(result.tokens);
            console.log(text);

            await deleteTranscription(transcriptionId);
            if (fileId) await deleteFile(fileId);
          }

          async function main() {
            const { values: argv } = parseArgs({
              options: {
                audio_url: {
                  type: "string",
                  description: "Public URL of the audio file to transcribe",
                },
                audio_path: {
                  type: "string",
                  description: "Path to a local audio file to transcribe",
                },
                delete_all_files: {
                  type: "boolean",
                  description: "Delete all uploaded files",
                },
                delete_all_transcriptions: {
                  type: "boolean",
                  description: "Delete all transcriptions",
                },
                translation: { type: "string", default: "none" },
              },
            });

            if (argv.delete_all_files) {
              await deleteAllFiles();
              return;
            }

            if (argv.delete_all_transcriptions) {
              await deleteAllTranscriptions();
              return;
            }

            await transcribeFile(argv.audio_url, argv.audio_path, argv.translation);
          }

          main().catch((err) => {
            console.error("Error:", err.message);
            process.exit(1);
          });

          ```
        
      

      
        ```sh title="Terminal"
        # Transcribe file from URL
        node soniox_async.js --audio_url "https://soniox.com/media/examples/coffee_shop.mp3"

        # Transcribe from local file
        node soniox_async.js --audio_path ../assets/coffee_shop.mp3

        # Delete all uploaded files
        node soniox_async.js --delete_all_files

        # Delete all transcriptions
        node soniox_async.js --delete_all_transcriptions
        ```
      
    
  

