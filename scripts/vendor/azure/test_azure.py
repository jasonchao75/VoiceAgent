import os
import sys
import wave
import time
import json
import logging
import argparse
from datetime import datetime
from dotenv import load_dotenv

import azure.cognitiveservices.speech as speechsdk

# Args
parser = argparse.ArgumentParser()
parser.add_argument('--audio', type=str, required=True)
args = parser.parse_args()

AUDIO_FILE = args.audio

base_dir = os.path.dirname(__file__)
logs_dir = os.path.join(base_dir, 'logs')
os.makedirs(logs_dir, exist_ok=True)
audio_filename = os.path.splitext(os.path.basename(AUDIO_FILE))[0]
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
log_file = os.path.join(logs_dir, f"{audio_filename}_{timestamp}.log")
CSV_RECORD_FILE = os.path.join(base_dir, 'azure_test_records.csv')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

load_dotenv(os.path.join(base_dir, '../../../.env'))
AZURE_SPEECH_KEY = os.environ.get("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.environ.get("AZURE_SPEECH_REGION")

if not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
    logging.error("AZURE_SPEECH_KEY or AZURE_SPEECH_REGION is missing in .env")
    logging.info("Please set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION in the .env file to run this test.")
    sys.exit(1)

# Load config
CONFIG_PATH = os.path.join(base_dir, '../../../configs/vendor/azure/config.json')
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    config = json.load(f)

def run_test():
    speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
    speech_config.speech_recognition_language = config.get("language", "ar-SA")
    
    if config.get("segmentation_strategy") == "Semantic":
        speech_config.set_property(speechsdk.PropertyId.Speech_SegmentationStrategy, "Semantic")

    wf = wave.open(AUDIO_FILE, 'rb')
    sample_rate = wf.getframerate()
    bits_per_sample = wf.getsampwidth() * 8
    channels = wf.getnchannels()
    
    stream_format = speechsdk.audio.AudioStreamFormat(samples_per_second=sample_rate, bits_per_sample=bits_per_sample, channels=channels)
    push_stream = speechsdk.audio.PushAudioInputStream(stream_format=stream_format)
    audio_config = speechsdk.audio.AudioConfig(stream=push_stream)
    
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    
    full_transcript = []
    first_partial_logged = False
    start_time = time.time()
    
    done = False
    
    def recognizing_cb(evt):
        nonlocal first_partial_logged
        if not first_partial_logged and evt.result.text.strip():
            delay = time.time() - start_time
            logging.info(f"First partial result delay: {delay:.3f}s")
            first_partial_logged = True
        logging.info(f"[Partial]: {evt.result.text}")
        
    def recognized_cb(evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            text = evt.result.text.strip()
            logging.info(f"[VAD Event]: Segment Recognized / Endpoint reached")
            logging.info(f"[Final]: {text}")
            if text:
                full_transcript.append(text)
        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            pass # ignore no match to keep logs clean

    def session_started_cb(evt):
        logging.info("Session started")
        
    def session_stopped_cb(evt):
        logging.info("Session stopped")
        nonlocal done
        done = True
        
    def canceled_cb(evt):
        if evt.result.cancellation_details.reason == speechsdk.CancellationReason.Error:
            logging.error(f"Error details: {evt.result.cancellation_details.error_details}")
        else:
            logging.info(f"Canceled: {evt.result.cancellation_details.reason}")
        nonlocal done
        done = True

    speech_recognizer.recognizing.connect(recognizing_cb)
    speech_recognizer.recognized.connect(recognized_cb)
    speech_recognizer.session_started.connect(session_started_cb)
    speech_recognizer.session_stopped.connect(session_stopped_cb)
    speech_recognizer.canceled.connect(canceled_cb)
    
    logging.info("Starting continuous recognition...")
    speech_recognizer.start_continuous_recognition()
    
    logging.info("Starting to push audio data...")
    chunk_frames = int(sample_rate * 0.02)
    while True:
        data = wf.readframes(chunk_frames)
        if not data:
            break
        push_stream.write(data)
        time.sleep(0.02)
        
    logging.info("Audio transmission finished. Closing stream...")
    push_stream.close()
    
    while not done:
        time.sleep(0.1)
        
    speech_recognizer.stop_continuous_recognition()
    
    final_text = " ".join(full_transcript)
    logging.info("\n" + "="*50)
    logging.info("=== FULL TRANSCRIPT SEGMENT ===")
    logging.info(final_text)
    logging.info("="*50 + "\n")
    
    os.makedirs(os.path.dirname(CSV_RECORD_FILE), exist_ok=True)
    file_exists = os.path.exists(CSV_RECORD_FILE)
    with open(CSV_RECORD_FILE, 'a', encoding='utf-8') as f:
        if not file_exists:
            f.write("Audio_File,Language,Full_Transcript\n")
        safe_transcript = final_text.replace('"', '""')
        filename = os.path.basename(AUDIO_FILE)
        lang = config.get("language", "ar-SA")
        f.write(f'"{filename}","{lang}","{safe_transcript}"\n')
    logging.info(f"Test record appended to CSV: {CSV_RECORD_FILE}")

if __name__ == "__main__":
    run_test()