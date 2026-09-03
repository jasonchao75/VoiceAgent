# Spec: Soniox Async Batch Arabic Transcription & Evaluation for RiyadBank

## 1. Overview & Goals

This specification defines the design and implementation of an offline batch transcription and evaluation script using the **Soniox ASR API** with the latest **`stt-async-v5`** model. The script is designed to:
- Recursively scan and locate Arabic WAV files under `benchmarks/arabic_audio/RiyadBank/`.
- Parse the gold standard annotations from `benchmarks/arabic_audio/RiyadBank/metadata.csv` and resolve file path mismatches (as files are physically stored in category subdirectories like `branch_code`, `branch_name`, `general_utterance`, and `unclear`, while the metadata lists them under `audio/`).
- Concurrently transcribe audio files using a highly optimized, semaphore-controlled asynchronous worker pool.
- Apply robust **Arabic Text Normalization** to both the human reference texts and the Soniox ASR transcriptions to ensure fair ASR evaluation.
- Compute Word Error Rate (WER) using a custom, word-level Levenshtein distance algorithm.
- Output detailed transcription logs and a structured CSV record containing the comparative evaluation results.
- Implement strict garbage collection to clean up all files and transcriptions from Soniox servers immediately after processing.

---

## 2. Technical Stack & API Specification

### 2.1 Technology Stack
- **Language**: Python 3.11+
- **Concurrency**: `asyncio` for non-blocking I/O and parallel execution
- **HTTP client**: `httpx` (async HTTP client) or `aiohttp` for async requests, or async wrapper on top of `requests` (we'll use `aiohttp` or `httpx` if installed, or use standard `asyncio` executor with `requests` to remain highly compatible and robust without adding mandatory external libraries if not already in the project; let's check what libraries are available. Wait, since python 3.11 is used, we can write an elegant `httpx` or `aiohttp` async implementation, or use `asyncio.to_thread` with `requests` which is very standard and robust).
- **Core modules**: `json`, `csv`, `re`, `logging`, `os`, `sys`, `time`, `datetime`, `wave`

### 2.2 API Endpoints & Authentication
- **Base URL**: `https://api.soniox.com`
- **Authentication Header**: `Authorization: Bearer {SONIOX_API_KEY}`
- **Operations**:
  1. **Upload**: `POST /v1/files` (multipart/form-data)
  2. **Create Job**: `POST /v1/transcriptions` (JSON)
  3. **Poll Status**: `GET /v1/transcriptions/{id}` (JSON, poll status until `"completed"` or `"error"`)
  4. **Fetch Result**: `GET /v1/transcriptions/{id}/transcript` (JSON)
  5. **Delete Job**: `DELETE /v1/transcriptions/{id}` (HTTP DELETE)
  6. **Delete File**: `DELETE /v1/files/{file_id}` (HTTP DELETE)

---

## 3. RiyadBank Data Mapping & Alignment

The metadata in `benchmarks/arabic_audio/RiyadBank/metadata.csv` specifies relative paths of the form `audio/RB_xxxx.wav` (e.g., `audio/RB_0001.wav`). However, the audio files are physically distributed under four category folders:
- `benchmarks/arabic_audio/RiyadBank/branch_code/`
- `benchmarks/arabic_audio/RiyadBank/branch_name/`
- `benchmarks/arabic_audio/RiyadBank/general_utterance/`
- `benchmarks/arabic_audio/RiyadBank/unclear/`

### File Path Resolution Strategy:
1. Scan the `metadata.csv` file, loading all records into a dictionary keyed by `audio_id` (e.g. `RB_0001`).
2. Recursively scan the `benchmarks/arabic_audio/RiyadBank/` folder for `.wav` files. Build a lookup map of `filename -> absolute_path` (e.g., `RB_0001.wav -> D:\...\RiyadBank\branch_code\RB_0001.wav`).
3. For each metadata record, resolve the physical file path by looking up `audio_id + ".wav"` in the lookup map. If found, proceed; if not, log a warning and skip.

---

## 4. Arabic Text Normalization

To evaluate ASR accuracy fairly, raw texts must undergo Arabic-specific text normalization before WER computation. The normalization pipeline will implement:

1. **Remove Diacritics (Harakat / Tashkeel)**:
   - Regex to strip: `َ` (Fatha), `ُ` (Damma), `ِ` (Kasra), `ّ` (Shadda), `ْ` (Sukun), `ً` (Tanween Fatha), `ٌ` (Tanween Damma), `ٍ` (Tanween Kasra).
2. **Normalize Alif**:
   - Replace any of `أ`, `إ`, `آ`, `ٱ` with the bare Alif `ا`.
3. **Normalize Ya**:
   - Replace word-final Alif Maqsura `ى` with Ya `ي`.
4. **Normalize Ta Marbuta**:
   - Replace word-final Ta Marbuta `ة` with Ha `ه` to neutralize grammatical gender ending variations.
5. **Strip Punctuation & Non-text symbols**:
   - Clean out separators and symbols such as `|`, `-`, `.`, `,`, `؟`, `!`, and other special characters.
6. **Normalize Digits**:
   - Translate Eastern Arabic-Indic digits (`٠١٢٣٤٥٦٧٨٩`) to Western Arabic digits (`0123456789`).
7. **Whitespace Standardization**:
   - Replace multiple spaces or tabs with a single space, and strip leading/trailing spaces.

---

## 5. Word Error Rate (WER) Evaluation

The Word Error Rate (WER) is computed at the word level using the Levenshtein distance algorithm:

- **Reference ($R$)**: Normalized human gold text, split into words.
- **Hypothesis ($H$)**: Normalized Soniox ASR transcription text, split into words.

The Levenshtein distance between $R$ and $H$ counts:
- **Substitutions ($S$)**: Word replaced.
- **Deletions ($D$)**: Word missing in hypothesis.
- **Insertions ($I$)**: Word added in hypothesis.

$$\text{WER} = \frac{S + D + I}{N}$$
where $N$ is the number of words in the Reference ($R$). If Reference is empty:
- If Hypothesis is also empty, $\text{WER} = 0.0$.
- If Hypothesis has words, $\text{WER} = 1.0$ (or count of words as insertions).

---

## 6. High-Performance Concurrency & Safety

To prevent hitting network rate limits, API rate limits, or exhausting file descriptors, we implement a **Semaphore Worker Pool** using `asyncio.Semaphore(limit=8)`.

```
[Main Thread] -> Resolves file paths -> Parses Metadata -> Spawns Worker Tasks
                                                             |
                                                             v
                                                  [Semaphore Queue (Max=8)]
                                                             |
                     +-------------------+-------------------+-------------------+
                     |                   |                   |                   |
                  [Worker 1]          [Worker 2]          [Worker 3]          [Worker 4]
                     |                   |                   |                   |
                     v                   v                   v                   v
                Upload Audio        Upload Audio        Upload Audio        Upload Audio
                     |                   |                   |                   |
                Create Job          Create Job          Create Job          Create Job
                     |                   |                   |                   |
                Poll Status         Poll Status         Poll Status         Poll Status
                     |                   |                   |                   |
                Get Transcript      Get Transcript      Get Transcript      Get Transcript
                     |                   |                   |                   |
                Cleanup API         Cleanup API         Cleanup API         Cleanup API
                     |                   |                   |                   |
                     +-------------------+-------------------+-------------------+
                                                             |
                                                             v
                                                  Aggregate & Compute WER
                                                             |
                                                             v
                                                  Write CSV & Log Report
```

### Safety & Cleanup Protocol:
- **Resource Cleanup in `finally` Block**: The upload `file_id` and transcription `transcription_id` must be deleted from Soniox servers inside a `try ... finally` block. This ensures that even if a worker crashes or a HTTP timeout occurs, the remote files are deleted, preventing quota leaks.
- **Connection Reuse**: Use a single authenticated `aiohttp.ClientSession` or wrapped session throughout the execution to reuse TCP connections.

---

## 7. Outputs

1. **Detail Log**: Saved to `scripts/vendor/soniox/logs_batch/soniox_batch_evaluation_<timestamp>.log`. Contains processing details, normalization steps, raw and normalized outputs for each WAV.
2. **Comparison Database CSV**: Saved to `scripts/vendor/soniox/soniox_batch_riyadbank_records.csv`. Contains:
   - `Audio_File_ID`
   - `Category`
   - `Human_Label`
   - `Soniox_Transcript`
   - `Normalized_Human`
   - `Normalized_Soniox`
   - `WER`
   - `Status`
3. **Summary Report**: Printed at the end of execution and written to log, summarizing total processed, total success, average WER, and category-wise WER statistics.
