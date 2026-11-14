"""Analysis persistence store (F-061, F-062).

Implements AnalysisStore to persist ScalarField instances between /analyze and /sonify calls.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

from earth_jukebox.application.ports import AnalysisStore
from earth_jukebox.domain.errors import NotFoundError
from earth_jukebox.domain.models import (
    ColormapKind,
    GeoExtent,
    LegendSpec,
    Orientation,
    RecoveryMode,
    RecoveryQuality,
    ScalarField,
    ScaleType,
    VariableCategory,
)

ANALYSIS_ID_PATTERN = re.compile(r"^[a-f0-9]{16}$")


class FileSystemAnalysisStore(AnalysisStore):
    """Persists recovered fields in data/cache/analysis/<analysis_id>.npz and memory."""

    def __init__(self, cache_dir: Path) -> None:
        self._dir = cache_dir / "analysis"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: dict[str, ScalarField] = {}

    def save(self, analysis_id: str, field: ScalarField) -> None:
        if not ANALYSIS_ID_PATTERN.match(analysis_id):
            raise ValueError(f"invalid analysis_id format: '{analysis_id}'")

        self._memory_cache[analysis_id] = field

        meta = {
            "legend": {
                "vmin": field.legend.vmin,
                "vmax": field.legend.vmax,
                "units": field.legend.units,
                "label": field.legend.label,
                "kind": field.legend.kind.value,
                "category": field.legend.category.value,
                "center": field.legend.center,
                "orientation": field.legend.orientation.value,
                "low_at_start": field.legend.low_at_start,
                "scale": field.legend.scale.value,
            },
            "extent": {
                "lat_min": field.extent.lat_min,
                "lat_max": field.extent.lat_max,
                "lon_min": field.extent.lon_min,
                "lon_max": field.extent.lon_max,
                "projection": field.extent.projection,
            },
            "quality": {
                "mean_delta_e": field.quality.mean_delta_e,
                "p95_delta_e": field.quality.p95_delta_e,
                "masked_fraction": field.quality.masked_fraction,
                "lut_is_monotonic_in_lightness": field.quality.lut_is_monotonic_in_lightness,
                "confidence": field.quality.confidence,
                "mode": field.quality.mode.value,
                "warnings": list(field.quality.warnings),
            },
            "source_hash": field.source_hash,
        }

        target_file = self._dir / f"{analysis_id}.npz"
        np.savez_compressed(
            target_file,
            values=field.values,
            meta=json.dumps(meta),
        )

    def load(self, analysis_id: str) -> ScalarField:
        if not ANALYSIS_ID_PATTERN.match(analysis_id):
            raise NotFoundError(f"analysis_id '{analysis_id}' not found")

        if analysis_id in self._memory_cache:
            return self._memory_cache[analysis_id]

        target_file = self._dir / f"{analysis_id}.npz"
        if not target_file.is_file():
            raise NotFoundError(f"analysis_id '{analysis_id}' not found")

        try:
            with np.load(target_file, allow_pickle=False) as data:
                values = data["values"].astype(np.float64)
                meta = json.loads(str(data["meta"]))
        except Exception as exc:
            raise NotFoundError(f"failed to read analysis '{analysis_id}': {exc}") from exc

        leg_d = meta["legend"]
        legend = LegendSpec(
            vmin=float(leg_d["vmin"]),
            vmax=float(leg_d["vmax"]),
            units=str(leg_d["units"]),
            label=str(leg_d["label"]),
            kind=ColormapKind(leg_d["kind"]),
            category=VariableCategory(leg_d["category"]),
            center=float(leg_d["center"]) if leg_d.get("center") is not None else None,
            orientation=Orientation(leg_d["orientation"]),
            low_at_start=bool(leg_d["low_at_start"]),
            scale=ScaleType(leg_d["scale"]),
        )

        ext_d = meta["extent"]
        extent = GeoExtent(
            lat_min=float(ext_d["lat_min"]),
            lat_max=float(ext_d["lat_max"]),
            lon_min=float(ext_d["lon_min"]),
            lon_max=float(ext_d["lon_max"]),
            projection=str(ext_d["projection"]),
        )

        q_d = meta["quality"]
        quality = RecoveryQuality(
            mean_delta_e=float(q_d["mean_delta_e"]),
            p95_delta_e=float(q_d["p95_delta_e"]),
            masked_fraction=float(q_d["masked_fraction"]),
            lut_is_monotonic_in_lightness=bool(q_d.get("lut_is_monotonic_in_lightness", True)),
            confidence=float(q_d["confidence"]),
            mode=RecoveryMode(q_d.get("mode", "colorbar")),
            warnings=tuple(q_d.get("warnings", ())),
        )

        field = ScalarField(
            values=values,
            legend=legend,
            extent=extent,
            quality=quality,
            source_hash=str(meta.get("source_hash", "")),
        )

        self._memory_cache[analysis_id] = field
        return field
