"""Integration tests for F-065: Jukebox catalog endpoints."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from earth_jukebox.bootstrap import build_app, build_settings
from earth_jukebox.infrastructure.vision.synthetic import generate_map


def _make_client(tmp_path: Path) -> TestClient:
    settings = build_settings(tmp_path)
    return TestClient(build_app(settings))


def test_f065_ac1_zero_samples(tmp_path: Path) -> None:
    # F-065 AC1: with zero samples -> []
    client = _make_client(tmp_path)
    r = client.get("/api/samples")
    assert r.status_code == 200
    assert r.json() == []


def test_f065_ac2_invalid_id_pattern_returns_404(tmp_path: Path) -> None:
    # F-065 AC2: invalid id pattern -> 404, never touches filesystem outside data/samples
    client = _make_client(tmp_path)

    invalid_ids = [
        "../secret",
        "../../etc/passwd",
        "INVALID_UPPERCASE",
        "/absolute/path",
        "has spaces",
        "-badstart",
    ]

    for bad_id in invalid_ids:
        r_meta = client.get(f"/api/samples/{bad_id}")
        assert r_meta.status_code == 404
        assert r_meta.json()["code"] == "not_found"

        r_img = client.get(f"/api/samples/{bad_id}/image")
        assert r_img.status_code == 404
        assert r_img.json()["code"] == "not_found"

        r_ana = client.post(f"/api/samples/{bad_id}/analyze")
        assert r_ana.status_code == 404
        assert r_ana.json()["code"] == "not_found"


def test_f065_with_sample_entry(tmp_path: Path) -> None:
    # Test catalog endpoints with a valid synthetic sample manifest
    samples_dir = tmp_path / "data" / "samples" / "sample01"
    samples_dir.mkdir(parents=True, exist_ok=True)

    png_bytes, _field, legend, cbox, mbox = generate_map(cmap="viridis", seed=42)
    (samples_dir / "image.png").write_bytes(png_bytes)

    meta = {
        "id": "sample01",
        "title": "Global Surface Temperature Anomaly",
        "image_file": "image.png",
        "legend": {
            "vmin": legend.vmin,
            "vmax": legend.vmax,
            "units": legend.units,
            "label": legend.label,
            "kind": legend.kind.value,
            "category": legend.category.value,
            "center": legend.center,
            "orientation": legend.orientation.value,
            "low_at_start": legend.low_at_start,
            "scale": legend.scale.value,
        },
        "extent": {
            "lat_min": -90.0,
            "lat_max": 90.0,
            "lon_min": -180.0,
            "lon_max": 180.0,
            "projection": "equirectangular",
        },
        "map_box": {"x": mbox.x, "y": mbox.y, "w": mbox.w, "h": mbox.h},
        "colorbar_box": {"x": cbox.x, "y": cbox.y, "w": cbox.w, "h": cbox.h},
        "source_url": "https://svs.gsfc.nasa.gov/12345",
        "credit": "NASA Scientific Visualization Studio",
        "description": "Temperature visualization frame.",
        "in_gallery": True,
    }
    (samples_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    client = _make_client(tmp_path)

    # 1. GET /api/samples
    r_list = client.get("/api/samples")
    assert r_list.status_code == 200
    sample_list = r_list.json()
    assert len(sample_list) == 1
    item = sample_list[0]
    assert item["id"] == "sample01"
    assert item["title"] == "Global Surface Temperature Anomaly"
    assert item["thumb_url"] == "/api/samples/sample01/image"

    # 2. GET /api/samples/{id}
    r_meta = client.get("/api/samples/sample01")
    assert r_meta.status_code == 200
    meta_res = r_meta.json()
    assert meta_res["id"] == "sample01"
    assert meta_res["credit"] == "NASA Scientific Visualization Studio"
    assert meta_res["legend"]["kind"] == "sequential"

    # 3. GET /api/samples/{id}/image
    r_img = client.get("/api/samples/sample01/image")
    assert r_img.status_code == 200
    assert r_img.headers["content-type"] == "image/png"
    assert r_img.content == png_bytes

    # 4. POST /api/samples/{id}/analyze
    r_ana = client.post("/api/samples/sample01/analyze")
    assert r_ana.status_code == 200
    ana_res = r_ana.json()
    assert "analysis_id" in ana_res
    assert ana_res["quality"]["confidence"] >= 0.8
    assert ana_res["grid"]["rows"] > 0
    assert ana_res["field_preview_png"].startswith("data:image/png;base64,")
