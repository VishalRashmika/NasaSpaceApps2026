"""Tests for F-008: Colour -> value inversion."""

from __future__ import annotations

import time

import cv2
import numpy as np

from earth_jukebox.domain.models import ColormapKind, Orientation
from earth_jukebox.infrastructure.vision.inversion import invert_field
from earth_jukebox.infrastructure.vision.lut import extract_lut
from earth_jukebox.infrastructure.vision.synthetic import generate_map


def _decode_png(png_bytes: bytes) -> np.ndarray:
    nparr = np.frombuffer(png_bytes, np.uint8)
    bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def test_f008_ac1_rmse_accuracy_targets() -> None:
    # F-008 AC1: synthetic fields recovered with RMSE <= 2 % of range for
    # sequential/diverging maps and <= 3 % for turbo/jet (doc 05 §9 table).
    test_cases = [
        ("viridis", 2.0),
        ("plasma", 2.0),
        ("inferno", 2.0),
        ("magma", 2.0),
        ("Blues", 2.0),
        ("Greens", 2.0),
        ("RdBu_r", 2.0),
        ("turbo", 3.0),
    ]

    for cmap, max_rmse_pct in test_cases:
        kind = ColormapKind.DIVERGING if cmap == "RdBu_r" else ColormapKind.SEQUENTIAL
        png, field, legend, cbar_box, map_box = generate_map(
            cmap=cmap,
            seed=42,
            orientation=Orientation.HORIZONTAL,
            kind=kind,
        )
        rgb = _decode_png(png)
        lut = extract_lut(rgb, cbar_box, legend)

        map_crop = rgb[map_box.y : map_box.y + map_box.h, map_box.x : map_box.x + map_box.w]
        recovered, _dists = invert_field(map_crop, lut, max_delta_e=12.0)

        # Evaluate on valid truth cells (where neither truth nor recovered is NaN)
        truth = field.values
        valid = (~np.isnan(truth)) & (~np.isnan(recovered))
        assert np.any(valid), f"no valid cells recovered for {cmap}"

        rmse = float(np.sqrt(np.mean((recovered[valid] - truth[valid]) ** 2)))
        rmse_pct = rmse / (legend.vmax - legend.vmin) * 100.0

        assert rmse_pct <= max_rmse_pct, (
            f"RMSE for {cmap} was {rmse_pct:.3f}%, expected <= {max_rmse_pct}%"
        )


def test_f008_ac2_determinism() -> None:
    # F-008 AC2: result is deterministic.
    png, _field, legend, cbar_box, map_box = generate_map(cmap="viridis", seed=7)
    rgb = _decode_png(png)
    lut = extract_lut(rgb, cbar_box, legend)
    map_crop = rgb[map_box.y : map_box.y + map_box.h, map_box.x : map_box.x + map_box.w]

    rec1, dists1 = invert_field(map_crop, lut)
    rec2, dists2 = invert_field(map_crop, lut)

    np.testing.assert_array_equal(np.isnan(rec1), np.isnan(rec2))
    valid = ~np.isnan(rec1)
    np.testing.assert_array_equal(rec1[valid], rec2[valid])
    np.testing.assert_array_equal(dists1, dists2)


def test_f008_ac3_performance_budget() -> None:
    # F-008 AC3: 2048x1024 image inverts in <= 3 s on the dev machine.
    png, _field, legend, cbar_box, _ = generate_map(
        cmap="viridis",
        seed=1,
        map_width=2048,
        map_height=1024,
    )
    rgb = _decode_png(png)
    lut = extract_lut(rgb, cbar_box, legend)

    # 2048x1024 synthetic crop
    large_crop = np.zeros((1024, 2048, 3), dtype=np.uint8)

    t0 = time.perf_counter()
    invert_field(large_crop, lut)
    elapsed = time.perf_counter() - t0

    assert elapsed <= 3.0, f"inversion took {elapsed:.2f}s > 3.0s"
