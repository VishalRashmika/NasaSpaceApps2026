"""Colorbar auto-detection (F-004).

Proposes candidate PixelBoxes and orientations for colorbars in NASA EIC/SVS images
using gradient continuity and geometric heuristics (docs/05 section 4a).
"""

from __future__ import annotations

import cv2
import numpy as np

from earth_jukebox.application.ports import ColorbarDetector
from earth_jukebox.domain.models import (
    ColorbarCandidate,
    DecodedImage,
    Orientation,
    PixelBox,
)
from earth_jukebox.infrastructure.vision.decoder import scale_box


class HeuristicColorbarDetector(ColorbarDetector):
    """F-004 adapter implementing ColorbarDetector protocol."""

    def detect(self, image: DecodedImage) -> list[ColorbarCandidate]:
        return detect_colorbar(image)


def _compute_iou(box1: PixelBox, box2: PixelBox) -> float:
    """Compute Intersection-over-Union between two boxes."""
    x_left = max(box1.x, box2.x)
    y_top = max(box1.y, box2.y)
    x_right = min(box1.x + box1.w, box2.x + box2.w)
    y_bottom = min(box1.y + box1.h, box2.y + box2.h)

    if x_right <= x_left or y_bottom <= y_top:
        return 0.0

    inter = (x_right - x_left) * (y_bottom - y_top)
    union = box1.w * box1.h + box2.w * box2.h - inter
    return float(inter / union) if union > 0 else 0.0


def _find_horizontal_candidates(
    lab: np.ndarray,
    rgb: np.ndarray,
    min_len_ratio: float = 0.12,
    min_thickness: int = 6,
    min_aspect_ratio: float = 5.0,
    overlap_threshold: float = 0.8,
) -> list[tuple[PixelBox, Orientation, float]]:
    h, w = lab.shape[:2]
    candidates: list[tuple[PixelBox, Orientation, float]] = []

    # 1. Gradient along rows (x-axis)
    de_main = np.zeros((h, w), dtype=np.float32)
    de_main[:, :-1] = np.linalg.norm(lab[:, 1:] - lab[:, :-1], axis=2)

    # Across thickness (y-axis): in a horizontal colorbar, columns are uniform
    de_cross = np.zeros((h, w), dtype=np.float32)
    de_cross[:-1, :] = np.linalg.norm(lab[1:, :] - lab[:-1, :], axis=2)

    # Gradient pixel: smooth change along x, and low variation along y
    grad = (de_main >= 0.05) & (de_main <= 8.0) & (de_cross <= 3.0)

    # Close small quantization plateaus (up to 11 px) along horizontal axis
    kernel = np.ones((1, 11), dtype=np.uint8)
    closed = cv2.morphologyEx(grad.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
    discontinuity = de_main > 12.0
    closed[discontinuity] = 0

    min_len = int(min_len_ratio * w)
    row_runs: dict[int, list[tuple[int, int]]] = {}
    for y in range(h):
        row_closed = closed[y, :]
        if not np.any(row_closed):
            continue
        padded = np.pad(row_closed.astype(np.int32), (1, 1), mode="constant")
        diff = np.diff(padded)
        starts = np.where(diff == 1)[0]
        ends = np.where(diff == -1)[0]
        for s, e in zip(starts, ends, strict=False):
            if e - s >= min_len:
                row_runs.setdefault(y, []).append((int(s), int(e)))

    # Stack adjacent rows whose runs overlap >= 80%
    blocks: list[list[tuple[int, tuple[int, int]]]] = []
    for y in sorted(row_runs.keys()):
        for run in row_runs[y]:
            matched_block: list[tuple[int, tuple[int, int]]] | None = None
            for block in blocks:
                last_y, last_run = block[-1]
                if last_y == y - 1:
                    inter = max(0, min(run[1], last_run[1]) - max(run[0], last_run[0]))
                    union = max(run[1], last_run[1]) - min(run[0], last_run[0])
                    if union > 0 and (inter / union) >= overlap_threshold:
                        matched_block = block
                        break
            if matched_block is not None:
                matched_block.append((y, run))
            else:
                blocks.append([(y, run)])

    for block in blocks:
        thickness = len(block)
        if thickness < min_thickness:
            continue
        y_start = block[0][0]
        y_end = block[-1][0] + 1
        x_starts = [r[1][0] for r in block]
        x_ends = [r[1][1] for r in block]
        x_start = int(np.median(x_starts))
        x_end = int(np.median(x_ends))
        length = x_end - x_start
        if length <= 0 or (length / thickness) < min_aspect_ratio:
            continue

        # Expand thickness by 2 px (top and bottom) and length by 1 px to cover outlines/margins
        exp_x = max(0, x_start - 1)
        exp_y = max(0, y_start - 2)
        exp_w = min(w - exp_x, length + 2)
        exp_h = min(h - exp_y, thickness + 4)
        box = PixelBox(x=exp_x, y=exp_y, w=exp_w, h=exp_h)

        # Score per doc 05 §4a
        # 1. Cumulative delta E along run / 200 (cap 1)
        cum_de_list = [float(np.sum(de_main[y_curr, s : e - 1])) for y_curr, (s, e) in block]
        mean_cum_de = float(np.median(cum_de_list))
        score_cum_de = min(1.0, mean_cum_de / 200.0)

        # 2. Unique colours / length (cap 1)
        mid_y, (ms, me) = block[len(block) // 2]
        row_rgb = rgb[mid_y, ms:me]
        unique_colours = len(np.unique(row_rgb, axis=0))
        score_unique = min(1.0, unique_colours / float(min(length, 256)))

        # 3. Edge proximity: within 25% of an image edge
        near_edge = (y_start < 0.25 * h) or (y_end > 0.75 * h)
        score_edge = 1.0 if near_edge else 0.5

        # 4. Thickness uniformity
        lengths = [r[1][1] - r[1][0] for r in block]
        std_l = float(np.std(lengths))
        mean_l = float(np.mean(lengths))
        score_uniformity = max(0.0, 1.0 - (std_l / mean_l if mean_l > 0 else 1.0))

        total_score = (
            0.4 * score_cum_de + 0.3 * score_unique + 0.2 * score_edge + 0.1 * score_uniformity
        )
        if total_score >= 0.35:
            candidates.append((box, Orientation.HORIZONTAL, float(total_score)))

    return candidates


def _find_vertical_candidates(
    lab: np.ndarray,
    rgb: np.ndarray,
    min_len_ratio: float = 0.12,
    min_thickness: int = 6,
    min_aspect_ratio: float = 5.0,
    overlap_threshold: float = 0.8,
) -> list[tuple[PixelBox, Orientation, float]]:
    h, w = lab.shape[:2]
    candidates: list[tuple[PixelBox, Orientation, float]] = []

    # 1. Gradient along columns (y-axis)
    de_main = np.zeros((h, w), dtype=np.float32)
    de_main[:-1, :] = np.linalg.norm(lab[1:, :] - lab[:-1, :], axis=2)

    # Across thickness (x-axis): in a vertical colorbar, rows are uniform
    de_cross = np.zeros((h, w), dtype=np.float32)
    de_cross[:, :-1] = np.linalg.norm(lab[:, 1:] - lab[:, :-1], axis=2)

    # Gradient pixel: smooth change along y, and low variation along x
    grad = (de_main >= 0.05) & (de_main <= 8.0) & (de_cross <= 3.0)

    # Close small quantization plateaus along vertical axis
    kernel = np.ones((11, 1), dtype=np.uint8)
    closed = cv2.morphologyEx(grad.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
    discontinuity = de_main > 12.0
    closed[discontinuity] = 0

    min_len = int(min_len_ratio * h)
    col_runs: dict[int, list[tuple[int, int]]] = {}
    for x in range(w):
        col_closed = closed[:, x]
        if not np.any(col_closed):
            continue
        padded = np.pad(col_closed.astype(np.int32), (1, 1), mode="constant")
        diff = np.diff(padded)
        starts = np.where(diff == 1)[0]
        ends = np.where(diff == -1)[0]
        for s, e in zip(starts, ends, strict=False):
            if e - s >= min_len:
                col_runs.setdefault(x, []).append((int(s), int(e)))

    # Stack adjacent columns whose runs overlap >= 80%
    blocks: list[list[tuple[int, tuple[int, int]]]] = []
    for x in sorted(col_runs.keys()):
        for run in col_runs[x]:
            matched_block: list[tuple[int, tuple[int, int]]] | None = None
            for block in blocks:
                last_x, last_run = block[-1]
                if last_x == x - 1:
                    inter = max(0, min(run[1], last_run[1]) - max(run[0], last_run[0]))
                    union = max(run[1], last_run[1]) - min(run[0], last_run[0])
                    if union > 0 and (inter / union) >= overlap_threshold:
                        matched_block = block
                        break
            if matched_block is not None:
                matched_block.append((x, run))
            else:
                blocks.append([(x, run)])

    for block in blocks:
        thickness = len(block)
        if thickness < min_thickness:
            continue
        x_start = block[0][0]
        x_end = block[-1][0] + 1
        y_starts = [r[1][0] for r in block]
        y_ends = [r[1][1] for r in block]
        y_start = int(np.median(y_starts))
        y_end = int(np.median(y_ends))
        length = y_end - y_start
        if length <= 0 or (length / thickness) < min_aspect_ratio:
            continue

        # Expand thickness by 2 px (left and right) and length by 1 px
        exp_x = max(0, x_start - 2)
        exp_y = max(0, y_start - 1)
        exp_w = min(w - exp_x, thickness + 4)
        exp_h = min(h - exp_y, length + 2)
        box = PixelBox(x=exp_x, y=exp_y, w=exp_w, h=exp_h)

        # Score per doc 05 §4a
        cum_de_list = [float(np.sum(de_main[s : e - 1, x_curr])) for x_curr, (s, e) in block]
        mean_cum_de = float(np.median(cum_de_list))
        score_cum_de = min(1.0, mean_cum_de / 200.0)

        mid_x, (ms, me) = block[len(block) // 2]
        col_rgb = rgb[ms:me, mid_x]
        unique_colours = len(np.unique(col_rgb, axis=0))
        score_unique = min(1.0, unique_colours / float(min(length, 256)))

        near_edge = (x_start < 0.25 * w) or (x_end > 0.75 * w)
        score_edge = 1.0 if near_edge else 0.5

        lengths = [r[1][1] - r[1][0] for r in block]
        std_l = float(np.std(lengths))
        mean_l = float(np.mean(lengths))
        score_uniformity = max(0.0, 1.0 - (std_l / mean_l if mean_l > 0 else 1.0))

        total_score = (
            0.4 * score_cum_de + 0.3 * score_unique + 0.2 * score_edge + 0.1 * score_uniformity
        )
        if total_score >= 0.35:
            candidates.append((box, Orientation.VERTICAL, float(total_score)))

    return candidates


def detect_colorbar(image: DecodedImage) -> list[ColorbarCandidate]:
    """Propose candidate colorbar boxes and orientations (F-004).

    Returns up to top 3 candidates sorted by confidence score in original coordinates.
    """
    working_h, working_w = image.rgb.shape[:2]
    if working_h < 10 or working_w < 10:
        return []

    rgb_f32 = image.rgb.astype(np.float32) / 255.0
    lab = cv2.cvtColor(rgb_f32, cv2.COLOR_RGB2LAB)

    cands_h = _find_horizontal_candidates(lab, image.rgb)
    cands_v = _find_vertical_candidates(lab, image.rgb)
    all_cands = sorted(cands_h + cands_v, key=lambda c: c[2], reverse=True)

    # Deduplicate candidates with high mutual overlap (IoU > 0.5)
    deduped: list[tuple[PixelBox, Orientation, float]] = []
    for cand in all_cands:
        box, orient, score = cand
        if any(_compute_iou(box, existing[0]) > 0.5 for existing in deduped):
            continue
        deduped.append(cand)
        if len(deduped) >= 3:
            break

    # Scale boxes to original coordinates if needed
    result: list[ColorbarCandidate] = []
    for box, orient, score in deduped:
        scaled = scale_box(
            box,
            from_w=working_w,
            from_h=working_h,
            to_w=image.original_width,
            to_h=image.original_height,
        )
        result.append(
            ColorbarCandidate(
                box=scaled,
                orientation=orient,
                score=round(score, 4),
            )
        )

    return result
