"""Pydantic schemas for the HTTP API (Module API).

Per docs/01 §3, Pydantic models live only in presentation/api/schemas.py.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProblemDetails(BaseModel):
    """RFC 7807 problem details response."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    code: str
    request_id: str


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    mapping_version: str


class BoxSchema(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    w: int = Field(gt=0)
    h: int = Field(gt=0)


class ColorbarCandidateResponse(BaseModel):
    box: BoxSchema
    orientation: str
    score: float


class DetectColorbarResponse(BaseModel):
    candidates: list[ColorbarCandidateResponse]


class QualityResponse(BaseModel):
    confidence: float
    confidence_badge: str
    mean_delta_e: float
    p95_delta_e: float
    masked_fraction: float
    warnings: list[str]
    recovery_mode: str | None = None


class GridSummary(BaseModel):
    rows: int
    cols: int
    min: float | None = None
    max: float | None = None


class ImageDimensions(BaseModel):
    width: int
    height: int


class AnalyzeResponse(BaseModel):
    analysis_id: str
    quality: QualityResponse
    warnings: list[str]
    field_preview_png: str
    grid: GridSummary
    image: ImageDimensions
    is_animation: bool = False
    n_frames: int = 1
    frame_previews: list[str] = Field(default_factory=list)


class SonifyRequest(BaseModel):
    analysis_id: str
    skin: str = "neutral"
    n_cols: int = Field(default=48, ge=16, le=128)


class FidelityResponse(BaseModel):
    round_trip_r: float
    legend_r: float | None = None


class SkinMetadataResponse(BaseModel):
    id: str
    name: str
    scale_description: str
    provisional: bool = False


class SonifyResponse(BaseModel):
    score: dict[str, Any]
    description: str
    fidelity: FidelityResponse
    skin: SkinMetadataResponse


class SkinResponse(BaseModel):
    id: str
    name: str
    provisional: bool
    scale_cents: list[float]
    description: str


class ColormapResponse(BaseModel):
    name: str
    kind: str


class SampleSummaryResponse(BaseModel):
    id: str
    title: str
    category: str
    thumb_url: str
    credit: str


class LegendMetaSchema(BaseModel):
    vmin: float
    vmax: float
    units: str
    label: str
    kind: str
    category: str
    center: float | None = None
    orientation: str
    low_at_start: bool
    scale: str


class ExtentMetaSchema(BaseModel):
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    projection: str


class SampleMetaResponse(BaseModel):
    id: str
    title: str
    image_file: str
    legend: LegendMetaSchema
    extent: ExtentMetaSchema
    source_url: str
    credit: str
    description: str
    map_box: BoxSchema | None = None
    colorbar_box: BoxSchema | None = None
    in_gallery: bool = True


class CategoryExampleImageResponse(BaseModel):
    filename: str
    title: str
    url: str
    thumb_url: str


class CategorySoundMappingResponse(BaseModel):
    data_characteristic: str
    sound_parameter: str
    technique: str
    detail: str


class CategoryPredefinedConfigResponse(BaseModel):
    label: str
    units: str
    vmin: float
    vmax: float
    kind: str
    category: str
    center: float | None = None
    scale: str = "linear"
    orientation: str = "horizontal"
    low_at_start: bool = True
    instrument_family: str = "pad"
    suggested_skin: str = "neutral"


class CategorySummaryResponse(BaseModel):
    id: str
    title: str
    description: str
    has_legend: bool
    legend_url: str | None = None
    legend_info: str | None = None
    image_count: int
    images: list[CategoryExampleImageResponse]
    predefined_config: CategoryPredefinedConfigResponse | None = None
    sonification_technique: str = ""
    sonification_description: str = ""
    sound_mappings: list[CategorySoundMappingResponse] = []


class CategoryDetailResponse(BaseModel):
    id: str
    title: str
    description: str
    info_markdown: str
    has_legend: bool
    legend_filename: str | None = None
    legend_url: str | None = None
    legend_info: str | None = None
    image_count: int
    images: list[CategoryExampleImageResponse]
    predefined_config: CategoryPredefinedConfigResponse | None = None
    sonification_technique: str = ""
    sonification_description: str = ""
    sound_mappings: list[CategorySoundMappingResponse] = []


def confidence_badge(confidence: float) -> str:
    """Return 'High', 'Medium', or 'Low' badge per docs/05 §8."""
    if confidence >= 0.8:
        return "High"
    if confidence >= 0.5:
        return "Medium"
    return "Low"
