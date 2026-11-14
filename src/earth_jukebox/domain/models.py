"""Core domain model. Pure data: stdlib + numpy only.

This file is mirrored verbatim in docs/02-DOMAIN-MODEL.md and a test
(tests/architecture/test_docs_in_sync.py) fails if they diverge.
To change it: update the docs block, record the change in PROJECT-STATE.md
(Decisions log), and bump MODEL_REVISION below.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
from numpy.typing import NDArray

MODEL_REVISION = 6

FloatArray = NDArray[np.float64]
UInt8Array = NDArray[np.uint8]


# ---------------------------------------------------------------- enums
class VariableCategory(str, Enum):
    """What the data is about. Selects the instrument family (doc 06 §6)."""

    TEMPERATURE = "temperature"
    PRECIPITATION = "precipitation"
    VEGETATION = "vegetation"
    ICE = "ice"
    AEROSOL = "aerosol"
    OCEAN = "ocean"
    GENERIC = "generic"


class ColormapKind(str, Enum):
    SEQUENTIAL = "sequential"
    DIVERGING = "diverging"


class ScaleType(str, Enum):
    """How the colorbar maps position to value."""

    LINEAR = "linear"
    LOG = "log"  # log10-spaced; requires vmin > 0


class Orientation(str, Enum):
    HORIZONTAL = "horizontal"  # low value at left unless low_at_start is False
    VERTICAL = "vertical"  # low value at bottom unless low_at_start is False


class RecoveryMode(str, Enum):
    COLORBAR = "colorbar"  # LUT extracted from the image's own colorbar
    PRESET = "preset"  # LUT taken from a named colormap preset
    LUMINANCE_FALLBACK = "luminance_fallback"  # NOT data-faithful; always flagged


# ---------------------------------------------------------------- geometry
@dataclass(frozen=True)
class PixelBox:
    """Axis-aligned box in ORIGINAL-image pixel coordinates."""

    x: int
    y: int
    w: int
    h: int

    def __post_init__(self) -> None:
        if self.w <= 0 or self.h <= 0 or self.x < 0 or self.y < 0:
            raise ValueError(f"invalid PixelBox: {self}")


@dataclass(frozen=True)
class ColorbarCandidate:
    """A proposed colorbar location and orientation with confidence score (F-004)."""

    box: PixelBox
    orientation: Orientation
    score: float


@dataclass(frozen=True)
class GeoExtent:
    """Geographic extent of the MAP region. Only equirectangular is supported."""

    lat_min: float = -90.0
    lat_max: float = 90.0
    lon_min: float = -180.0
    lon_max: float = 180.0
    projection: str = "equirectangular"

    def __post_init__(self) -> None:
        if not (self.lat_min < self.lat_max and self.lon_min < self.lon_max):
            raise ValueError(f"invalid GeoExtent: {self}")


# ---------------------------------------------------------------- legend
@dataclass(frozen=True)
class LegendSpec:
    """Human-supplied (or OCR-assisted) meaning of the colorbar."""

    vmin: float
    vmax: float
    units: str
    label: str
    kind: ColormapKind
    category: VariableCategory = VariableCategory.GENERIC
    center: float | None = None  # diverging only; defaults to midpoint of vmin/vmax
    orientation: Orientation = Orientation.HORIZONTAL
    low_at_start: bool = True  # False if low value is at right/top
    scale: ScaleType = ScaleType.LINEAR

    def __post_init__(self) -> None:
        if not self.vmin < self.vmax:
            raise ValueError("vmin must be < vmax")
        if self.scale is ScaleType.LOG and self.vmin <= 0:
            raise ValueError("log scale requires vmin > 0")
        if self.center is not None and not self.vmin <= self.center <= self.vmax:
            raise ValueError("center must lie within [vmin, vmax]")

    @property
    def effective_center(self) -> float:
        return self.center if self.center is not None else (self.vmin + self.vmax) / 2.0


# ---------------------------------------------------------------- images
@dataclass(frozen=True, eq=False)
class DecodedImage:
    """Normalised RGB image. `content_hash` is SHA-256 hex of the ORIGINAL bytes."""

    rgb: UInt8Array  # (H, W, 3)
    content_hash: str
    original_width: int
    original_height: int


@dataclass(frozen=True, eq=False)
class ColorLUT:
    """Ordered colour -> value lookup. Rows ordered from vmin to vmax."""

    lab: FloatArray  # (N, 3) CIE L*a*b*
    values: FloatArray  # (N,) physical values, ascending
    source: RecoveryMode


@dataclass(frozen=True)
class RecoveryQuality:
    mean_delta_e: float  # mean CIE76 distance of matched pixels to their LUT colour
    p95_delta_e: float
    masked_fraction: float  # 0..1, share of MAP pixels left as NaN
    lut_is_monotonic_in_lightness: bool  # False for rainbow-like maps (informational)
    confidence: float  # 0..1 aggregate, formula in doc 05 §8
    mode: RecoveryMode
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, eq=False)
class ScalarField:
    """Recovered physical field. NaN = masked/no data. Row 0 = northern edge."""

    values: FloatArray  # (H, W)
    legend: LegendSpec
    extent: GeoExtent
    quality: RecoveryQuality
    source_hash: str


# ---------------------------------------------------------------- skins
@dataclass(frozen=True)
class Skin:
    """Aesthetic layer. MUST NOT change what is encoded, only how it sounds (doc 08)."""

    id: str  # "neutral" | "hindustani" | "sri_lankan" ...
    name: str
    tonic_midi: float  # e.g. 48.0 == C3
    scale_cents: tuple[float, ...]  # ascending pitch classes within one octave, first == 0.0
    n_octaves: int
    instrument_map: Mapping[VariableCategory, str]  # category -> instrument family id
    rhythm_patterns: Mapping[str, tuple[float, ...]] = field(default_factory=dict)
    # ornament phrases as scale-degree offsets (doc 08)
    phrases: Mapping[str, tuple[int, ...]] = field(default_factory=dict)
    glide_descending: bool = False  # meend-style glide on descending steps (doc 08)
    provisional: bool = False  # note set not yet validated by a musician (doc 08 section 5)
    tension_cents: float | None = None  # skin-defined tension interval (doc 03 F-092)


# ---------------------------------------------------------------- score
@dataclass(frozen=True)
class Voice:
    id: str  # e.g. "band0"
    band_index: int  # 0 = northernmost
    instrument: str  # instrument family id
    pan: float  # -1..1


@dataclass(frozen=True)
class NoteEvent:
    """One sounding note. Every note carries its data provenance."""

    voice_id: str
    t_beat: float
    dur_beat: float
    pitch_midi: float  # fractional allowed (microtones)
    velocity: float  # 0..1
    accent: bool
    col: int  # source grid column
    band: int  # source latitude band
    value: float | None  # recovered physical value this note encodes
    glide_to_midi: float | None = None
    roughness: float = 0.0  # 0..1 timbre hint from local variability (doc 06 section 7)
    kind: str = "main"  # "main" | "ornament" | "accent_bell"; only "main" is decoded (doc 06)


@dataclass(frozen=True)
class Score:
    """The engine's single output. Serialised to JSON for the browser and to MIDI/WAV."""

    mapping_version: str
    skin_id: str
    seed: int
    bpm: float
    total_beats: float
    n_cols: int
    n_bands: int
    voices: tuple[Voice, ...]
    notes: tuple[NoteEvent, ...]
    drone_midi: tuple[float, ...]
    legend: LegendSpec
    provenance: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SonificationParams:
    skin_id: str = "neutral"
    n_cols: int = 48
    n_bands: int = 5
    seed: int | None = None  # None => derived from source_hash (doc 06 §9)


# ---------------------------------------------------------------- evaluation
@dataclass(frozen=True)
class FidelityReport:
    score_round_trip_r: float  # Pearson r: decoded Score vs. grid-resampled field
    audio_legend_monotonic: bool | None  # None if audio check was not run
    audio_legend_r: float | None  # Pearson r of detected pitch vs. legend value
    n_samples: int


# ---------------------------------------------------------------- samples
@dataclass(frozen=True)
class SampleMeta:
    """Mirror of data/samples/<id>/meta.json (schema in docs/12)."""

    id: str
    title: str
    image_file: str
    legend: LegendSpec
    extent: GeoExtent
    colorbar_box: PixelBox | None
    map_box: PixelBox | None
    colormap_hint: str | None
    source_url: str
    credit: str
    description: str
    in_gallery: bool = True  # False for special test samples (no legend, globe)


# ---------------------------------------------------------------- dataset categories
@dataclass(frozen=True)
class ExampleImage:
    filename: str
    title: str


@dataclass(frozen=True)
class CategorySoundMapping:
    """A data characteristic mapped to a specific sound quality/parameter (F-108)."""

    data_characteristic: str
    sound_parameter: str
    technique: str
    detail: str


@dataclass(frozen=True)
class CategoryPredefinedConfig:
    """Predefined metadata and audio parameters automatically supplied for a category (F-108)."""

    label: str
    units: str
    vmin: float
    vmax: float
    kind: ColormapKind
    category: VariableCategory
    center: float | None = None
    scale: ScaleType = ScaleType.LINEAR
    orientation: Orientation = Orientation.HORIZONTAL
    low_at_start: bool = True
    instrument_family: str = "pad"
    suggested_skin: str = "neutral"


@dataclass(frozen=True)
class DatasetCategory:
    id: str
    title: str
    description: str
    info_markdown: str
    has_legend: bool
    legend_filename: str | None
    legend_info: str | None
    example_images: tuple[ExampleImage, ...]
    predefined_config: CategoryPredefinedConfig | None = None
    sonification_technique: str = ""
    sonification_description: str = ""
    sound_mappings: tuple[CategorySoundMapping, ...] = ()
