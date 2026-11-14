"""Legend metadata validation and construction (F-007).

Constructs LegendSpec from user input, validating ranges, categories, and diverging midpoints.
"""

from __future__ import annotations

from earth_jukebox.domain.errors import InvalidLegendError
from earth_jukebox.domain.models import (
    ColormapKind,
    LegendSpec,
    Orientation,
    ScaleType,
    VariableCategory,
)

CATEGORY_ALIASES: dict[str, VariableCategory] = {
    "wind_speed": VariableCategory.OCEAN,
    "wind": VariableCategory.OCEAN,
    "aerosol_optical_depth": VariableCategory.AEROSOL,
    "other": VariableCategory.GENERIC,
    "deep_space": VariableCategory.ICE,
    "lightning": VariableCategory.PRECIPITATION,
}


def build_legend_spec(
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
) -> tuple[LegendSpec, tuple[str, ...]]:
    """Validate and construct LegendSpec, adding warnings if defaults were applied (F-007).

    Returns:
        (LegendSpec, warnings)
    """
    if vmin >= vmax:
        raise InvalidLegendError(f"vmin must be < vmax (got vmin={vmin}, vmax={vmax})")

    # Validate category
    if isinstance(category, str):
        if category in CATEGORY_ALIASES:
            category_enum = CATEGORY_ALIASES[category]
        else:
            try:
                category_enum = VariableCategory(category)
            except ValueError as exc:
                raise InvalidLegendError(f"unknown variable category '{category}'") from exc
    else:
        category_enum = category

    # Validate scale
    if scale == ScaleType.LOG and vmin <= 0:
        raise InvalidLegendError(f"log scale requires vmin > 0, got {vmin}")

    warnings: list[str] = []

    # Diverging center handling (F-007 AC2)
    if kind == ColormapKind.DIVERGING and center is None:
        center = (vmin + vmax) / 2.0
        warnings.append("diverging_center_defaulted")

    if center is not None and not (vmin <= center <= vmax):
        raise InvalidLegendError(
            f"center ({center}) must lie within [vmin ({vmin}), vmax ({vmax})]"
        )

    if scale == ScaleType.LOG:
        warnings.append("log_scale_assumed")

    legend = LegendSpec(
        vmin=vmin,
        vmax=vmax,
        units=units,
        label=label,
        kind=kind,
        category=category_enum,
        center=center,
        orientation=orientation,
        low_at_start=low_at_start,
        scale=scale,
    )
    return legend, tuple(warnings)
