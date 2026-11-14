"""Domain sonification rules and algorithms."""

from __future__ import annotations

from earth_jukebox.domain.sonification.accents import find_accented_cells
from earth_jukebox.domain.sonification.drone import compute_drone
from earth_jukebox.domain.sonification.normalization import denormalize_u, normalize_value
from earth_jukebox.domain.sonification.pitch import (
    get_pitch_set,
    pitch_to_degree_index,
    quantize_pitch,
    round_half_up,
)
from earth_jukebox.domain.sonification.resampling import ResampledGrid, resample_field
from earth_jukebox.domain.sonification.seeding import canonicalize_params, compute_seed, get_rng
from earth_jukebox.domain.sonification.tension import (
    compute_inter_frame_change_from_fields,
    compute_inter_frame_change_from_grids,
    compute_tension_drone,
)
from earth_jukebox.domain.sonification.time_voices import (
    DEFAULT_BAND_BRIGHTNESS,
    DEFAULT_BAND_PANS,
    build_voices,
    col_to_beat,
    compute_total_beats,
    get_band_brightness_str,
)
from earth_jukebox.domain.sonification.variability import (
    MIN_COVERAGE_FOR_DATA,
    compute_bpm,
    compute_local_variability,
)

__all__ = [
    "DEFAULT_BAND_BRIGHTNESS",
    "DEFAULT_BAND_PANS",
    "MIN_COVERAGE_FOR_DATA",
    "ResampledGrid",
    "build_voices",
    "canonicalize_params",
    "col_to_beat",
    "compute_bpm",
    "compute_drone",
    "compute_inter_frame_change_from_fields",
    "compute_inter_frame_change_from_grids",
    "compute_local_variability",
    "compute_seed",
    "compute_tension_drone",
    "compute_total_beats",
    "denormalize_u",
    "find_accented_cells",
    "get_band_brightness_str",
    "get_pitch_set",
    "get_rng",
    "normalize_value",
    "pitch_to_degree_index",
    "quantize_pitch",
    "resample_field",
    "round_half_up",
]
