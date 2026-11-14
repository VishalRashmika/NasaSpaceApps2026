"""Tests for F-001 (Upload validation & decoding) and F-002 (Image normalisation)."""

from __future__ import annotations

import hashlib
import io

import numpy as np
import pytest
from PIL import Image

from earth_jukebox.domain.errors import InvalidImageError
from earth_jukebox.domain.models import PixelBox
from earth_jukebox.infrastructure.vision.decoder import PillowImageDecoder, scale_box


def _make_image_bytes(fmt: str, size: tuple[int, int] = (100, 80), mode: str = "RGB") -> bytes:
    img = Image.new(mode, size, color=(120, 150, 180) if mode == "RGB" else (120, 150, 180, 255))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


# ---------------------------------------------------------------- F-001 AC tests
def test_f001_ac1_supported_formats() -> None:
    # F-001 AC1: valid PNG/JPEG/WebP/GIF fixtures decode to (H,W,3) uint8.
    decoder = PillowImageDecoder()
    for fmt in ("PNG", "JPEG", "WEBP", "GIF"):
        data = _make_image_bytes(fmt)
        decoded = decoder.decode(data)
        assert decoded.rgb.ndim == 3
        assert decoded.rgb.shape[2] == 3
        assert decoded.rgb.dtype == np.uint8
        assert decoded.original_width == 100
        assert decoded.original_height == 80


def test_f001_ac2_distinct_invalid_image_errors() -> None:
    # F-001 AC2: a text file renamed .png, a truncated PNG, and a 9000x10 PNG
    # each raise InvalidImageError (distinct messages).
    decoder = PillowImageDecoder()

    # 1. Text file
    text_data = b"This is not a PNG file, just plain text."
    with pytest.raises(InvalidImageError) as exc_text:
        decoder.decode(text_data)
    msg_text = str(exc_text.value)

    # 2. Truncated PNG
    valid_png = _make_image_bytes("PNG")
    truncated_png = valid_png[: len(valid_png) // 3]
    with pytest.raises(InvalidImageError) as exc_trunc:
        decoder.decode(truncated_png)
    msg_trunc = str(exc_trunc.value)

    # 3. 9000x10 PNG
    img_large = Image.new("RGB", (9000, 10), color="red")
    buf_large = io.BytesIO()
    img_large.save(buf_large, format="PNG")
    large_png = buf_large.getvalue()

    with pytest.raises(InvalidImageError) as exc_large:
        decoder.decode(large_png)
    msg_large = str(exc_large.value)

    # All three messages must be distinct
    assert msg_text != msg_trunc
    assert msg_text != msg_large
    assert msg_trunc != msg_large


def test_f001_ac3_content_hash() -> None:
    # F-001 AC3: content_hash equals hashlib.sha256(original_bytes).hexdigest().
    decoder = PillowImageDecoder()
    data = _make_image_bytes("PNG")
    decoded = decoder.decode(data)
    expected_hash = hashlib.sha256(data).hexdigest()
    assert decoded.content_hash == expected_hash


def test_f001_size_cap() -> None:
    decoder = PillowImageDecoder(max_upload_bytes=100)
    data = _make_image_bytes("PNG")
    assert len(data) > 100
    with pytest.raises(InvalidImageError) as exc:
        decoder.decode(data)
    assert "maximum size" in str(exc.value)


# ---------------------------------------------------------------- F-002 AC tests
def test_f002_ac1_alpha_flattened_to_white() -> None:
    # F-002 AC1: RGBA with transparent corners -> corners white.
    img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 255))
    # make (0, 0) transparent
    img.putpixel((0, 0), (0, 0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()

    decoder = PillowImageDecoder()
    decoded = decoder.decode(data)

    # Corner (0, 0) must be white (255, 255, 255)
    np.testing.assert_array_equal(decoded.rgb[0, 0], [255, 255, 255])
    # Center (50, 50) must remain red (255, 0, 0)
    np.testing.assert_array_equal(decoded.rgb[50, 50], [255, 0, 0])


def test_f002_ac2_exif_orientation_upright() -> None:
    # F-002 AC2: EXIF-rotated JPEG fixture comes out upright.
    # Orientation 6 means 90 deg CW rotation needed to be upright.
    img = Image.new("RGB", (100, 60), color="blue")
    # Draw a marker at (0, 0)
    img.putpixel((0, 0), (255, 255, 0))
    exif = img.getexif()
    exif[0x0112] = 6  # Orientation tag = 6 (Rotate 90 CW)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    data = buf.getvalue()

    decoder = PillowImageDecoder()
    decoded = decoder.decode(data)

    # After orientation 6 transpose, (100, 60) becomes (60, 100)
    assert decoded.rgb.shape[0] == 100
    assert decoded.rgb.shape[1] == 60


def test_f002_ac3_scale_box_round_trip() -> None:
    # F-002 AC3: boxes given in original coordinates are mapped to working
    # coordinates by scale_box, round-trip error <= 1 px.
    orig_box = PixelBox(x=123, y=456, w=789, h=321)
    orig_w, orig_h = 3000, 2000
    work_w, work_h = 1500, 1000

    work_box = scale_box(orig_box, orig_w, orig_h, work_w, work_h)
    round_trip_box = scale_box(work_box, work_w, work_h, orig_w, orig_h)

    assert abs(round_trip_box.x - orig_box.x) <= 1
    assert abs(round_trip_box.y - orig_box.y) <= 1
    assert abs(round_trip_box.w - orig_box.w) <= 1
    assert abs(round_trip_box.h - orig_box.h) <= 1


def test_f002_downscale_to_working_dimension() -> None:
    # 4000x2000 image downscaled to working_max_dimension=2048
    img = Image.new("RGB", (4000, 2000), color="green")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()

    decoder = PillowImageDecoder(working_max_dimension=2048)
    decoded = decoder.decode(data)

    assert decoded.original_width == 4000
    assert decoded.original_height == 2000
    assert decoded.rgb.shape[1] == 2048
    assert decoded.rgb.shape[0] == 1024
