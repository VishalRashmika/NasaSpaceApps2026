"""Unit tests for F-091: Per-frame phrases use case and phrase concatenation."""

from __future__ import annotations

import numpy as np
import pytest

from earth_jukebox.application.use_cases.sonify import sonify
from earth_jukebox.application.use_cases.time_mode import concatenate_phrases, sonify_animation
from earth_jukebox.domain.errors import InvalidImageError
from earth_jukebox.domain.models import (
    ColormapKind,
    DecodedImage,
    GeoExtent,
    LegendSpec,
    RecoveryMode,
    RecoveryQuality,
    ScalarField,
    SonificationParams,
)
from earth_jukebox.infrastructure.colormaps.catalog import MatplotlibColormapCatalog
from earth_jukebox.infrastructure.vision.recoverer import VisionFieldRecoverer


def _make_field(values: np.ndarray) -> ScalarField:
    legend = LegendSpec(
        vmin=0.0,
        vmax=100.0,
        units="°C",
        label="Temperature",
        kind=ColormapKind.SEQUENTIAL,
    )
    extent = GeoExtent()
    quality = RecoveryQuality(
        mean_delta_e=0.1,
        p95_delta_e=0.2,
        masked_fraction=0.0,
        lut_is_monotonic_in_lightness=True,
        confidence=0.95,
        mode=RecoveryMode.COLORBAR,
    )
    return ScalarField(
        values=values,
        legend=legend,
        extent=extent,
        quality=quality,
        source_hash="test_hash",
    )


def test_concatenate_phrases_timing_ac2_ac3_ac4() -> None:
    """F-091 AC2, AC3, AC4: Phrases concatenated with 1-beat rest, total_beats correct."""
    f1 = _make_field(np.full((10, 10), 20.0, dtype=np.float64))
    f2 = _make_field(np.full((10, 10), 40.0, dtype=np.float64))
    f3 = _make_field(np.full((10, 10), 60.0, dtype=np.float64))

    params = SonificationParams(n_cols=16, n_bands=5)
    p1 = sonify(f1, params)
    p2 = sonify(f2, params)
    p3 = sonify(f3, params)

    phrase_beats = p1.total_beats  # 16.0
    assert phrase_beats == 16.0

    score = concatenate_phrases([p1, p2, p3], [f1, f2, f3], skin_id="neutral")

    # F-091 AC4: total_beats = 3 * 16 + 2 * 1 = 48 + 2 = 50.0
    expected_total_beats = 3 * 16.0 + 2 * 1.0
    assert score.total_beats == expected_total_beats

    # F-091 AC3: Notes in phrase 0 start at >= 0.0 and < 16.0
    p0_notes = [n for n in score.notes if n.t_beat < 16.0]
    assert len(p0_notes) > 0

    # Phrase 1 starts at 16.0 + 1.0 = 17.0
    p1_notes = [n for n in score.notes if 17.0 <= n.t_beat < 33.0]
    assert len(p1_notes) > 0

    # There should be NO notes in the 1-beat rest [16.0, 17.0)
    rest_0_notes = [n for n in score.notes if 16.0 <= n.t_beat < 17.0]
    assert len(rest_0_notes) == 0

    # Phrase 2 starts at 33.0 + 1.0 = 34.0
    p2_notes = [n for n in score.notes if 34.0 <= n.t_beat < 50.0]
    assert len(p2_notes) > 0

    # There should be NO notes in the 1-beat rest [33.0, 34.0)
    rest_1_notes = [n for n in score.notes if 33.0 <= n.t_beat < 34.0]
    assert len(rest_1_notes) == 0

    # Provenance
    assert score.provenance["time_mode"] == "true"
    assert score.provenance["n_frames"] == "3"
    assert score.provenance["frame_beats"] == "16.0"
    assert score.provenance["rest_beats"] == "1.0"


def test_sonify_3d_field_delegation() -> None:
    """F-091: 3D field (F, H, W) automatically invokes time mode."""
    stacked_vals = np.stack(
        [
            np.full((10, 10), 20.0, dtype=np.float64),
            np.full((10, 10), 50.0, dtype=np.float64),
        ],
        axis=0,
    )
    field_3d = _make_field(stacked_vals)
    params = SonificationParams(n_cols=16, n_bands=5)

    score = sonify(field_3d, params)
    # 2 frames * 16 + 1 rest = 33.0 beats
    assert score.total_beats == 33.0
    assert score.provenance["time_mode"] == "true"
    assert score.provenance["n_frames"] == "2"


def test_sonify_animation_use_case_ac1() -> None:
    """F-091 AC1: Each frame recovered with same legend/boxes into a ScalarField."""
    catalog = MatplotlibColormapCatalog()
    recoverer = VisionFieldRecoverer(catalog)

    # 2 synthetic images
    img1 = DecodedImage(
        rgb=np.full((32, 32, 3), 100, dtype=np.uint8),
        content_hash="frame_1",
        original_width=32,
        original_height=32,
    )
    img2 = DecodedImage(
        rgb=np.full((32, 32, 3), 200, dtype=np.uint8),
        content_hash="frame_2",
        original_width=32,
        original_height=32,
    )

    legend = LegendSpec(
        vmin=0.0,
        vmax=50.0,
        units="mm",
        label="Rainfall",
        kind=ColormapKind.SEQUENTIAL,
    )
    params = SonificationParams(n_cols=16, n_bands=5)

    score = sonify_animation(
        frames=[img1, img2],
        legend=legend,
        recoverer=recoverer,
        preset_name="viridis",
        params=params,
    )

    assert score.provenance["time_mode"] == "true"
    assert score.provenance["n_frames"] == "2"
    assert score.total_beats == 33.0


def test_concatenate_empty_raises() -> None:
    """Empty phrases raise InvalidImageError."""
    with pytest.raises(InvalidImageError, match="no phrases to concatenate"):
        concatenate_phrases([], [])
