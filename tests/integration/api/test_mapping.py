"""Integration tests for F-064: Mapping endpoint."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from earth_jukebox.bootstrap import build_app, build_settings
from earth_jukebox.domain.mapping_version import MAPPING_VERSION


def _make_client(tmp_path: Path) -> TestClient:
    settings = build_settings(tmp_path)
    return TestClient(build_app(settings))


def test_f064_mapping_manifest(tmp_path: Path) -> None:
    # F-064: GET /api/mapping -> F-033 manifest
    client = _make_client(tmp_path)
    r = client.get("/api/mapping")
    assert r.status_code == 200
    res = r.json()

    assert res["mapping_version"] == MAPPING_VERSION
    assert "mappings" in res
    assert "value->pitch" in res["mappings"]
    assert "longitude->time" in res["mappings"]
    assert "latitude_band->voice_pan" in res["mappings"]
    assert "local_variability->rhythm_density" in res["mappings"]
    assert "local_variability->roughness" in res["mappings"]
    assert "global_variability->tempo" in res["mappings"]
    assert "extremes->accent" in res["mappings"]
    assert "masked->silence" in res["mappings"]
    assert res["n_bands_default"] == 5
    assert res["n_octaves"] == 2
