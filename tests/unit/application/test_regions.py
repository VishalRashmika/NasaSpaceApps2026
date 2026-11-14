"""Tests for F-005: Manual region specification."""

from __future__ import annotations

import pytest

from earth_jukebox.application.use_cases.region_spec import resolve_regions
from earth_jukebox.domain.errors import InvalidLegendError
from earth_jukebox.domain.models import PixelBox


def test_f005_ac1_boxes_outside_image_raise() -> None:
    # F-005 AC1: boxes outside the image -> InvalidLegendError.
    img_w, img_h = 1000, 500

    # Map box outside
    with pytest.raises(InvalidLegendError) as exc1:
        resolve_regions(
            img_w=img_w,
            img_h=img_h,
            map_box=PixelBox(x=900, y=0, w=200, h=500),  # x+w = 1100 > 1000
            colorbar_box=None,
        )
    assert "map_box" in str(exc1.value)

    # Colorbar box outside
    with pytest.raises(InvalidLegendError) as exc2:
        resolve_regions(
            img_w=img_w,
            img_h=img_h,
            map_box=PixelBox(x=0, y=0, w=500, h=500),
            colorbar_box=PixelBox(x=500, y=400, w=100, h=200),  # y+h = 600 > 500
        )
    assert "colorbar_box" in str(exc2.value)


def test_f005_ac2_overlapping_boxes_raise() -> None:
    # F-005 AC2: overlap of map and colorbar boxes > 0 -> InvalidLegendError.
    img_w, img_h = 1000, 500
    mbox = PixelBox(x=100, y=100, w=400, h=300)
    cbox = PixelBox(x=450, y=200, w=200, h=50)  # overlaps with mbox from x=450 to 500

    with pytest.raises(InvalidLegendError) as exc:
        resolve_regions(
            img_w=img_w,
            img_h=img_h,
            map_box=mbox,
            colorbar_box=cbox,
        )
    assert "overlap" in str(exc.value)


def test_f005_omitted_map_box_computes_default() -> None:
    # If map_box is omitted, map region = whole image minus colorbar box (minus 1% border)
    img_w, img_h = 1000, 600
    # Colorbar at bottom
    cbox = PixelBox(x=200, y=500, w=600, h=40)
    resolved_mbox, resolved_cbox = resolve_regions(
        img_w=img_w,
        img_h=img_h,
        map_box=None,
        colorbar_box=cbox,
    )
    assert resolved_cbox == cbox
    assert resolved_mbox.x >= int(img_w * 0.01)
    assert resolved_mbox.y >= int(img_h * 0.01)
    assert resolved_mbox.y + resolved_mbox.h <= cbox.y  # above colorbar
