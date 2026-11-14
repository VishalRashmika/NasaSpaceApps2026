"""OCR legend assist (F-012).

Reads numbers and units near the colorbar to propose vmin/vmax/units.
Optional extra using pytesseract and the system tesseract binary (docs/05).
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass

import cv2
import numpy as np

from earth_jukebox.domain.models import DecodedImage, Orientation, PixelBox
from earth_jukebox.infrastructure.vision.decoder import scale_box


@dataclass(frozen=True)
class OcrLegendResult:
    """Proposed physical range and units extracted via OCR from colorbar tick labels (F-012)."""

    vmin: float
    vmax: float
    units: str | None = None


def is_tesseract_available() -> bool:
    """Check if the tesseract system binary and pytesseract are available."""
    if shutil.which("tesseract") is None:
        return False
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def parse_legend_text(text: str) -> OcrLegendResult | None:
    """Parse physical min/max values and optional units from OCR text (F-012)."""
    norm = text.replace("\u2212", "-").replace("—", "-").strip()
    if not norm:
        return None

    # Find all signed floating point and integer numbers
    num_strs = re.findall(r"[-+]?(?:\d*\.\d+|\d+)", norm)
    nums: list[float] = []
    for s in num_strs:
        try:
            nums.append(float(s))
        except ValueError:
            continue

    if len(nums) < 2:
        return None

    vmin = min(nums)
    vmax = max(nums)
    if vmin >= vmax:
        return None

    # Search for scientific units
    units: str | None = None
    units_match = re.search(
        r"(°C|degC|K|mm|cm|m|km|kg|g|%|ppm|DU|W/m²|W/m2|m/s|hPa|units)",
        norm,
        re.IGNORECASE,
    )
    if units_match:
        units = units_match.group(1)

    return OcrLegendResult(vmin=vmin, vmax=vmax, units=units)


def _crop_tick_region(
    rgb: np.ndarray,
    colorbar_box: PixelBox,
    orientation: Orientation,
) -> np.ndarray:
    """Crop image area adjacent to colorbar where tick labels and units are drawn."""
    h, w = rgb.shape[:2]

    if orientation == Orientation.HORIZONTAL:
        # Tick labels typically drawn below the horizontal colorbar
        y0 = max(0, colorbar_box.y - 10)
        y1 = min(h, colorbar_box.y + colorbar_box.h + max(50, int(colorbar_box.h * 2.5)))
        x0 = max(0, colorbar_box.x - 30)
        x1 = min(w, colorbar_box.x + colorbar_box.w + 30)
    else:
        # Tick labels typically drawn to the right of the vertical colorbar
        x0 = max(0, colorbar_box.x - 10)
        x1 = min(w, colorbar_box.x + colorbar_box.w + max(60, int(colorbar_box.w * 3.0)))
        y0 = max(0, colorbar_box.y - 30)
        y1 = min(h, colorbar_box.y + colorbar_box.h + 30)

    return rgb[y0:y1, x0:x1]


def ocr_legend(
    image: DecodedImage,
    colorbar_box: PixelBox,
    orientation: Orientation = Orientation.HORIZONTAL,
) -> OcrLegendResult | None:
    """Extract candidate vmin, vmax, and units from image near colorbar (F-012).

    Returns None if Tesseract is not available or if numbers cannot be parsed.
    Never raises exceptions.
    """
    if not is_tesseract_available():
        return None

    try:
        import pytesseract

        working_h, working_w = image.rgb.shape[:2]
        cbar_working = scale_box(
            colorbar_box,
            from_w=image.original_width,
            from_h=image.original_height,
            to_w=working_w,
            to_h=working_h,
        )

        crop = _crop_tick_region(image.rgb, cbar_working, orientation)
        if crop.size == 0:
            return None

        # Preprocess: grayscale and 2x upscale for clearer OCR recognition
        gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
        scaled_gray = cv2.resize(gray, (0, 0), fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

        text = str(pytesseract.image_to_string(scaled_gray, config="--psm 6"))
        return parse_legend_text(text)
    except Exception:
        return None
