"""FastAPI app factory. Receives already-wired Services; imports nothing from infrastructure."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

from earth_jukebox.application.services import Services
from earth_jukebox.presentation.api.errors import register_error_handlers
from earth_jukebox.presentation.api.routes_analyze import router as analyze_router
from earth_jukebox.presentation.api.routes_categories import router as categories_router
from earth_jukebox.presentation.api.routes_colormaps import router as colormaps_router
from earth_jukebox.presentation.api.routes_health import router as health_router
from earth_jukebox.presentation.api.routes_mapping import router as mapping_router
from earth_jukebox.presentation.api.routes_render import router as render_router
from earth_jukebox.presentation.api.routes_samples import router as samples_router
from earth_jukebox.presentation.api.routes_skins import router as skins_router
from earth_jukebox.presentation.api.routes_sonify import router as sonify_router


def create_app(services: Services) -> FastAPI:
    app = FastAPI(
        title="Earth Jukebox",
        description="Data recovery and sonification API for NASA Earth Information Center imagery.",
        version=services.version,
    )
    app.state.services = services

    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        req_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = req_id
        return response

    register_error_handlers(app)

    # API Routers
    app.include_router(health_router)
    app.include_router(mapping_router)
    app.include_router(skins_router)
    app.include_router(colormaps_router)
    app.include_router(analyze_router)
    app.include_router(sonify_router)
    app.include_router(render_router)
    app.include_router(samples_router)
    app.include_router(categories_router)

    web_dir = services.settings.web_dir
    if web_dir.is_dir():
        # Mounted last so /api/* routes win.
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")

    return app
