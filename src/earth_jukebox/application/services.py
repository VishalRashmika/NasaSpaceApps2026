"""The set of use-case services handed to the presentation layer.

Phase 0 has none. Each later phase ADDS a field here (never reorders/renames
existing ones) and the composition root (earth_jukebox/bootstrap.py) fills it.
"""

from __future__ import annotations

from dataclasses import dataclass

from earth_jukebox.application.ports import (
    AnalysisStore,
    AudioRenderer,
    CategoryRepository,
    ColorbarDetector,
    ColormapCatalog,
    FieldPreviewRenderer,
    FieldRecoverer,
    FrameExtractor,
    ImageDecoder,
    MidiExporter,
    Mp3Exporter,
    SampleRepository,
)
from earth_jukebox.application.settings import Settings


@dataclass(frozen=True)
class Services:
    settings: Settings
    version: str
    image_decoder: ImageDecoder | None = None
    colormap_catalog: ColormapCatalog | None = None
    field_recoverer: FieldRecoverer | None = None
    sample_repository: SampleRepository | None = None
    audio_renderer: AudioRenderer | None = None
    midi_exporter: MidiExporter | None = None
    analysis_store: AnalysisStore | None = None
    field_preview_renderer: FieldPreviewRenderer | None = None
    colorbar_detector: ColorbarDetector | None = None
    frame_extractor: FrameExtractor | None = None
    mp3_exporter: Mp3Exporter | None = None
    category_repository: CategoryRepository | None = None
