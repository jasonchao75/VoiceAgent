# Speechmatics Batch (Pre-Recorded) API

## 1. 核心信息
- **接口协议**: HTTP REST (`https://asr.api.speechmatics.com/v2/jobs/`)
- **鉴权方式**: Header 中携带 `Authorization: Bearer YOUR_API_KEY`
- **基础流程**:
  1. 上传音频并提交配置，创建一个 Job (POST `/v2/jobs/`)。
  2. 轮询获取 Job 状态，直到变为 `done` (GET `/v2/jobs/{job_id}`)。
  3. 下载转写结果 (GET `/v2/jobs/{job_id}/transcript?format=json-v2`)。

## 2. 关键请求流程

### 2.1 创建 Job
`POST /v2/jobs/`
Content-Type 必须是 `multipart/form-data`。

需要提供两个部分 (parts):
1. `data_file`: 音频文件（如果在 config 中使用了 `fetch_data` 提供了音频 URL，则可以省略此字段）。
2. `config`: JSON 格式的配置项，包含各种转写与拓展能力的配置。

#### 请求示例：上传本地文件
```bash
curl -X POST https://asr.api.speechmatics.com/v2/jobs/ \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F data_file=@/path/to/your/audio.wav \
  -F config='{
    "type": "transcription",
    "transcription_config": {
      "language": "zh",
      "operating_point": "standard",
      "diarization": "speaker"
    }
  }'
```

#### 请求示例：提供音频外网 URL
```bash
curl -X POST https://asr.api.speechmatics.com/v2/jobs/ \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: multipart/form-data" \
  -F config='{
    "type": "transcription",
    "fetch_data": {
      "url": "https://example.com/audio.wav"
    },
    "transcription_config": {
      "language": "en"
    },
    "translation_config": {
      "target_languages": ["zh"]
    },
    "summarization_config": {
      "content_type": "informative",
      "summary_length": "brief",
      "summary_type": "bullets"
    }
  }'
```

#### `config` 核心参数详情：
- **`type`**: 必填。固定为 `"transcription"` 或 `"alignment"`。
- **`transcription_config`**: 核心转写配置（与 Realtime 大部分通用）。
  - `language`: 必填。ISO 语言代码（如 "en", "zh"）。
  - `operating_point`: 模型选择，`standard` 或 `enhanced`（增强版识别率更高但稍慢）。
  - `diarization`: 说话人分离 (`none`, `speaker`, `channel`)。
  - `domain`: 领域模型（如 `finance`, `medical`）。
  - `additional_vocab`: 自定义词典热词，提升专有名词准确率。
  - `enable_entities`: 是否格式化数字、日期、货币等实体。
  - `punctuation_overrides`: 自定义标点符号偏好。
- **拓展能力配置 (Batch 专属)**:
  - **`translation_config`**: 翻译配置。`target_languages` 为目标语言代码数组。
  - **`summarization_config`**: 摘要配置。可指定 `content_type` (如 `conversational`, `informative`), `summary_length` (`brief`, `detailed`), 和 `summary_type` (`bullets`, `paragraphs`)。
  - **`sentiment_analysis_config`**: 情感分析（无内部参数，传 `{}` 开启），可为每个句子生成情感评分。
  - **`topic_detection_config`**: 话题检测（无内部参数，传 `{}` 开启）。
  - **`auto_chapters_config`**: 自动分段/章节划分（无内部参数，传 `{}` 开启）。
- **流程控制配置**:
  - **`fetch_data`**: 直接提供音频文件的外网 URL，服务端会自动下载处理，无需上传 `data_file`。
  - **`notification_config`**: 任务完成后的 Webhook 回调地址配置。可以指定 Webhook 需要附带的内容 (`jobinfo`, `transcript` 等)。
  - **`output_config`**: 对输出结果进行微调，比如配置 SRT 字幕格式的单行字符数等 (`srt_overrides`)。

### 2.2 轮询 Job 状态
`GET /v2/jobs/{job_id}`
持续请求直到响应中的 `job.status` 变为 `done` (成功) 或 `rejected`/`error` (失败)。

### 2.3 获取结果
`GET /v2/jobs/{job_id}/transcript?format=json-v2` (或 txt, srt)。

## 3. 常见问题
- Batch API 支持几乎所有常见音频格式（wav, mp3, mp4等），无需像 Realtime 那样严格指定 `audio_format` 的裸流参数，因为可以自行解码。
- `config` 表单字段的值必须是合法的 JSON 字符串。

---

## 4. Reference: Official API Spec
> **防幻觉红线**: 以下为官方原始 API 规范文档备份。当上方精简版参数无法满足需求或出现争议时，请**绝对以本段下方的官方原始定义为准**。

# Create a new job

```
POST 
/jobs
```

Create a new job

## Request

## Responses

* 201
* 400
* 401
* 403
* 410
* 429
* 500

OK

Bad request

Unauthorized

Forbidden

Gone

Rate Limited

Internal Server Error

# Get job details

```
GET 
/jobs/:jobid
```

Get job details, including progress and any error reports.

## Request

## Responses

* 200
* 401
* 404
* 410
* 429
* 500

OK

Unauthorized

Not found

Gone

Rate Limited

Internal Server Error

# Get the transcript for a transcription job

```
GET 
/jobs/:jobid/transcript
```

Get the transcript for a transcription job

## Request

## Responses

* 200
* 401
* 404
* 410
* 429
* 500

OK

Unauthorized

Not found

Gone

Rate Limited

Internal Server Error
