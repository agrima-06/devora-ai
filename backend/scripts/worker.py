"""Devora AI Background Worker: runs scheduled recovery sweeps and handles async task processing."""
import asyncio
import os
import signal
import sys

# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.session import AsyncSessionLocal
from app.services.recovery_manager import WorkflowRecoveryManager

setup_logging()
logger = get_logger("background_worker")

running = True


def handle_shutdown(signum, frame):
    global running
    logger.info("worker_shutdown_signal_received", signal=signum)
    running = False


async def run_worker_loop():
    """Execute continuous periodic sweeps for interrupted workflows and recovery leases."""
    recovery_manager = WorkflowRecoveryManager()
    logger.info(
        "worker_started",
        environment=settings.ENVIRONMENT,
        recovery_enabled=settings.RECOVERY_ENABLED,
        heartbeat_timeout=settings.RECOVERY_HEARTBEAT_TIMEOUT_SECONDS,
    )

    while running:
        if settings.RECOVERY_ENABLED:
            try:
                async with AsyncSessionLocal() as db:
                    interrupted = await recovery_manager.scan_interrupted_tasks(db)
                    if interrupted:
                        logger.info("interrupted_tasks_detected", count=len(interrupted))
            except Exception as exc:
                logger.error("worker_sweep_error", error=str(exc))

        # Sleep with graceful interrupt checking
        for _ in range(30):
            if not running:
                break
            await asyncio.sleep(1)

    logger.info("worker_stopped_cleanly")


def main():
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    asyncio.run(run_worker_loop())


if __name__ == "__main__":
    main()
