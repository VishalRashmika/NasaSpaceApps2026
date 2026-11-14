"""Colorbar to LUT extraction (F-006).

Extracts ColorLUT from a colorbar crop with border trimming, thickness median,
end-cap trimming, and Lab resampling.
"""

from __future__ import annotations

import cv2
import numpy as np

from earth_jukebox.domain.models import (
    ColorLUT,
    LegendSpec,
    Orientation,
    PixelBox,
    RecoveryMode,
    ScaleType,
    UInt8Array,
)


def dedupe_lut(lab: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    """Merge consecutive entries with ΔE < threshold (docs/05 section 3)."""
    if len(lab) <= 2:
        return lab

    deduped = [lab[0]]
    for i in range(1, len(lab) - 1):
        de = float(np.linalg.norm(lab[i] - deduped[-1]))
        if de >= threshold:
            deduped.append(lab[i])
    deduped.append(lab[-1])
    return np.asarray(deduped, dtype=np.float64)


def extract_lut(
    rgb: UInt8Array,
    colorbar_box: PixelBox,
    legend: LegendSpec,
    trim_border_px: int = 2,
    max_cap_trim_pct: float = 0.03,
    cap_delta_e_thresh: float = 20.0,
    max_entries: int = 512,
) -> ColorLUT:
    """Extract ColorLUT from image and colorbar box (F-006)."""
    # 1. Crop colorbar box
    crop = rgb[
        colorbar_box.y : colorbar_box.y + colorbar_box.h,
        colorbar_box.x : colorbar_box.x + colorbar_box.w,
    ]

    # Trim border all round
    h, w = crop.shape[:2]
    tb = trim_border_px
    if h > 2 * tb and w > 2 * tb:
        crop = crop[tb : h - tb, tb : w - tb]

    # 2 & 3. Thickness median
    if legend.orientation == Orientation.HORIZONTAL:
        # Position is columns (axis=1), thickness is rows (axis=0)
        median_rgb = np.median(crop, axis=0)  # shape (L, 3)
    else:
        # Position is rows (axis=0, top to bottom), thickness is columns (axis=1)
        median_rgb = np.median(crop, axis=1)  # shape (L, 3)

    length = len(median_rgb)
    rgb_f32 = (median_rgb / 255.0).astype(np.float32).reshape(1, length, 3)
    lab = cv2.cvtColor(rgb_f32, cv2.COLOR_RGB2LAB).reshape(length, 3).astype(np.float64)

    # 4. End-cap trim: drop up to 3% of length at both ends if Delta E > 20
    max_trim = max(1, round(length * max_cap_trim_pct))
    start = 0
    while start < max_trim and start + 1 < len(lab):
        if np.linalg.norm(lab[start] - lab[start + 1]) > cap_delta_e_thresh:
            start += 1
        else:
            break

    end = len(lab) - 1
    min_end = len(lab) - 1 - max_trim
    while end > min_end and end - 1 >= 0:
        if np.linalg.norm(lab[end] - lab[end - 1]) > cap_delta_e_thresh:
            end -= 1
        else:
            break

    if start < end:
        lab = lab[start : end + 1]

    # 5. Resample to <= max_entries if longer
    curr_len = len(lab)
    if curr_len > max_entries:
        t_old = np.linspace(0.0, 1.0, curr_len)
        t_new = np.linspace(0.0, 1.0, max_entries)
        lab = np.column_stack([np.interp(t_new, t_old, lab[:, c]) for c in range(3)])

    # 6. Order:
    # HORIZONTAL: low_at_start => left=vmin (start), else reverse
    # VERTICAL: low_at_start => bottom=vmin (so reverse top->bottom array), else keep top=vmin
    if legend.orientation == Orientation.HORIZONTAL:
        if not legend.low_at_start:
            lab = lab[::-1]
    else:
        if legend.low_at_start:
            lab = lab[::-1]

    # 7. Assign values
    n_pts = len(lab)
    if legend.scale == ScaleType.LOG:
        log_vmin = np.log10(legend.vmin)
        log_vmax = np.log10(legend.vmax)
        values = np.logspace(log_vmin, log_vmax, n_pts, dtype=np.float64)
    else:
        values = np.linspace(legend.vmin, legend.vmax, n_pts, dtype=np.float64)

    return ColorLUT(
        lab=lab,
        values=values,
        source=RecoveryMode.COLORBAR,
    )
