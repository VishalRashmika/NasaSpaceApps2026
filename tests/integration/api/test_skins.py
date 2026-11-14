"""Integration tests for F-067 (Skins endpoint) and F-055 (Skin selection in API)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from earth_jukebox.bootstrap import build_app, build_settings
from earth_jukebox.infrastructure.vision.synthetic import generate_map


def _make_client(tmp_path: Path) -> TestClient:
    settings = build_settings(tmp_path)
    return TestClient(build_app(settings))


def _analyze_synthetic_image(client: TestClient) -> str:
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
    assert r.status_code == 200, r.text
    analysis_id: str = r.json()["analysis_id"]
    return analysis_id


def test_f067_skins_endpoint_lists_all_skins(tmp_path: Path) -> None:
    # F-067: GET /api/skins returns list of skins with scale_cents and description
    client = _make_client(tmp_path)
    r = client.get("/api/skins")
    assert r.status_code == 200
    skins = r.json()
    assert isinstance(skins, list)
    assert len(skins) >= 3

    skin_ids = [s["id"] for s in skins]
    assert "neutral" in skin_ids
    assert "hindustani" in skin_ids
    assert "sri_lankan" in skin_ids

    neutral = next(s for s in skins if s["id"] == "neutral")
    assert neutral["name"] == "Neutral (scientific)"
    assert neutral["provisional"] is False
    assert neutral["scale_cents"] == [0.0, 200.0, 400.0, 700.0, 900.0]
    assert "pentatonic" in neutral["description"].lower()

    hindustani = next(s for s in skins if s["id"] == "hindustani")
    assert hindustani["name"] == "Hindustani"
    assert hindustani["provisional"] is True
    assert hindustani["scale_cents"] == [0.0, 200.0, 300.0, 500.0, 700.0, 900.0, 1000.0]

    sri_lankan = next(s for s in skins if s["id"] == "sri_lankan")
    assert sri_lankan["name"] == "Sri Lankan"
    assert sri_lankan["provisional"] is True
    assert sri_lankan["scale_cents"] == [0.0, 200.0, 400.0, 700.0, 1000.0]


def test_f055_ac_skin_selection_in_sonify(tmp_path: Path) -> None:
    # F-055 AC: sonify endpoint accepts skin; unknown -> 404-style problem response;
    # response includes skin metadata (name, scale description).
    client = _make_client(tmp_path)
    analysis_id = _analyze_synthetic_image(client)

    for skin_id in ("neutral", "hindustani", "sri_lankan", "hindustani_malhar"):
        r = client.post(
            "/api/sonify",
            json={"analysis_id": analysis_id, "skin": skin_id, "n_cols": 32},
        )
        assert r.status_code == 200, f"Failed for skin {skin_id}: {r.text}"
        data = r.json()
        assert "skin" in data
        meta = data["skin"]
        assert meta["name"] in ("Neutral (scientific)", "Hindustani", "Sri Lankan")
        assert len(meta["scale_description"]) > 0
        if skin_id in ("hindustani", "sri_lankan", "hindustani_malhar"):
            assert meta["provisional"] is True
        else:
            assert meta["provisional"] is False

    # Unknown skin -> 404 problem
    r_bad = client.post(
        "/api/sonify",
        json={"analysis_id": analysis_id, "skin": "non_existent_skin"},
    )
    assert r_bad.status_code == 404
    prob = r_bad.json()
    assert prob["code"] == "not_found"
    assert "non_existent_skin" in prob["detail"]
