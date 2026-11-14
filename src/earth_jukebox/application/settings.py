"""Runtime settings (plain data, built by the composition root)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    web_dir: Path
    data_dir: Path
    cache_dir: Path
    dataset_dir: Path | None = None
    max_upload_bytes: int = 20 * 1024 * 1024
    max_image_dimension: int = 8000
    working_max_dimension: int = 2048
