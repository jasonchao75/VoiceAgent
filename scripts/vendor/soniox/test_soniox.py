import os
import sys
import wave
import time
import json
import logging
import argparse
import asyncio
import websockets
import ssl
from datetime import datetime
from pathlib import Path

import certifi
from dotenv import load_dotenv

parser = argparse.ArgumentParser()
parser.add_argument('--audio', type=str, required=True)
parser.add_argument('--result-json', type=Path)
args = parser.parse_args()

AUDIO_FILE = args.audio

base_dir = os.path.dirname(__file__)
logs_dir = os.path.join(base_dir, 'logs')
os.makedirs(logs_dir, exist_ok=True)
audio_filename = os.path.splitext(os.path.basename(AUDIO_FILE))[0]
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
log_file = os.path.join(logs_dir, f"{audio_filename}_{timestamp}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

load_dotenv(os.path.join(base_dir, '../../../.env'))
SONIOX_API_KEY = os.environ.get("SONIOX_API_KEY")

if not SONIOX_API_KEY:
    logging.error("SONIOX_API_KEY is missing in .env")
    logging.info("Please set SONIOX_API_KEY in the .env file to run this test.")
    sys.exit(1)

CONFIG_PATH = os.path.join(base_dir, '../../../configs/vendor/soniox/config.json')
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    config = json.load(f)

LOCAL_CONFIG_KEYS = {
    "endpoint",
    "chunk_size_ms",
    "open_timeout_seconds",
    "close_timeout_seconds",
}

async def send_audio(websocket, wf, chunk_size_ms, timing):
    request_config = {
        key: value for key, value in config.items() if key not in LOCAL_CONFIG_KEYS
    }
    request_config["api_key"] = SONIOX_API_KEY
    safe_config = {**request_config, "api_key": "***"}
    logging.info(f"Sending initial config: {json.dumps(safe_config)}")
    await websocket.send(json.dumps(request_config))
    
    sample_rate = config["sample_rate"]
    chunk_frames = int(sample_rate * (chunk_size_ms / 1000.0))
    
    await asyncio.sleep(0.1)
    logging.info("Starting to send audio data...")
    timing["first_audio_sent_at"] = time.monotonic()
    while True:
        data = wf.readframes(chunk_frames)
        if not data:
            break
        await websocket.send(data)
        await asyncio.sleep(chunk_size_ms / 1000.0)
        
    logging.info("Audio transmission finished. Sending empty string...")
    await websocket.send("")

async def receive_results(websocket, timing):
    full_transcript = []
    first_packet = True
    first_result_latency_ms = None
    
    final_tokens = []
    last_printed_non_final = ""
    
    try:
        async for message in websocket:
            res = json.loads(message)
            if res.get("error_code"):
                logging.error(f"Error: {res['error_code']} - {res['error_message']}")
                break
                
            non_final_tokens = []
            
            for token in res.get("tokens", []):
                if token.get("text"):
                    if token.get("is_final"):
                        final_tokens.append(token["text"])
                        if first_packet:
                            first_result_latency_ms = (
                                time.monotonic() - timing["first_audio_sent_at"]
                            ) * 1000.0
                            logging.info(
                                "First partial result delay: %.3fs",
                                first_result_latency_ms / 1000.0,
                            )
                            first_packet = False
                        
                        if token["text"] == "<end>" or token["text"] == "<fin>":
                            logging.info(f"[VAD Event]: Endpoint detected {token['text']}")
                            final_text = "".join(final_tokens).replace("<end>", "").replace("<fin>", "")
                            if final_text.strip():
                                logging.info(f"[Final]: {final_text}")
                                full_transcript.append(final_text.strip())
                            final_tokens = []
                    else:
                        non_final_tokens.append(token["text"])
                        
            if non_final_tokens:
                if first_packet:
                    first_result_latency_ms = (
                        time.monotonic() - timing["first_audio_sent_at"]
                    ) * 1000.0
                    logging.info(
                        "First partial result delay: %.3fs",
                        first_result_latency_ms / 1000.0,
                    )
                    first_packet = False
                current_partial = "".join(final_tokens).replace("<end>", "").replace("<fin>", "") + "".join(non_final_tokens)
                if current_partial != last_printed_non_final and current_partial.strip():
                    logging.info(f"[Partial]: {current_partial}")
                    last_printed_non_final = current_partial
                    
            if res.get("finished"):
                logging.info("Session finished.")
                break
    except websockets.exceptions.ConnectionClosed as e:
        logging.info(f"Connection closed: {e}")
        
    if final_tokens:
        final_text = "".join(final_tokens).replace("<end>", "").replace("<fin>", "")
        if final_text.strip():
            logging.info(f"[Final]: {final_text}")
            full_transcript.append(final_text.strip())
            
    return " ".join(full_transcript), first_result_latency_ms

async def run_test():
    wf = wave.open(AUDIO_FILE, 'rb')
    config["sample_rate"] = wf.getframerate()
    
    endpoint = config["endpoint"]
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    timing = {}
    
    logging.info(f"Connecting to {endpoint}")
    try:
        async with websockets.connect(
            endpoint,
            ssl=ssl_context,
            open_timeout=float(config["open_timeout_seconds"]),
            close_timeout=float(config["close_timeout_seconds"]),
        ) as websocket:
            send_task = asyncio.create_task(
                send_audio(websocket, wf, int(config["chunk_size_ms"]), timing)
            )
            receive_task = asyncio.create_task(receive_results(websocket, timing))
            _, receive_result = await asyncio.gather(send_task, receive_task)
            final_text, first_result_latency_ms = receive_result
            
            logging.info("\n" + "="*50)
            logging.info("=== FULL TRANSCRIPT SEGMENT ===")
            logging.info(final_text)
            logging.info("="*50 + "\n")
            
            result = {
                "audio_file": os.path.basename(AUDIO_FILE),
                "language": ",".join(config.get("language_hints", [])),
                "transcript": final_text,
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
    asyncio.run(run_test())
