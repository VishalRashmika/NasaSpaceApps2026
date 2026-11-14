"""F-036: Text description generator use case.

Produces plain-English accessible description per template in docs/06 §14.
"""

from __future__ import annotations

import numpy as np

from earth_jukebox.domain.models import RecoveryMode, ScalarField
from earth_jukebox.domain.sonification import resample_field

BAND_NAMES = (
    "arctic/subarctic, 90°N-54°N",
    "northern temperate, 54°N-18°N",
    "tropics, 18°N-18°S",
    "southern temperate, 18°S-54°S",
    "antarctic, 54°S-90°S",
)


def _where_is_cell(r: int, c: int, n_cols: int) -> str:
    band_name = BAND_NAMES[r] if r < len(BAND_NAMES) else f"band {r}"
    third_size = n_cols / 3.0
    if c < third_size:
        third = "western third"
    elif c < 2 * third_size:
        third = "central third"
    else:
        third = "eastern third"
    return f"{band_name}, {third}"


def generate_description(field: ScalarField) -> str:
    """Generate accessible text description of the field and its sonification mapping."""
    legend = field.legend
    values_2d = field.values[0] if field.values.ndim == 3 else field.values
    grid = resample_field(values_2d, n_bands=5, n_cols=48)
    means = grid.means
    valid_mask = ~np.isnan(means)

    if np.any(valid_mask):
        valid_indices = np.argwhere(valid_mask)
        # Find max and min cells (row-major order tie-breaker)
        best_max_val = -float("inf")
        best_max_idx = valid_indices[0]
        best_min_val = float("inf")
        best_min_idx = valid_indices[0]

        for r, c in valid_indices:
            val = float(means[r, c])
            if val > best_max_val:
                best_max_val = val
                best_max_idx = (r, c)
            if val < best_min_val:
                best_min_val = val
                best_min_idx = (r, c)

        where_high = _where_is_cell(int(best_max_idx[0]), int(best_max_idx[1]), 48)
        where_low = _where_is_cell(int(best_min_idx[0]), int(best_min_idx[1]), 48)
    else:
        where_high = "unspecified region"
        where_low = "unspecified region"

    masked_pct = round(field.quality.masked_fraction * 100)

    caveat = ""
    if field.quality.mode is RecoveryMode.LUMINANCE_FALLBACK:
        caveat = "This sound is not data-faithful: no colour legend was used."
    elif field.quality.confidence < 0.7:
        caveat = "These values are approximate, recovered from the image's colour legend."

    base_desc = (
        f"{legend.label} ({legend.units}), {legend.kind.value}: values range about "
        f"{legend.vmin}-{legend.vmax}. Highest values are mostly in the {where_high}; "
        f"lowest in the {where_low}. {masked_pct}% of the map has no data and is silent. "
        "Lower values sound lower in pitch; the track moves from west to east. "
        "Five voices from north to south pan left to right."
    )

    return f"{base_desc} {caveat}" if caveat else base_desc
