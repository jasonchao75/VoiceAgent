# Qwen3-ASR-Flash-Filetrans 离线长音频转写 (Async Batch) 规范

> **协议**: HTTP REST (DashScope 异步任务 API)
> **Base URL (北京地域)**: `https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription`

## 1. 核心流程与鉴权

千问3-ASR 针对长音频文件的离线转写采用**“提交-轮询”**的两步式异步调用流程。
- **提交请求 Header**: 
  - `Authorization: Bearer $DASHSCOPE_API_KEY`
  - `X-DashScope-Async: enable` (必须包含此 Header 开启异步)

## 2. 第一步：提交任务 (Submit Task)

**请求 Endpoint**: `POST /api/v1/services/audio/asr/transcription`

### 请求示例
```bash
curl -X POST 'https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription' \
-H "Authorization: Bearer $DASHSCOPE_API_KEY" \
-H "Content-Type: application/json" \
-H "X-DashScope-Async: enable" \
-d '{
    "model": "qwen3-asr-flash-filetrans",
    "input": {
        "file_url": "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3"
    },
    "parameters": {
        "channel_id": [0],
        "enable_itn": false,
        "enable_words": true,
        "language": "zh"
    }
}'
```

### 核心参数详解
- **`model`**: 必须为 `qwen3-asr-flash-filetrans`。
- **`input.file_url`**: 音频文件 URL。必须为公网可访问的地址。（生产环境建议使用阿里云 OSS，切勿使用临时有效期的 OSS 凭证）。
- **`parameters`**:
  - `language` (可选): 指定语种，如 `zh`, `en`。若不确定则留空。
  - `enable_itn` (可选): 逆文本标准化，默认 `false`。
  - `enable_words` (可选): 默认 `false`。若设为 `true`，将返回**字级别时间戳**，且断句规则将从“纯 VAD 断句”变为“VAD + 标点符号断句”。字级时间戳仅支持中、英、日、韩等部分主流语种。
  - `channel_id` (可选): 指定要识别的音轨索引，默认 `[0]`。例如 `[0, 1]` 表示同时识别两个音轨（**注意：多音轨将独立产生计费**）。

### 提交响应
成功时返回：
```json
{
  "request_id": "...",
  "output": {
    "task_id": "YOUR_TASK_ID",
    "task_status": "PENDING"
  }
}
```

## 3. 第二步：轮询状态与获取结果

拿到 `task_id` 后，通过 GET 请求轮询结果。

**查询 Endpoint**: `GET https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}`
**Header**: `Authorization: Bearer $DASHSCOPE_API_KEY`

状态 (`task_status`) 包括 `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`。
当为 `SUCCEEDED` 时，`output.results` 会包含转写的句子、时间戳甚至情绪标签（如果是支持的版本）。

---

## 4. Reference: Official API Spec
> **防幻觉红线**: 以下为官方原始 API 规范文档备份。当上方精简版参数无法满足需求或出现争议时，请**绝对以本段下方的官方原始定义为准**。

```markdown
千问3-ASR-Flash-Filetrans 仅支持 DashScope 异步调用方式。

### 提交任务
HTTP请求地址：POST https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription
Headers: 
- Authorization: Bearer $DASHSCOPE_API_KEY
- Content-Type: application/json
- X-DashScope-Async: enable

#### 请求体参数
- `model`: 必选，固定为 `qwen3-asr-flash-filetrans`。
- `input`: 必选对象。
  - `file_url`: 必选，公网可访问的待识别文件 URL。
- `parameters`: 可选对象。
  - `language`: string，指定语种。
  - `enable_itn`: boolean，默认 false。
  - `enable_words`: boolean，默认 false。控制是否返回字级别时间戳。true返回字级时间戳（且断句规则变为VAD+标点）。
  - `channel_id`: array，默认 `[0]`。指定多音轨的索引。指定的每一个音轨都将独立计费。
```
