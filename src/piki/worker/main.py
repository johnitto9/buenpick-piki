import argparse
import asyncio
import os
import signal
import time
from pathlib import Path

from piki.conversation.worker import (
    ConversationProcessingWorker,
    create_processing_worker,
)
from piki.core.config import Settings, get_settings
from piki.core.logging import configure_logging, get_logger


async def run_worker(settings: Settings) -> None:
    configure_logging(settings.log_level)
    logger = get_logger(service="piki-worker")
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, stop_event.set)

    heartbeat = Path(settings.worker_heartbeat_path)
    processor: ConversationProcessingWorker | None = None
    if settings.conversation_worker_enabled:
        processor = create_processing_worker(settings)
    logger.info("worker_started")
    try:
        while not stop_event.is_set():
            await asyncio.to_thread(heartbeat.touch)
            if processor is not None and await processor.process_once():
                continue
            wait_seconds = (
                settings.conversation_worker_poll_seconds
                if processor is not None
                else settings.worker_heartbeat_seconds
            )
            try:
                await asyncio.wait_for(
                    stop_event.wait(), timeout=wait_seconds
                )
            except TimeoutError:
                continue
    finally:
        if processor is not None:
            await processor.close()
        await asyncio.to_thread(heartbeat.unlink, missing_ok=True)
        logger.info("worker_stopped")


def heartbeat_is_fresh(settings: Settings) -> bool:
    heartbeat = Path(settings.worker_heartbeat_path)
    if not heartbeat.exists():
        return False
    max_age = settings.worker_heartbeat_seconds * 3
    return (time.time() - heartbeat.stat().st_mtime) <= max_age


def main() -> None:
    parser = argparse.ArgumentParser(prog="piki-worker")
    parser.add_argument("--check", action="store_true", help="check worker heartbeat")
    args = parser.parse_args()
    settings = get_settings()
    if args.check:
        raise SystemExit(os.EX_OK if heartbeat_is_fresh(settings) else 1)
    asyncio.run(run_worker(settings))


if __name__ == "__main__":
    main()
