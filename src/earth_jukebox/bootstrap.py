"""COMPOSITION ROOT. The only module allowed to import every layer.

Infrastructure adapters are constructed here and injected into application
services. Nothing else may import `earth_jukebox.infrastructure` from the
presentation side (enforced by import-linter).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from earth_jukebox import __version__
from earth_jukebox.application.services import Services
from earth_jukebox.application.settings import Settings
from earth_jukebox.infrastructure.audio.cache import CachedAudioRenderer
from earth_jukebox.infrastructure.audio.midi import MidoMidiExporter
from earth_jukebox.infrastructure.audio.mp3 import FfmpegMp3Exporter
from earth_jukebox.infrastructure.audio.renderer import NumpyAudioRenderer
from earth_jukebox.infrastructure.colormaps.catalog import MatplotlibColormapCatalog
from earth_jukebox.infrastructure.storage.analysis import FileSystemAnalysisStore
from earth_jukebox.infrastructure.storage.categories import (
    FileSystemCategoryRepository,
    extract_category_lut,
)
from earth_jukebox.infrastructure.storage.samples import FileSystemSampleRepository
from earth_jukebox.infrastructure.vision.autodetect import HeuristicColorbarDetector
from earth_jukebox.infrastructure.vision.decoder import PillowImageDecoder
from earth_jukebox.infrastructure.vision.frames import VisionFrameExtractor
from earth_jukebox.infrastructure.vision.preview import VisionFieldPreviewRenderer
from earth_jukebox.infrastructure.vision.recoverer import VisionFieldRecoverer
from earth_jukebox.presentation.api.app import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def build_settings(root: Path = PROJECT_ROOT) -> Settings:
    dataset_path = root / "Dataset" if (root / "Dataset").exists() else root / "dataset"
    return Settings(
        web_dir=root / "web",
        data_dir=root / "data",
        cache_dir=root / "data" / "cache",
        dataset_dir=dataset_path,
    )


def build_services(settings: Settings | None = None) -> Services:
    settings = settings or build_settings()
    decoder = PillowImageDecoder(
        max_upload_bytes=settings.max_upload_bytes,
        max_image_dimension=settings.max_image_dimension,
        working_max_dimension=settings.working_max_dimension,
    )
    catalog = MatplotlibColormapCatalog()
    recoverer = VisionFieldRecoverer(colormap_catalog=catalog)
    sample_repo = FileSystemSampleRepository(samples_dir=settings.data_dir / "samples")
    base_renderer = NumpyAudioRenderer()
    audio_renderer = CachedAudioRenderer(inner=base_renderer, cache_dir=settings.cache_dir)
    midi_exporter = MidoMidiExporter()
    analysis_store = FileSystemAnalysisStore(cache_dir=settings.cache_dir)
    preview_renderer = VisionFieldPreviewRenderer()
    colorbar_detector = HeuristicColorbarDetector()
    frame_extractor = VisionFrameExtractor(
        decoder=decoder,
        max_upload_bytes=settings.max_upload_bytes,
        max_image_dimension=settings.max_image_dimension,
        working_max_dimension=settings.working_max_dimension,
    )
    mp3_exporter = FfmpegMp3Exporter()
    cat_dir = settings.dataset_dir or (PROJECT_ROOT / "Dataset")
    category_repo = FileSystemCategoryRepository(dataset_dir=cat_dir)

    # Register dataset category legend presets (F-108)
    for cat in category_repo.list():
        if cat.has_legend:
            extracted = extract_category_lut(
                category_id=cat.id,
                repository=category_repo,
                decoder=decoder,
                detector=colorbar_detector,
            )
            if extracted is not None:
                lut, lut_kind = extracted
                catalog.register_lut(f"category:{cat.id}", lut, kind=lut_kind)
                catalog.register_lut(cat.id, lut, kind=lut_kind)
                catalog.register_lut(f"category:{cat.id.lower()}", lut, kind=lut_kind)
                catalog.register_lut(cat.id.lower(), lut, kind=lut_kind)

    return Services(
        settings=settings,
        version=__version__,
        image_decoder=decoder,
        colormap_catalog=catalog,
        field_recoverer=recoverer,
        sample_repository=sample_repo,
        audio_renderer=audio_renderer,
        midi_exporter=midi_exporter,
        analysis_store=analysis_store,
        field_preview_renderer=preview_renderer,
        colorbar_detector=colorbar_detector,
        frame_extractor=frame_extractor,
        mp3_exporter=mp3_exporter,
        category_repository=category_repo,
    )


def build_app(settings: Settings | None = None) -> FastAPI:
    return create_app(build_services(settings))
