"""Category discovery and asset endpoints (F-107)."""

from __future__ import annotations

import urllib.parse
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response

from earth_jukebox.application.services import Services
from earth_jukebox.domain.errors import NotFoundError
from earth_jukebox.presentation.api.dependencies import get_services
from earth_jukebox.presentation.api.schemas import (
    CategoryDetailResponse,
    CategoryExampleImageResponse,
    CategoryPredefinedConfigResponse,
    CategorySoundMappingResponse,
    CategorySummaryResponse,
)

router = APIRouter(prefix="/api/categories", tags=["categories"])


def _encode_id(cat_id: str) -> str:
    return urllib.parse.quote(cat_id, safe="")


def _encode_filename(fn: str) -> str:
    return urllib.parse.quote(fn, safe="")


def _format_predefined(cfg: Any) -> CategoryPredefinedConfigResponse | None:
    if cfg is None:
        return None
    return CategoryPredefinedConfigResponse(
        label=cfg.label,
        units=cfg.units,
        vmin=cfg.vmin,
        vmax=cfg.vmax,
        kind=cfg.kind.value if hasattr(cfg.kind, "value") else str(cfg.kind),
        category=cfg.category.value if hasattr(cfg.category, "value") else str(cfg.category),
        center=cfg.center,
        scale=cfg.scale.value if hasattr(cfg.scale, "value") else str(cfg.scale),
        orientation=cfg.orientation.value
        if hasattr(cfg.orientation, "value")
        else str(cfg.orientation),
        low_at_start=cfg.low_at_start,
        instrument_family=cfg.instrument_family,
        suggested_skin=cfg.suggested_skin,
    )


def _format_mappings(mappings: Any) -> list[CategorySoundMappingResponse]:
    if not mappings:
        return []
    return [
        CategorySoundMappingResponse(
            data_characteristic=m.data_characteristic,
            sound_parameter=m.sound_parameter,
            technique=m.technique,
            detail=m.detail,
        )
        for m in mappings
    ]


@router.get("", response_model=list[CategorySummaryResponse])
def list_categories(
    services: Annotated[Services, Depends(get_services)],
) -> list[CategorySummaryResponse]:
    """List all discovered dataset categories with legends and examples (F-107)."""
    if services.category_repository is None:
        return []

    cats = services.category_repository.list()
    result: list[CategorySummaryResponse] = []
    for c in cats:
        encoded_id = _encode_id(c.id)
        legend_url = f"/api/categories/{encoded_id}/legend" if c.has_legend else None
        images = [
            CategoryExampleImageResponse(
                filename=img.filename,
                title=img.title,
                url=f"/api/categories/{encoded_id}/images/{_encode_filename(img.filename)}",
                thumb_url=f"/api/categories/{encoded_id}/images/{_encode_filename(img.filename)}",
            )
            for img in c.example_images
        ]
        result.append(
            CategorySummaryResponse(
                id=c.id,
                title=c.title,
                description=c.description,
                has_legend=c.has_legend,
                legend_url=legend_url,
                legend_info=c.legend_info,
                image_count=len(c.example_images),
                images=images,
                predefined_config=_format_predefined(c.predefined_config),
                sonification_technique=c.sonification_technique,
                sonification_description=c.sonification_description,
                sound_mappings=_format_mappings(c.sound_mappings),
            )
        )
    return result


@router.get("/{category_id}", response_model=CategoryDetailResponse)
def get_category_detail(
    category_id: str,
    services: Annotated[Services, Depends(get_services)],
) -> CategoryDetailResponse:
    """Get full details, info.md content, and example images for a specific category (F-107)."""
    if services.category_repository is None:
        raise NotFoundError("Category repository service unavailable")

    c = services.category_repository.get(category_id)
    encoded_id = _encode_id(c.id)
    legend_url = f"/api/categories/{encoded_id}/legend" if c.has_legend else None
    images = [
        CategoryExampleImageResponse(
            filename=img.filename,
            title=img.title,
            url=f"/api/categories/{encoded_id}/images/{_encode_filename(img.filename)}",
            thumb_url=f"/api/categories/{encoded_id}/images/{_encode_filename(img.filename)}",
        )
        for img in c.example_images
    ]
    return CategoryDetailResponse(
        id=c.id,
        title=c.title,
        description=c.description,
        info_markdown=c.info_markdown,
        has_legend=c.has_legend,
        legend_filename=c.legend_filename,
        legend_url=legend_url,
        legend_info=c.legend_info,
        image_count=len(c.example_images),
        images=images,
        predefined_config=_format_predefined(c.predefined_config),
        sonification_technique=c.sonification_technique,
        sonification_description=c.sonification_description,
        sound_mappings=_format_mappings(c.sound_mappings),
    )


@router.get("/{category_id}/legend")
def get_category_legend(
    category_id: str,
    services: Annotated[Services, Depends(get_services)],
) -> Response:
    """Serve the optional color legend image for a category (F-107)."""
    if services.category_repository is None:
        raise NotFoundError("Category repository service unavailable")

    data, mime = services.category_repository.legend_bytes(category_id)
    return Response(
        content=data,
        media_type=mime,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/{category_id}/images/{filename}")
def get_category_image(
    category_id: str,
    filename: str,
    services: Annotated[Services, Depends(get_services)],
) -> Response:
    """Serve a preloaded example image for a category (F-107)."""
    if services.category_repository is None:
        raise NotFoundError("Category repository service unavailable")

    data, mime = services.category_repository.image_bytes(category_id, filename)
    return Response(
        content=data,
        media_type=mime,
        headers={"Cache-Control": "public, max-age=3600"},
    )
