import asyncio
import websockets
import json
import wave
import os
import sys
import logging
import time
import argparse
from datetime import datetime
from dotenv import load_dotenv

parser = argparse.ArgumentParser()
parser.add_argument('--audio', type=str, default=os.path.join(os.path.dirname(__file__), '../../../benchmarks/arabic_audio/New Recording 7.wav'))
args = parser.parse_args()

AUDIO_FILE = args.audio
CSV_RECORD_FILE = os.path.join(os.path.dirname(__file__), 'speechmatics_test_records.csv')

# 配置日志
logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
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

# 加载配置
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '../../../configs/vendor/speechmatics/config.json')
try:
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
except Exception as e:
    logging.error(f"Failed to load config from {CONFIG_PATH}: {e}")
    sys.exit(1)

load_dotenv(os.path.join(os.path.dirname(__file__), '../../../.env'))
API_KEY = os.environ.get("SPEECHMATICS_API_KEY")

if not API_KEY:
    logging.error("SPEECHMATICS_API_KEY is not set in .env file or environment variables.")
    logging.info("Please set SPEECHMATICS_API_KEY in the .env file to run this test.")
    sys.exit(1)

async def send_audio(websocket):
    # 发送 StartRecognition
    start_msg = {
        "message": "StartRecognition",
        "audio_format": config["audio_format"],
        "transcription_config": config["transcription_config"]
    }
    
    logging.info(f"Sending StartRecognition: {json.dumps(start_msg)}")
    await websocket.send(json.dumps(start_msg))
    
    chunk_size_ms = config.get("chunk_size_ms", 20)
    sample_rate = config["audio_format"]["sample_rate"]
    chunk_frames = int(sample_rate * (chunk_size_ms / 1000.0))

    try:
        wf = wave.open(AUDIO_FILE, 'rb')
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        
        if channels != 1 or sampwidth != 2 or framerate != sample_rate:
            logging.warning(f"Audio file properties do not strictly match requirements: "
                            f"{channels} channels, {sampwidth} bytes/sample, {framerate} Hz. "
                            f"Expected: 1 channel, 2 bytes/sample, {sample_rate} Hz.")
    except Exception as e:
        logging.error(f"Failed to open audio file {AUDIO_FILE}: {e}")
        return

    # 等待一小段时间，确保服务器能接收 RecognitionStarted
    await asyncio.sleep(0.5)

    logging.info("Starting to send audio data...")
    seq_no = 0
    while True:
        data = wf.readframes(chunk_frames)
        if not data:
            break
        await websocket.send(data)
        seq_no += 1
        # 模拟实时音频流发送速度
        await asyncio.sleep(chunk_size_ms / 1000.0)

    logging.info("Audio transmission finished. Sending EndOfStream...")
    end_msg = {
        "message": "EndOfStream",
        "last_seq_no": seq_no
    }
    await websocket.send(json.dumps(end_msg))

async def receive_results(websocket):
    first_packet = True
    start_time = time.time()
    full_transcript = []
    
    try:
        async for message in websocket:
            msg = json.loads(message)
            msg_type = msg.get("message")
            
            if msg_type == "RecognitionStarted":
                logging.info("Received RecognitionStarted from server.")
            elif msg_type == "AddPartialTranscript":
                transcript = msg.get("metadata", {}).get("transcript", "")
                if first_packet and transcript.strip():
                    delay = time.time() - start_time
                    logging.info(f"First partial result delay: {delay:.3f}s")
                    first_packet = False
                logging.info(f"[Partial]: {transcript}")
            elif msg_type == "AddTranscript":
                transcript = msg.get("metadata", {}).get("transcript", "")
                logging.info(f"[Final]: {transcript}")
                if transcript.strip():
                    full_transcript.append(transcript.strip())
            elif msg_type == "EndOfTranscript":
                logging.info("Received EndOfTranscript. Server has finished processing.")
                break
            elif msg_type == "Error":
                logging.error(f"Received Error: {json.dumps(msg)}")
                break
            elif msg_type == "Warning":
                logging.warning(f"Received Warning: {json.dumps(msg)}")
            elif msg_type == "EndOfUtterance":
                logging.info("[VAD Event]: EndOfUtterance detected")
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
        
    return " ".join(full_transcript)

async def run_test():
    endpoint = config.get("endpoint", "wss://eu.rt.speechmatics.com/v2/")
    
    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }

    logging.info(f"Connecting to {endpoint}")
    import ssl
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        async with websockets.connect(endpoint, additional_headers=headers, ssl=ssl_context) as websocket:
            send_task = asyncio.create_task(send_audio(websocket))
            receive_task = asyncio.create_task(receive_results(websocket))
            
            _, full_transcript = await asyncio.gather(send_task, receive_task)
            
            # 打印完整组装好的分段文本
            logging.info("\n" + "="*50)
            logging.info("=== FULL TRANSCRIPT SEGMENT ===")
            logging.info(full_transcript)
            logging.info("="*50 + "\n")
            
            # 将测试记录保存到 CSV
            os.makedirs(os.path.dirname(CSV_RECORD_FILE), exist_ok=True)
            file_exists = os.path.exists(CSV_RECORD_FILE)
            with open(CSV_RECORD_FILE, 'a', encoding='utf-8') as f:
                if not file_exists:
                    f.write("Audio_File,Language,Full_Transcript\n")
                
                filename = os.path.basename(AUDIO_FILE)
                lang = config.get("transcription_config", {}).get("language", "unknown")
                safe_transcript = full_transcript.replace('"', '""') # 转义双引号
                f.write(f'"{filename}","{lang}","{safe_transcript}"\n')
                
            logging.info(f"Test record appended to CSV: {CSV_RECORD_FILE}")
            
    except Exception as e:
        logging.error(f"WebSocket connection failed: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(run_test())
    except KeyboardInterrupt:
        logging.info("Test stopped by user.")