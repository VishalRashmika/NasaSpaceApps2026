"""Recover field use case (F-005, F-007, F-010, F-011).

Orchestrates input validation, region specification, extent verification,
and field recovery.
"""

from __future__ import annotations

from earth_jukebox.application.ports import FieldRecoverer
from earth_jukebox.application.use_cases.extent_check import check_extent
from earth_jukebox.application.use_cases.legend_metadata import build_legend_spec
from earth_jukebox.application.use_cases.region_spec import resolve_regions
from earth_jukebox.domain.models import (
    ColormapKind,
    DecodedImage,
    GeoExtent,
    Orientation,
    PixelBox,
    RecoveryQuality,
    ScalarField,
    ScaleType,
    VariableCategory,
)


def recover_field(
    image: DecodedImage,
    field_recoverer: FieldRecoverer,
    vmin: float,
    vmax: float,
    units: str,
    label: str,
    kind: ColormapKind,
    category: VariableCategory | str = VariableCategory.GENERIC,
    center: float | None = None,
    orientation: Orientation = Orientation.HORIZONTAL,
    low_at_start: bool = True,
    scale: ScaleType = ScaleType.LINEAR,
    map_box: PixelBox | None = None,
    colorbar_box: PixelBox | None = None,
    preset_name: str | None = None,
    extent: GeoExtent | None = None,
) -> ScalarField:
    """Recover ScalarField from DecodedImage with full metadata and validations."""
    # 1. Legend metadata validation (F-007)
    legend, legend_warnings = build_legend_spec(
        vmin=vmin,
        vmax=vmax,
        units=units,
        label=label,
        kind=kind,
        category=category,
        center=center,
        orientation=orientation,
        low_at_start=low_at_start,
        scale=scale,
    )

    # 2. Region validation on original coordinates (F-005)
    resolved_mbox, resolved_cbox = resolve_regions(
        img_w=image.original_width,
        img_h=image.original_height,
        map_box=map_box,
        colorbar_box=colorbar_box,
    )

    # 3. GeoExtent validation and projection warning (F-010)
    extent_obj = extent or GeoExtent()
    extent_warnings = check_extent(
        extent=extent_obj,
        map_width=resolved_mbox.w,
        map_height=resolved_mbox.h,
    )

    # 4. Perform recovery via infrastructure adapter
    field = field_recoverer.recover(
        image=image,
        legend=legend,
        map_box=resolved_mbox,
        colorbar_box=resolved_cbox,
        preset_name=preset_name,
    )

    # 5. Merge warnings into quality report
    all_warnings = list(field.quality.warnings)
    for w in legend_warnings + extent_warnings:
        if w not in all_warnings:
            all_warnings.append(w)

    confidence = field.quality.confidence
    if (
        "projection_unverified" in extent_warnings
        and "projection_unverified" not in field.quality.warnings
    ):
        confidence *= 0.8

    merged_quality = RecoveryQuality(
        mean_delta_e=field.quality.mean_delta_e,
        p95_delta_e=field.quality.p95_delta_e,
        masked_fraction=field.quality.masked_fraction,
        lut_is_monotonic_in_lightness=field.quality.lut_is_monotonic_in_lightness,
        confidence=confidence,
        mode=field.quality.mode,
        warnings=tuple(all_warnings),
    )

    return ScalarField(
        values=field.values,
        legend=legend,
        extent=extent_obj,
        quality=merged_quality,
        source_hash=image.content_hash,
    )
