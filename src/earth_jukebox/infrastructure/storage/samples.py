"""Ground-truth manifest loader & validator (F-101).

Implements SampleRepository for loading sample metadata from the filesystem.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from PIL import Image

from earth_jukebox.application.ports import SampleRepository
from earth_jukebox.domain.errors import InvalidImageError, InvalidLegendError, NotFoundError
from earth_jukebox.domain.models import (
    ColormapKind,
    GeoExtent,
    LegendSpec,
    Orientation,
    PixelBox,
    SampleMeta,
    ScaleType,
    VariableCategory,
)

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class FileSystemSampleRepository(SampleRepository):
    """Loads and validates sample manifests from data/samples/<id>/meta.json."""

    def __init__(self, samples_dir: Path) -> None:
        self._samples_dir = samples_dir

    def list(self) -> Sequence[SampleMeta]:
        """Return all samples with in_gallery=True, sorted by id."""
        if not self._samples_dir.exists():
            return []

        samples: list[SampleMeta] = []
        for entry in sorted(self._samples_dir.iterdir()):
            if entry.is_dir() and not entry.name.startswith("_"):
                meta_file = entry / "meta.json"
                if meta_file.exists():
                    sample = self._load_sample(entry.name)
                    if sample.in_gallery:
                        samples.append(sample)
        return samples

    def get(self, sample_id: str) -> SampleMeta:
        """Return sample by id, including hidden samples (in_gallery=False)."""
        sample_dir = self._samples_dir / sample_id
        if not sample_dir.is_dir() or sample_id.startswith("_"):
            raise NotFoundError(f"sample '{sample_id}' not found")

        meta_file = sample_dir / "meta.json"
        if not meta_file.exists():
            raise NotFoundError(f"meta.json not found for sample '{sample_id}'")

        return self._load_sample(sample_id)

    def image_bytes(self, sample_id: str) -> bytes:
        """Read raw bytes of sample image."""
        sample = self.get(sample_id)
        image_path = self._samples_dir / sample_id / sample.image_file
        if not image_path.exists():
            raise NotFoundError(f"image '{sample.image_file}' not found for sample '{sample_id}'")
        return image_path.read_bytes()

    def _load_sample(self, sample_id: str) -> SampleMeta:
        sample_dir = self._samples_dir / sample_id
        meta_file = sample_dir / "meta.json"

        try:
            data: dict[str, Any] = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception as exc:
            raise InvalidLegendError(f"{meta_file}: invalid JSON: {exc}") from exc

        # 1. Validate ID
        sid = data.get("id")
        if not sid or not isinstance(sid, str) or not ID_PATTERN.match(sid):
            raise InvalidLegendError(f"{meta_file}: bad id '{sid}' (field 'id')")

        # 2. Required top-level fields
        required_fields = (
            "title",
            "image_file",
            "legend",
            "extent",
            "source_url",
            "credit",
            "description",
        )
        for rf in required_fields:
            if rf not in data:
                raise InvalidLegendError(f"{meta_file}: missing required field '{rf}'")

        # 3. Validate image existence and dimensions
        image_file_name = data["image_file"]
        image_path = sample_dir / image_file_name
        if not image_path.exists():
            raise InvalidImageError(
                f"{meta_file}: image file '{image_file_name}' does not exist (field 'image_file')"
            )

        try:
            with Image.open(image_path) as img:
                img_w, img_h = img.size
        except Exception as exc:
            raise InvalidImageError(
                f"{meta_file}: failed to open image '{image_file_name}': {exc} (field 'image_file')"
            ) from exc

        # 4. Validate boxes inside image
        colorbar_box = self._parse_box(
            data.get("colorbar_box"), "colorbar_box", meta_file, img_w, img_h
        )
        map_box = self._parse_box(data.get("map_box"), "map_box", meta_file, img_w, img_h)

        # 5. Validate legend
        legend_data = data["legend"]
        if not isinstance(legend_data, dict):
            raise InvalidLegendError(f"{meta_file}: field 'legend' must be an object")

        for l_field in ("vmin", "vmax", "units", "label", "kind"):
            if l_field not in legend_data:
                raise InvalidLegendError(f"{meta_file}: missing required legend field '{l_field}'")

        vmin = float(legend_data["vmin"])
        vmax = float(legend_data["vmax"])
        if vmin >= vmax:
            raise InvalidLegendError(
                f"{meta_file}: vmin ({vmin}) must be < vmax ({vmax}) (field 'vmin')"
            )

        cat_str = legend_data.get("category", "generic")
        try:
            category = VariableCategory(cat_str)
        except ValueError as exc:
            raise InvalidLegendError(
                f"{meta_file}: invalid category '{cat_str}' (field 'category')"
            ) from exc

        kind_str = legend_data["kind"]
        try:
            kind = ColormapKind(kind_str)
        except ValueError as exc:
            raise InvalidLegendError(
                f"{meta_file}: invalid kind '{kind_str}' (field 'kind')"
            ) from exc

        orient_str = legend_data.get("orientation", "horizontal")
        try:
            orientation = Orientation(orient_str)
        except ValueError as exc:
            raise InvalidLegendError(
                f"{meta_file}: invalid orientation '{orient_str}' (field 'orientation')"
            ) from exc

        scale_str = legend_data.get("scale", "linear")
        try:
            scale = ScaleType(scale_str)
        except ValueError as exc:
            raise InvalidLegendError(
                f"{meta_file}: invalid scale '{scale_str}' (field 'scale')"
            ) from exc

        center = float(legend_data["center"]) if legend_data.get("center") is not None else None
        if center is not None and not (vmin <= center <= vmax):
            raise InvalidLegendError(
                f"{meta_file}: center ({center}) must be in [vmin, vmax] (field 'center')"
            )

        low_at_start = bool(legend_data.get("low_at_start", True))

        legend = LegendSpec(
            vmin=vmin,
            vmax=vmax,
            units=str(legend_data["units"]),
            label=str(legend_data["label"]),
            kind=kind,
            category=category,
            center=center,
            orientation=orientation,
            low_at_start=low_at_start,
            scale=scale,
        )

        # 6. Validate extent
        ext_data = data["extent"]
        extent = GeoExtent(
            lat_min=float(ext_data.get("lat_min", -90.0)),
            lat_max=float(ext_data.get("lat_max", 90.0)),
            lon_min=float(ext_data.get("lon_min", -180.0)),
            lon_max=float(ext_data.get("lon_max", 180.0)),
            projection=str(ext_data.get("projection", "equirectangular")),
        )

        return SampleMeta(
            id=sid,
            title=str(data["title"]),
            image_file=str(image_file_name),
            legend=legend,
            extent=extent,
            colorbar_box=colorbar_box,
            map_box=map_box,
            colormap_hint=data.get("colormap_hint"),
            source_url=str(data["source_url"]),
            credit=str(data["credit"]),
            description=str(data["description"]),
            in_gallery=bool(data.get("in_gallery", True)),
        )

    def _parse_box(
        self,
        box_data: Any,
        field_name: str,
        meta_file: Path,
        img_w: int,
        img_h: int,
    ) -> PixelBox | None:
        if box_data is None:
            return None
        if not isinstance(box_data, dict):
            raise InvalidLegendError(f"{meta_file}: bad box for field '{field_name}'")

        try:
            x = int(box_data["x"])
            y = int(box_data["y"])
            w = int(box_data["w"])
            h = int(box_data["h"])
            box = PixelBox(x=x, y=y, w=w, h=h)
        except (KeyError, ValueError) as exc:
            raise InvalidLegendError(
                f"{meta_file}: bad box coordinates for field '{field_name}': {exc}"
            ) from exc

        if box.x + box.w > img_w or box.y + box.h > img_h:
            raise InvalidLegendError(
                f"{meta_file}: box '{field_name}' ({box}) exceeds image size ({img_w}x{img_h})"
            )

        return box
