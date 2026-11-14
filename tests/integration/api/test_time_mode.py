"""Integration tests for Time Mode API endpoints (F-090, F-091, F-092)."""

from __future__ import annotations

import io
import json

from fastapi.testclient import TestClient
from PIL import Image

from earth_jukebox.bootstrap import build_app


def _create_test_gif(n_frames: int = 3, size: tuple[int, int] = (64, 64)) -> bytes:
    frames = []
    for i in range(n_frames):
        color = (int(255 * i / max(1, n_frames - 1)), 80, 120)
        img = Image.new("RGB", size, color)
        frames.append(img)

    bio = io.BytesIO()
    frames[0].save(
        bio,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0,
    )
    return bio.getvalue()


def test_api_time_mode_pipeline() -> None:
    """Upload animated GIF -> analyze -> sonify -> render WAV."""
    app = build_app()
    client = TestClient(app)

    gif_bytes = _create_test_gif(n_frames=3)
    legend_json = json.dumps(
        {
            "vmin": 0.0,
            "vmax": 100.0,
            "units": "°C",
            "label": "Sea Surface Temperature",
            "kind": "sequential",
            "category": "temperature",
        }
    )

    # 1. POST /api/analyze
    resp = client.post(
        "/api/analyze",
        files={"image": ("anim.gif", gif_bytes, "image/gif")},
        data={"legend": legend_json, "preset": "viridis"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["is_animation"] is True
    assert data["n_frames"] == 3
    assert len(data["frame_previews"]) == 3
    analysis_id = data["analysis_id"]

    # 2. POST /api/sonify
    sonify_resp = client.post(
        "/api/sonify",
        json={"analysis_id": analysis_id, "skin": "neutral", "n_cols": 48},
    )
    assert sonify_resp.status_code == 200, sonify_resp.text
    son_data = sonify_resp.json()
    score = son_data["score"]

    # 3 frames * 48 beats + 2 rests * 1.0 = 146.0 beats
    assert score["total_beats"] == 146.0
    assert score["provenance"]["time_mode"] == "true"
    assert score["provenance"]["n_frames"] == "3"

    # 3. GET /api/render/wav
    wav_resp = client.get(f"/api/render/{analysis_id}.wav?skin=neutral&n_cols=48")
    assert wav_resp.status_code == 200
    assert wav_resp.headers["content-type"] == "audio/wav"
    assert len(wav_resp.content) > 1000  # valid wav header and PCM audio
