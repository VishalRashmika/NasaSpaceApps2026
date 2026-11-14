"""F-030: Drone / harmonic bed.

Per docs/06 §10:
drone_midi = (T, T + fifth) where fifth = scale degree of the skin closest to 700 cents.
Brightness hint = mean u over valid cells formatted as 3 decimals in provenance["drone_brightness"].
"""

from __future__ import annotations

import numpy as np

from earth_jukebox.domain.models import FloatArray, Skin
from earth_jukebox.domain.sonification.variability import MIN_COVERAGE_FOR_DATA


def compute_drone(
    grid_u: FloatArray,
    coverage: FloatArray,
    skin: Skin,
) -> tuple[tuple[float, ...], str]:
    """Compute (drone_midi, drone_brightness_str)."""
    t = skin.tonic_midi

    # Find degree closest to 700 cents
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
    drone_midi = (round(t, 2), round(t + fifth, 2))

    valid_mask = (coverage >= MIN_COVERAGE_FOR_DATA) & (~np.isnan(grid_u))
    valid_u = grid_u[valid_mask]
    if len(valid_u) > 0:
        mean_u = float(np.mean(valid_u))
        brightness_str = f"{mean_u:.3f}"
    else:
        brightness_str = "0.000"

    return drone_midi, brightness_str
