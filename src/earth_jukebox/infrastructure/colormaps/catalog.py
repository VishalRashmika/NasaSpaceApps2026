"""Colormap preset catalog (F-003).

Implements ColormapCatalog using matplotlib colormaps converted to CIE L*a*b*.
"""

from __future__ import annotations

from collections.abc import Sequence

import cv2
import matplotlib

matplotlib.use("Agg")
import numpy as np

from earth_jukebox.application.ports import ColormapCatalog
from earth_jukebox.domain.errors import InvalidLegendError
from earth_jukebox.domain.models import ColorLUT, ColormapKind, RecoveryMode

# Presets required by F-003:
# viridis, plasma, inferno, magma, cividis, turbo, jet,
# Blues, Greens, YlGnBu, YlOrRd, Reds, RdBu_r, RdYlBu_r, coolwarm, BrBG, PuOr, seismic, gray
DIVERGING_PRESETS = frozenset(
    {
        "BrBG",
        "PuOr",
        "RdBu_r",
        "RdYlBu_r",
        "coolwarm",
        "seismic",
    }
)

SEQUENTIAL_PRESETS = frozenset(
    {
        "Blues",
        "Greens",
        "Reds",
        "YlGnBu",
        "YlOrRd",
        "cividis",
        "gray",
        "inferno",
        "jet",
        "magma",
        "plasma",
        "turbo",
        "viridis",
    }
)

CATALOG_PRESETS = sorted(DIVERGING_PRESETS | SEQUENTIAL_PRESETS)


class MatplotlibColormapCatalog(ColormapCatalog):
    """ColormapCatalog backed by matplotlib's colormap registry."""

    def __init__(self, preset_names: Sequence[str] | None = None) -> None:
        self._names = tuple(sorted(preset_names or CATALOG_PRESETS))
        self._custom_luts: dict[str, ColorLUT] = {}
        self._custom_kinds: dict[str, ColormapKind] = {}

    def register_lut(
        self,
        name: str,
        lut: ColorLUT,
        kind: ColormapKind = ColormapKind.SEQUENTIAL,
    ) -> None:
        """Register a custom ColorLUT preset (e.g. from a category legend)."""
        self._custom_luts[name] = lut
        self._custom_kinds[name] = kind
        if name not in self._names:
            self._names = tuple(sorted([*self._names, name]))

    def names(self) -> Sequence[str]:
        """Return sorted and stable list of available preset names."""
        return self._names

    def kind(self, name: str) -> ColormapKind:
        """Return ColormapKind (SEQUENTIAL or DIVERGING) for the named preset."""
        if name in self._custom_kinds:
            return self._custom_kinds[name]
        if name not in self._names:
            raise InvalidLegendError(f"unknown colormap preset '{name}'")
        return ColormapKind.DIVERGING if name in DIVERGING_PRESETS else ColormapKind.SEQUENTIAL

    def lut(self, name: str, n: int = 256) -> ColorLUT:
        """Return named preset as a ColorLUT with values scaled to [0, 1] (F-003 AC1)."""
        if name in self._custom_luts:
            return self._custom_luts[name]
        if name not in self._names:
            raise InvalidLegendError(f"unknown colormap preset '{name}'")
        if n < 2:
            raise ValueError("n must be at least 2")

        try:
            cmap = matplotlib.colormaps.get_cmap(name)
        except Exception as exc:
            raise InvalidLegendError(f"failed to load colormap '{name}': {exc}") from exc

        positions = np.linspace(0.0, 1.0, n, dtype=np.float64)
        rgb_f32 = cmap(positions)[:, :3].astype(np.float32)

        # Convert float32 sRGB (0..1) to CIE L*a*b* using OpenCV (docs/05 section 2)
        rgb_2d = rgb_f32.reshape(1, n, 3)
        lab_2d = cv2.cvtColor(rgb_2d, cv2.COLOR_RGB2LAB)
        lab = lab_2d.reshape(n, 3).astype(np.float64)

        return ColorLUT(
            lab=lab,
            values=positions,
            source=RecoveryMode.PRESET,
        )
