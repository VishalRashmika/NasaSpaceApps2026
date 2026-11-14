"""Integration tests for F-062: Sonify endpoint."""

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


def _validate_score_schema(d: dict[str, object]) -> None:
    schema_path = Path("docs/schemas/score.schema.json")
    assert schema_path.exists()
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    for req in schema["required"]:
        assert req in d, f"Missing required top-level key: {req}"

    assert d["schema"] == "earth-jukebox.score/1"
    assert isinstance(d["mapping_version"], str)
    assert isinstance(d["bpm"], (int, float))
    assert isinstance(d["total_beats"], (int, float))
    assert isinstance(d["notes"], list)
    assert len(d["notes"]) > 0


def test_f062_ac_success_and_determinism(tmp_path: Path) -> None:
    # F-062 AC: response validates against docs/07 §2 schema; same request twice -> identical body
    client = _make_client(tmp_path)
    analysis_id = _analyze_synthetic_image(client)

    payload = {
        "analysis_id": analysis_id,
        "skin": "neutral",
        "n_cols": 48,
    }

    r1 = client.post("/api/sonify", json=payload)
    assert r1.status_code == 200, r1.text
    res1 = r1.json()

    assert "score" in res1
    assert "description" in res1
    assert "fidelity" in res1
    assert res1["fidelity"]["round_trip_r"] >= 0.90
    assert res1["fidelity"]["legend_r"] is not None
    assert res1["fidelity"]["legend_r"] >= 0.95
    assert len(res1["description"].split()) <= 120

    _validate_score_schema(res1["score"])

    # Identical request returns byte-identical body
    r2 = client.post("/api/sonify", json=payload)
    assert r2.status_code == 200
    assert r1.text == r2.text


def test_f062_unknown_analysis_id_returns_404(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    r = client.post("/api/sonify", json={"analysis_id": "0123456789abcdef", "skin": "neutral"})
    assert r.status_code == 404
    prob = r.json()
    assert prob["code"] == "not_found"


def test_f062_unknown_skin_returns_404(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    analysis_id = _analyze_synthetic_image(client)

    r = client.post(
        "/api/sonify",
        json={"analysis_id": analysis_id, "skin": "nonexistent_skin"},
    )
    assert r.status_code == 404
    prob = r.json()
    assert prob["code"] == "not_found"


def test_f062_out_of_range_n_cols_returns_422(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    analysis_id = _analyze_synthetic_image(client)

    # Below 16
    r = client.post("/api/sonify", json={"analysis_id": analysis_id, "n_cols": 10})
    assert r.status_code == 422
    assert r.json()["code"] == "validation_error"

    # Above 128
    r2 = client.post("/api/sonify", json={"analysis_id": analysis_id, "n_cols": 200})
    assert r2.status_code == 422
    assert r2.json()["code"] == "validation_error"
