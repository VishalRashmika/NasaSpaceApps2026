"""Tests for F-009: Non-data masking."""

from __future__ import annotations

import cv2
import numpy as np

from earth_jukebox.infrastructure.vision.inversion import apply_masking, invert_field
from earth_jukebox.infrastructure.vision.lut import extract_lut
from earth_jukebox.infrastructure.vision.synthetic import generate_map


def _decode_png(png_bytes: bytes) -> np.ndarray:
    nparr = np.frombuffer(png_bytes, np.uint8)
    bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def test_f009_ac1_land_mask_iou() -> None:
    # F-009 AC1: synthetic land mask recovered with IoU >= 0.95.
    png, field, legend, cbar_box, map_box = generate_map(cmap="viridis", seed=42)
    rgb = _decode_png(png)
    lut = extract_lut(rgb, cbar_box, legend)
    map_crop = rgb[map_box.y : map_box.y + map_box.h, map_box.x : map_box.x + map_box.w]

    values, dists = invert_field(map_crop, lut)
    values, dists = apply_masking(values, dists, map_crop, lut)

    truth = field.values
    truth_land = np.isnan(truth)
    pred_nan = np.isnan(values)

    intersection = np.logical_and(pred_nan, truth_land).sum()
    union = np.logical_or(pred_nan, truth_land).sum()
    iou = float(intersection / union)

    assert iou >= 0.95, f"Land mask IoU was {iou:.4f} < 0.95"


def test_f009_ac2_graticule_lines_not_extreme() -> None:
    # F-009 AC2: synthetic black graticule lines (1 px) do not appear as extreme values
    # (no value outside [vmin - 1 %, vmax + 1 %]).
    png, _field, legend, cbar_box, map_box = generate_map(
        cmap="viridis",
        seed=42,
        with_graticule=True,
    )
    rgb = _decode_png(png)
    lut = extract_lut(rgb, cbar_box, legend)
    map_crop = rgb[map_box.y : map_box.y + map_box.h, map_box.x : map_box.x + map_box.w]

    values, dists = invert_field(map_crop, lut)
    values, dists = apply_masking(values, dists, map_crop, lut)

    valid_values = values[~np.isnan(values)]
    assert len(valid_values) > 0

    v_range = legend.vmax - legend.vmin
    v_min_bound = legend.vmin - 0.01 * v_range
    v_max_bound = legend.vmax + 0.01 * v_range

    outliers = (valid_values < v_min_bound) | (valid_values > v_max_bound)
    assert not np.any(outliers), (
        f"Found {outliers.sum()} values outside [{v_min_bound}, {v_max_bound}]"
    )


def test_f009_dominant_background_cluster() -> None:
    # Dominant background colour covering > 5% of the map with dist > 6 -> NaN
    png, _field, legend, cbar_box, map_box = generate_map(cmap="viridis", seed=1)
    rgb = _decode_png(png)
    lut = extract_lut(rgb, cbar_box, legend)
    map_crop = rgb[map_box.y : map_box.y + map_box.h, map_box.x : map_box.x + map_box.w].copy()

    # Draw a 100x100 square of solid hot-pink (not in viridis) in map_crop
    # (100x100 = 10,000 px out of 524,288 px ~ 2%, let's make it 200x200 = 40,000 px ~ 7.6%)
    map_crop[50:250, 50:250] = [255, 20, 147]

    values, dists = invert_field(map_crop, lut)
    values, dists = apply_masking(values, dists, map_crop, lut)

    # Square region should be masked as NaN
    patch = values[50:250, 50:250]
    assert np.all(np.isnan(patch))
