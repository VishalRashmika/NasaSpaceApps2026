"""Jukebox catalog endpoints (F-065)."""

from __future__ import annotations

import base64
import mimetypes
import re
from typing import Annotated, Any

import numpy as np
from fastapi import APIRouter, Depends, Response

from earth_jukebox.application.services import Services
from earth_jukebox.application.use_cases.recover_field import recover_field
from earth_jukebox.domain.errors import NotFoundError
from earth_jukebox.presentation.api.dependencies import get_services
from earth_jukebox.presentation.api.routes_analyze import _compute_analysis_id
from earth_jukebox.presentation.api.schemas import (
    AnalyzeResponse,
    BoxSchema,
    ExtentMetaSchema,
    GridSummary,
    ImageDimensions,
    LegendMetaSchema,
    QualityResponse,
    SampleMetaResponse,
    SampleSummaryResponse,
    confidence_badge,
)

router = APIRouter(prefix="/api/samples", tags=["samples"])

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _validate_id(sample_id: str) -> None:
    if not ID_PATTERN.match(sample_id):
        raise NotFoundError(f"sample '{sample_id}' not found")


@router.get("", response_model=list[SampleSummaryResponse])
def list_samples(
    services: Annotated[Services, Depends(get_services)],
) -> list[SampleSummaryResponse]:
    """List bundled gallery samples (F-065)."""
    if services.sample_repository is None:
        return []

    samples = services.sample_repository.list()
    return [
        SampleSummaryResponse(
            id=s.id,
            title=s.title,
            category=s.legend.category.value,
            thumb_url=f"/api/samples/{s.id}/image",
            credit=s.credit,
        )
        for s in samples
    ]


@router.get("/{sample_id}", response_model=SampleMetaResponse)
def get_sample_meta(
    sample_id: str,
    services: Annotated[Services, Depends(get_services)],
) -> SampleMetaResponse:
    """Get metadata for a specific sample (F-065)."""
    _validate_id(sample_id)
    if services.sample_repository is None:
        raise NotFoundError(f"sample '{sample_id}' not found")

    sample = services.sample_repository.get(sample_id)
    return SampleMetaResponse(
        id=sample.id,
        title=sample.title,
        image_file=sample.image_file,
        legend=LegendMetaSchema(
            vmin=sample.legend.vmin,
            vmax=sample.legend.vmax,
            units=sample.legend.units,
            label=sample.legend.label,
            kind=sample.legend.kind.value,
            category=sample.legend.category.value,
            center=sample.legend.center,
            orientation=sample.legend.orientation.value,
            low_at_start=sample.legend.low_at_start,
            scale=sample.legend.scale.value,
        ),
        extent=ExtentMetaSchema(
            lat_min=sample.extent.lat_min,
            lat_max=sample.extent.lat_max,
            lon_min=sample.extent.lon_min,
            lon_max=sample.extent.lon_max,
            projection=sample.extent.projection,
        ),
        source_url=sample.source_url,
        credit=sample.credit,
        description=sample.description,
        map_box=BoxSchema(
            x=sample.map_box.x,
            y=sample.map_box.y,
            w=sample.map_box.w,
            h=sample.map_box.h,
        )
        if sample.map_box
        else None,
        colorbar_box=BoxSchema(
            x=sample.colorbar_box.x,
            y=sample.colorbar_box.y,
            w=sample.colorbar_box.w,
            h=sample.colorbar_box.h,
        )
        if sample.colorbar_box
        else None,
        in_gallery=sample.in_gallery,
    )


@router.get("/{sample_id}/image")
def get_sample_image(
    sample_id: str,
    services: Annotated[Services, Depends(get_services)],
) -> Response:
    """Get image bytes for a sample (F-065)."""
    _validate_id(sample_id)
    if services.sample_repository is None:
        raise NotFoundError(f"sample '{sample_id}' not found")

    sample = services.sample_repository.get(sample_id)
    img_bytes = services.sample_repository.image_bytes(sample_id)
    mime_type, _ = mimetypes.guess_type(sample.image_file)
    content_type = mime_type or "image/png"

    return Response(content=img_bytes, media_type=content_type)


@router.post("/{sample_id}/analyze", response_model=AnalyzeResponse)
def analyze_sample(
    sample_id: str,
    services: Annotated[Services, Depends(get_services)],
) -> AnalyzeResponse:
    """Analyze a catalog sample using its ground-truth annotations (F-065)."""
    _validate_id(sample_id)
    if (
        services.sample_repository is None
        or services.image_decoder is None
        or services.field_recoverer is None
    ):
        raise NotFoundError(f"sample '{sample_id}' not found")

    sample = services.sample_repository.get(sample_id)
    raw_bytes = services.sample_repository.image_bytes(sample_id)
    decoded = services.image_decoder.decode(raw_bytes)

    field = recover_field(
        image=decoded,
        field_recoverer=services.field_recoverer,
        vmin=sample.legend.vmin,
        vmax=sample.legend.vmax,
        units=sample.legend.units,
        label=sample.legend.label,
        kind=sample.legend.kind,
        category=sample.legend.category,
        center=sample.legend.center,
        orientation=sample.legend.orientation,
        low_at_start=sample.legend.low_at_start,
        scale=sample.legend.scale,
        map_box=sample.map_box,
        colorbar_box=sample.colorbar_box,
        preset_name=None,
        extent=sample.extent,
    )

    legend_data: dict[str, Any] = {
        "vmin": sample.legend.vmin,
        "vmax": sample.legend.vmax,
        "units": sample.legend.units,
        "label": sample.legend.label,
        "kind": sample.legend.kind.value,
        "category": sample.legend.category.value,
        "center": sample.legend.center,
        "orientation": sample.legend.orientation.value,
        "low_at_start": sample.legend.low_at_start,
        "scale": sample.legend.scale.value,
    }

    analysis_id = _compute_analysis_id(
        image_hash=decoded.content_hash,
        legend_data=legend_data,
        cbox=sample.colorbar_box,
        mbox=sample.map_box,
        preset=None,
        extent=sample.extent,
    )

    if services.analysis_store is not None:
        services.analysis_store.save(
            analysis_id,
            field,
            image_bytes=raw_bytes,
            map_box=sample.map_box,
        )

    field_preview_png = ""
    if services.field_preview_renderer is not None:
        preview_bytes = services.field_preview_renderer.render_preview_png(field, width=512)
        b64 = base64.b64encode(preview_bytes).decode("ascii")
        field_preview_png = f"data:image/png;base64,{b64}"

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
        ),
        warnings=list(field.quality.warnings),
        field_preview_png=field_preview_png,
        grid=GridSummary(
            rows=field.values.shape[0],
            cols=field.values.shape[1],
            min=grid_min,
            max=grid_max,
        ),
        image=ImageDimensions(
            width=decoded.original_width,
            height=decoded.original_height,
        ),
    )
