import asyncio
import websockets
import json
import wave
import os
import sys
import logging
import time
import argparse
import base64
import math
import struct
from datetime import datetime
from dotenv import load_dotenv

# Command line arguments
parser = argparse.ArgumentParser()
parser.add_argument(
    "--audio",
    type=str,
    default=os.path.join(
        os.path.dirname(__file__),
        "../../../benchmarks/arabic_audio/check my account balance.wav",
    ),
    help="Path to the WAV audio file for testing",
)
args = parser.parse_args()

AUDIO_FILE = args.audio
CSV_RECORD_FILE = os.path.join(os.path.dirname(__file__), "elevenlabs_test_records.csv")

# Set up logging directories and files
logs_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(logs_dir, exist_ok=True)
audio_filename = os.path.splitext(os.path.basename(AUDIO_FILE))[0]
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = os.path.join(logs_dir, f"{audio_filename}_{timestamp}.log")

# Force UTF-8 stdout encoding on Windows to support Arabic characters in the terminal
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), "../../../.env"))
API_KEY = os.environ.get("ELEVENLABS_API_KEY")

# Load external configuration
CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "../../../configs/vendor/elevenlabs/config.json"
)
try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
except Exception as e:
    logging.error(f"Failed to load config from {CONFIG_PATH}: {e}")
    sys.exit(1)


# Generate dummy audio if file is missing (ASR Survey requirement)
def generate_dummy_wav(
    file_path: str, duration_sec: float = 3.0, sample_rate: int = 8000
):
    logging.info(
        f"Test audio file not found. Generating a dummy 440Hz sine-wave WAV at: {file_path}"
    )
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    try:
        with wave.open(file_path, "wb") as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)

            num_samples = int(duration_sec * sample_rate)
            frequency = 440.0
            for i in range(num_samples):
                value = int(
                    16000.0 * math.sin(2.0 * math.pi * frequency * i / sample_rate)
                )
                data = struct.pack("<h", value)
                wav_file.writeframes(data)
        logging.info("Dummy WAV file generated successfully.")
    except Exception as e:
        logging.error(f"Failed to generate dummy WAV file: {e}")
        sys.exit(1)


if not os.path.exists(AUDIO_FILE):
    generate_dummy_wav(AUDIO_FILE)

# Event to coordinate sender starting after session starts
session_started_event = asyncio.Event()


async def send_audio(websocket, framerate):
    try:
        wf = wave.open(AUDIO_FILE, "rb")
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        file_framerate = wf.getframerate()
        logging.info(
            f"Successfully opened WAV file: {AUDIO_FILE} ({channels} channels, {sampwidth} bytes/sample, {file_framerate} Hz)"
        )
    except Exception as e:
        logging.error(f"Failed to open audio file {AUDIO_FILE}: {e}")
        return

    # Wait for the session_started handshake from the receiver
    logging.info("Waiting for SessionStarted confirmation from server...")
    try:
        await asyncio.wait_for(session_started_event.wait(), timeout=15.0)
    except asyncio.TimeoutError:
        logging.error(
            "Timeout waiting for SessionStarted handshake from ElevenLabs. Aborting stream."
        )
        return

    chunk_size_ms = config.get("chunk_size_ms", 20)
    chunk_frames = int(file_framerate * (chunk_size_ms / 1000.0))

    logging.info(
        f"Starting to stream audio chunks (chunk size: {chunk_size_ms}ms, {chunk_frames} frames)..."
    )
    seq_no = 0

    while True:
        data = wf.readframes(chunk_frames)
        if not data:
            break

        # ElevenLabs requires Base64 JSON messages, NOT raw bytes!
        base64_data = base64.b64encode(data).decode("utf-8")
        chunk_msg = {
            "message_type": "input_audio_chunk",
            "audio_base_64": base64_data,
            "commit": False,
            "sample_rate": file_framerate,
        }

        await websocket.send(json.dumps(chunk_msg))
        seq_no += 1

        # Emulate real-time streaming interval
        await asyncio.sleep(chunk_size_ms / 1000.0)

    logging.info(
        f"Audio transmission finished. Sent {seq_no} chunks. Sending final commit block..."
    )

    # Send empty commit block to finalize any uncommitted transcripts
    final_msg = {
        "message_type": "input_audio_chunk",
        "audio_base_64": "",
        "commit": True,
        "sample_rate": file_framerate,
    }
    await websocket.send(json.dumps(final_msg))


async def receive_results(websocket):
    first_packet = True
    start_time = time.time()
    segments = []

    try:
        async for message in websocket:
            msg = json.loads(message)
            msg_type = msg.get("message_type")

            if msg_type == "session_started":
                session_id = msg.get("session_id")
                logging.info(f"Received SessionStarted. Session ID: {session_id}")
                session_started_event.set()

            elif msg_type == "partial_transcript":
                text = msg.get("text", "")
                if text.strip():
                    if first_packet:
                        delay = time.time() - start_time
                        logging.info(f"First partial result delay: {delay:.3f}s")
                        first_packet = False
                    logging.info(f"[Partial]: {text}")

            elif msg_type in [
                "committed_transcript",
                "committed_transcript_with_timestamps",
            ]:
                text = msg.get("text", "")
                logging.info(f"[Final Committed]: {text}")
                if text.strip():
                    segments.append(text.strip())

            elif msg_type in [
                "error",
                "auth_error",
                "quota_exceeded",
                "chunk_size_exceeded",
            ]:
                logging.error(f"Received Server Error [{msg_type}]: {msg.get('error')}")
                break
            else:
                logging.debug(f"Received other message [{msg_type}]: {json.dumps(msg)}")

    except websockets.exceptions.ConnectionClosed as e:
        logging.info(f"Connection closed by server: {e}")
    except Exception as e:
        logging.error(f"Error in receiver loop: {e}")

    return segments


async def run_test():
    if not API_KEY:
        logging.error(
            "ELEVENLABS_API_KEY is not set in .env file or environment variables."
        )
        logging.info("Please set ELEVENLABS_API_KEY to run this live test.")
        return

    # Open WAV file briefly to determine its sample rate and adjust URL format parameter
    try:
        wf = wave.open(AUDIO_FILE, "rb")
        file_framerate = wf.getframerate()
        wf.close()
    except Exception as e:
        logging.error(f"Failed to check WAV file {AUDIO_FILE}: {e}")
        return

    # Map sample rate to ElevenLabs parameter
    rate_map = {
        8000: "pcm_8000",
        16000: "pcm_16000",
        22050: "pcm_22050",
        24000: "pcm_24000",
        44100: "pcm_44100",
        48000: "pcm_48000",
    }
    audio_format = rate_map.get(file_framerate, "pcm_16000")
    logging.info(
        f"Mapped file sample rate {file_framerate}Hz to parameter audio_format={audio_format}"
    )

    # Build connection query string from config
    params = []
    if config.get("model_id"):
        params.append(f"model_id={config['model_id']}")
    params.append(f"audio_format={audio_format}")
    if config.get("language_code"):
        params.append(f"language_code={config['language_code']}")
    if config.get("commit_strategy"):
        params.append(f"commit_strategy={config['commit_strategy']}")
    if config.get("include_timestamps") is not None:
        params.append(f"include_timestamps={str(config['include_timestamps']).lower()}")
    if config.get("include_language_detection") is not None:
        params.append(
            f"include_language_detection={str(config['include_language_detection']).lower()}"
        )
    if config.get("no_verbatim") is not None:
        params.append(f"no_verbatim={str(config['no_verbatim']).lower()}")
    if config.get("vad_silence_threshold_secs") is not None:
        params.append(
            f"vad_silence_threshold_secs={config['vad_silence_threshold_secs']}"
        )
    if config.get("vad_threshold") is not None:
        params.append(f"vad_threshold={config['vad_threshold']}")
    if config.get("min_speech_duration_ms") is not None:
        params.append(f"min_speech_duration_ms={config['min_speech_duration_ms']}")
    if config.get("min_silence_duration_ms") is not None:
        params.append(f"min_silence_duration_ms={config['min_silence_duration_ms']}")
    if config.get("enable_logging") is not None:
        params.append(f"enable_logging={str(config['enable_logging']).lower()}")

    # Handle keyterms (use URL encoding/percent-encoding for non-ASCII Arabic terms)
    import urllib.parse

    keyterms = config.get("keyterms", [])
    for term in keyterms:
        encoded_term = urllib.parse.quote(term)
        params.append(f"keyterms={encoded_term}")

    query_string = "&".join(params)
    ws_url = f"{config.get('endpoint', 'wss://api.elevenlabs.io/v1/speech-to-text/realtime')}?{query_string}"

    # xi-api-key authentication header
    headers = {"xi-api-key": API_KEY}

    logging.info(f"Connecting to: {ws_url}")

    import ssl

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        async with websockets.connect(
            ws_url, additional_headers=headers, ssl=ssl_context
        ) as websocket:
            send_task = asyncio.create_task(send_audio(websocket, file_framerate))
            receive_task = asyncio.create_task(receive_results(websocket))

            _, segments_result = await asyncio.gather(send_task, receive_task)

            full_transcript_str = " | ".join(segments_result)

            # Output aggregated results
            logging.info("\n" + "=" * 50)
            logging.info("=== ELEVENLABS FULL TRANSCRIPT SEGMENTS ===")
            for i, seg in enumerate(segments_result):
                logging.info(f"[{i + 1}] {seg}")
            logging.info("=" * 50 + "\n")

            # Save test records to CSV for benchmark verification
            os.makedirs(os.path.dirname(CSV_RECORD_FILE), exist_ok=True)
            file_exists = os.path.exists(CSV_RECORD_FILE)
            with open(CSV_RECORD_FILE, "a", encoding="utf-8") as f:
                if not file_exists:
                    f.write("Audio_File,Language,Full_Transcript\n")

                filename = os.path.basename(AUDIO_FILE)
                lang = config.get("language_code", "en")
                safe_transcript = full_transcript_str.replace('"', '""')
                f.write(f'"{filename}","{lang}","{safe_transcript}"\n')

            logging.info(f"Test record appended to CSV: {CSV_RECORD_FILE}")

    except Exception as e:
        logging.error(f"WebSocket connection or execution failed: {e}")


if __name__ == "__main__":
    asyncio.run(run_test())
