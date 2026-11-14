"""Colour to physical value inversion and non-data masking (F-008, F-009, F-013).

Converts map pixels to CIE L*a*b*, queries cKDTree over the LUT, interpolates
value with sub-step precision, and masks non-data pixels.
"""

from __future__ import annotations

import cv2
import numpy as np
from scipy.spatial import cKDTree

from earth_jukebox.domain.models import ColorLUT, FloatArray, LegendSpec, ScaleType, UInt8Array


def invert_field(
    map_rgb: UInt8Array,
    lut: ColorLUT,
    max_delta_e: float = 12.0,
) -> tuple[FloatArray, FloatArray]:
    """Invert RGB map pixels to physical scalar values using ColorLUT (F-008).

    Returns:
        (values, distances): 2D float arrays of shape (H, W). NaN where dist > max_delta_e.
    """
    h, w = map_rgb.shape[:2]
    if h == 0 or w == 0:
        empty = np.empty((h, w), dtype=np.float64)
        return empty, empty

    # 1. Convert map pixels to CIE L*a*b*
    map_f32 = map_rgb.astype(np.float32) * (1.0 / 255.0)
    map_lab = cv2.cvtColor(map_f32, cv2.COLOR_RGB2LAB).astype(np.float64)  # (H, W, 3)
    flat_lab = map_lab.reshape(-1, 3)

    # 2. Build cKDTree over LUT lab
    n_lut = len(lut.lab)
    if n_lut == 0:
        nan_arr = np.full((h, w), np.nan, dtype=np.float64)
        return nan_arr, nan_arr

    tree = cKDTree(lut.lab)
    dists, idxs = tree.query(flat_lab, k=1, workers=-1)

    # 3. Sub-step interpolation (docs/05 section 5)
    # Pick nearer neighbour j in {i-1, i+1}
    j_left = np.clip(idxs - 1, 0, n_lut - 1)
    j_right = np.clip(idxs + 1, 0, n_lut - 1)
    diff_l = flat_lab - lut.lab[j_left]
    diff_r = flat_lab - lut.lab[j_right]
    d_left = np.einsum("ij,ij->i", diff_l, diff_l)
    d_right = np.einsum("ij,ij->i", diff_r, diff_r)
    j = np.where(d_left < d_right, j_left, j_right)

    li = lut.lab[idxs]
    lj = lut.lab[j]
    segment = lj - li
    seg_sq = np.einsum("ij,ij->i", segment, segment)
    diff = flat_lab - li
    dot = np.einsum("ij,ij->i", diff, segment)

    # Avoid division by zero on flat/identical points
    t = np.where(seg_sq > 1e-8, np.clip(dot / np.maximum(seg_sq, 1e-8), 0.0, 1.0), 0.0)

    vi = lut.values[idxs]
    vj = lut.values[j]
    flat_values = vi + t * (vj - vi)

    # 4. Mask where distance > max_delta_e
    dist_mask = dists > max_delta_e
    flat_values[dist_mask] = np.nan

    values = flat_values.reshape(h, w)
    distances = dists.reshape(h, w)

    return values, distances


def find_outer_black_bars(
    rgb: UInt8Array,
    max_black_mean: float = 4.5,
    min_bar_thickness: int = 12,
) -> np.ndarray:
    """Detect outer pillarbox (left/right) and letterbox (top/bottom) black bars."""
    h, w = rgb.shape[:2]
    mask = np.zeros((h, w), dtype=bool)
    if h == 0 or w == 0:
        return mask

    col_mean = np.mean(rgb, axis=(0, 2))
    row_mean = np.mean(rgb, axis=(1, 2))

    left = 0
    while left < w and col_mean[left] <= max_black_mean:
        left += 1

    right = w
    while right > left and col_mean[right - 1] <= max_black_mean:
        right -= 1

    top = 0
    while top < h and row_mean[top] <= max_black_mean:
        top += 1

    bottom = h
    while bottom > top and row_mean[bottom - 1] <= max_black_mean:
        bottom -= 1

    if left >= min_bar_thickness:
        mask[:, :left] = True
    if w - right >= min_bar_thickness:
        mask[:, right:] = True
    if top >= min_bar_thickness:
        mask[:top, :] = True
    if h - bottom >= min_bar_thickness:
        mask[bottom:, :] = True

    return mask


def apply_masking(
    values: FloatArray,
    distances: FloatArray,
    map_rgb: UInt8Array,
    lut: ColorLUT,
    max_delta_e: float = 12.0,
    dominant_cluster_min_share: float = 0.05,
) -> tuple[FloatArray, FloatArray]:
    """Mask non-data pixels: distance, text/graticule, and dominant background (F-009).

    Returns:
        (masked_values, distances)
    """
    h, w = values.shape
    if h == 0 or w == 0:
        return values, distances

    # 1. Base distance mask
    mask = distances > max_delta_e

    # Convert image to Lab for color and lightness tests
    map_f32 = (map_rgb / 255.0).astype(np.float32)
    map_lab = cv2.cvtColor(map_f32, cv2.COLOR_RGB2LAB).astype(np.float64)
    l_chan = map_lab[:, :, 0]
    a_chan = map_lab[:, :, 1]
    b_chan = map_lab[:, :, 2]

    # 2. Dominant background cluster on non-LUT matched pixels (distances > 6.0)
    non_lut = distances > 6.0
    if np.any(non_lut):
        total_pixels = h * w
        l_bin = np.clip((l_chan / 100.0 * 15.999).astype(np.int32), 0, 15)
        a_bin = np.clip(((a_chan + 128.0) / 256.0 * 15.999).astype(np.int32), 0, 15)
        b_bin = np.clip(((b_chan + 128.0) / 256.0 * 15.999).astype(np.int32), 0, 15)
        clusters = (l_bin << 8) | (a_bin << 4) | b_bin

        non_lut_clusters = clusters[non_lut]
        unique_c, counts = np.unique(non_lut_clusters, return_counts=True)
        max_c_idx = int(np.argmax(counts))
        if counts[max_c_idx] > dominant_cluster_min_share * total_pixels:
            dominant_id = unique_c[max_c_idx]
            cluster_mask = non_lut & (clusters == dominant_id)
            mask |= cluster_mask

    # 3. Thin lines and text suppression (doc 05 section 6)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    n_lut = len(lut.lab)
    if n_lut > 0:
        d_start = np.linalg.norm(map_lab - lut.lab[0], axis=2)
        d_end = np.linalg.norm(map_lab - lut.lab[-1], axis=2)
        extreme = ((l_chan < 20.0) | (l_chan > 97.0)) & (d_start > 6.0) & (d_end > 6.0)
        thick_extreme = cv2.morphologyEx(extreme.astype(np.uint8), cv2.MORPH_OPEN, kernel).astype(
            bool
        )
        thin_extreme = extreme & ~thick_extreme
        mask |= thin_extreme

    chroma = np.sqrt(a_chan**2 + b_chan**2)
    grey = (chroma < 8.0) & (distances > 6.0)
    thick_grey = cv2.morphologyEx(grey.astype(np.uint8), cv2.MORPH_OPEN, kernel).astype(bool)
    thin_grey = grey & ~thick_grey
    mask |= thin_grey

    # 4. Outer letterbox/pillarbox padding suppression
    outer_black_mask = find_outer_black_bars(map_rgb)
    mask |= outer_black_mask

    masked_values = values.copy()
    masked_values[mask] = np.nan
    return masked_values, distances


def luminance_fallback(
    map_rgb: UInt8Array,
    legend: LegendSpec,
) -> tuple[FloatArray, FloatArray]:
    """Recover scalar field using CIE L* luminance fallback (F-013)."""
    h, w = map_rgb.shape[:2]
    if h == 0 or w == 0:
        empty = np.empty((h, w), dtype=np.float64)
        return empty, empty

    map_f32 = (map_rgb / 255.0).astype(np.float32)
    map_lab = cv2.cvtColor(map_f32, cv2.COLOR_RGB2LAB).astype(np.float64)
    l_chan = map_lab[:, :, 0]  # in 0..100

    if legend.scale == ScaleType.LOG:
        log_vmin = np.log10(legend.vmin)
        log_vmax = np.log10(legend.vmax)
        values = 10.0 ** (log_vmin + (l_chan / 100.0) * (log_vmax - log_vmin))
    else:
        values = legend.vmin + (l_chan / 100.0) * (legend.vmax - legend.vmin)

    # Mask outer letterbox/pillarbox padding if present
    outer_black_mask = find_outer_black_bars(map_rgb)
    values[outer_black_mask] = np.nan

    distances = np.zeros((h, w), dtype=np.float64)
    return values, distances
