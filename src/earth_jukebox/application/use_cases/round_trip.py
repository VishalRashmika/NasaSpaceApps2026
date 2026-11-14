"""F-035: Score round-trip decoder use case.

Decodes Score notes back to a (n_bands, n_cols) grid of physical values using
Score data only, and computes Pearson r fidelity.
"""

from __future__ import annotations

import numpy as np

from earth_jukebox.domain.models import FloatArray, ScalarField, Score
from earth_jukebox.domain.skins import get_skin
from earth_jukebox.domain.sonification import (
    denormalize_u,
    get_pitch_set,
    pitch_to_degree_index,
    resample_field,
)


def decode_score(score: Score) -> FloatArray:
    """Decode Score intermediate representation back into a (n_bands, n_cols) grid.

    Uses Score data ONLY (legend, notes, dimensions, skin).
    """
    n_bands = score.n_bands
    n_cols = score.n_cols
    grid = np.full((n_bands, n_cols), np.nan, dtype=np.float64)

    skin = get_skin(score.skin_id)
    p_set = get_pitch_set(skin)
    n_pitches = len(p_set)
    if n_pitches <= 1:
        return grid

    # Group main band notes by (band, col)
    cell_pitches: dict[tuple[int, int], list[float]] = {}
    for n in score.notes:
        if n.kind == "main" and n.voice_id.startswith("band"):
            key = (n.band, n.col)
            if key not in cell_pitches:
                cell_pitches[key] = []
            cell_pitches[key].append(n.pitch_midi)

    for (b, c), pitches in cell_pitches.items():
        if 0 <= b < n_bands and 0 <= c < n_cols and pitches:
            med_pitch = float(np.median(pitches))
            deg_idx = pitch_to_degree_index(med_pitch, skin)
            u = deg_idx / float(n_pitches - 1)
            v = float(denormalize_u(u, score.legend))
            grid[b, c] = v

    return grid


def fidelity_round_trip(field: ScalarField, score: Score) -> float:
    """Calculate Pearson r between original field resampled grid and decoded Score grid."""
    values_2d = field.values[0] if field.values.ndim == 3 else field.values
    grid_truth = resample_field(values_2d, score.n_bands, score.n_cols).means
    grid_decoded = decode_score(score)

    mask = (~np.isnan(grid_truth)) & (~np.isnan(grid_decoded))
    x = grid_truth[mask]
    y = grid_decoded[mask]

    if len(x) < 2:
        return 1.0 if len(x) == 1 else 0.0

    std_x = float(np.std(x))
    std_y = float(np.std(y))
    if std_x == 0.0 and std_y == 0.0:
        return 1.0
    if std_x == 0.0 or std_y == 0.0:
        return 0.0

    r_matrix = np.corrcoef(x, y)
    r = float(r_matrix[0, 1])
    return r
