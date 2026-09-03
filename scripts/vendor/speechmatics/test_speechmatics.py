import asyncio
import websockets
import json
import wave
import os
import sys
import logging
import time
import argparse
import ssl
from pathlib import Path
from datetime import datetime

import certifi
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument(
    "--audio",
    type=str,
    default=os.path.join(
        os.path.dirname(__file__),
        "../../../benchmarks/arabic_audio/New Recording 7.wav",
    ),
)
parser.add_argument(
    "--config",
    type=Path,
    default=BASE_DIR / "../../../configs/vendor/speechmatics/config.json",
)
parser.add_argument("--result-json", type=Path)
args = parser.parse_args()

AUDIO_FILE = args.audio

# 配置日志
logs_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(logs_dir, exist_ok=True)
audio_filename = os.path.splitext(os.path.basename(AUDIO_FILE))[0]
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = os.path.join(logs_dir, f"{audio_filename}_{timestamp}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

# 加载配置
CONFIG_PATH = args.config.resolve()
try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
except Exception as e:
    logging.error(f"Failed to load config from {CONFIG_PATH}: {e}")
    sys.exit(1)

load_dotenv(os.path.join(os.path.dirname(__file__), "../../../.env"))
API_KEY = os.environ.get("SPEECHMATICS_API_KEY")

if not API_KEY:
    logging.error(
        "SPEECHMATICS_API_KEY is not set in .env file or environment variables."
    )
    logging.info("Please set SPEECHMATICS_API_KEY in the .env file to run this test.")
    sys.exit(1)


async def send_audio(websocket, recognition_started, timing):
    try:
        wf = wave.open(AUDIO_FILE, "rb")
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
    except Exception as e:
        logging.error(f"Failed to open audio file {AUDIO_FILE}: {e}")
        return

    # Dynamically adapt configuration based on the WAV file properties
    audio_format = config["audio_format"].copy()
    audio_format["sample_rate"] = framerate

    # Map sample width to encoding
    if sampwidth == 2:
        audio_format["encoding"] = "pcm_s16le"
    elif sampwidth == 1:
        audio_format["encoding"] = "pcm_u8"
    elif sampwidth == 4:
        audio_format["encoding"] = "pcm_f32le"

    # Dynamic transcription configuration (disable additional_vocab for non-Arabic)
    transcription_config = config["transcription_config"].copy()
    if (
        transcription_config.get("language") != "ar"
        and "additional_vocab" in transcription_config
    ):
        # Avoid passing Arabic-specific additional vocab for non-Arabic transcription
        transcription_config.pop("additional_vocab")

    # 发送 StartRecognition
    start_msg = {
        "message": "StartRecognition",
        "audio_format": audio_format,
        "transcription_config": transcription_config,
    }

    logging.info(f"Sending StartRecognition: {json.dumps(start_msg)}")
    await websocket.send(json.dumps(start_msg))

    chunk_size_ms = config.get("chunk_size_ms", 20)
    chunk_frames = int(framerate * (chunk_size_ms / 1000.0))

    await asyncio.wait_for(
        recognition_started.wait(),
        timeout=float(config.get("recognition_start_timeout_seconds", 10.0)),
    )

    logging.info(
        f"Starting to send audio data ({channels} channels, {sampwidth} bytes/sample, {framerate} Hz)..."
    )
    seq_no = 0
    timing["first_audio_sent_at"] = time.monotonic()
    while True:
        data = wf.readframes(chunk_frames)
        if not data:
            break
        await websocket.send(data)
        seq_no += 1
        # 模拟实时音频流发送速度
        await asyncio.sleep(chunk_size_ms / 1000.0)

    logging.info("Audio transmission finished. Sending EndOfStream...")
    end_msg = {"message": "EndOfStream", "last_seq_no": seq_no}
    await websocket.send(json.dumps(end_msg))


async def receive_results(websocket, recognition_started, timing):
    first_packet = True
    first_result_latency_ms = None
    segments = []
    current_segment = []

    try:
        async for message in websocket:
            msg = json.loads(message)
            msg_type = msg.get("message")

            if msg_type == "RecognitionStarted":
                logging.info("Received RecognitionStarted from server.")
                recognition_started.set()
            elif msg_type == "AddPartialTranscript":
                transcript = msg.get("metadata", {}).get("transcript", "")
                if first_packet and transcript.strip():
                    first_result_latency_ms = (
                        time.monotonic() - timing["first_audio_sent_at"]
                    ) * 1000.0
                    logging.info(
                        "First partial result delay: %.3fs",
                        first_result_latency_ms / 1000.0,
                    )
                    first_packet = False
                logging.info(f"[Partial]: {transcript}")
            elif msg_type == "AddTranscript":
                transcript = msg.get("metadata", {}).get("transcript", "")
                logging.info(f"[Final]: {transcript}")
                if transcript.strip():
                    current_segment.append(transcript.strip())
            elif msg_type == "EndOfTranscript":
                logging.info(
                    "Received EndOfTranscript. Server has finished processing."
                )
                if current_segment:
                    segments.append(" ".join(current_segment))
                    current_segment = []
                break
            elif msg_type == "Error":
                logging.error(f"Received Error: {json.dumps(msg)}")
                break
            elif msg_type == "Warning":
                logging.warning(f"Received Warning: {json.dumps(msg)}")
            elif msg_type == "EndOfUtterance":
                logging.info("[VAD Event]: EndOfUtterance detected")
                if current_segment:
                    segment_text = " ".join(current_segment)
                    segments.append(segment_text)
                    logging.info(f"--- Segment Emitted ---: {segment_text}")
                    current_segment = []
            elif msg_type in ["AudioEventStarted", "AudioEventEnded"]:
                event_type = msg.get("event", {}).get("type", "")
                logging.info(f"[VAD Event]: {msg_type} - {event_type}")
            elif msg_type in ["AudioAdded", "Info"]:
                # 忽略干扰日志，保持控制台清洁
                pass
            else:
                logging.info(f"Received other message: {msg_type}")
    except websockets.exceptions.ConnectionClosed as e:
        logging.info(f"Connection closed: {e}")
    except Exception as e:
        logging.error(f"Error in receive loop: {e}")

    # 如果结束时还有未输出的 segment，兜底输出
    if current_segment:
        segments.append(" ".join(current_segment))

    return segments, first_result_latency_ms


async def run_test():
    endpoint = config.get("endpoint", "wss://eu.rt.speechmatics.com/v2/")

    headers = {"Authorization": f"Bearer {API_KEY}"}

    logging.info(f"Connecting to {endpoint}")
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    recognition_started = asyncio.Event()
    timing = {}

    try:
        async with websockets.connect(
            endpoint,
            additional_headers=headers,
            ssl=ssl_context,
            open_timeout=float(config.get("open_timeout_seconds", 10.0)),
            close_timeout=float(config.get("close_timeout_seconds", 10.0)),
        ) as websocket:
            send_task = asyncio.create_task(
                send_audio(websocket, recognition_started, timing)
            )
            receive_task = asyncio.create_task(
                receive_results(websocket, recognition_started, timing)
            )

            _, receive_result = await asyncio.gather(send_task, receive_task)
            segments_result, first_result_latency_ms = receive_result

            full_transcript_str = " | ".join(segments_result)

            # 打印完整组装好的分段文本
            logging.info("\n" + "=" * 50)
            logging.info("=== FULL TRANSCRIPT SEGMENTS ===")
            for i, seg in enumerate(segments_result):
                logging.info(f"[{i + 1}] {seg}")
            logging.info("=" * 50 + "\n")

            result = {
                "audio_file": os.path.basename(AUDIO_FILE),
                "language": config.get("transcription_config", {}).get(
                    "language", "unknown"
                ),
                "transcript": full_transcript_str,
                "first_result_latency_ms": first_result_latency_ms,
            }
            if args.result_json:
                args.result_json.parent.mkdir(parents=True, exist_ok=True)
                args.result_json.write_text(
                    json.dumps(result, ensure_ascii=False), encoding="utf-8"
                )
            return result

    except Exception as e:
        logging.error(f"WebSocket connection failed: {e}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(run_test())
    except KeyboardInterrupt:
        logging.info("Test stopped by user.")
