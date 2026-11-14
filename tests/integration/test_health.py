from __future__ import annotations

from fastapi.testclient import TestClient

from earth_jukebox.bootstrap import build_app
from earth_jukebox.domain.mapping_version import MAPPING_VERSION


def test_health_reports_versions() -> None:  # F-060
    client = TestClient(build_app())
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["mapping_version"] == MAPPING_VERSION


def test_static_shell_is_served() -> None:  # F-070 (stub)
    client = TestClient(build_app())
    r = client.get("/")
    assert r.status_code == 200
    assert "Earth Jukebox" in r.text
