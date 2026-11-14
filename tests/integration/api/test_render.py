"""Integration tests for F-063: Render and download endpoints."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from earth_jukebox.bootstrap import build_app, build_settings
from earth_jukebox.infrastructure.vision.synthetic import generate_map


def _make_client(tmp_path: Path) -> TestClient:
    settings = build_settings(tmp_path)
    return TestClient(build_app(settings))


def _analyze_image(client: TestClient) -> str:
    png_bytes, _field, legend, cbox, mbox = generate_map(cmap="viridis", seed=42)
    legend_data = {
        "vmin": legend.vmin,
        "vmax": legend.vmax,
        "units": legend.units,
        "label": legend.label,
        "kind": legend.kind.value,
        "category": legend.category.value,
    }
    files = {"image": ("test.png", png_bytes, "image/png")}
    data = {
        "legend": json.dumps(legend_data),
        "colorbar_box": json.dumps({"x": cbox.x, "y": cbox.y, "w": cbox.w, "h": cbox.h}),
        "map_box": json.dumps({"x": mbox.x, "y": mbox.y, "w": mbox.w, "h": mbox.h}),
    }
    r = client.post("/api/analyze", files=files, data=data)
    assert r.status_code == 200
    aid: str = r.json()["analysis_id"]
    return aid


def test_f063_ac_render_wav_success(tmp_path: Path) -> None:
    # F-063 AC: correct Content-Type; WAV header valid; Cache-Control set
    client = _make_client(tmp_path)
    aid = _analyze_image(client)

    r = client.get(f"/api/render/{aid}.wav?skin=neutral&n_cols=32")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/wav")
    assert "Cache-Control" in r.headers
    assert "public" in r.headers["Cache-Control"]
    assert "max-age" in r.headers["Cache-Control"]

    # Validate RIFF WAVE header
    content = r.content
    assert len(content) > 44
    assert content[:4] == b"RIFF"
    assert content[8:12] == b"WAVE"
    assert content[12:16] == b"fmt "


def test_f063_ac_render_midi_success(tmp_path: Path) -> None:
    # F-063 AC: MIDI export
    client = _make_client(tmp_path)
    aid = _analyze_image(client)

    r = client.get(f"/api/render/{aid}.mid?skin=neutral&n_cols=32")
    assert r.status_code == 200
    assert "audio/midi" in r.headers["content-type"]
    assert "Cache-Control" in r.headers

    # Validate MIDI MThd header
    content = r.content
    assert len(content) > 14
    assert content[:4] == b"MThd"


def test_f063_ac_render_json_success(tmp_path: Path) -> None:
    # F-063 AC: Score JSON download
    client = _make_client(tmp_path)
    aid = _analyze_image(client)

    r = client.get(f"/api/render/{aid}.json?skin=neutral&n_cols=32")
    assert r.status_code == 200
    assert "application/json" in r.headers["content-type"]
    assert "Cache-Control" in r.headers

    score = r.json()
    assert score["schema"] == "earth-jukebox.score/1"
    assert "notes" in score


def test_f063_ac_legend_sound_wav_success(tmp_path: Path) -> None:
    # F-063 AC: Audio legend sweep WAV
    client = _make_client(tmp_path)
    aid = _analyze_image(client)

    r = client.get(f"/api/legend-sound/{aid}.wav?skin=neutral")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/wav")
    assert "Cache-Control" in r.headers

    content = r.content
    assert len(content) > 44
    assert content[:4] == b"RIFF"
    assert content[8:12] == b"WAVE"


def test_f063_ac_unknown_id_returns_404(tmp_path: Path) -> None:
    # F-063 AC: unknown id -> 404 problem response
    client = _make_client(tmp_path)
    unknown_id = "deadbeef12345678"

    for path in [
        f"/api/render/{unknown_id}.wav",
        f"/api/render/{unknown_id}.mid",
        f"/api/render/{unknown_id}.json",
        f"/api/legend-sound/{unknown_id}.wav",
    ]:
        r = client.get(path)
        assert r.status_code == 404
        assert r.headers["content-type"].startswith("application/problem+json")
        prob = r.json()
        assert prob["code"] == "not_found"


def test_f044_render_mp3_returns_501_when_unavailable(tmp_path: Path) -> None:
    # F-044 AC: absent ffmpeg -> graceful 501-style problem response, no crash
    from dataclasses import replace

    from earth_jukebox.bootstrap import build_services
    from earth_jukebox.presentation.api.app import create_app

    settings = build_settings(tmp_path)
    base_services = build_services(settings)
    # Simulate unavailable ffmpeg
    services = replace(base_services, mp3_exporter=None)
    client = TestClient(create_app(services))
    aid = _analyze_image(client)

    r = client.get(f"/api/render/{aid}.mp3")
    assert r.status_code == 501
    prob = r.json()
    assert prob["code"] == "not_implemented"


def test_f044_render_mp3_success(tmp_path: Path) -> None:
    # F-044 AC: if ffmpeg on PATH, convert WAV -> MP3
    import shutil

    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed on system")

    client = _make_client(tmp_path)
    aid = _analyze_image(client)

    r = client.get(f"/api/render/{aid}.mp3?skin=neutral&n_cols=32")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/mpeg")
    assert "Cache-Control" in r.headers
    assert "public" in r.headers["Cache-Control"]
    assert f'filename="earth_jukebox_{aid}.mp3"' in r.headers.get("Content-Disposition", "")
    assert len(r.content) > 0
    is_id3 = r.content.startswith(b"ID3")
    is_sync = r.content[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")
    assert is_id3 or is_sync
