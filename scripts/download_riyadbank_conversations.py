"""Download RiyadBank conversation histories and call recordings."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

LOGGER = logging.getLogger(__name__)
BASE_URL = "https://voiceagent-saudi.dyna.ai/voiceagent-op"
DEFAULT_OUTPUT_DIR = Path("benchmarks/RiyadBankConversation")
MAX_CONCURRENCY = 10
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class DownloadConfig:
    """Runtime settings for the RiyadBank data export."""

    session_id: str
    client_id: str
    company_id: int
    create_start: str
    create_end: str
    output_dir: Path
    concurrency: int
    timeout: float


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company-id", type=int, default=1018)
    parser.add_argument("--create-start", default="2026-08-15 00:00:00")
    parser.add_argument("--create-end", default="2026-09-14 23:59:59")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=60.0)
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> DownloadConfig:
    """Build and validate configuration from arguments and environment.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Validated download configuration.

    Raises:
        ValueError: If credentials or concurrency settings are invalid.
    """
    session_id = os.environ.get("VOICE_AGENT_SESSION_ID", "").strip()
    client_id = os.environ.get("VOICE_AGENT_CLIENT_ID", "").strip()
    if not session_id or not client_id:
        raise ValueError(
            "VOICE_AGENT_SESSION_ID and VOICE_AGENT_CLIENT_ID must be set"
        )
    if not 1 <= args.concurrency <= MAX_CONCURRENCY:
        raise ValueError(f"concurrency must be between 1 and {MAX_CONCURRENCY}")
    if args.timeout <= 0:
        raise ValueError("timeout must be greater than zero")
    return DownloadConfig(
        session_id=session_id,
        client_id=client_id,
        company_id=args.company_id,
        create_start=args.create_start,
        create_end=args.create_end,
        output_dir=args.output_dir,
        concurrency=args.concurrency,
        timeout=args.timeout,
    )


def build_headers(config: DownloadConfig) -> dict[str, str]:
    """Create common request headers without logging credentials.

    Args:
        config: Validated download configuration.

    Returns:
        HTTP headers required by the platform.
    """
    return {
        "Accept": "application/json, text/plain, */*",
        "AiLanguage": "en_US",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://voiceagent-saudi.dyna.ai/voice-admin/login",
        "User-Agent": "Mozilla/5.0",
        "apiCode": str(config.company_id),
        "sessionId": config.session_id,
        "voigpt-client-id": config.client_id,
    }


async def fetch_records(
    client: httpx.AsyncClient, config: DownloadConfig
) -> list[dict[str, Any]]:
    """Fetch all matching conversation records in one page.

    Args:
        client: Authenticated asynchronous HTTP client.
        config: Validated download configuration.

    Returns:
        Conversation records returned by the platform.

    Raises:
        RuntimeError: If the platform response is unsuccessful or incomplete.
        httpx.HTTPError: If the request fails.
    """
    response = await client.post(
        "/global/inbound/caseLog/list",
        data={
            "companyId": config.company_id,
            "useLlm": 1,
            "currentPage": 1,
            "pageSize": 100,
            "createStart": config.create_start,
            "createEnd": config.create_end,
        },
        timeout=config.timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != "000000":
        raise RuntimeError(f"list request failed: {payload.get('message', 'unknown error')}")
    data = payload.get("data") or {}
    records = data.get("records") or []
    total = data.get("total")
    if total != len(records):
        raise RuntimeError(
            f"expected all records in one page, but received {len(records)} of {total}"
        )
    return records


async def save_stream(
    response: httpx.Response, destination: Path
) -> Path:
    """Stream a response to an atomically completed local file.

    Args:
        response: Open streaming response.
        destination: Final destination path including the verified extension.

    Returns:
        Final downloaded file path.
    """
    if destination.exists() and destination.stat().st_size > 0:
        return destination
    temporary = destination.with_suffix(f"{destination.suffix}.part")
    with temporary.open("wb") as output:
        async for chunk in response.aiter_bytes(CHUNK_SIZE):
            output.write(chunk)
    temporary.replace(destination)
    return destination


async def download_recording(
    client: httpx.AsyncClient,
    source_path: str,
    destination: Path,
    config: DownloadConfig,
    semaphore: asyncio.Semaphore,
) -> Path:
    """Download one recording from a platform storage path.

    Args:
        client: Authenticated asynchronous HTTP client.
        source_path: Server-side recording path from the list response.
        destination: Final destination path using the verified audio format.
        config: Validated download configuration.
        semaphore: Global request concurrency limiter.

    Returns:
        Final downloaded recording path.

    Raises:
        httpx.HTTPError: If the request fails.
    """
    if destination.exists() and destination.stat().st_size > 0:
        return destination
    async with semaphore:
        async with client.stream(
            "GET",
            "/voigpt/recording",
            params={"path": source_path},
            timeout=config.timeout,
        ) as response:
            response.raise_for_status()
            return await save_stream(response, destination)


async def download_history(
    client: httpx.AsyncClient,
    log_id: int,
    destination: Path,
    config: DownloadConfig,
    semaphore: asyncio.Semaphore,
) -> Path:
    """Download one conversation history export.

    Args:
        client: Authenticated asynchronous HTTP client.
        log_id: Log identifier from the list response.
        destination: Final XLSX destination path.
        config: Validated download configuration.
        semaphore: Global request concurrency limiter.

    Returns:
        Final downloaded history path.

    Raises:
        httpx.HTTPError: If the request fails.
    """
    if destination.exists() and destination.stat().st_size > 0:
        return destination
    async with semaphore:
        async with client.stream(
            "POST",
            "/global/inbound/caseLog/downloadLogDetail",
            data={"logId": log_id, "companyId": config.company_id},
            timeout=config.timeout,
        ) as response:
            response.raise_for_status()
            if "spreadsheet" not in response.headers.get("content-type", "").lower():
                body = (await response.aread()).decode("utf-8", errors="replace")
                raise RuntimeError(f"history {log_id} returned an invalid response: {body}")
            return await save_stream(response, destination)


async def download_one(
    client: httpx.AsyncClient,
    record: dict[str, Any],
    config: DownloadConfig,
    semaphore: asyncio.Semaphore,
) -> tuple[int, list[Path]]:
    """Download all three artifacts for one conversation.

    Args:
        client: Authenticated asynchronous HTTP client.
        record: One list response record.
        config: Validated download configuration.
        semaphore: Global concurrency limiter.

    Returns:
        Log identifier and downloaded paths.

    Raises:
        ValueError: If required record fields are missing.
    """
    log_id = int(record["logId"])
    recording_url = str(record.get("recordingUrl") or "")
    user_recording_url = str(record.get("userPcmRecordUrl") or "")
    if not recording_url or not user_recording_url:
        raise ValueError(f"record {log_id} is missing a recording path")

    paths = await asyncio.gather(
        download_history(
            client,
            log_id,
            config.output_dir / "conversation_history" / f"{log_id}.xlsx",
            config,
            semaphore,
        ),
        download_recording(
            client,
            recording_url,
            config.output_dir / "record" / f"{log_id}.mp3",
            config,
            semaphore,
        ),
        download_recording(
            client,
            user_recording_url,
            config.output_dir / "user_record" / f"{log_id}.wav",
            config,
            semaphore,
        ),
    )
    return log_id, list(paths)


async def run(config: DownloadConfig) -> None:
    """Fetch the record list and download every artifact.

    Args:
        config: Validated download configuration.

    Raises:
        RuntimeError: If one or more records fail to download.
    """
    for directory in ("conversation_history", "record", "user_record"):
        (config.output_dir / directory).mkdir(parents=True, exist_ok=True)

    limits = httpx.Limits(
        max_connections=config.concurrency,
        max_keepalive_connections=config.concurrency,
    )
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers=build_headers(config),
        limits=limits,
        follow_redirects=True,
        timeout=config.timeout,
    ) as client:
        records = await fetch_records(client, config)
        LOGGER.info("Found %d conversations", len(records))
        semaphore = asyncio.Semaphore(config.concurrency)
        results = await asyncio.gather(
            *(download_one(client, record, config, semaphore) for record in records),
            return_exceptions=True,
        )

    failures = [result for result in results if isinstance(result, BaseException)]
    completed = len(results) - len(failures)
    LOGGER.info("Completed %d/%d conversations", completed, len(results))
    if failures:
        for failure in failures:
            LOGGER.error("Download failed: %s", failure)
        raise RuntimeError(f"{len(failures)} conversations failed to download")


def main() -> None:
    """Run the command-line downloader."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        config = build_config(parse_args())
        asyncio.run(run(config))
    except (ValueError, RuntimeError, httpx.HTTPError) as exc:
        LOGGER.error("%s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
