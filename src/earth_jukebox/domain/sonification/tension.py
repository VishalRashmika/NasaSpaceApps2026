"""F-092: Inter-frame change -> harmonic tension.

Per docs/03 F-092:
Mean absolute change between consecutive fields -> drone adds a second/tritone-ish
colour interval (skin-defined "tension degree") scaled by change.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from earth_jukebox.domain.models import FloatArray, ScalarField, Skin
from earth_jukebox.domain.sonification.normalization import normalize_value

DEFAULT_TENSION_CENTS = 200.0  # Major second (200 cents) default if unspecified


def compute_inter_frame_change_from_fields(fields: Sequence[ScalarField]) -> float:
    """Compute mean absolute difference of normalized u across consecutive fields (F-092 AC1)."""
    if len(fields) <= 1:
        return 0.0

    pair_changes: list[float] = []
    prev_u = normalize_value(fields[0].values, fields[0].legend)

    for k in range(1, len(fields)):
        curr_u = normalize_value(fields[k].values, fields[k].legend)
        # Valid cells where both fields have data (not NaN)
        valid = (~np.isnan(prev_u)) & (~np.isnan(curr_u))
        if np.any(valid):
            diff = np.abs(curr_u[valid] - prev_u[valid])
            pair_changes.append(float(np.mean(diff)))
        else:
            pair_changes.append(0.0)
        prev_u = curr_u

    if not pair_changes:
        return 0.0
    return float(np.clip(np.mean(pair_changes), 0.0, 1.0))


def compute_inter_frame_change_from_grids(grids_u: Sequence[FloatArray]) -> float:
    """Compute mean absolute difference across consecutive (n_bands, n_cols) normalized grids."""
    if len(grids_u) <= 1:
        return 0.0

    pair_changes: list[float] = []
    prev_u = grids_u[0]

    for k in range(1, len(grids_u)):
        curr_u = grids_u[k]
        valid = (~np.isnan(prev_u)) & (~np.isnan(curr_u))
        if np.any(valid):
            diff = np.abs(curr_u[valid] - prev_u[valid])
            pair_changes.append(float(np.mean(diff)))
        else:
            pair_changes.append(0.0)
        prev_u = curr_u

    if not pair_changes:
        return 0.0
    return float(np.clip(np.mean(pair_changes), 0.0, 1.0))


def compute_tension_drone(
    skin: Skin,
    mean_change: float,
    max_change_scale: float = 0.25,
) -> tuple[tuple[float, ...], float | None]:
    """Compute drone_midi pitches and tension_pitch (F-092 AC2, AC3).

    - If mean_change <= 0.0, returns (T, T + fifth) without tension pitch.
    - If mean_change > 0.0, adds tension interval scaled by change.
    """
    t = skin.tonic_midi

    # Find degree closest to 700 cents (fifth)
    closest_cents = 700.0
    if skin.scale_cents:
        best_diff = abs(skin.scale_cents[0] - 700.0)
        closest_cents = skin.scale_cents[0]
        for c in skin.scale_cents[1:]:
            diff = abs(c - 700.0)
            if diff < best_diff:
                best_diff = diff
                closest_cents = c
    fifth = closest_cents / 100.0
    base_drone = (round(t, 2), round(t + fifth, 2))

    if mean_change <= 0.0001:
        return base_drone, None

    # Skin-defined tension interval (doc 03 F-092)
    tension_cents = skin.tension_cents if skin.tension_cents is not None else DEFAULT_TENSION_CENTS
    tension_semitones = tension_cents / 100.0

    scale = float(np.clip(mean_change / max_change_scale, 0.0, 1.0))
    tension_pitch = round(t + tension_semitones * scale, 2)

    # Return sorted drone pitches
    drone_pitches = tuple(sorted([base_drone[0], base_drone[1], tension_pitch]))
    return drone_pitches, tension_pitch
