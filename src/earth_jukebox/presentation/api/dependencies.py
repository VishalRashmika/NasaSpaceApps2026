"""Dependencies for FastAPI endpoints."""

from __future__ import annotations

from fastapi import Request

from earth_jukebox.application.services import Services


def get_services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services
