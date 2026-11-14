"""Unit tests for F-023 (Time/sweep mapping) and F-024 (Latitude band voice & pan)."""

from __future__ import annotations

from earth_jukebox.domain.models import VariableCategory
from earth_jukebox.domain.skins.neutral import NEUTRAL_SKIN
from earth_jukebox.domain.sonification.time_voices import (
    DEFAULT_BAND_BRIGHTNESS,
    DEFAULT_BAND_PANS,
    build_voices,
    col_to_beat,
    compute_total_beats,
)


def test_f023_ac_time_sweep_mapping() -> None:
    # AC: for n_cols=48 the last note starts at beat <= 47 and total_beats == 48
    n_cols = 48
    total_beats = compute_total_beats(n_cols)
    assert total_beats == 48.0
    last_note_start = col_to_beat(n_cols - 1)
    assert last_note_start <= 47.0
    assert last_note_start == 47.0
    assert col_to_beat(0) == 0.0


def test_f024_ac_latitude_band_voice_and_pan() -> None:
    # AC: voices constructed deterministically; pans exactly as table; instrument from skin
    voices = build_voices(NEUTRAL_SKIN, VariableCategory.TEMPERATURE, n_bands=5)
    # 5 band voices + 1 accent voice
    assert len(voices) == 6

    # 5 bands
    for b in range(5):
        v = voices[b]
        assert v.id == f"band{b}"
        assert v.band_index == b
        assert v.instrument == "strings"  # temperature on neutral skin is strings
        assert v.pan == DEFAULT_BAND_PANS[b]

    assert DEFAULT_BAND_PANS == (-0.6, -0.3, 0.0, 0.3, 0.6)
    assert DEFAULT_BAND_BRIGHTNESS == (0.6, 0.85, 1.15, 0.85, 0.6)

    # Accent voice
    accent_v = voices[5]
    assert accent_v.id == "accent"
    assert accent_v.band_index == -1
    assert accent_v.instrument == "bell"
    assert accent_v.pan == 0.0
