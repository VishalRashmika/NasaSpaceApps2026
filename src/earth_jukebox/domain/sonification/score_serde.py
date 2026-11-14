"""Score wire format serialization and deserialization per docs/07 §2."""

from __future__ import annotations

import json
from typing import Any

from earth_jukebox.domain.models import (
    ColormapKind,
    LegendSpec,
    NoteEvent,
    Orientation,
    ScaleType,
    Score,
    VariableCategory,
    Voice,
)


def _round_float(val: float | None) -> float | None:
    if val is None:
        return None
    return round(float(val), 6)


def score_to_dict(score: Score) -> dict[str, Any]:
    """Convert Score to dictionary matching wire schema docs/07 §2."""
    notes_sorted = sorted(
        score.notes,
        key=lambda n: (round(n.t_beat, 6), n.voice_id, round(n.pitch_midi, 6)),
    )

    return {
        "schema": "earth-jukebox.score/1",
        "mapping_version": score.mapping_version,
        "skin_id": score.skin_id,
        "seed": score.seed,
        "bpm": round(score.bpm, 6),
        "total_beats": round(score.total_beats, 6),
        "n_cols": score.n_cols,
        "n_bands": score.n_bands,
        "legend": {
            "vmin": round(score.legend.vmin, 6),
            "vmax": round(score.legend.vmax, 6),
            "units": score.legend.units,
            "label": score.legend.label,
            "kind": score.legend.kind.value,
            "category": score.legend.category.value,
            "center": _round_float(score.legend.center),
            "orientation": score.legend.orientation.value,
            "low_at_start": score.legend.low_at_start,
            "scale": score.legend.scale.value,
        },
        "voices": [
            {
                "id": v.id,
                "band_index": v.band_index,
                "instrument": v.instrument,
                "pan": round(v.pan, 6),
            }
            for v in score.voices
        ],
        "drone_midi": [round(p, 6) for p in score.drone_midi],
        "notes": [
            {
                "voice_id": n.voice_id,
                "t_beat": round(n.t_beat, 6),
                "dur_beat": round(n.dur_beat, 6),
                "pitch_midi": round(n.pitch_midi, 6),
                "velocity": round(n.velocity, 6),
                "accent": n.accent,
                "col": n.col,
                "band": n.band,
                "value": _round_float(n.value),
                "glide_to_midi": _round_float(n.glide_to_midi),
                "roughness": round(n.roughness, 6),
                "kind": n.kind,
            }
            for n in notes_sorted
        ],
        "provenance": dict(score.provenance),
    }


def score_to_json(score: Score) -> str:
    """Serialize Score to JSON string per docs/07 §2."""
    d = score_to_dict(score)
    return json.dumps(d, separators=(",", ":"), ensure_ascii=False)


def score_from_dict(d: dict[str, Any]) -> Score:
    """Deserialize dictionary into a Score object."""
    leg_d = d["legend"]
    legend = LegendSpec(
        vmin=float(leg_d["vmin"]),
        vmax=float(leg_d["vmax"]),
        units=str(leg_d["units"]),
        label=str(leg_d["label"]),
        kind=ColormapKind(leg_d["kind"]),
        category=VariableCategory(leg_d.get("category", "generic")),
        center=float(leg_d["center"]) if leg_d.get("center") is not None else None,
        orientation=Orientation(leg_d.get("orientation", "horizontal")),
        low_at_start=bool(leg_d.get("low_at_start", True)),
        scale=ScaleType(leg_d.get("scale", "linear")),
    )

    voices = tuple(
        Voice(
            id=str(v["id"]),
            band_index=int(v["band_index"]),
            instrument=str(v["instrument"]),
            pan=float(v["pan"]),
        )
        for v in d["voices"]
    )

    notes = tuple(
        NoteEvent(
            voice_id=str(n["voice_id"]),
            t_beat=float(n["t_beat"]),
            dur_beat=float(n["dur_beat"]),
            pitch_midi=float(n["pitch_midi"]),
            velocity=float(n["velocity"]),
            accent=bool(n["accent"]),
            col=int(n["col"]),
            band=int(n["band"]),
            value=float(n["value"]) if n.get("value") is not None else None,
            glide_to_midi=(
                float(n["glide_to_midi"]) if n.get("glide_to_midi") is not None else None
            ),
            roughness=float(n.get("roughness", 0.0)),
            kind=str(n.get("kind", "main")),
        )
        for n in d["notes"]
    )

    return Score(
        mapping_version=str(d["mapping_version"]),
        skin_id=str(d["skin_id"]),
        seed=int(d["seed"]),
        bpm=float(d["bpm"]),
        total_beats=float(d["total_beats"]),
        n_cols=int(d["n_cols"]),
        n_bands=int(d["n_bands"]),
        voices=voices,
        notes=notes,
        drone_midi=tuple(float(p) for p in d["drone_midi"]),
        legend=legend,
        provenance=dict(d.get("provenance", {})),
    )
