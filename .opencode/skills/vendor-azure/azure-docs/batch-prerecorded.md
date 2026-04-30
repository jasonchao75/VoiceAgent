# Azure Fast / Batch Transcription (REST API) 规范

> **推荐方案**: 对于非实时的离线录音文件，Azure 提供了两种 REST API：**Fast Transcription** (快速转写，适合短音频同步返回) 和 **Batch Transcription** (批量转写，异步，适合大量或长音频)。目前官方最新的 API 版本为 `2024-11-15` 或 `2025-10-15`（旧版 v3.0 已于 2026 年初废弃）。

## 1. 核心信息与鉴权
- **Base URL**: `https://<YOUR_REGION>.api.cognitive.microsoft.com`
- **鉴权**: 
  - `Ocp-Apim-Subscription-Key: YOUR_AZURE_SPEECH_KEY` 必须放置于请求头中。

## 2. Fast Transcription (短音频同步转写)
如果你需要对一个不超过 60 秒（通常限制）的短音频进行极速转写，并且需要**同步等待返回结果**，使用此接口。

**请求 Endpoint**: `POST /speechtotext/transcriptions:transcribe?api-version=2025-10-15`

### 示例请求
```bash
curl -X POST "https://eastus.api.cognitive.microsoft.com/speechtotext/transcriptions:transcribe?api-version=2025-10-15" \
  -H "Ocp-Apim-Subscription-Key: YOUR_AZURE_SPEECH_KEY" \
  -H "Content-Type: multipart/form-data" \
  -F "audio=@/path/to/short_audio.wav" \
  -F "definition={\"locales\":[\"en-US\"]}"
```
**注意**: Azure 的快速转写必须通过 `multipart/form-data` 提供音频，并且使用 `definition` 字段指定 JSON 配置，或者直接在 URL 中使用 `?language=en-US`。

## 3. Batch Transcription (长音频异步批量转写)
如果你需要转写很长的大文件或一批量文件，使用异步 Batch 接口。Azure 不支持直接上传大文件本体进行批量任务，**必须**将音频上传到可以通过 HTTP(S) 公网访问的 Blob URL (如 Azure Blob Storage，带 SAS Token)。

**请求 Endpoint**: `POST /speechtotext/transcriptions:submit?api-version=2025-10-15` (或者使用传统的模型创建转写任务 `POST /speechtotext/v3.1/transcriptions`)

### 3.1 创建异步任务
```bash
curl -X POST "https://eastus.api.cognitive.microsoft.com/speechtotext/v3.1/transcriptions" \
  -H "Ocp-Apim-Subscription-Key: YOUR_AZURE_SPEECH_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "contentUrls": [
      "https://example.com/audio1.wav",
      "https://example.com/audio2.wav"
    ],
    "locale": "en-US",
    "displayName": "My Batch Job",
    "properties": {
      "diarizationEnabled": true,
      "wordLevelTimestampsEnabled": true,
      "punctuationMode": "DictatedAndAutomatic"
    }
  }'
```

### 3.2 轮询与获取结果
1. 创建任务后会返回一个带有 `self` 链接的 JSON，或者在 Header 返回 `Location`。
2. 发送 `GET` 请求到该 URL 获取状态，直到 `status` 变为 `Succeeded`。
3. 成功后，发送请求到 `{transcription_url}/files` 来获取包含真正转写文本 (contentUrl) 的文件列表，随后下载。

---

## 4. Reference: Official API Documentation
> **防幻觉红线**: 以下为官方原始文档备份。当上方精简版参数无法满足需求或出现争议时，请**绝对以本段下方的官方原始定义为准**。

```markdown
Use Speech to text REST API to do the following:

- Fast transcription: Transcribe audio files with returning results synchronously and much faster than real-time audio. Use the fast transcription API (/speechtotext/transcriptions:transcribe) in the scenarios that you need the transcript of an audio recording as quickly as possible with predictable latency.
- Batch transcription: Transcribe audio files as a batch from multiple URLs or an Azure container. Use the batch transcription API (/speechtotext/transcriptions:submit) in the scenarios that you need to transcribe a large amount of audio in storage, such as a large number of files or a long audio file.

Important
Speech to text REST API version 2025-10-15 is the latest version that's generally available.
Speech to text REST API v3.0, 3.2-preview.1, and 3.2-preview.2 were retired on March 31, 2026.

How does it work?
With batch transcriptions, you submit the audio data, and then retrieve transcription results asynchronously.
1. Locate audio files for batch transcription - You can upload your own data or use existing audio files via public URI or shared access signature (SAS) URI.
2. Create a batch transcription - Submit the transcription job with parameters such as the audio files, the transcription language, and the transcription model.
3. Get batch transcription results - Check transcription status and retrieve transcription results asynchronously.
```
