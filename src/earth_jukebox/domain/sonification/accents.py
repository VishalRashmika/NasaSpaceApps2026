"""F-027: Extremes accents.

Per docs/06 §9:
e = |u - 0.5|
thr = percentile(e over valid cells, 95)
A cell is accented iff e >= thr and e > 0
"""

from __future__ import annotations

import numpy as np

from earth_jukebox.domain.models import FloatArray
from earth_jukebox.domain.sonification.variability import MIN_COVERAGE_FOR_DATA


def find_accented_cells(
    grid_u: FloatArray,
    coverage: FloatArray,
) -> np.ndarray[tuple[int, ...], np.dtype[np.bool_]]:
    """Return boolean mask (n_bands, n_cols) where cells are accented."""
    n_bands, n_cols = grid_u.shape
    accented = np.zeros((n_bands, n_cols), dtype=bool)

    valid_mask = (coverage >= MIN_COVERAGE_FOR_DATA) & (~np.isnan(grid_u))
    if not np.any(valid_mask):
        return accented

    e = np.abs(grid_u - 0.5)
    valid_e = e[valid_mask]

    thr = float(np.percentile(valid_e, 95))
    accented_mask = valid_mask & (e >= thr) & (e > 0.0)
    return accented_mask
