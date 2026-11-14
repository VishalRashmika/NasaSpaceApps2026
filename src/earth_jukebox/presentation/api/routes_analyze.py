"""Analyze and colorbar detection endpoints (F-061, F-004)."""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Annotated, Any

import numpy as np
from fastapi import APIRouter, Depends, File, Form, UploadFile

from earth_jukebox.application.services import Services
from earth_jukebox.application.use_cases.recover_field import recover_field
from earth_jukebox.domain.errors import InvalidImageError, InvalidLegendError
from earth_jukebox.domain.mapping_version import MAPPING_VERSION
from earth_jukebox.domain.models import (
    ColormapKind,
    GeoExtent,
    Orientation,
    PixelBox,
    ScaleType,
    VariableCategory,
)
from earth_jukebox.presentation.api.dependencies import get_services
from earth_jukebox.presentation.api.schemas import (
    AnalyzeResponse,
    BoxSchema,
    ColorbarCandidateResponse,
    DetectColorbarResponse,
    GridSummary,
    ImageDimensions,
    QualityResponse,
    confidence_badge,
)

router = APIRouter(prefix="/api", tags=["analyze"])


def _compute_analysis_id(
    image_hash: str,
    legend_data: dict[str, Any],
    cbox: PixelBox | None,
    mbox: PixelBox | None,
    preset: str | None,
    extent: GeoExtent | None,
    category_id: str | None = None,
) -> str:
    canonical_payload = {
        "legend": legend_data,
        "colorbar_box": {"x": cbox.x, "y": cbox.y, "w": cbox.w, "h": cbox.h} if cbox else None,
        "map_box": {"x": mbox.x, "y": mbox.y, "w": mbox.w, "h": mbox.h} if mbox else None,
        "preset": preset,
        "category_id": category_id,
        "extent": {
            "lat_min": extent.lat_min,
            "lat_max": extent.lat_max,
            "lon_min": extent.lon_min,
            "lon_max": extent.lon_max,
            "projection": extent.projection,
        }
        if extent
        else None,
        "mapping_version": MAPPING_VERSION,
    }
    canonical_str = json.dumps(canonical_payload, sort_keys=True)
    return hashlib.sha256((image_hash + canonical_str).encode("utf-8")).hexdigest()[:16]


@router.post("/detect-colorbar", response_model=DetectColorbarResponse)
async def detect_colorbar_endpoint(
    image: Annotated[UploadFile, File(...)],
    services: Annotated[Services, Depends(get_services)],
) -> DetectColorbarResponse:
    """Auto-detect candidate colorbar bounding boxes and orientations (F-004)."""
    raw_bytes = await image.read()
    if services.image_decoder is None:
        raise InvalidImageError("Image decoder service unavailable")

    decoded = services.image_decoder.decode(raw_bytes)
    if services.colorbar_detector is None:
        return DetectColorbarResponse(candidates=[])

    candidates = services.colorbar_detector.detect(decoded)
    return DetectColorbarResponse(
        candidates=[
            ColorbarCandidateResponse(
                box=BoxSchema(x=c.box.x, y=c.box.y, w=c.box.w, h=c.box.h),
                orientation=c.orientation.value,
                score=c.score,
            )
            for c in candidates
        ]
    )


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_endpoint(
    image: Annotated[UploadFile, File(...)],
    legend: Annotated[str, Form(...)],
    services: Annotated[Services, Depends(get_services)],
    colorbar_box: Annotated[str | None, Form()] = None,
    map_box: Annotated[str | None, Form()] = None,
    preset: Annotated[str | None, Form()] = None,
    extent: Annotated[str | None, Form()] = None,
    category_id: Annotated[str | None, Form()] = None,
) -> AnalyzeResponse:
    """Analyze image and recover scalar data field with quality metrics (F-061)."""
    raw_bytes = await image.read()
    max_bytes = services.settings.max_upload_bytes
    if len(raw_bytes) > max_bytes:
        raise InvalidImageError(f"image upload exceeds maximum size of {max_bytes} bytes")

    if services.image_decoder is None or services.field_recoverer is None:
        raise InvalidImageError("Required recovery services not available")

    # Decode and validate image
    decoded = services.image_decoder.decode(raw_bytes)

    # Parse legend metadata
    try:
        legend_data = json.loads(legend)
    except Exception as exc:
        raise InvalidLegendError(f"invalid JSON in legend: {exc}") from exc

    if not isinstance(legend_data, dict):
        raise InvalidLegendError("legend must be a JSON object")

    try:
        vmin = float(legend_data["vmin"])
        vmax = float(legend_data["vmax"])
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidLegendError(f"legend requires numeric vmin and vmax: {exc}") from exc

    units = str(legend_data.get("units", ""))
    label = str(legend_data.get("label", ""))

    kind_raw = legend_data.get("kind", "sequential")
    try:
        kind = ColormapKind(kind_raw)
    except ValueError as exc:
        raise InvalidLegendError(f"unknown colormap kind: '{kind_raw}'") from exc

    cat_raw = legend_data.get("category", "generic")
    try:
        category = VariableCategory(cat_raw)
    except ValueError as exc:
        raise InvalidLegendError(f"unknown variable category: '{cat_raw}'") from exc

    center = float(legend_data["center"]) if legend_data.get("center") is not None else None

    ori_raw = legend_data.get("orientation", "horizontal")
    try:
        orientation = Orientation(ori_raw)
    except ValueError as exc:
        raise InvalidLegendError(f"unknown orientation: '{ori_raw}'") from exc

    low_at_start = bool(legend_data.get("low_at_start", True))

    scale_raw = legend_data.get("scale", "linear")
    try:
        scale = ScaleType(scale_raw)
    except ValueError as exc:
        raise InvalidLegendError(f"unknown scale type: '{scale_raw}'") from exc

    # Parse boxes if provided
    cbox: PixelBox | None = None
    if colorbar_box:
        try:
            cbd = json.loads(colorbar_box)
            cbox = PixelBox(x=int(cbd["x"]), y=int(cbd["y"]), w=int(cbd["w"]), h=int(cbd["h"]))
        except Exception as exc:
            raise InvalidLegendError(f"invalid colorbar_box: {exc}") from exc

    mbox: PixelBox | None = None
    if map_box:
        try:
            mbd = json.loads(map_box)
            mbox = PixelBox(x=int(mbd["x"]), y=int(mbd["y"]), w=int(mbd["w"]), h=int(mbd["h"]))
        except Exception as exc:
            raise InvalidLegendError(f"invalid map_box: {exc}") from exc

    # Resolve category-driven legend preset if no manual preset/colorbar supplied (F-108)
    if not preset and cbox is None and category_id and services.colormap_catalog is not None:
        cat_candidates = [
            f"category:{category_id}",
            category_id,
            f"category:{category_id.lower()}",
            category_id.lower(),
        ]
        available_names = set(services.colormap_catalog.names())
        for cand in cat_candidates:
            if cand in available_names:
                preset = cand
                break

    extent_obj: GeoExtent | None = None
    if extent:
        try:
            extd = json.loads(extent)
            extent_obj = GeoExtent(
                lat_min=float(extd.get("lat_min", -90.0)),
                lat_max=float(extd.get("lat_max", 90.0)),
                lon_min=float(extd.get("lon_min", -180.0)),
                lon_max=float(extd.get("lon_max", 180.0)),
                projection=str(extd.get("projection", "equirectangular")),
            )
        except Exception as exc:
            raise InvalidLegendError(f"invalid extent: {exc}") from exc

    # Check if input is multi-frame animation (F-090, F-091)
    frames = [decoded]
    if services.frame_extractor is not None:
        try:
            extracted = services.frame_extractor.extract_frames(raw_bytes)
            if len(extracted) > 1:
                frames = list(extracted)
        except Exception:
            pass

    is_animation = len(frames) > 1
    n_frames = len(frames)

    # Execute recovery use case
    if is_animation:
        import dataclasses

        recovered_fields = [
            recover_field(
                image=f,
                field_recoverer=services.field_recoverer,
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
                map_box=mbox,
                colorbar_box=cbox,
                preset_name=preset,
                extent=extent_obj,
            )
            for f in frames
        ]
        stacked = np.stack([rf.values for rf in recovered_fields], axis=0)
        field = dataclasses.replace(recovered_fields[0], values=stacked)
    else:
        field = recover_field(
            image=decoded,
            field_recoverer=services.field_recoverer,
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
            map_box=mbox,
            colorbar_box=cbox,
            preset_name=preset,
            extent=extent_obj,
        )

    # Compute analysis_id
    analysis_id = _compute_analysis_id(
        image_hash=decoded.content_hash,
        legend_data=legend_data,
        cbox=cbox,
        mbox=mbox,
        preset=preset,
        extent=extent_obj,
        category_id=category_id,
    )

    # Persist in analysis_store
    if services.analysis_store is not None:
        services.analysis_store.save(analysis_id, field)

    # Generate preview PNG
    field_preview_png = ""
    frame_previews: list[str] = []
    if services.field_preview_renderer is not None:
        first_2d = (
            field if field.values.ndim == 2 else dataclasses.replace(field, values=field.values[0])
        )
        preview_bytes = services.field_preview_renderer.render_preview_png(first_2d, width=512)
        b64 = base64.b64encode(preview_bytes).decode("ascii")
        field_preview_png = f"data:image/png;base64,{b64}"

        if is_animation:
            for rf in recovered_fields:
                fp_bytes = services.field_preview_renderer.render_preview_png(rf, width=128)
                fp_b64 = base64.b64encode(fp_bytes).decode("ascii")
                frame_previews.append(f"data:image/png;base64,{fp_b64}")

    valid_vals = field.values[~np.isnan(field.values)]
    grid_min = float(np.min(valid_vals)) if len(valid_vals) > 0 else None
    grid_max = float(np.max(valid_vals)) if len(valid_vals) > 0 else None

    return AnalyzeResponse(
        analysis_id=analysis_id,
        quality=QualityResponse(
            confidence=field.quality.confidence,
            confidence_badge=confidence_badge(field.quality.confidence),
            mean_delta_e=field.quality.mean_delta_e,
            p95_delta_e=field.quality.p95_delta_e,
            masked_fraction=field.quality.masked_fraction,
            warnings=list(field.quality.warnings),
            recovery_mode=(
                field.quality.mode.value
                if hasattr(field.quality.mode, "value")
                else str(field.quality.mode)
            ),
        ),
        warnings=list(field.quality.warnings),
        field_preview_png=field_preview_png,
        grid=GridSummary(
            rows=field.values.shape[-2],
            cols=field.values.shape[-1],
            min=grid_min,
            max=grid_max,
        ),
        image=ImageDimensions(
            width=decoded.original_width,
            height=decoded.original_height,
        ),
        is_animation=is_animation,
        n_frames=n_frames,
        frame_previews=frame_previews,
    )
