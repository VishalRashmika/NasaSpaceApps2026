"""Ports: interfaces the application layer needs. Implemented in infrastructure/.

Mirrored verbatim in docs/02-DOMAIN-MODEL.md (§ Ports); a test enforces sync.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from earth_jukebox.domain.models import (
    ColorbarCandidate,
    ColorLUT,
    ColormapKind,
    DatasetCategory,
    DecodedImage,
    LegendSpec,
    PixelBox,
    SampleMeta,
    ScalarField,
    Score,
)


class ImageDecoder(Protocol):
    def decode(self, data: bytes) -> DecodedImage:
        """Validate + decode + normalise. Raises domain errors on invalid input."""
        ...


class ColormapCatalog(Protocol):
    def names(self) -> Sequence[str]: ...

    def kind(self, name: str) -> ColormapKind: ...

    def lut(self, name: str, n: int = 256) -> ColorLUT:
        """Return the named preset as a LUT with values scaled to [0, 1]."""
        ...


class FieldRecoverer(Protocol):
    def recover(
        self,
        image: DecodedImage,
        legend: LegendSpec,
        map_box: PixelBox | None,
        colorbar_box: PixelBox | None,
        preset_name: str | None,
    ) -> ScalarField:
        """colorbar_box -> COLORBAR mode; preset_name -> PRESET mode; neither -> fallback."""
        ...


class AudioRenderer(Protocol):
    def render_wav(self, score: Score, sample_rate: int = 44100) -> bytes: ...


class MidiExporter(Protocol):
    def export_midi(self, score: Score) -> bytes: ...


class SampleRepository(Protocol):
    def list(self) -> Sequence[SampleMeta]: ...

    def get(self, sample_id: str) -> SampleMeta: ...

    def image_bytes(self, sample_id: str) -> bytes: ...


class ColorbarDetector(Protocol):
    def detect(self, image: DecodedImage) -> Sequence[ColorbarCandidate]: ...


class FieldPreviewRenderer(Protocol):
    def render_preview_png(self, field: ScalarField, width: int = 512) -> bytes: ...


class AnalysisStore(Protocol):
    """Persists recovered fields between /analyze and /sonify calls."""

    def save(self, analysis_id: str, field: ScalarField) -> None: ...

    def load(self, analysis_id: str) -> ScalarField:
        """Raises NotFoundError if unknown."""
        ...


class FrameExtractor(Protocol):
    def extract_frames(self, data: bytes, max_frames: int = 24) -> Sequence[DecodedImage]:
        """Extract up to max_frames evenly sampled frames from animated GIF/APNG or video bytes."""
        ...


class Mp3Exporter(Protocol):
    def is_available(self) -> bool: ...

    def export_mp3(self, wav_bytes: bytes) -> bytes:
        """Convert WAV audio bytes to MP3 audio bytes using ffmpeg."""
        ...


class CategoryRepository(Protocol):
    def list(self) -> Sequence[DatasetCategory]: ...

    def get(self, category_id: str) -> DatasetCategory: ...

    def legend_bytes(self, category_id: str) -> tuple[bytes, str]: ...

    def image_bytes(self, category_id: str, filename: str) -> tuple[bytes, str]: ...
