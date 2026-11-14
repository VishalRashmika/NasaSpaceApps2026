"""Tests for F-012: OCR legend assist."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

from earth_jukebox.domain.models import DecodedImage, Orientation, PixelBox
from earth_jukebox.infrastructure.vision.decoder import PillowImageDecoder
from earth_jukebox.infrastructure.vision.ocr import (
    OcrLegendResult,
    is_tesseract_available,
    ocr_legend,
    parse_legend_text,
)
from earth_jukebox.infrastructure.vision.synthetic import generate_map


def test_f012_ac1_tesseract_missing_returns_none_without_raising() -> None:
    # F-012 AC1: with Tesseract missing, returns None without raising.
    img = DecodedImage(
        rgb=np.zeros((100, 100, 3), dtype=np.uint8),
        content_hash="test",
        original_width=100,
        original_height=100,
    )
    box = PixelBox(x=10, y=10, w=80, h=20)

    # When is_tesseract_available returns False
    with patch(
        "earth_jukebox.infrastructure.vision.ocr.is_tesseract_available",
        return_value=False,
    ):
        res = ocr_legend(img, box, Orientation.HORIZONTAL)
        assert res is None

    # When pytesseract raises an exception during execution
    with (
        patch("earth_jukebox.infrastructure.vision.ocr.is_tesseract_available", return_value=True),
        patch("pytesseract.image_to_string", side_effect=RuntimeError("OCR failure")),
    ):
        res = ocr_legend(img, box, Orientation.HORIZONTAL)
        assert res is None


def test_f012_parse_legend_text_cases() -> None:
    # Test text parsing on variety of formats and colormap types
    # 1. Standard integer range with units
    res1 = parse_legend_text("0 20 40 60 80 100 units")
    assert res1 == OcrLegendResult(vmin=0.0, vmax=100.0, units="units")

    # 2. Diverging with negative numbers and unicode minus
    res2 = parse_legend_text("\u22124.0 \u22122.0 0.0 2.0 4.0 °C")
    assert res2 == OcrLegendResult(vmin=-4.0, vmax=4.0, units="°C")

    # 3. Fractional / decimal range
    res3 = parse_legend_text("0.1 0.3 0.5 0.7 0.9 mm")
    assert res3 == OcrLegendResult(vmin=0.1, vmax=0.9, units="mm")

    # 4. Range without units
    res4 = parse_legend_text("10.0 25.0 50.0")
    assert res4 == OcrLegendResult(vmin=10.0, vmax=50.0, units=None)

    # 5. Invalid: single number
    assert parse_legend_text("42") is None

    # 6. Invalid: no numbers
    assert parse_legend_text("No labels here") is None

    # 7. Invalid: empty string
    assert parse_legend_text("") is None

    # 8. Invalid: vmin >= vmax (all same numbers)
    assert parse_legend_text("5.0 5.0") is None


def test_f012_mocked_ac2_eight_synthetic_layouts() -> None:
    # F-012 AC2: extracts min and max within 1% in >= 6/8 cases (tested with mock OCR)
    layouts = [
        ("0.0 20.0 40.0 60.0 80.0 100.0 units", 0.0, 100.0, "units"),
        ("\u22124.0 \u22122.0 0.0 2.0 4.0 °C", -4.0, 4.0, "°C"),
        ("10.0 30.0 50.0 70.0 90.0 %", 10.0, 90.0, "%"),
        ("0.5 1.5 2.5 3.5 4.5 5.5 K", 0.5, 5.5, "K"),
        ("100 200 300 400 500 mm", 100.0, 500.0, "mm"),
        ("\u221210.0 \u22125.0 0.0 5.0 10.0 degC", -10.0, 10.0, "degC"),
        ("0.0 0.2 0.4 0.6 0.8 1.0", 0.0, 1.0, None),
        ("50 100 150 200 250 ppm", 50.0, 250.0, "ppm"),
    ]

    img = DecodedImage(
        rgb=np.ones((200, 400, 3), dtype=np.uint8) * 200,
        content_hash="test",
        original_width=400,
        original_height=200,
    )
    box = PixelBox(x=20, y=50, w=300, h=25)

    passed = 0
    with patch("earth_jukebox.infrastructure.vision.ocr.is_tesseract_available", return_value=True):
        for ocr_str, true_vmin, true_vmax, true_units in layouts:
            with patch("pytesseract.image_to_string", return_value=ocr_str):
                res = ocr_legend(img, box, Orientation.HORIZONTAL)
                assert res is not None
                val_range = true_vmax - true_vmin
                assert abs(res.vmin - true_vmin) <= 0.01 * val_range
                assert abs(res.vmax - true_vmax) <= 0.01 * val_range
                assert res.units == true_units
                passed += 1

    assert passed == 8


@pytest.mark.skipif(
    not is_tesseract_available(),
    reason="tesseract binary not installed on system (docs/10 §2)",
)
def test_f012_ac2_live_synthetic_bars() -> None:
    # F-012 AC2: live tesseract run on synthetic maps (skipped if tesseract binary is missing)
    decoder = PillowImageDecoder()
    passed = 0
    for seed in range(1, 9):
        png_bytes, _, legend, cbar_box, _ = generate_map(
            seed=seed,
            vmin=0.0,
            vmax=100.0,
            units="units",
            with_margin=True,
        )
        img = decoder.decode(png_bytes)
        res = ocr_legend(img, cbar_box, Orientation.HORIZONTAL)
        if res is not None:
            val_range = legend.vmax - legend.vmin
            if (
                abs(res.vmin - legend.vmin) <= 0.01 * val_range
                and abs(res.vmax - legend.vmax) <= 0.01 * val_range
            ):
                passed += 1

    assert passed >= 6, f"Expected >= 6/8, got {passed}/8"
