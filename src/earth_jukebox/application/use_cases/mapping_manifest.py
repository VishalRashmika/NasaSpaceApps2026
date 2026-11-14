"""F-033: Mapping manifest.

Exposes the fixed mapping metadata (docs/06 tables, constants, version) for the
UI "How to listen" panel and submission documentation.
"""

from __future__ import annotations

from typing import Any

from earth_jukebox.domain.mapping_version import MAPPING_VERSION

MAPPING_TABLE: dict[str, dict[str, str]] = {
    "value->pitch": {
        "data_property": "Cell mean value u",
        "sound_parameter": "Pitch (scale-quantised, 2 octaves)",
        "rule": "Section 4: P = [T + 12*o + c_k/100] + [T + 24], idx = round_half_up(u * (N - 1))",
    },
    "longitude->time": {
        "data_property": "Column index (W->E)",
        "sound_parameter": "Time (1 column = 1 beat; playhead sweeps west->east)",
        "rule": "Section 5: t_beat = col * 1.0, total_beats = n_cols",
    },
    "latitude_band->voice_pan": {
        "data_property": "Band index (N->S)",
        "sound_parameter": "Voice id, pan, brightness (not pitch)",
        "rule": "Section 5: 5 equal bands north->south, pans [-0.6, -0.3, 0.0, 0.3, 0.6]",
    },
    "local_variability->rhythm_density": {
        "data_property": "Local gradient g",
        "sound_parameter": "Notes per beat: 1 / 2 / 4",
        "rule": "Section 7: 4-neighbour gradient percentiles (p50, p85)",
    },
    "local_variability->roughness": {
        "data_property": "Local gradient g",
        "sound_parameter": "NoteEvent.roughness (filter/detune amount)",
        "rule": "Section 7: clamp(g / max(g), 0, 1)",
    },
    "global_variability->tempo": {
        "data_property": "Std of valid u",
        "sound_parameter": "BPM 72..120",
        "rule": "Section 8: bpm = 72 + 48 * clamp(std(u)/0.30, 0, 1)",
    },
    "extremes->accent": {
        "data_property": "Top 5 % of |u-0.5|",
        "sound_parameter": "Velocity +0.25, bell doubling +12 st, optional ornament",
        "rule": "Section 9: e = |u - 0.5| >= 95th percentile and e > 0",
    },
    "masked->silence": {
        "data_property": "coverage < 0.25",
        "sound_parameter": "Rest",
        "rule": "Section 1: cells with coverage < 0.25 emit no notes",
    },
    "category->instrument": {
        "data_property": "VariableCategory",
        "sound_parameter": "Instrument family (from skin)",
        "rule": "Section 6: skin instrument_map per category",
    },
    "global_mean->drone_brightness": {
        "data_property": "Mean u over valid cells",
        "sound_parameter": "Drone brightness hint (provenance)",
        "rule": "Section 10: drone_midi = (T, T + fifth), brightness = mean u",
    },
}


def describe_mapping() -> dict[str, Any]:
    """Return JSON-serializable mapping manifest."""
    # Expose both at top level and inside 'mappings' for convenience
    manifest: dict[str, Any] = {
        "mapping_version": MAPPING_VERSION,
        "n_bands_default": 5,
        "n_cols_default": 48,
        "n_octaves": 2,
        "mappings": MAPPING_TABLE,
    }
    # Also copy all 10 keys to top level
    for k, v in MAPPING_TABLE.items():
        manifest[k] = v
    return manifest
