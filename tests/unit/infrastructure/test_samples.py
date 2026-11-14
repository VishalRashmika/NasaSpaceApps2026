"""Tests for F-101: Ground-truth manifest loader & validator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from earth_jukebox.domain.errors import InvalidImageError, InvalidLegendError, NotFoundError
from earth_jukebox.infrastructure.storage.samples import FileSystemSampleRepository


def _create_sample_dir(
    root: Path,
    sample_id: str,
    meta_dict: dict[str, Any],
    create_image: bool = True,
    img_size: tuple[int, int] = (200, 100),
) -> Path:
    sample_dir = root / sample_id
    sample_dir.mkdir(parents=True, exist_ok=True)
    meta_file = sample_dir / "meta.json"
    meta_file.write_text(json.dumps(meta_dict), encoding="utf-8")
    if create_image and "image_file" in meta_dict:
        img = Image.new("RGB", img_size, color="blue")
        img.save(sample_dir / meta_dict["image_file"])
    return sample_dir


@pytest.fixture
def valid_meta_dict() -> dict[str, Any]:
    return {
        "id": "valid-sample-1",
        "title": "Valid Sample 1",
        "image_file": "image.png",
        "legend": {
            "vmin": 0.0,
            "vmax": 100.0,
            "units": "K",
            "label": "Temperature",
            "kind": "sequential",
            "category": "temperature",
            "center": None,
            "orientation": "horizontal",
            "low_at_start": True,
            "scale": "linear",
        },
        "extent": {
            "lat_min": -90.0,
            "lat_max": 90.0,
            "lon_min": -180.0,
            "lon_max": 180.0,
            "projection": "equirectangular",
        },
        "colorbar_box": {"x": 10, "y": 80, "w": 80, "h": 10},
        "map_box": {"x": 0, "y": 0, "w": 200, "h": 70},
        "colormap_hint": "viridis",
        "source_url": "https://example.com",
        "credit": "NASA",
        "description": "Test description",
        "in_gallery": True,
    }


def test_f101_ac1_template_ignored_and_list_get(
    tmp_path: Path, valid_meta_dict: dict[str, Any]
) -> None:
    # Directory starting with _ is ignored
    _template_dict = dict(valid_meta_dict, id="_TEMPLATE")
    _create_sample_dir(tmp_path, "_TEMPLATE", _template_dict)

    # Valid in-gallery sample
    _create_sample_dir(tmp_path, "valid-sample-1", valid_meta_dict)

    # Valid hidden sample (in_gallery = False)
    hidden_dict = dict(valid_meta_dict, id="hidden-sample", in_gallery=False)
    _create_sample_dir(tmp_path, "hidden-sample", hidden_dict)

    repo = FileSystemSampleRepository(tmp_path)

    # list() only returns in_gallery=True
    samples = repo.list()
    assert len(samples) == 1
    assert samples[0].id == "valid-sample-1"
    assert samples[0].in_gallery is True

    # get(id) returns hidden ones too
    hidden = repo.get("hidden-sample")
    assert hidden.id == "hidden-sample"
    assert hidden.in_gallery is False

    # image_bytes works
    b = repo.image_bytes("valid-sample-1")
    assert len(b) > 0

    # unknown id raises NotFoundError
    with pytest.raises(NotFoundError):
        repo.get("non-existent")


def test_f101_ac2_six_invalid_meta_files(tmp_path: Path, valid_meta_dict: dict[str, Any]) -> None:
    # 1. Missing field (e.g. missing 'title')
    d1 = dict(valid_meta_dict)
    del d1["title"]
    _create_sample_dir(tmp_path, "bad-missing-field", d1)

    # 2. Bad box (e.g. map_box outside image dimensions 200x100)
    d2 = dict(valid_meta_dict, id="bad-box")
    d2["map_box"] = {"x": 150, "y": 0, "w": 100, "h": 50}  # x+w = 250 > 200
    _create_sample_dir(tmp_path, "bad-box", d2)

    # 3. vmin >= vmax
    d3 = dict(valid_meta_dict, id="bad-vmin")
    d3["legend"] = dict(valid_meta_dict["legend"], vmin=100.0, vmax=50.0)
    _create_sample_dir(tmp_path, "bad-vmin", d3)

    # 4. Bad id
    d4 = dict(valid_meta_dict, id="INVALID_ID!")
    _create_sample_dir(tmp_path, "bad-id", d4)

    # 5. Missing image
    d5 = dict(valid_meta_dict, id="missing-img")
    _create_sample_dir(tmp_path, "missing-img", d5, create_image=False)

    # 6. Bad category
    d6 = dict(valid_meta_dict, id="bad-cat")
    d6["legend"] = dict(valid_meta_dict["legend"], category="not_a_category")
    _create_sample_dir(tmp_path, "bad-cat", d6)

    repo = FileSystemSampleRepository(tmp_path)

    # Each must raise InvalidLegendError or InvalidImageError naming the file and field
    with pytest.raises((InvalidLegendError, InvalidImageError)) as exc1:
        repo.get("bad-missing-field")
    assert "meta.json" in str(exc1.value)
    assert "title" in str(exc1.value)

    with pytest.raises((InvalidLegendError, InvalidImageError)) as exc2:
        repo.get("bad-box")
    assert "meta.json" in str(exc2.value)
    assert "map_box" in str(exc2.value)

    with pytest.raises((InvalidLegendError, InvalidImageError)) as exc3:
        repo.get("bad-vmin")
    assert "meta.json" in str(exc3.value)
    assert "vmin" in str(exc3.value) or "vmax" in str(exc3.value)

    with pytest.raises((InvalidLegendError, InvalidImageError)) as exc4:
        repo.get("bad-id")
    assert "meta.json" in str(exc4.value)
    assert "id" in str(exc4.value)

    with pytest.raises((InvalidLegendError, InvalidImageError)) as exc5:
        repo.get("missing-img")
    assert "meta.json" in str(exc5.value)
    assert "image_file" in str(exc5.value)

    with pytest.raises((InvalidLegendError, InvalidImageError)) as exc6:
        repo.get("bad-cat")
    assert "meta.json" in str(exc6.value)
    assert "category" in str(exc6.value)


def test_f101_ac3_listing_zero_samples_returns_empty_list(tmp_path: Path) -> None:
    # AC3: listing with zero real samples returns an empty list, not an error.
    repo = FileSystemSampleRepository(tmp_path)
    assert repo.list() == []
