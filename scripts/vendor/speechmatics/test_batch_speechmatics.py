import os
import sys
import logging
import time
import argparse
import requests
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from datetime import datetime
from dotenv import load_dotenv

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('--audio', type=str, required=True, help="Path to the audio file")
args = parser.parse_args()

AUDIO_FILE = args.audio

if not os.path.exists(AUDIO_FILE):
    print(f"Error: Audio file {AUDIO_FILE} does not exist.")
    sys.exit(1)

# Setup paths
base_dir = os.path.dirname(__file__)
logs_dir = os.path.join(base_dir, 'logs_batch')
os.makedirs(logs_dir, exist_ok=True)

audio_filename = os.path.splitext(os.path.basename(AUDIO_FILE))[0]
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
log_file = os.path.join(logs_dir, f"{audio_filename}_{timestamp}.log")
CSV_RECORD_FILE = os.path.join(base_dir, 'speechmatics_batch_test_records.csv')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Load ENV
load_dotenv(os.path.join(base_dir, '../../../.env'))
API_KEY = os.environ.get("SPEECHMATICS_API_KEY")

if not API_KEY:
    logging.error("SPEECHMATICS_API_KEY is not set in .env file or environment variables.")
    sys.exit(1)

# API Endpoints
BASE_URL = "https://asr.api.speechmatics.com/v2"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}"
}

def run_batch_test():
    logging.info(f"Starting batch test for file: {AUDIO_FILE}")
    
    # 1. Submit Job
    submit_url = f"{BASE_URL}/jobs/"
    
    config = {
        "type": "transcription",
        "transcription_config": {
            "language": "ar",
            "operating_point": "enhanced",
            "enable_entities": True
        }
    }
    
    logging.info(f"Submitting job with config: {json.dumps(config)}")
    
    with open(AUDIO_FILE, 'rb') as f:
        files = {
            'data_file': (os.path.basename(AUDIO_FILE), f, 'audio/wav'),
            'config': (None, json.dumps(config), 'application/json')
        }
        
        response = requests.post(submit_url, headers=HEADERS, files=files, verify=False)
        
    if response.status_code != 201:
        logging.error(f"Failed to submit job. Status: {response.status_code}, Body: {response.text}")
        return
        
    job_id = response.json().get('id')
    logging.info(f"Job successfully submitted. Job ID: {job_id}")
    
    # 2. Poll for completion
    poll_url = f"{BASE_URL}/jobs/{job_id}"
    while True:
        time.sleep(3)
        poll_response = requests.get(poll_url, headers=HEADERS, verify=False)
        if poll_response.status_code != 200:
            logging.error(f"Failed to poll job status. Status: {poll_response.status_code}")
            return
            
        status = poll_response.json().get('job', {}).get('status')
        logging.info(f"Job status: {status}")
        
        if status == 'done':
            break
        elif status in ['rejected', 'error']:
            logging.error(f"Job failed with status: {status}")
            return
            
    # 3. Retrieve transcript
    transcript_url = f"{BASE_URL}/jobs/{job_id}/transcript?format=txt"
    transcript_response = requests.get(transcript_url, headers=HEADERS, verify=False)
    
    if transcript_response.status_code != 200:
        logging.error(f"Failed to get transcript. Status: {transcript_response.status_code}")
        return
        
    transcript_response.encoding = 'utf-8'
    full_transcript = transcript_response.text.strip()
    
    logging.info("\n" + "="*50)
    logging.info("=== FULL TRANSCRIPT SEGMENT ===")
    logging.info(full_transcript)
    logging.info("="*50 + "\n")
    
    # 4. Save to CSV
    os.makedirs(os.path.dirname(CSV_RECORD_FILE), exist_ok=True)
    file_exists = os.path.exists(CSV_RECORD_FILE)
    with open(CSV_RECORD_FILE, 'a', encoding='utf-8') as f:
        if not file_exists:
            f.write("Audio_File,Language,Full_Transcript\n")
            
        filename = os.path.basename(AUDIO_FILE)
        lang = config["transcription_config"]["language"]
        safe_transcript = full_transcript.replace('"', '""') # escape quotes
        f.write(f'"{filename}","{lang}","{safe_transcript}"\n')
        
    logging.info(f"Test record appended to CSV: {CSV_RECORD_FILE}")

if __name__ == "__main__":
    try:
        run_batch_test()
    except KeyboardInterrupt:
        logging.info("Batch test stopped by user.")
    except Exception as e:
        logging.error(f"Error during batch test: {e}")
