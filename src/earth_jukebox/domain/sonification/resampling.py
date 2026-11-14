"""F-020: Field resampling to grid.

Resamples a ScalarField (or 2D float array) to (n_bands, n_cols) using NaN-aware
mean and computing per-cell coverage.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from earth_jukebox.domain.models import FloatArray


@dataclass(frozen=True)
class ResampledGrid:
    means: FloatArray  # (n_bands, n_cols)
    coverage: FloatArray  # (n_bands, n_cols)


def resample_field(values: FloatArray, n_bands: int = 5, n_cols: int = 48) -> ResampledGrid:
    """Resample a 2D float array to (n_bands, n_cols).

    Row blocks split H (band 0 = north / top).
    Column blocks split W (col 0 = west / left).
    """
    if values.ndim != 2:
        raise ValueError(f"values must be 2D, got shape {values.shape}")
    h, w = values.shape
    if h == 0 or w == 0:
        raise ValueError(f"values cannot be empty, got shape {(h, w)}")

    means = np.full((n_bands, n_cols), np.nan, dtype=np.float64)
    coverage = np.zeros((n_bands, n_cols), dtype=np.float64)

    for b in range(n_bands):
        r_start = round(b * h / n_bands)
        r_end = round((b + 1) * h / n_bands)
        for c in range(n_cols):
            c_start = round(c * w / n_cols)
            c_end = round((c + 1) * w / n_cols)

            block = values[r_start:r_end, c_start:c_end]
            valid_mask = ~np.isnan(block)
            valid_count = int(np.sum(valid_mask))
            total_count = block.size

            if total_count > 0:
                coverage[b, c] = valid_count / total_count
                if valid_count > 0:
                    means[b, c] = float(np.mean(block[valid_mask]))

    return ResampledGrid(means=means, coverage=coverage)
