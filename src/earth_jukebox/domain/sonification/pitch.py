"""F-022: Value -> pitch (scale quantisation).

Pitch mapping per docs/06 §4:
P = [ T + 12*o + c_k/100 for o in 0..n_octaves-1 for k in 0..L-1 ] + [ T + 12*n_octaves ]
N = 2L + 1 pitches, ascending
idx = round_half_up(u * (N - 1))
pitch_midi = P[idx]
"""

from __future__ import annotations

import math

from earth_jukebox.domain.models import Skin


def round_half_up(x: float) -> int:
    """Deterministic rounding: floor(x + 0.5)."""
    return math.floor(x + 0.5)


def get_pitch_set(skin: Skin) -> tuple[float, ...]:
    """Compute the ascending pitch set P for the given skin over n_octaves (default 2)."""
    t = skin.tonic_midi
    n_octaves = skin.n_octaves
    pitches: list[float] = []
    for o in range(n_octaves):
        for c in skin.scale_cents:
            pitches.append(t + 12.0 * o + c / 100.0)
    pitches.append(t + 12.0 * n_octaves)
    return tuple(pitches)


def quantize_pitch(u: float, skin: Skin) -> float:
    """Map normalized value u in [0, 1] to fractional MIDI pitch per docs/06 §4."""
    if math.isnan(u):
        return float("nan")

    p_set = get_pitch_set(skin)
    n = len(p_set)
    u_clamped = min(max(u, 0.0), 1.0)
    idx = round_half_up(u_clamped * (n - 1))
    idx_clamped = min(max(idx, 0), n - 1)
    return p_set[idx_clamped]


def pitch_to_degree_index(pitch_midi: float, skin: Skin) -> int:
    """Find the nearest pitch index in P for a given pitch_midi."""
    p_set = get_pitch_set(skin)
    best_idx = 0
    best_diff = abs(pitch_midi - p_set[0])
    for i in range(1, len(p_set)):
        diff = abs(pitch_midi - p_set[i])
        if diff < best_diff:
            best_diff = diff
            best_idx = i
    return best_idx
