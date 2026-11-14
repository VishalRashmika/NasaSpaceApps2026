"""Unit tests for F-032 (Score assembly) and F-028 (Silence for masked data)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from earth_jukebox.application.use_cases.sonify import sonify
from earth_jukebox.domain.models import (
    ColormapKind,
    GeoExtent,
    LegendSpec,
    RecoveryMode,
    RecoveryQuality,
    ScalarField,
    ScaleType,
    SonificationParams,
    VariableCategory,
)
from earth_jukebox.domain.sonification.score_serde import (
    score_from_dict,
    score_to_dict,
    score_to_json,
)


def _validate_score_schema(d: dict[str, object]) -> None:
    """Validate dictionary against docs/schemas/score.schema.json structure."""
    schema_path = Path("docs/schemas/score.schema.json")
    assert schema_path.exists()
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    # Required top-level keys
    for req in schema["required"]:
        assert req in d, f"Missing required top-level key: {req}"

    assert d["schema"] == "earth-jukebox.score/1"
    assert isinstance(d["mapping_version"], str)
    assert isinstance(d["skin_id"], str)
    assert isinstance(d["seed"], int)
    assert isinstance(d["bpm"], (int, float)) and d["bpm"] >= 0
    assert isinstance(d["total_beats"], (int, float)) and d["total_beats"] >= 0
    assert isinstance(d["n_cols"], int) and d["n_cols"] >= 1
    assert isinstance(d["n_bands"], int) and d["n_bands"] >= 1

    # Legend
    leg = d["legend"]
    assert isinstance(leg, dict)
    for req in schema["properties"]["legend"]["required"]:
        assert req in leg, f"Missing required legend key: {req}"

    # Voices
    voices = d["voices"]
    assert isinstance(voices, list)
    for v in voices:
        assert isinstance(v, dict)
        for req in schema["properties"]["voices"]["items"]["required"]:
            assert req in v, f"Missing required voice key: {req}"
        assert -1.0 <= v["pan"] <= 1.0

    # Drone
    drone = d["drone_midi"]
    assert isinstance(drone, list)
    assert len(drone) == 2

    # Notes
    notes = d["notes"]
    assert isinstance(notes, list)
    for n in notes:
        assert isinstance(n, dict)
        for req in schema["properties"]["notes"]["items"]["required"]:
            assert req in n, f"Missing required note key: {req}"
        assert n["t_beat"] >= 0
        assert n["dur_beat"] >= 0
        assert 0.0 <= n["velocity"] <= 1.0
        assert 0.0 <= n["roughness"] <= 1.0
        assert n["kind"] in ("main", "ornament", "accent_bell")

    # Provenance
    prov = d["provenance"]
    assert isinstance(prov, dict)
    for k, v in prov.items():
        assert isinstance(k, str)
        assert isinstance(v, str)


def _make_sample_field(
    h: int = 100,
    w: int = 200,
    vmin: float = -5.0,
    vmax: float = 35.0,
    all_nan: bool = False,
) -> ScalarField:
    legend = LegendSpec(
        vmin=vmin,
        vmax=vmax,
        units="°C",
        label="Surface Temperature",
        kind=ColormapKind.DIVERGING,
        category=VariableCategory.TEMPERATURE,
        center=15.0,
        scale=ScaleType.LINEAR,
    )
    extent = GeoExtent()
    quality = RecoveryQuality(
        mean_delta_e=1.2,
        p95_delta_e=2.5,
        masked_fraction=0.1,
        lut_is_monotonic_in_lightness=True,
        confidence=0.92,
        mode=RecoveryMode.COLORBAR,
        warnings=(),
    )
    if all_nan:
        values = np.full((h, w), np.nan, dtype=np.float64)
    else:
        rng = np.random.default_rng(42)
        values = rng.uniform(vmin, vmax, size=(h, w)).astype(np.float64)
        # Mask 10%
        values[rng.random(size=(h, w)) < 0.1] = np.nan

    return ScalarField(
        values=values,
        legend=legend,
        extent=extent,
        quality=quality,
        source_hash="deadbeef12345678",
    )


def test_f032_ac1_score_json_schema_valid() -> None:
    # AC1: Score JSON validates against docs/07 §2 schema
    field = _make_sample_field()
    score = sonify(field, SonificationParams(n_bands=5, n_cols=48))

    score_d = score_to_dict(score)
    _validate_score_schema(score_d)

    json_str = score_to_json(score)
    assert isinstance(json_str, str)
    # Deserialize back
    score_reloaded = score_from_dict(json.loads(json_str))
    assert score_reloaded.mapping_version == score.mapping_version
    assert score_reloaded.seed == score.seed
    assert score_reloaded.bpm == score.bpm
    assert len(score_reloaded.notes) == len(score.notes)


def test_f032_ac2_notes_sorted_and_no_nan() -> None:
    # AC2: notes are sorted by (t_beat, voice_id, pitch); no NaN anywhere
    field = _make_sample_field()
    score = sonify(field)
    notes = score.notes
    assert len(notes) > 0

    for i in range(len(notes) - 1):
        n1 = notes[i]
        n2 = notes[i + 1]
        k1 = (round(n1.t_beat, 6), n1.voice_id, round(n1.pitch_midi, 6))
        k2 = (round(n2.t_beat, 6), n2.voice_id, round(n2.pitch_midi, 6))
        assert k1 <= k2, f"Notes out of order: {n1} vs {n2}"

    # No NaN anywhere in notes
    for n in notes:
        assert not np.isnan(n.t_beat)
        assert not np.isnan(n.dur_beat)
        assert not np.isnan(n.pitch_midi)
        assert not np.isnan(n.velocity)
        assert not np.isnan(n.roughness)
        assert n.value is not None
        assert not np.isnan(n.value)


def test_f032_ac3_every_note_value_within_bounds() -> None:
    # AC3: every note value is within [vmin, vmax]
    vmin, vmax = -5.0, 35.0
    field = _make_sample_field(vmin=vmin, vmax=vmax)
    score = sonify(field)

    for n in score.notes:
        assert n.value is not None
        assert vmin - 1e-5 <= n.value <= vmax + 1e-5


def test_f028_ac1_ac2_all_nan_silence() -> None:
    # AC1: all-NaN field -> Score with zero notes (plus drone) and warnings provenance entry
    field = _make_sample_field(all_nan=True)
    score = sonify(field)

    assert len(score.notes) == 0
    assert len(score.drone_midi) == 2
    assert "all_cells_masked" in score.provenance["warnings"]
