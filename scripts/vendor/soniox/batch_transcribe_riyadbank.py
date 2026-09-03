import os
import sys
import csv
import json
import time
import logging
import asyncio
import argparse
import requests
import urllib3
from datetime import datetime
from dotenv import load_dotenv

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
sys.path.insert(0, ROOT_DIR)

from benchmarks.library_ar.asr_char_accuracy import (  # noqa: E402
    levenshtein_counts,
    normalize_combined_words,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Enforce UTF-8 standard output to prevent GBK encoding issues on Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

SONIOX_API_BASE_URL = "https://api.soniox.com"

# Setup Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(ROOT_DIR, "configs/vendor/soniox/batch_config.json")
METADATA_PATH = os.path.join(ROOT_DIR, "benchmarks/arabic_audio/RiyadBank/metadata.csv")
RIYADBANK_DIR = os.path.join(ROOT_DIR, "benchmarks/arabic_audio/RiyadBank")
CSV_OUTPUT_PATH = os.path.join(BASE_DIR, "soniox_batch_riyadbank_records.csv")

# Setup Logging
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
logs_dir = os.path.join(BASE_DIR, "logs_batch")
os.makedirs(logs_dir, exist_ok=True)
log_file = os.path.join(logs_dir, f"soniox_batch_evaluation_{timestamp}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

# Load API Key
load_dotenv(os.path.join(ROOT_DIR, ".env"))
SONIOX_API_KEY = os.environ.get("SONIOX_API_KEY")

if not SONIOX_API_KEY:
    logging.error("SONIOX_API_KEY is missing in .env")
    sys.exit(1)

# Load Config
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    BATCH_CONFIG = json.load(f)

# Global Semaphore to limit concurrent executions (uploads, polling)
CONCURRENCY_LIMIT = 8
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)


def calculate_library_ar_wer(
    reference_text: str, hypothesis_text: str
) -> tuple[str, str, float, int, int, int, int]:
    """Calculate WER with the unchanged library_ar normalization logic.

    Args:
        reference_text: Human reference transcript.
        hypothesis_text: ASR hypothesis transcript.

    Returns:
        Normalized texts, WER, edit counts, and reference word count.
    """
    reference_words = normalize_combined_words(reference_text)
    hypothesis_words = normalize_combined_words(hypothesis_text)
    counts = levenshtein_counts(reference_words, hypothesis_words)
    reference_word_count = len(reference_words)
    if reference_word_count:
        wer = counts.total / reference_word_count
    else:
        wer = 0.0 if not hypothesis_words else 1.0
    return (
        " ".join(reference_words),
        " ".join(hypothesis_words),
        wer,
        counts.substitutions,
        counts.deletions,
        counts.insertions,
        reference_word_count,
    )


def scan_wav_files(directory: str) -> dict:
    """Recursively scans directory for wav files and returns a map of filename -> abs_path."""
    wav_map = {}
    for root, _, files in os.walk(directory):
        for f in files:
            if f.lower().endswith(".wav"):
                wav_map[f] = os.path.join(root, f)
    return wav_map


def parse_metadata(csv_path: str) -> list:
    """Parses metadata.csv and returns list of dictionaries."""
    records = []
    if not os.path.exists(csv_path):
        logging.error(f"Metadata file not found: {csv_path}")
        return records

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
    return records


# Synchronous HTTP wrappers executed in asyncio.to_thread for safety and thread reuse
def upload_file_sync(session: requests.Session, file_path: str) -> str:
    logging.info(f"Uploading file: {os.path.basename(file_path)}")
    with open(file_path, "rb") as f:
        res = session.post(
            f"{SONIOX_API_BASE_URL}/v1/files",
            files={"file": (os.path.basename(file_path), f, "audio/wav")},
            verify=False,
        )
    res.raise_for_status()
    file_id = res.json()["id"]
    logging.info(f"Uploaded successfully. File ID: {file_id}")
    return file_id


def create_transcription_sync(
    session: requests.Session, file_id: str, client_ref_id: str
) -> str:
    logging.info(f"Creating job for file_id: {file_id}")
    config = {**BATCH_CONFIG, "file_id": file_id, "client_reference_id": client_ref_id}
    res = session.post(
        f"{SONIOX_API_BASE_URL}/v1/transcriptions", json=config, verify=False
    )
    res.raise_for_status()
    trans_id = res.json()["id"]
    logging.info(f"Created job successfully. Job ID: {trans_id}")
    return trans_id


def get_job_status_sync(session: requests.Session, trans_id: str) -> str:
    res = session.get(
        f"{SONIOX_API_BASE_URL}/v1/transcriptions/{trans_id}", verify=False
    )
    res.raise_for_status()
    return res.json()["status"]


def get_transcript_sync(session: requests.Session, trans_id: str) -> list:
    res = session.get(
        f"{SONIOX_API_BASE_URL}/v1/transcriptions/{trans_id}/transcript", verify=False
    )
    res.raise_for_status()
    return res.json().get("tokens", [])


def delete_transcription_sync(session: requests.Session, trans_id: str):
    logging.info(f"Deleting transcription job: {trans_id}")
    res = session.delete(
        f"{SONIOX_API_BASE_URL}/v1/transcriptions/{trans_id}", verify=False
    )
    res.raise_for_status()


def delete_file_sync(session: requests.Session, file_id: str):
    logging.info(f"Deleting remote file: {file_id}")
    res = session.delete(f"{SONIOX_API_BASE_URL}/v1/files/{file_id}", verify=False)
    res.raise_for_status()


def render_tokens(tokens: list) -> str:
    """Assembles token list into raw string."""
    text_parts = []
    for token in tokens:
        text_parts.append(token.get("text", ""))
    return "".join(text_parts).strip()


async def transcribe_and_evaluate_single(
    session: requests.Session, record: dict, file_path: str
) -> dict:
    """Worker task processing a single WAV file from upload to cleanup, computing WER."""
    audio_id = record["audio_id"]
    category = record.get("category", "unclear")
    human_label = record.get("label_text", "")

    file_id = None
    trans_id = None
    asr_transcript = ""
    status = "error"
    error_msg = ""

    async with semaphore:
        try:
            # 1. Upload File
            file_id = await asyncio.to_thread(upload_file_sync, session, file_path)

            # 2. Submit Transcription
            trans_id = await asyncio.to_thread(
                create_transcription_sync, session, file_id, audio_id
            )

            # 3. Poll Status
            logging.info(f"Polling job: {trans_id}")
            while True:
                job_status = await asyncio.to_thread(
                    get_job_status_sync, session, trans_id
                )
                if job_status == "completed":
                    break
                elif job_status == "error":
                    raise Exception("Soniox transcription job failed on server side.")
                await asyncio.sleep(2)

            # 4. Fetch Result
            tokens = await asyncio.to_thread(get_transcript_sync, session, trans_id)
            asr_transcript = render_tokens(tokens)
            status = "success"

        except Exception as e:
            error_msg = str(e)
            logging.error(f"Failed to process {audio_id}: {error_msg}")
            status = "failed"

        finally:
            # Strict Garbage Collection in finally block to ensure no orphaned files on Soniox
            if trans_id:
                try:
                    await asyncio.to_thread(
                        delete_transcription_sync, session, trans_id
                    )
                except Exception as ex:
                    logging.error(f"Failed to cleanup job {trans_id}: {ex}")
            if file_id:
                try:
                    await asyncio.to_thread(delete_file_sync, session, file_id)
                except Exception as ex:
                    logging.error(f"Failed to cleanup file {file_id}: {ex}")

    # Evaluation must use the existing library_ar implementation unchanged.
    norm_human = ""
    norm_asr = ""
    wer = 1.0
    sub, dele, ins, n_ref = 0, 0, 0, 0
    if status == "success":
        (
            norm_human,
            norm_asr,
            wer,
            sub,
            dele,
            ins,
            n_ref,
        ) = calculate_library_ar_wer(human_label, asr_transcript)

    result_record = {
        "audio_id": audio_id,
        "category": category,
        "human_label": human_label,
        "asr_transcript": asr_transcript,
        "normalized_human": norm_human,
        "normalized_asr": norm_asr,
        "wer": wer if status == "success" else None,
        "sub": sub,
        "del": dele,
        "ins": ins,
        "ref_word_count": n_ref,
        "status": status,
        "error_message": error_msg,
    }

    if status == "success":
        logging.info(
            f"[SUCCESS] {audio_id} ({category}) | Human: '{human_label}' -> ASR: '{asr_transcript}' | Normalized Human: '{norm_human}' -> Normalized ASR: '{norm_asr}' | WER: {wer:.2%}"
        )
    else:
        logging.info(f"[FAILED] {audio_id} ({category}) | Error: {error_msg}")

    return result_record


async def main_async(limit: int | None = None, concurrency: int = 8):
    global semaphore, CONCURRENCY_LIMIT
    CONCURRENCY_LIMIT = concurrency
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    logging.info("Starting Soniox Batch Evaluation...")
    logging.info(f"Metadata file path: {METADATA_PATH}")
    logging.info(f"Scanning target directory: {RIYADBANK_DIR}")

    # 1. Scan local files
    local_wav_map = scan_wav_files(RIYADBANK_DIR)
    logging.info(f"Found {len(local_wav_map)} .wav files locally.")

    # 2. Parse metadata.csv
    records = parse_metadata(METADATA_PATH)
    logging.info(f"Loaded {len(records)} records from metadata.csv.")

    # 3. Match metadata records with actual wav file paths
    matched_items = []
    for record in records:
        audio_file_rel = record.get("audio_file", "")  # e.g. "audio/RB_0001.wav"
        filename = os.path.basename(audio_file_rel)  # e.g. "RB_0001.wav"

        if filename in local_wav_map:
            file_path = local_wav_map[filename]
            matched_items.append((record, file_path))
        else:
            logging.warning(
                f"File {filename} (ID: {record['audio_id']}) listed in metadata.csv but NOT found under {RIYADBANK_DIR}"
            )

    logging.info(f"Matched {len(matched_items)} files for execution.")

    if limit is not None and limit > 0:
        matched_items = matched_items[:limit]
        logging.info(f"Limiting execution to the first {limit} matched files.")

    if not matched_items:
        logging.error("No matching audio files to process. Exiting.")
        return

    # Instantiate the standard Requests session and tasks list
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {SONIOX_API_KEY}"
    tasks = [
        transcribe_and_evaluate_single(session, record, file_path)
        for record, file_path in matched_items
    ]

    # 4. Gather Async tasks with concurrency limit and real-time progress saving
    logging.info(
        f"Spawning {len(tasks)} parallel worker pipelines (Max concurrency: {CONCURRENCY_LIMIT})..."
    )

    results = []
    completed_count = 0

    try:
        for coro in asyncio.as_completed(tasks):
            res = await coro
            results.append(res)
            completed_count += 1

            # Real-time progress logging
            percent = (completed_count / len(tasks)) * 100
            success_count = sum(1 for r in results if r["status"] == "success")
            failed_count = completed_count - success_count
            logging.info(
                f"==> [PROGRESS] {completed_count}/{len(tasks)} ({percent:.1f}%) "
                f"| Active: {len(tasks) - completed_count} "
                f"| Success: {success_count} | Failed: {failed_count}"
            )
    except (KeyboardInterrupt, asyncio.CancelledError):
        logging.warning(
            "\n[INTERRUPTED] Execution interrupted by user! Initiating safe saving of partial results..."
        )
    except Exception as e:
        logging.error(f"\n[ERROR] Unexpected batch run failure: {e}")
    finally:
        if not results:
            logging.warning("No transcription results collected to save.")
            return

        # 5. Compile evaluation stats and write CSV output (inside finally to guarantee saving on exit)
        success_count = sum(1 for r in results if r["status"] == "success")
        failed_count = len(results) - success_count

        logging.info(f"Saving {len(results)} collected records to CSV...")
        fieldnames = [
            "audio_id",
            "category",
            "human_label",
            "asr_transcript",
            "normalized_human",
            "normalized_asr",
            "wer",
            "sub",
            "del",
            "ins",
            "ref_word_count",
            "status",
            "error_message",
        ]

        with open(CSV_OUTPUT_PATH, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                # Format WER as float or leave empty on failure
                row = {**r}
                if r["wer"] is not None:
                    row["wer"] = f"{r['wer']:.4f}"
                writer.writerow(row)

        logging.info(f"Results saved to: {CSV_OUTPUT_PATH}")

        # Category-wise Stats Compilation
        categories = {}
        total_words_global = 0
        total_wer_distance_global = 0

        for r in results:
            if r["status"] == "success":
                cat = r["category"]
                if cat not in categories:
                    categories[cat] = {
                        "words": 0,
                        "dist": 0,
                        "count": 0,
                        "total_wer_sum": 0.0,
                    }

                categories[cat]["words"] += r["ref_word_count"]
                categories[cat]["dist"] += r["sub"] + r["del"] + r["ins"]
                categories[cat]["count"] += 1
                categories[cat]["total_wer_sum"] += r["wer"]

                total_words_global += r["ref_word_count"]
                total_wer_distance_global += r["sub"] + r["del"] + r["ins"]

        global_wer = (
            total_wer_distance_global / total_words_global
            if total_words_global > 0
            else 0.0
        )

        # Print beautiful performance report
        logging.info("\n" + "=" * 60)
        logging.info(
            "================ RIYADBANK BATCH EVALUATION REPORT ================"
        )
        logging.info("=" * 60)
        logging.info(
            f"Timestamp:              {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        logging.info(f"Latest Soniox Model:    {BATCH_CONFIG['model']}")
        logging.info(f"Total Processed Files:  {len(results)}")
        logging.info(f"  - Success:            {success_count}")
        logging.info(f"  - Failed/Error:       {failed_count}")
        logging.info(
            f"Global Word Error Rate: {global_wer:.2%} ({total_wer_distance_global}/{total_words_global} words)"
        )
        logging.info("-" * 60)
        logging.info("CATEGORY-WISE EVALUATION DETAIL:")
        logging.info("-" * 60)

        for cat, stats in categories.items():
            cat_wer = stats["dist"] / stats["words"] if stats["words"] > 0 else 0.0
            avg_wer = (
                stats["total_wer_sum"] / stats["count"] if stats["count"] > 0 else 0.0
            )
            logging.info(
                f"Category: {cat:<20} | Files: {stats['count']:<4} | Global Category WER: {cat_wer:.2%} | Avg File WER: {avg_wer:.2%}"
            )

        logging.info("=" * 60 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Soniox Batch Transcriber and Evaluator for RiyadBank"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of processed files for a quick test",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=8,
        help="Max concurrent transcription pipelines",
    )
    args = parser.parse_args()

    asyncio.run(main_async(args.limit, args.concurrency))
