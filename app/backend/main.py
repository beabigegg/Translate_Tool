"""FastAPI entry point."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.backend.api.routes import router
from app.backend.config import ALLOWED_ORIGINS, DEFAULT_HOST, DEFAULT_PORT, LOG_DIR
from app.backend.utils.font_utils import get_font_check_message
from app.backend.utils.logging_utils import setup_logging

logger = logging.getLogger(__name__)

app = FastAPI(title="Translate Tool API")

setup_logging(LOG_DIR)

# Check for required fonts at startup
_font_warning = get_font_check_message()
if _font_warning:
    logger.warning(_font_warning)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

# Serve frontend build if present
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


def run() -> None:
    import uvicorn

    uvicorn.run(app, host=DEFAULT_HOST, port=DEFAULT_PORT)


if __name__ == "__main__":
    run()
