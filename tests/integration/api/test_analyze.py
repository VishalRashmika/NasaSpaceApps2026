"""Integration tests for F-061: Analyze endpoint and F-004 colorbar auto-detect."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from earth_jukebox.bootstrap import build_app, build_settings
from earth_jukebox.infrastructure.vision.synthetic import generate_map


def _make_client(tmp_path: Path) -> TestClient:
    settings = build_settings(tmp_path)
    return TestClient(build_app(settings))


def test_f061_ac1_success_path_synthetic_image(tmp_path: Path) -> None:
    # F-061 AC1: success path on synthetic image
    client = _make_client(tmp_path)
    png_bytes, _field, legend, cbox, mbox = generate_map(cmap="viridis", seed=42)

    legend_data = {
        "vmin": legend.vmin,
        "vmax": legend.vmax,
        "units": legend.units,
        "label": legend.label,
        "kind": legend.kind.value,
        "category": legend.category.value,
        "orientation": legend.orientation.value,
        "low_at_start": legend.low_at_start,
        "scale": legend.scale.value,
    }

    files = {"image": ("test.png", png_bytes, "image/png")}
    data = {
        "legend": json.dumps(legend_data),
        "colorbar_box": json.dumps({"x": cbox.x, "y": cbox.y, "w": cbox.w, "h": cbox.h}),
        "map_box": json.dumps({"x": mbox.x, "y": mbox.y, "w": mbox.w, "h": mbox.h}),
    }

    r = client.post("/api/analyze", files=files, data=data)
    assert r.status_code == 200, r.text
    res = r.json()

    assert "analysis_id" in res
    assert len(res["analysis_id"]) == 16
    assert res["quality"]["confidence"] >= 0.8
    assert res["quality"]["confidence_badge"] == "High"
    assert res["field_preview_png"].startswith("data:image/png;base64,")
    assert res["grid"]["rows"] > 0
    assert res["grid"]["cols"] > 0
    assert res["image"]["width"] > 0
    assert res["image"]["height"] > 0
    assert "X-Request-Id" in r.headers


def test_f061_ac1_preset_recovery_mode(tmp_path: Path) -> None:
    # F-061 AC1: preset recovery mode without colorbar box
    client = _make_client(tmp_path)
    png_bytes, _field, legend, _cbox, mbox = generate_map(cmap="viridis", seed=42)

    legend_data = {
        "vmin": legend.vmin,
        "vmax": legend.vmax,
        "units": legend.units,
        "label": legend.label,
        "kind": legend.kind.value,
    }

    files = {"image": ("test.png", png_bytes, "image/png")}
    data = {
        "legend": json.dumps(legend_data),
        "map_box": json.dumps({"x": mbox.x, "y": mbox.y, "w": mbox.w, "h": mbox.h}),
        "preset": "viridis",
    }

    r = client.post("/api/analyze", files=files, data=data)
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["quality"]["confidence"] > 0.0


def test_f061_ac1_invalid_legend_returns_problem_422(tmp_path: Path) -> None:
    # F-061 AC1: problem response for domain error invalid_legend with status 422
    client = _make_client(tmp_path)
    png_bytes, _field, _leg, _cbox, _mbox = generate_map(cmap="viridis", seed=1)

    files = {"image": ("test.png", png_bytes, "image/png")}
    # vmin > vmax invalid
    data = {"legend": json.dumps({"vmin": 100.0, "vmax": 0.0, "units": "K", "kind": "sequential"})}

    r = client.post("/api/analyze", files=files, data=data)
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    prob = r.json()
    assert prob["code"] == "invalid_legend"
    assert prob["status"] == 422
    assert "vmin must be < vmax" in prob["detail"]


def test_f061_ac1_corrupt_image_returns_problem_422(tmp_path: Path) -> None:
    # F-061 AC1: corrupt/truncated image bytes returns 422 problem response
    client = _make_client(tmp_path)
    png_bytes, _field, _leg, _cbox, _mbox = generate_map(cmap="viridis", seed=1)
    files = {"image": ("test.png", png_bytes[:150], "image/png")}
    data = {"legend": json.dumps({"vmin": 0.0, "vmax": 10.0, "units": "K", "kind": "sequential"})}

    r = client.post("/api/analyze", files=files, data=data)
    assert r.status_code == 422
    prob = r.json()
    assert prob["code"] == "invalid_image"
    assert "truncated" in prob["detail"].lower() or "corrupt" in prob["detail"].lower()


def test_f061_ac2_oversize_upload_returns_413(tmp_path: Path) -> None:
    # F-061 AC2: oversize upload -> 413 problem response
    client = _make_client(tmp_path)
    huge_data = b"0" * (20 * 1024 * 1024 + 1024)
    files = {"image": ("big.png", huge_data, "image/png")}
    data = {"legend": json.dumps({"vmin": 0.0, "vmax": 1.0, "units": "", "kind": "sequential"})}

    r = client.post("/api/analyze", files=files, data=data)
    assert r.status_code == 413
    assert r.headers["content-type"].startswith("application/problem+json")
    prob = r.json()
    assert prob["code"] == "invalid_image"
    assert prob["status"] == 413
    assert "exceeds maximum size" in prob["detail"]


def test_f061_ac2_wrong_media_type_returns_415(tmp_path: Path) -> None:
    # F-061 AC2: wrong format -> 415 problem response
    client = _make_client(tmp_path)
    # Valid BMP header (not in PNG/JPEG/WEBP/GIF)
    bmp_header = b"BM" + (54).to_bytes(4, "little") + b"\x00\x00\x00\x00\x36\x00\x00\x00"
    bmp_info = (40).to_bytes(4, "little") + (1).to_bytes(4, "little") + (1).to_bytes(4, "little")
    bmp_info += (1).to_bytes(2, "little") + (24).to_bytes(2, "little") + b"\x00" * 24
    bmp_bytes = bmp_header + bmp_info + b"\x00\x00\x00\x00"

    files = {"image": ("test.bmp", bmp_bytes, "image/bmp")}
    data = {"legend": json.dumps({"vmin": 0.0, "vmax": 1.0, "units": "", "kind": "sequential"})}

    r = client.post("/api/analyze", files=files, data=data)
    assert r.status_code == 415
    prob = r.json()
    assert prob["code"] == "invalid_image"
    assert prob["status"] == 415
    assert "unsupported" in prob["detail"].lower()


def test_f004_detect_colorbar_endpoint(tmp_path: Path) -> None:
    # Test POST /api/detect-colorbar returns candidates
    client = _make_client(tmp_path)
    png_bytes, _field, _leg, _cbox, _mbox = generate_map(cmap="viridis", seed=42)

    files = {"image": ("test.png", png_bytes, "image/png")}
    r = client.post("/api/detect-colorbar", files=files)
    assert r.status_code == 200
    res = r.json()
    assert "candidates" in res
    assert len(res["candidates"]) > 0
    top = res["candidates"][0]
    assert "box" in top
    assert "orientation" in top
    assert "score" in top
