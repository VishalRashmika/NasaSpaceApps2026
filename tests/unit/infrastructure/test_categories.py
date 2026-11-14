"""Unit tests for FileSystemCategoryRepository (F-107)."""

from __future__ import annotations

from pathlib import Path

import pytest

from earth_jukebox.domain.errors import NotFoundError
from earth_jukebox.infrastructure.storage.categories import (
    FileSystemCategoryRepository,
    _format_image_title,
    _parse_info_sections,
)

DATASET_DIR = Path(__file__).resolve().parents[3] / "Dataset"
ALT_DATASET_DIR = Path(__file__).resolve().parents[3] / "dataset"


@pytest.fixture
def repo() -> FileSystemCategoryRepository:
    target = DATASET_DIR if DATASET_DIR.exists() else ALT_DATASET_DIR
    return FileSystemCategoryRepository(target)


def test_format_image_title() -> None:
    assert _format_image_title("01_m30s-sparkling-stars.jpg") == "M30S Sparkling Stars"
    assert (
        _format_image_title(
            "MC01_stage3_GMAO_near_surface_temperature_2048x1024_en.00001_print.jpg"
        )
        == "Mc01 Stage3 Gmao Near Surface Temperature 2048X1024 En"
    )
    assert _format_image_title("iss_lightning_preview.jpg") == "Iss Lightning Preview"


def test_parse_info_sections_with_legend_and_sonification() -> None:
    sample_md = """# Sample Dataset: Solar Winds

## Overview
Solar wind measurements from deep space probes tracking plasma density.

## Legend & Color Mapping
Values map from 0 to 100 km/s. Blue indicates slow wind; red indicates fast solar storms.

## Sonification Strategy
Granular noise with cutoff frequency modulated by wind speed.

## Processing Pipeline
Extract colorbar, build KD-tree, downsample grid.
"""
    title, desc, leg, son, pipe = _parse_info_sections(sample_md)
    assert title == "Sample Dataset: Solar Winds"
    assert "Solar wind measurements" in desc
    assert leg is not None and "0 to 100 km/s" in leg
    assert son is not None and "Granular noise" in son
    assert pipe is not None and "Extract colorbar" in pipe


def test_list_categories(repo: FileSystemCategoryRepository) -> None:
    cats = repo.list()
    assert len(cats) >= 6
    names = [c.id for c in cats]
    assert "GIOS Aerols" in names
    assert "Geos-fp-precipitation-and-clouds" in names
    assert "Hubble+IOTD" in names
    assert "Near-Surface-Temperature" in names
    assert "Near-Surface-Wind-Speed" in names
    assert "lightningEvents" in names

    # Verify legend detection
    temp_cat = next(c for c in cats if c.id == "Near-Surface-Temperature")
    assert temp_cat.has_legend is True
    assert temp_cat.legend_filename == "legend.png"
    assert len(temp_cat.example_images) >= 1

    hubble_cat = next(c for c in cats if c.id == "Hubble+IOTD")
    assert hubble_cat.has_legend is False
    assert hubble_cat.legend_filename is None
    assert len(hubble_cat.example_images) >= 20  # Hubble has 28 images


def test_get_category_and_not_found(repo: FileSystemCategoryRepository) -> None:
    cat = repo.get("Near-Surface-Temperature")
    assert cat.id == "Near-Surface-Temperature"
    assert "Temperature" in cat.title

    # Case-insensitive lookup
    cat_ci = repo.get("near-surface-temperature")
    assert cat_ci.id == "Near-Surface-Temperature"

    with pytest.raises(NotFoundError):
        repo.get("non-existent-category-12345")


def test_legend_bytes(repo: FileSystemCategoryRepository) -> None:
    # Category with legend
    data, mime = repo.legend_bytes("Near-Surface-Temperature")
    assert len(data) > 0
    assert mime in ("image/png", "image/jpeg")

    # Category without legend raises NotFoundError
    with pytest.raises(NotFoundError):
        repo.legend_bytes("Hubble+IOTD")

    with pytest.raises(NotFoundError):
        repo.legend_bytes("lightningEvents")


def test_image_bytes_and_security(repo: FileSystemCategoryRepository) -> None:
    cat = repo.get("Hubble+IOTD")
    first_img = cat.example_images[0].filename
    data, mime = repo.image_bytes("Hubble+IOTD", first_img)
    assert len(data) > 0
    assert mime in ("image/jpeg", "image/png", "image/webp")

    # Path traversal attempt
    with pytest.raises(NotFoundError):
        repo.image_bytes("Hubble+IOTD", "../../../etc/passwd")

    with pytest.raises(NotFoundError):
        repo.image_bytes("Hubble+IOTD", "non_existent.jpg")


def test_category_predefined_configs_and_sound_mappings(
    repo: FileSystemCategoryRepository,
) -> None:
    """F-108 AC1, AC3: Verify predefined configs and sound mappings for all 6 categories."""
    cats = repo.list()
    cat_map = {c.id: c for c in cats}

    # 1. Near-Surface Temperature
    temp = cat_map["Near-Surface-Temperature"]
    assert temp.predefined_config is not None
    assert temp.predefined_config.vmin == -40.0
    assert temp.predefined_config.vmax == 40.0
    assert temp.predefined_config.units == "°C"
    assert temp.predefined_config.kind.value == "diverging"
    assert temp.predefined_config.center == 0.0
    assert temp.predefined_config.category.value == "temperature"
    assert temp.predefined_config.instrument_family == "strings"
    assert "Thermal Tension" in temp.sonification_technique
    assert len(temp.sound_mappings) >= 5

    # 2. Near-Surface Wind Speed
    wind = cat_map["Near-Surface-Wind-Speed"]
    assert wind.predefined_config is not None
    assert wind.predefined_config.vmin == 0.0
    assert wind.predefined_config.vmax == 40.0
    assert wind.predefined_config.units == "m/s"
    assert wind.predefined_config.kind.value == "sequential"
    assert wind.predefined_config.center is None
    assert wind.predefined_config.category.value == "ocean"
    assert wind.predefined_config.instrument_family == "pad"
    assert "Ukusa" in wind.sonification_technique
    assert len(wind.sound_mappings) >= 5

    # 3. Geos-fp Precipitation and Clouds
    precip = cat_map["Geos-fp-precipitation-and-clouds"]
    assert precip.predefined_config is not None
    assert precip.predefined_config.vmin == 0.0
    assert precip.predefined_config.vmax == 20.0
    assert precip.predefined_config.units == "mm"
    assert precip.predefined_config.kind.value == "sequential"
    assert precip.predefined_config.category.value == "precipitation"
    assert precip.predefined_config.instrument_family == "pluck"
    assert "Uraga" in precip.sonification_technique
    assert len(precip.sound_mappings) >= 5

    # 4. GIOS Aerosols
    aerosols = cat_map["GIOS Aerols"]
    assert aerosols.predefined_config is not None
    assert aerosols.predefined_config.vmin == 0.0
    assert aerosols.predefined_config.vmax == 5.0
    assert aerosols.predefined_config.units == "AOD"
    assert aerosols.predefined_config.category.value == "aerosol"
    assert aerosols.predefined_config.instrument_family == "texture"
    assert "Particulate" in aerosols.sonification_technique
    assert len(aerosols.sound_mappings) >= 5

    # 5. Lightning Events
    lightning = cat_map["lightningEvents"]
    assert lightning.predefined_config is not None
    assert lightning.predefined_config.vmin == 0.0
    assert lightning.predefined_config.vmax == 1.0
    assert lightning.predefined_config.instrument_family in ("pluck", "bell")
    assert "Transient" in lightning.sonification_technique
    assert len(lightning.sound_mappings) >= 4

    # 6. Hubble+IOTD
    hubble = cat_map["Hubble+IOTD"]
    assert hubble.predefined_config is not None
    assert hubble.predefined_config.vmin == 0.0
    assert hubble.predefined_config.vmax == 100.0
    assert hubble.predefined_config.instrument_family == "bell"
    assert "Celestial" in hubble.sonification_technique
    assert len(hubble.sound_mappings) >= 5
