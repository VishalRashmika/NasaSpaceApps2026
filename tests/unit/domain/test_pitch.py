"""Unit tests for F-022 (Value -> pitch scale quantisation)."""

from __future__ import annotations

import math

import numpy as np

from earth_jukebox.domain.models import Skin
from earth_jukebox.domain.skins.neutral import NEUTRAL_SKIN
from earth_jukebox.domain.sonification.pitch import get_pitch_set, quantize_pitch


def test_f022_ac1_monotonic_non_decreasing() -> None:
    # AC1: monotonic non-decreasing in u for every skin
    u_vals = np.linspace(0.0, 1.0, 100)
    pitches = [quantize_pitch(float(u), NEUTRAL_SKIN) for u in u_vals]
    for i in range(len(pitches) - 1):
        assert pitches[i] <= pitches[i + 1]


def test_f022_ac2_bounds_and_centre() -> None:
    # AC2: u=0 -> lowest note; u=1 -> highest note; diverging centre -> tonic of middle octave
    p_set = get_pitch_set(NEUTRAL_SKIN)
    assert len(p_set) == 11  # 2 * 5 + 1
    # Lowest note: C3 (48.0)
    assert quantize_pitch(0.0, NEUTRAL_SKIN) == p_set[0]
    assert quantize_pitch(0.0, NEUTRAL_SKIN) == 48.0

    # Highest note: C5 (72.0)
    assert quantize_pitch(1.0, NEUTRAL_SKIN) == p_set[-1]
    assert quantize_pitch(1.0, NEUTRAL_SKIN) == 72.0

    # Diverging centre u=0.5 -> index L=5 -> C4 (60.0)
    assert quantize_pitch(0.5, NEUTRAL_SKIN) == p_set[5]
    assert quantize_pitch(0.5, NEUTRAL_SKIN) == 60.0


def test_f022_ac3_pitch_invariant_to_band() -> None:
    # AC3: same u gives same pitch regardless of band (P2)
    u = 0.37
    p1 = quantize_pitch(u, NEUTRAL_SKIN)
    p2 = quantize_pitch(u, NEUTRAL_SKIN)
    assert p1 == p2


def test_f022_custom_skin_with_cents() -> None:
    # Verify fractional cents handling
    skin = Skin(
        id="microtonal",
        name="Microtonal",
        tonic_midi=60.0,
        scale_cents=(0.0, 150.0, 300.0, 700.0),
        n_octaves=2,
        instrument_map={},
    )
    p_set = get_pitch_set(skin)
    assert len(p_set) == 2 * 4 + 1
    assert math.isclose(p_set[1], 61.5)
    assert quantize_pitch(0.0, skin) == 60.0
    assert quantize_pitch(0.5, skin) == 72.0  # middle tonic
    assert quantize_pitch(1.0, skin) == 84.0  # top tonic
