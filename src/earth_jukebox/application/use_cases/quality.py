"""Recovery quality and confidence assessment (F-011).

Implements quality metrics and confidence calculation strictly per docs/05 section 8.
"""

from __future__ import annotations

import numpy as np

from earth_jukebox.domain.models import FloatArray, RecoveryMode, RecoveryQuality


def is_lut_monotonic_in_lightness(lut_lab: FloatArray) -> bool:
    """Check if CIE L* along the LUT is monotonic after ignoring +-1 L noise (doc 05 section 8)."""
    if len(lut_lab) <= 2:
        return True

    l_vals = lut_lab[:, 0]
    # Check increasing with tolerance -1.0
    diffs = np.diff(l_vals)
    inc_monotonic = bool(np.all(diffs >= -1.0))
    if inc_monotonic:
        return True

    # Check decreasing with tolerance +1.0
    dec_monotonic = bool(np.all(diffs <= 1.0))
    return dec_monotonic


def compute_quality(
    values: FloatArray,
    distances: FloatArray,
    mode: RecoveryMode,
    lut_is_monotonic_in_lightness: bool,
    map_width: int,
    extra_warnings: tuple[str, ...] = (),
) -> RecoveryQuality:
    """Compute RecoveryQuality and confidence score (F-011)."""
    h, w = values.shape
    total_pixels = h * w
    if total_pixels == 0:
        return RecoveryQuality(
            mean_delta_e=0.0,
            p95_delta_e=0.0,
            masked_fraction=1.0,
            lut_is_monotonic_in_lightness=lut_is_monotonic_in_lightness,
            confidence=0.0,
            mode=mode,
            warnings=extra_warnings,
        )

    matched = ~np.isnan(values)
    matched_count = int(np.sum(matched))

    if matched_count > 0:
        matched_d = distances[matched]
        mean_de = float(np.mean(matched_d))
        p95_de = float(np.percentile(matched_d, 95))
    else:
        mean_de = 0.0
        p95_de = 0.0

    masked_fraction = float(np.isnan(values).mean())

    # Formulas from docs/05 §8:
    f_de = float(np.clip(1.0 - mean_de / 10.0, 0.0, 1.0))
    if masked_fraction <= 0.6:
        f_cov = 1.0
    else:
        f_cov = float(np.clip(1.0 - (masked_fraction - 0.6) / 0.35, 0.0, 1.0))

    base = 0.6 * f_de + 0.4 * f_cov

    mode_factor = {
        RecoveryMode.COLORBAR: 1.0,
        RecoveryMode.PRESET: 0.9,
        RecoveryMode.LUMINANCE_FALLBACK: 0.3,
    }[mode]

    confidence = base * mode_factor

    warnings_list = list(extra_warnings)
    if "projection_unverified" in warnings_list:
        confidence *= 0.8

    if mode == RecoveryMode.LUMINANCE_FALLBACK:
        confidence = min(confidence, 0.3)
        if "not_data_faithful" not in warnings_list:
            warnings_list.append("not_data_faithful")

    if (mean_de > 6.0 or masked_fraction > 0.8) and "high_color_distance" not in warnings_list:
        warnings_list.append("high_color_distance")

    if masked_fraction > 0.9 and "mostly_masked" not in warnings_list:
        warnings_list.append("mostly_masked")

    if map_width < 200 and "low_resolution" not in warnings_list:
        warnings_list.append("low_resolution")

    if not lut_is_monotonic_in_lightness and "lut_not_monotonic_lightness" not in warnings_list:
        warnings_list.append("lut_not_monotonic_lightness")

    return RecoveryQuality(
        mean_delta_e=mean_de,
        p95_delta_e=p95_de,
        masked_fraction=masked_fraction,
        lut_is_monotonic_in_lightness=lut_is_monotonic_in_lightness,
        confidence=confidence,
        mode=mode,
        warnings=tuple(warnings_list),
    )
