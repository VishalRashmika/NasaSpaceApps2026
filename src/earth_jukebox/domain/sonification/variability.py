"""F-025: Local variability and F-026: Global variability -> tempo.

Per docs/06 §7 & §8:
- Valid cells: coverage >= 0.25 and not np.isnan(u)
- For each valid cell: g = mean(|u - u_nbr|) over valid 4-neighbours (0 if none)
- Over valid cells compute p50, p85 of g
- Density: g <= p50 -> 1, p50 < g <= p85 -> 2, g > p85 -> 4
- Roughness: clamp(g / max(g over valid cells), 0, 1) (0 if max=0)
- Global variability: s = clamp(std(u over valid cells) / 0.30, 0, 1)
- bpm = 72 + 48 * s, rounded to 2 decimals
"""

from __future__ import annotations

import numpy as np

from earth_jukebox.domain.models import FloatArray

MIN_COVERAGE_FOR_DATA = 0.25


def compute_local_variability(
    grid_u: FloatArray,
    coverage: FloatArray,
) -> tuple[np.ndarray[tuple[int, ...], np.dtype[np.int64]], FloatArray]:
    """Compute per-cell rhythm density (1, 2, 4) and roughness in [0.0, 1.0].

    Returns (density_grid, roughness_grid). Invalid cells get density 0 and roughness 0.0.
    """
    n_bands, n_cols = grid_u.shape
    valid_mask = (coverage >= MIN_COVERAGE_FOR_DATA) & (~np.isnan(grid_u))

    g_grid = np.zeros((n_bands, n_cols), dtype=np.float64)

    for r in range(n_bands):
        for c in range(n_cols):
            if not valid_mask[r, c]:
                continue
            u_val = grid_u[r, c]
            diffs: list[float] = []
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                if 0 <= nr < n_bands and 0 <= nc < n_cols and valid_mask[nr, nc]:
                    diffs.append(abs(float(u_val - grid_u[nr, nc])))
            if diffs:
                g_grid[r, c] = float(np.mean(diffs))
            else:
                g_grid[r, c] = 0.0

    valid_g = g_grid[valid_mask]
    density = np.zeros((n_bands, n_cols), dtype=np.int64)
    roughness = np.zeros((n_bands, n_cols), dtype=np.float64)

    if len(valid_g) == 0:
        return density, roughness

    max_g = float(np.max(valid_g))
    if max_g > 0.0:
        roughness[valid_mask] = np.clip(g_grid[valid_mask] / max_g, 0.0, 1.0)

    # Flat field special case: all valid_g == 0 or all equal
    p50 = float(np.percentile(valid_g, 50))
    p85 = float(np.percentile(valid_g, 85))

    for r in range(n_bands):
        for c in range(n_cols):
            if not valid_mask[r, c]:
                continue
            g = g_grid[r, c]
            if g <= p50:
                density[r, c] = 1
            elif g <= p85:
                density[r, c] = 2
            else:
                density[r, c] = 4

    return density, roughness


def compute_bpm(grid_u: FloatArray, coverage: FloatArray) -> float:
    """Compute tempo in [72.0, 120.0] based on standard deviation of valid u."""
    valid_mask = (coverage >= MIN_COVERAGE_FOR_DATA) & (~np.isnan(grid_u))
    valid_u = grid_u[valid_mask]
    if len(valid_u) <= 1:
        return 72.0

    std_val = float(np.std(valid_u))
    s = min(max(std_val / 0.30, 0.0), 1.0)
    return round(72.0 + 48.0 * s, 2)
