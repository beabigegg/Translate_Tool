"""FastAPI entry point."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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

# Serve frontend build if present (SPA mode: index.html for all non-API routes)
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    # Mount /assets first so Vite's hashed bundles are served as static files
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # Catch-all: React Router handles client-side routing, so every non-API,
    # non-asset path must return index.html (Starlette 1.x StaticFiles(html=True)
    # does NOT fall back to index.html for unknown paths — it 404s instead).
    _spa_index = frontend_dist / "index.html"

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> FileResponse:
        return FileResponse(str(_spa_index))


def run() -> None:
    import uvicorn

    uvicorn.run(app, host=DEFAULT_HOST, port=DEFAULT_PORT)


if __name__ == "__main__":
    run()
