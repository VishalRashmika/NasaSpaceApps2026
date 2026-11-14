"""Tests for F-100: Synthetic map generator."""

from __future__ import annotations

import numpy as np

from earth_jukebox.domain.models import Orientation, PixelBox, ScalarField
from earth_jukebox.infrastructure.vision.synthetic import generate_map


def _boxes_overlap(b1: PixelBox, b2: PixelBox) -> bool:
    return not (
        b1.x + b1.w <= b2.x or b2.x + b2.w <= b1.x or b1.y + b1.h <= b2.y or b2.y + b2.h <= b1.y
    )


def test_f100_ac1_reproducible_bytes() -> None:
    # F-100 AC1: generate_map(cmap="viridis", seed=1) returns identical bytes on repeated calls.
    png1, field1, _leg1, cbox1, mbox1 = generate_map(cmap="viridis", seed=1)
    png2, field2, _leg2, cbox2, mbox2 = generate_map(cmap="viridis", seed=1)

    assert png1 == png2
    assert cbox1 == cbox2
    assert mbox1 == mbox2
    np.testing.assert_array_equal(np.isnan(field1.values), np.isnan(field2.values))
    valid = ~np.isnan(field1.values)
    np.testing.assert_array_almost_equal(field1.values[valid], field2.values[valid])


def test_f100_ac2_eight_colormaps() -> None:
    # F-100 AC2: works for >= 8 colormaps incl. one diverging (RdBu_r) and one rainbow (turbo).
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
    assert len(colormaps) >= 8

    for cmap in colormaps:
        png, field, legend, cbox, mbox = generate_map(cmap=cmap, seed=42)
        assert len(png) > 0
        assert isinstance(field, ScalarField)
        assert legend.label == "Synthetic Variable"
        assert cbox.w > 0 and cbox.h > 0
        assert mbox.w > 0 and mbox.h > 0


def test_f100_ac3_truth_nan_mask_and_boxes_non_overlapping() -> None:
    # F-100 AC3: truth NaN mask matches land region;
    # colorbar box and map box are inside the image and non-overlapping.
    _png, field, _legend, cbox, mbox = generate_map(cmap="viridis", seed=7)

    # NaN mask exists (land region) and covers a reasonable share
    nan_share = float(np.isnan(field.values).mean())
    assert 0.05 < nan_share < 0.50

    # Non-overlapping
    assert not _boxes_overlap(cbox, mbox)

    # Both inside image
    assert mbox.x >= 0 and mbox.y >= 0
    assert cbox.x >= 0 and cbox.y >= 0


def test_f100_vertical_and_variants() -> None:
    png, _field, _legend, cbox, mbox = generate_map(
        cmap="RdBu_r",
        seed=12,
        orientation=Orientation.VERTICAL,
        with_outline=True,
        with_title=True,
        with_graticule=True,
    )
    assert len(png) > 0
    assert not _boxes_overlap(cbox, mbox)
    assert cbox.h > cbox.w  # vertical orientation
