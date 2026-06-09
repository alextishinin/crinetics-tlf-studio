"""FastAPI entrypoint.

  uvicorn main:app --reload --port 8000

All routers are mounted under /api/*. Service modules read configuration
from the Settings singleton in config.py.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import APP_VERSION, get_settings
from routers import ai, jobs, outputs, preview, settings as settings_router, shells, studies


def create_app() -> FastAPI:
    settings = get_settings()  # primes sys.path for the tlf library

    app = FastAPI(
        title="TLF Studio API",
        version=APP_VERSION,
        description="Internal API for Crinetics TLF Studio.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(studies.router)
    app.include_router(shells.router)
    app.include_router(jobs.router)
    app.include_router(preview.router)
    app.include_router(outputs.router)
    app.include_router(ai.router)
    app.include_router(settings_router.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "tlf-studio", "model": settings.anthropic_model}

    return app


app = create_app()
