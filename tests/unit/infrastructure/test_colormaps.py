"""Tests for F-003: Colormap preset catalog."""

from __future__ import annotations

import numpy as np
import pytest

from earth_jukebox.domain.errors import InvalidLegendError
from earth_jukebox.domain.models import ColormapKind, RecoveryMode
from earth_jukebox.infrastructure.colormaps.catalog import MatplotlibColormapCatalog

REQUIRED_NAMES = [
    "Blues",
    "BrBG",
    "Greens",
    "PuOr",
    "RdBu_r",
    "RdYlBu_r",
    "Reds",
    "YlGnBu",
    "YlOrRd",
    "cividis",
    "coolwarm",
    "gray",
    "inferno",
    "jet",
    "magma",
    "plasma",
    "seismic",
    "turbo",
    "viridis",
]


def test_f003_ac1_lut_shape_and_values() -> None:
    # F-003 AC1: lut("viridis", 256) has shape (256,3) Lab, values ascending 0..1.
    cat = MatplotlibColormapCatalog()
    lut = cat.lut("viridis", 256)

    assert lut.lab.shape == (256, 3)
    assert lut.values.shape == (256,)
    assert lut.values[0] == 0.0
    assert lut.values[-1] == 1.0
    assert np.all(np.diff(lut.values) > 0)
    assert lut.source == RecoveryMode.PRESET

    # Check CIE Lab ranges: L is in [0, 100]
    assert np.all((lut.lab[:, 0] >= 0.0) & (lut.lab[:, 0] <= 100.0))


def test_f003_ac2_unknown_name_raises() -> None:
    # F-003 AC2: unknown name raises InvalidLegendError.
    cat = MatplotlibColormapCatalog()
    with pytest.raises(InvalidLegendError) as exc:
        cat.lut("non_existent_cmap")
    assert "non_existent_cmap" in str(exc.value)


def test_f003_ac3_names_sorted_and_stable() -> None:
    # F-003 AC3: names() is sorted and stable.
    cat = MatplotlibColormapCatalog()
    names1 = cat.names()
    names2 = cat.names()

    assert names1 == names2
    assert list(names1) == sorted(names1)
    for req in REQUIRED_NAMES:
        assert req in names1


def test_f003_colormap_kinds() -> None:
    cat = MatplotlibColormapCatalog()
    assert cat.kind("RdBu_r") == ColormapKind.DIVERGING
    assert cat.kind("coolwarm") == ColormapKind.DIVERGING
    assert cat.kind("viridis") == ColormapKind.SEQUENTIAL
    assert cat.kind("Blues") == ColormapKind.SEQUENTIAL
