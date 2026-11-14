"""Unit tests for F-053: Sri Lankan skin."""

from __future__ import annotations

import numpy as np

from earth_jukebox.application.use_cases.sonify import sonify
from earth_jukebox.domain.models import (
    ColormapKind,
    GeoExtent,
    LegendSpec,
    RecoveryMode,
    RecoveryQuality,
    ScalarField,
    ScaleType,
    SonificationParams,
    VariableCategory,
)
from earth_jukebox.domain.skins import get_skin


def test_f053_ac_skin_properties_and_provisional() -> None:
    # F-053 AC: scale choice, provisional flag, lead flute, rhythm patterns in data
    skin = get_skin("sri_lankan")
    assert skin.scale_cents == (0.0, 200.0, 400.0, 700.0, 1000.0)
    assert skin.provisional is True
    assert skin.tonic_midi == 48.0
    assert skin.n_octaves == 2
    assert skin.instrument_map[VariableCategory.GENERIC] == "flute"
    assert skin.instrument_map[VariableCategory.TEMPERATURE] == "flute"


def test_f053_ac2_rhythm_pattern_data_lives_in_skin() -> None:
    # F-053 AC2: rhythm pattern data lives in the skin (data), not in code branches
    skin = get_skin("sri_lankan")
    assert "d1" in skin.rhythm_patterns
    assert "d2" in skin.rhythm_patterns
    assert "d4" in skin.rhythm_patterns
    assert skin.rhythm_patterns["d1"] == (1.0,)
    assert skin.rhythm_patterns["d2"] == (1.0, 0.6)
    assert skin.rhythm_patterns["d4"] == (1.0, 0.5, 0.8, 0.5)


def test_f053_percussion_voice_and_notes() -> None:
    # Verify percussion voice in score.voices and percussion notes emitted
    h, w = 10, 40
    values = np.full((h, w), 50.0, dtype=np.float64)

    legend = LegendSpec(
        vmin=0.0,
        vmax=100.0,
        units="mm",
        label="Precipitation",
        kind=ColormapKind.SEQUENTIAL,
        category=VariableCategory.PRECIPITATION,
        scale=ScaleType.LINEAR,
    )
    field = ScalarField(
        values=values,
        legend=legend,
        extent=GeoExtent(),
        quality=RecoveryQuality(
            mean_delta_e=0.1,
            p95_delta_e=0.2,
            masked_fraction=0.0,
            lut_is_monotonic_in_lightness=True,
            confidence=0.95,
            mode=RecoveryMode.COLORBAR,
        ),
        source_hash="test_sri_lankan_hash_1",
    )

    params = SonificationParams(skin_id="sri_lankan", n_cols=8, n_bands=3, seed=42)
    score = sonify(field, params)

    # Percussion voice must be in score.voices
    perc_voices = [v for v in score.voices if v.id == "perc"]
    assert len(perc_voices) == 1
    assert perc_voices[0].band_index == -2
    assert perc_voices[0].instrument == "percussion"
    assert perc_voices[0].pan == 0.0

    # Percussion notes must be generated
    perc_notes = [n for n in score.notes if n.voice_id == "perc"]
    assert len(perc_notes) > 0
    for pn in perc_notes:
        assert pn.kind == "ornament"
        assert pn.band == -2
        assert pn.value is None
        assert pn.pitch_midi == 45.0
        assert 0.0 <= pn.velocity <= 1.0


def test_f053_percussion_silence_on_masked_column() -> None:
    # If a column is completely masked, no percussion notes are emitted for that column
    h, w = 10, 40
    values = np.full((h, w), 50.0, dtype=np.float64)
    # Mask column 2 completely (indices 10 to 15)
    values[:, 10:15] = np.nan

    legend = LegendSpec(
        vmin=0.0,
        vmax=100.0,
        units="mm",
        label="Precipitation",
        kind=ColormapKind.SEQUENTIAL,
        category=VariableCategory.PRECIPITATION,
        scale=ScaleType.LINEAR,
    )
    field = ScalarField(
        values=values,
        legend=legend,
        extent=GeoExtent(),
        quality=RecoveryQuality(
            mean_delta_e=0.1,
            p95_delta_e=0.2,
            masked_fraction=0.1,
            lut_is_monotonic_in_lightness=True,
            confidence=0.9,
            mode=RecoveryMode.COLORBAR,
        ),
        source_hash="test_sri_lankan_masked",
    )

    # With n_cols=4, col 1 is columns 10..19, which is half NaN -> coverage < 0.25 if we mask all
    values[:, 10:20] = np.nan
    field = ScalarField(
        values=values,
        legend=legend,
        extent=GeoExtent(),
        quality=field.quality,
        source_hash="test_sri_lankan_masked2",
    )
    params = SonificationParams(skin_id="sri_lankan", n_cols=4, n_bands=2, seed=42)
    score = sonify(field, params)

    # Column 1 should be completely masked, so no perc notes at col=1
    perc_col1 = [n for n in score.notes if n.voice_id == "perc" and n.col == 1]
    assert len(perc_col1) == 0
