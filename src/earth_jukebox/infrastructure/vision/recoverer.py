"""Field recoverer implementation (F-006, F-008, F-009, F-011, F-013).

Implements FieldRecoverer protocol to recover ScalarField from DecodedImage
using Colorbar, Preset, or Luminance fallback modes.
"""

from __future__ import annotations

import numpy as np

from earth_jukebox.application.ports import ColormapCatalog, FieldRecoverer
from earth_jukebox.application.use_cases.quality import (
    compute_quality,
    is_lut_monotonic_in_lightness,
)
from earth_jukebox.application.use_cases.region_spec import resolve_regions
from earth_jukebox.domain.models import (
    ColorLUT,
    DecodedImage,
    GeoExtent,
    LegendSpec,
    PixelBox,
    RecoveryMode,
    ScalarField,
    ScaleType,
)
from earth_jukebox.infrastructure.vision.decoder import scale_box
from earth_jukebox.infrastructure.vision.inversion import (
    apply_masking,
    invert_field,
    luminance_fallback,
)
from earth_jukebox.infrastructure.vision.lut import extract_lut


class VisionFieldRecoverer(FieldRecoverer):
    """FieldRecoverer adapter implementing full recovery pipeline (docs/05)."""

    def __init__(self, colormap_catalog: ColormapCatalog) -> None:
        self.catalog = colormap_catalog

    def recover(
        self,
        image: DecodedImage,
        legend: LegendSpec,
        map_box: PixelBox | None,
        colorbar_box: PixelBox | None,
        preset_name: str | None,
    ) -> ScalarField:
        """Recover ScalarField from DecodedImage with strict fallback order (doc 05 section 1)."""
        work_h, work_w = image.rgb.shape[:2]
        orig_w = image.original_width
        orig_h = image.original_height

        # 1. Scale boxes from original coordinates to working coordinates (F-002 AC3)
        scaled_cbox: PixelBox | None = None
        if colorbar_box is not None:
            scaled_cbox = scale_box(colorbar_box, orig_w, orig_h, work_w, work_h)

        scaled_mbox: PixelBox | None = None
        if map_box is not None:
            scaled_mbox = scale_box(map_box, orig_w, orig_h, work_w, work_h)

        # Resolve regions if map_box was omitted (F-005)
        resolved_mbox, resolved_cbox = resolve_regions(
            img_w=work_w,
            img_h=work_h,
            map_box=scaled_mbox,
            colorbar_box=scaled_cbox,
        )

        map_crop = image.rgb[
            resolved_mbox.y : resolved_mbox.y + resolved_mbox.h,
            resolved_mbox.x : resolved_mbox.x + resolved_mbox.w,
        ]

        # 2. Mode selection (doc 05 section 1)
        if resolved_cbox is not None:
            mode = RecoveryMode.COLORBAR
            lut = extract_lut(image.rgb, resolved_cbox, legend)
            raw_values, dists = invert_field(map_crop, lut)
            values, dists = apply_masking(raw_values, dists, map_crop, lut)
            lut_monotonic = is_lut_monotonic_in_lightness(lut.lab)
        elif preset_name is not None:
            mode = RecoveryMode.PRESET
            cat_lut = self.catalog.lut(preset_name, n=256)
            # Scale preset LUT values from [0, 1] to legend range
            n_lut = len(cat_lut.lab)
            if legend.scale == ScaleType.LOG:
                log_vmin = np.log10(legend.vmin)
                log_vmax = np.log10(legend.vmax)
                scaled_values = np.logspace(log_vmin, log_vmax, n_lut, dtype=np.float64)
            else:
                scaled_values = np.linspace(legend.vmin, legend.vmax, n_lut, dtype=np.float64)

            lut = ColorLUT(
                lab=cat_lut.lab,
                values=scaled_values,
                source=RecoveryMode.PRESET,
            )
            raw_values, dists = invert_field(map_crop, lut)
            values, dists = apply_masking(raw_values, dists, map_crop, lut)
            lut_monotonic = is_lut_monotonic_in_lightness(lut.lab)
        else:
            mode = RecoveryMode.LUMINANCE_FALLBACK
            values, dists = luminance_fallback(map_crop, legend)
            lut_monotonic = True

        # 3. Quality report (F-011)
        quality = compute_quality(
            values=values,
            distances=dists,
            mode=mode,
            lut_is_monotonic_in_lightness=lut_monotonic,
            map_width=resolved_mbox.w,
        )

        return ScalarField(
            values=values,
            legend=legend,
            extent=GeoExtent(),
            quality=quality,
            source_hash=image.content_hash,
        )
