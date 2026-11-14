"""Tests for F-006: Colorbar -> LUT extraction."""

from __future__ import annotations

import cv2
import matplotlib

matplotlib.use("Agg")
import numpy as np

from earth_jukebox.domain.models import ColormapKind, Orientation, RecoveryMode
from earth_jukebox.infrastructure.vision.lut import extract_lut
from earth_jukebox.infrastructure.vision.synthetic import generate_map


def _decode_png(png_bytes: bytes) -> np.ndarray:
    nparr = np.frombuffer(png_bytes, np.uint8)
    bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def test_f006_ac1_extracted_lut_mean_delta_e_eight_colormaps() -> None:
    # F-006 AC1: on synthetic horizontal and vertical bars of 8 colormaps,
    # extracted LUT vs. matplotlib's colormap has mean Delta E <= 2.0.
    colormaps = [
        "viridis",
        "plasma",
        "inferno",
        "magma",
        "Blues",
        "Greens",
        "RdBu_r",
        "turbo",
    ]

    for cmap in colormaps:
        for orient in (Orientation.HORIZONTAL, Orientation.VERTICAL):
            kind = ColormapKind.DIVERGING if cmap == "RdBu_r" else ColormapKind.SEQUENTIAL
            png, _field, legend, cbar_box, _mbox = generate_map(
                cmap=cmap,
                seed=42,
                orientation=orient,
                kind=kind,
            )
            rgb = _decode_png(png)
            extracted = extract_lut(rgb, cbar_box, legend)

            assert extracted.source == RecoveryMode.COLORBAR
            n_entries = len(extracted.lab)
            assert n_entries <= 512

            # Compute truth LUT from matplotlib
            cmap_obj = matplotlib.colormaps.get_cmap(cmap)
            positions = np.linspace(0.0, 1.0, n_entries)
            truth_rgb = cmap_obj(positions)[:, :3].astype(np.float32).reshape(1, n_entries, 3)
            truth_lab = (
                cv2.cvtColor(truth_rgb, cv2.COLOR_RGB2LAB).reshape(n_entries, 3).astype(np.float64)
            )

            mean_de = float(np.mean(np.linalg.norm(extracted.lab - truth_lab, axis=1)))
            assert mean_de <= 2.0, f"mean ΔE = {mean_de:.3f} > 2.0 for {cmap} ({orient})"


def test_f006_ac2_low_at_start_false_reverses_order() -> None:
    # F-006 AC2: low_at_start=False reverses order.
    png, _field, legend_normal, cbar_box, _mbox = generate_map(
        cmap="viridis",
        seed=1,
        orientation=Orientation.HORIZONTAL,
    )
    rgb = _decode_png(png)

    lut_normal = extract_lut(rgb, cbar_box, legend_normal)

    # Now create legend with low_at_start=False
    legend_reversed = legend_normal.__class__(
        vmin=legend_normal.vmin,
        vmax=legend_normal.vmax,
        units=legend_normal.units,
        label=legend_normal.label,
        kind=legend_normal.kind,
        category=legend_normal.category,
        center=legend_normal.center,
        orientation=legend_normal.orientation,
        low_at_start=False,
        scale=legend_normal.scale,
    )
    lut_reversed = extract_lut(rgb, cbar_box, legend_reversed)

    # Reversing lut_normal's lab should match lut_reversed's lab
    np.testing.assert_allclose(lut_normal.lab[::-1], lut_reversed.lab, atol=1e-3)


def test_f006_ac3_outline_invariance() -> None:
    # F-006 AC3: a bar with a 1-px black outline gives the same LUT (+- Delta E 1) as without.
    png_no_outline, _, legend, cbar_box1, _ = generate_map(
        cmap="viridis",
        seed=1,
        with_outline=False,
    )
    png_with_outline, _, _, cbar_box2, _ = generate_map(
        cmap="viridis",
        seed=1,
        with_outline=True,
    )

    rgb1 = _decode_png(png_no_outline)
    rgb2 = _decode_png(png_with_outline)

    lut1 = extract_lut(rgb1, cbar_box1, legend)
    lut2 = extract_lut(rgb2, cbar_box2, legend)

    assert len(lut1.lab) == len(lut2.lab)
    mean_diff = float(np.mean(np.linalg.norm(lut1.lab - lut2.lab, axis=1)))
    assert mean_diff <= 1.0, f"outline diff {mean_diff:.3f} > 1.0"
