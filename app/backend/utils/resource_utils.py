"""Resource release utilities."""

from __future__ import annotations

import atexit
import gc
from typing import Callable, Optional

from app.backend.clients.ollama_client import OllamaClient
from app.backend.utils.logging_utils import logger


def release_resources(
    client: Optional[OllamaClient] = None,
    log: Callable[[str], None] = lambda s: None,
) -> None:
    """Release resources after a job completes.

    Note: This does NOT close the shared HTTP session as it may be used by other jobs.
    The session is only closed during full application shutdown.
    """
    log("[CLEANUP] Releasing resources...")
    logger.info("Starting resource release")

    if client is not None:
        try:
            log(f"[CLEANUP] Unloading model {client.model}")
            ok, msg = client.unload_model()
            if ok:
                log("[CLEANUP] VRAM released")
                logger.info("VRAM released: %s", msg)
            else:
                log(f"[CLEANUP] VRAM release failed: {msg}")
                logger.warning("Failed to release VRAM: %s", msg)
        except Exception as exc:
            log(f"[CLEANUP] VRAM release error: {exc}")
            logger.error("Error during model unload: %s", exc)

    try:
        collected = gc.collect()
        log("[CLEANUP] Python memory collected")
        logger.info("Python gc collected %s objects", collected)
    except Exception as exc:
        logger.error("Error during gc.collect(): %s", exc)

    log("[CLEANUP] Resource release complete")
    logger.info("Resource release completed")


def full_shutdown_cleanup() -> None:
    """Perform full cleanup on application shutdown.

    This closes shared resources like HTTP connection pools.
    Should only be called during application shutdown.
    """
    logger.info("Performing full shutdown cleanup")

    # Close shared HTTP session
    try:
        OllamaClient.close_session()
        logger.info("Closed HTTP session pool")
    except Exception as exc:
        logger.error("Error closing HTTP session: %s", exc)

    # Force garbage collection
    try:
        collected = gc.collect()
        logger.info("Final gc collected %s objects", collected)
    except Exception as exc:
        logger.error("Error during final gc.collect(): %s", exc)

    logger.info("Full shutdown cleanup completed")


# Register full cleanup on application exit
atexit.register(full_shutdown_cleanup)
