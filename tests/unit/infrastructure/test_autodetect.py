"""Tests for F-004: Colorbar auto-detection."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from earth_jukebox.domain.models import DecodedImage, Orientation
from earth_jukebox.infrastructure.storage.samples import FileSystemSampleRepository
from earth_jukebox.infrastructure.vision.autodetect import (
    _compute_iou,
    detect_colorbar,
)
from earth_jukebox.infrastructure.vision.decoder import PillowImageDecoder
from earth_jukebox.infrastructure.vision.synthetic import generate_map


def test_f004_ac1_eight_synthetic_layouts() -> None:
    # F-004 AC1: on >= 8 synthetic layouts, true box is top candidate with IoU >= 0.8 in >= 7 of 8.
    layouts = [
        # 1. viridis, horizontal, with margin, without outline, with title
        {
            "cmap": "viridis",
            "orientation": Orientation.HORIZONTAL,
            "with_margin": True,
            "with_outline": False,
            "with_title": True,
        },
        # 2. viridis, vertical, with margin, without outline, with title
        {
            "cmap": "viridis",
            "orientation": Orientation.VERTICAL,
            "with_margin": True,
            "with_outline": False,
            "with_title": True,
        },
        # 3. turbo, horizontal, without margin, without outline, without title
        {
            "cmap": "turbo",
            "orientation": Orientation.HORIZONTAL,
            "with_margin": False,
            "with_outline": False,
            "with_title": False,
        },
        # 4. RdBu_r, vertical, without margin, without outline, without title
        {
            "cmap": "RdBu_r",
            "orientation": Orientation.VERTICAL,
            "with_margin": False,
            "with_outline": False,
            "with_title": False,
        },
        # 5. plasma, horizontal, with margin, with outline, with title
        {
            "cmap": "plasma",
            "orientation": Orientation.HORIZONTAL,
            "with_margin": True,
            "with_outline": True,
            "with_title": True,
        },
        # 6. Blues, vertical, with margin, with outline, with title
        {
            "cmap": "Blues",
            "orientation": Orientation.VERTICAL,
            "with_margin": True,
            "with_outline": True,
            "with_title": True,
        },
        # 7. magma, horizontal, without margin, with outline, without title
        {
            "cmap": "magma",
            "orientation": Orientation.HORIZONTAL,
            "with_margin": False,
            "with_outline": True,
            "with_title": False,
        },
        # 8. coolwarm, vertical, without margin, with outline, without title
        {
            "cmap": "coolwarm",
            "orientation": Orientation.VERTICAL,
            "with_margin": False,
            "with_outline": True,
            "with_title": False,
        },
    ]

    decoder = PillowImageDecoder()
    passed = 0

    for i, cfg in enumerate(layouts):
        png_bytes, _, _, true_cbar, _ = generate_map(seed=i + 1, **cfg)
        img = decoder.decode(png_bytes)
        cands = detect_colorbar(img)

        assert len(cands) >= 1
        top = cands[0]
        iou = _compute_iou(top.box, true_cbar)
        if iou >= 0.8:
            passed += 1

    assert passed >= 7, f"Expected at least 7/8 layouts with IoU >= 0.8, got {passed}/8"


def test_f004_ac2_blank_and_noise_images() -> None:
    # F-004 AC2: on blank/noise images returns an empty list, not an error.
    # 1. Blank white image
    white_rgb = np.ones((400, 600, 3), dtype=np.uint8) * 255
    white_img = DecodedImage(
        rgb=white_rgb,
        content_hash="white",
        original_width=600,
        original_height=400,
    )
    assert detect_colorbar(white_img) == []

    # 2. Blank black image
    black_rgb = np.zeros((400, 600, 3), dtype=np.uint8)
    black_img = DecodedImage(
        rgb=black_rgb,
        content_hash="black",
        original_width=600,
        original_height=400,
    )
    assert detect_colorbar(black_img) == []

    # 3. Uniform random noise
    rng = np.random.default_rng(12345)
    noise_rgb = rng.integers(0, 256, (400, 600, 3), dtype=np.uint8)
    noise_img = DecodedImage(
        rgb=noise_rgb,
        content_hash="noise",
        original_width=600,
        original_height=400,
    )
    assert detect_colorbar(noise_img) == []

    # 4. Tiny image (smaller than minimal dimensions)
    tiny_rgb = np.ones((5, 5, 3), dtype=np.uint8) * 128
    tiny_img = DecodedImage(
        rgb=tiny_rgb,
        content_hash="tiny",
        original_width=5,
        original_height=5,
    )
    assert detect_colorbar(tiny_img) == []


@pytest.mark.needs_real_samples
def test_f004_ac3_real_samples() -> None:
    # F-004 AC3: on real samples report hit-rate; skipped if no samples present.
    repo = FileSystemSampleRepository(Path("data/samples"))
    samples = repo.list()
    if not samples:
        pytest.skip("no real samples in data/samples")

    decoder = PillowImageDecoder()
    hits = 0
    for meta in samples:
        if meta.colorbar_box is None:
            continue
        data = repo.image_bytes(meta.id)
        img = decoder.decode(data)
        cands = detect_colorbar(img)
        if cands and _compute_iou(cands[0].box, meta.colorbar_box) >= 0.5:
            hits += 1


def test_f004_scaling_coordinates() -> None:
    # When image is downscaled, detected candidate box is in original image coordinates
    png_bytes, _, _, true_cbar, _ = generate_map(
        seed=42,
        map_width=1024,
        map_height=512,
        with_margin=True,
    )
    # Decode with a smaller working max dimension to force downscaling
    small_decoder = PillowImageDecoder(working_max_dimension=400)
    img = small_decoder.decode(png_bytes)
    assert img.rgb.shape[1] < img.original_width

    cands = detect_colorbar(img)
    assert len(cands) >= 1
    top = cands[0]
    # top.box must be in original coordinates (original_width/height scale)
    iou = _compute_iou(top.box, true_cbar)
    assert iou >= 0.75
