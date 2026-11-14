"""Integration tests for F-066: Error model & limits, and F-003 colormaps."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from earth_jukebox.bootstrap import build_app, build_settings
from earth_jukebox.domain.errors import (
    InvalidImageError,
    JukeboxError,
    RecoveryError,
)
from earth_jukebox.infrastructure.vision.synthetic import generate_map


def _make_client(tmp_path: Path, raise_server_exceptions: bool = True) -> TestClient:
    settings = build_settings(tmp_path)
    return TestClient(build_app(settings), raise_server_exceptions=raise_server_exceptions)


def test_f066_ac_each_error_class_status_and_code(tmp_path: Path) -> None:
    # F-066 AC: each error class has a test asserting status + code
    client = _make_client(tmp_path)
    png_bytes, _field, _leg, _cbox, _mbox = generate_map(cmap="viridis", seed=1)

    # 1. NotFoundError -> 404, "not_found"
    r_not_found = client.get("/api/samples/nonexistent")
    assert r_not_found.status_code == 404
    assert r_not_found.headers["content-type"].startswith("application/problem+json")
    prob = r_not_found.json()
    assert prob["code"] == "not_found"
    assert prob["status"] == 404
    assert prob["title"] == "Not Found"
    assert "request_id" in prob
    assert r_not_found.headers["X-Request-Id"] == prob["request_id"]

    # 2. InvalidLegendError -> 422, "invalid_legend"
    files = {"image": ("test.png", png_bytes, "image/png")}
    data = {"legend": "invalid json string {"}
    r_bad_legend = client.post("/api/analyze", files=files, data=data)
    assert r_bad_legend.status_code == 422
    assert r_bad_legend.json()["code"] == "invalid_legend"

    # 3. InvalidImageError (general) -> 422, "invalid_image"
    with patch(
        "earth_jukebox.infrastructure.vision.decoder.PillowImageDecoder.decode",
        side_effect=InvalidImageError("general image error"),
    ):
        r_img_err = client.post(
            "/api/analyze",
            files={"image": ("test.png", png_bytes, "image/png")},
            data={"legend": '{"vmin": 0, "vmax": 1, "units": ""}'},
        )
        assert r_img_err.status_code == 422
        assert r_img_err.json()["code"] == "invalid_image"

    # 4. InvalidImageError (oversize) -> 413, "invalid_image"
    with patch(
        "earth_jukebox.infrastructure.vision.decoder.PillowImageDecoder.decode",
        side_effect=InvalidImageError("image upload exceeds maximum size of 20971520 bytes"),
    ):
        r_size_err = client.post(
            "/api/analyze",
            files={"image": ("test.png", png_bytes, "image/png")},
            data={"legend": '{"vmin": 0, "vmax": 1, "units": ""}'},
        )
        assert r_size_err.status_code == 413
        assert r_size_err.json()["code"] == "invalid_image"

    # 5. InvalidImageError (unsupported format) -> 415, "invalid_image"
    with patch(
        "earth_jukebox.infrastructure.vision.decoder.PillowImageDecoder.decode",
        side_effect=InvalidImageError("unsupported image format 'TIFF'"),
    ):
        r_type_err = client.post(
            "/api/analyze",
            files={"image": ("test.tiff", png_bytes, "image/tiff")},
            data={"legend": '{"vmin": 0, "vmax": 1, "units": ""}'},
        )
        assert r_type_err.status_code == 415
        assert r_type_err.json()["code"] == "invalid_image"

    # 6. RecoveryError -> 422, "recovery_failed"
    with patch(
        "earth_jukebox.infrastructure.vision.recoverer.VisionFieldRecoverer.recover",
        side_effect=RecoveryError("recovery failed due to unresolvable colorbar"),
    ):
        r_rec_err = client.post(
            "/api/analyze",
            files={"image": ("test.png", png_bytes, "image/png")},
            data={"legend": '{"vmin": 0, "vmax": 1, "units": ""}'},
        )
        assert r_rec_err.status_code == 422
        assert r_rec_err.json()["code"] == "recovery_failed"

    # 7. Base JukeboxError -> 422, "jukebox_error"
    with patch(
        "earth_jukebox.infrastructure.vision.decoder.PillowImageDecoder.decode",
        side_effect=JukeboxError("arbitrary domain error"),
    ):
        r_base_err = client.post(
            "/api/analyze",
            files={"image": ("test.png", png_bytes, "image/png")},
            data={"legend": '{"vmin": 0, "vmax": 1, "units": ""}'},
        )
        assert r_base_err.status_code == 422
        assert r_base_err.json()["code"] == "jukebox_error"


def test_f066_unhandled_exception_returns_500_without_traceback(tmp_path: Path) -> None:
    # F-066: no tracebacks to clients; request-id header present
    client = _make_client(tmp_path, raise_server_exceptions=False)
    png_bytes, _field, _leg, _cbox, _mbox = generate_map(cmap="viridis", seed=1)

    with patch(
        "earth_jukebox.infrastructure.vision.decoder.PillowImageDecoder.decode",
        side_effect=RuntimeError("secret internal database failure"),
    ):
        r = client.post(
            "/api/analyze",
            files={"image": ("test.png", png_bytes, "image/png")},
            data={"legend": '{"vmin": 0, "vmax": 1, "units": ""}'},
        )
        assert r.status_code == 500
        assert r.headers["content-type"].startswith("application/problem+json")
        prob = r.json()
        assert prob["code"] == "internal_error"
        assert prob["status"] == 500
        # Must NOT leak exception message or traceback to client
        assert "secret internal database failure" not in prob["detail"]
        assert "Traceback" not in r.text
        assert "X-Request-Id" in r.headers
        assert r.headers["X-Request-Id"] == prob["request_id"]


def test_f003_colormaps_endpoint(tmp_path: Path) -> None:
    # F-003: GET /api/colormaps returns preset catalog with kind
    client = _make_client(tmp_path)
    r = client.get("/api/colormaps")
    assert r.status_code == 200
    cmaps = r.json()
    assert isinstance(cmaps, list)
    assert len(cmaps) >= 19

    names = {c["name"] for c in cmaps}
    assert "viridis" in names
    assert "turbo" in names
    assert "RdBu_r" in names

    viridis_entry = next(c for c in cmaps if c["name"] == "viridis")
    assert viridis_entry["kind"] == "sequential"

    rdbu_entry = next(c for c in cmaps if c["name"] == "RdBu_r")
    assert rdbu_entry["kind"] == "diverging"
