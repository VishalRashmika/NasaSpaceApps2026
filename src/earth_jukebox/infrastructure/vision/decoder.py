"""Upload validation, decoding and image normalisation (F-001, F-002).

Implements ImageDecoder using Pillow and OpenCV for area downscaling.
"""

from __future__ import annotations

import contextlib
import hashlib
import io

import cv2
import numpy as np
from PIL import Image, ImageOps

from earth_jukebox.application.ports import ImageDecoder
from earth_jukebox.domain.errors import InvalidImageError
from earth_jukebox.domain.models import DecodedImage, PixelBox

SUPPORTED_FORMATS = ("PNG", "JPEG", "WEBP", "GIF")


def scale_box(box: PixelBox, from_w: int, from_h: int, to_w: int, to_h: int) -> PixelBox:
    """Scale a PixelBox from one image coordinate system to another (F-002 AC3)."""
    if from_w <= 0 or from_h <= 0 or to_w <= 0 or to_h <= 0:
        raise ValueError("dimensions must be positive")
    if from_w == to_w and from_h == to_h:
        return box

    sx = to_w / from_w
    sy = to_h / from_h
    x = round(box.x * sx)
    y = round(box.y * sy)
    w = max(1, round(box.w * sx))
    h = max(1, round(box.h * sy))

    x = min(max(0, x), to_w - 1)
    y = min(max(0, y), to_h - 1)
    w = min(w, to_w - x)
    h = min(h, to_h - y)
    return PixelBox(x=x, y=y, w=w, h=h)


class PillowImageDecoder(ImageDecoder):
    """ImageDecoder implementing F-001 and F-002."""

    def __init__(
        self,
        max_upload_bytes: int = 20 * 1024 * 1024,
        max_image_dimension: int = 8000,
        working_max_dimension: int = 2048,
    ) -> None:
        self.max_upload_bytes = max_upload_bytes
        self.max_image_dimension = max_image_dimension
        self.working_max_dimension = working_max_dimension

    def decode(self, data: bytes) -> DecodedImage:
        """Validate, decode, and normalise image bytes (F-001, F-002)."""
        # 1. Size check
        if len(data) > self.max_upload_bytes:
            raise InvalidImageError(
                f"image upload exceeds maximum size of {self.max_upload_bytes} bytes"
            )

        content_hash = hashlib.sha256(data).hexdigest()

        # 2. Open image with Pillow
        try:
            pil_img: Image.Image = Image.open(io.BytesIO(data))
        except Exception as exc:
            raise InvalidImageError(
                f"unrecognized image format or cannot decode image: {exc}"
            ) from exc

        # 3. Format check
        fmt = (pil_img.format or "").upper()
        if fmt not in SUPPORTED_FORMATS:
            raise InvalidImageError(f"unsupported image format '{fmt}'")

        # 4. Truncation / integrity check
        try:
            pil_img.seek(0)
            pil_img.load()
        except Exception as exc:
            raise InvalidImageError(f"corrupt or truncated image data: {exc}") from exc

        # 5. Dimension check
        orig_w, orig_h = pil_img.size
        if orig_w > self.max_image_dimension or orig_h > self.max_image_dimension:
            raise InvalidImageError(
                f"image dimension {max(orig_w, orig_h)} exceeds maximum of "
                f"{self.max_image_dimension} px/side ({orig_w}x{orig_h})"
            )

        # 6. EXIF orientation (F-002 AC2)
        with contextlib.suppress(Exception):
            pil_img = ImageOps.exif_transpose(pil_img) or pil_img

        orig_w, orig_h = pil_img.size

        # 7. Flatten alpha onto white (F-002 AC1)
        if pil_img.mode in ("RGBA", "LA") or (
            pil_img.mode == "P" and "transparency" in pil_img.info
        ):
            rgba_img = pil_img.convert("RGBA")
            bg = Image.new("RGBA", rgba_img.size, (255, 255, 255, 255))
            composite = Image.alpha_composite(bg, rgba_img)
            rgb_img = composite.convert("RGB")
        else:
            rgb_img = pil_img.convert("RGB")

        # 8. Convert to uint8 numpy array (H, W, 3)
        rgb_array = np.asarray(rgb_img, dtype=np.uint8)

        # 9. Downscale working copy if > working_max_dimension using area interpolation
        max_dim = max(orig_w, orig_h)
        if max_dim > self.working_max_dimension:
            scale = self.working_max_dimension / float(max_dim)
            target_w = round(orig_w * scale)
            target_h = round(orig_h * scale)
            resized = cv2.resize(rgb_array, (target_w, target_h), interpolation=cv2.INTER_AREA)
            rgb_array = np.asarray(resized, dtype=np.uint8)

        return DecodedImage(
            rgb=rgb_array,
            content_hash=content_hash,
            original_width=orig_w,
            original_height=orig_h,
        )
