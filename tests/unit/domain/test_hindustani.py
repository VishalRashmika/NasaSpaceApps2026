"""Unit tests for F-052: Hindustani raga skin."""

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


def test_f052_ac1_scale_and_provisional() -> None:
    # F-052 AC1: the skin's scale equals the note set in the docs/08 §3 table
    # (provisional flag set until the musician validates).
    skin = get_skin("hindustani")
    assert skin.scale_cents == (0.0, 200.0, 300.0, 500.0, 700.0, 900.0, 1000.0)
    assert skin.provisional is True
    assert skin.tonic_midi == 48.0
    assert skin.n_octaves == 2
    assert skin.glide_descending is True
    assert "pakad_1" in skin.phrases
    assert skin.phrases["pakad_1"] == (0, -1, -2, -1, 0)

    # Alias check
    alias_skin = get_skin("hindustani_malhar")
    assert alias_skin.id == skin.id
    assert alias_skin.scale_cents == skin.scale_cents


def test_f052_ac3_descending_glides() -> None:
    # F-052 AC3: with glide_descending, every descending step between consecutive
    # columns in the same band has glide_to_midi set.
    # Create a simple field with a clear descending gradient west to east
    # e.g. values 100.0 down to 0.0 across 4 columns
    h, w = 10, 40
    gradient = np.linspace(100.0, 0.0, w, dtype=np.float64)
    values = np.tile(gradient, (h, 1))

    legend = LegendSpec(
        vmin=0.0,
        vmax=100.0,
        units="°C",
        label="Temperature",
        kind=ColormapKind.SEQUENTIAL,
        category=VariableCategory.TEMPERATURE,
        scale=ScaleType.LINEAR,
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
    field = ScalarField(
        values=values,
        legend=legend,
        extent=extent,
        quality=quality,
        source_hash="test_gradient_hash_1234",
    )

    params = SonificationParams(skin_id="hindustani", n_cols=8, n_bands=3, seed=42)
    score = sonify(field, params)

    # For each band and each column step where pitch descends:
    for b in range(score.n_bands):
        for c in range(score.n_cols - 1):
            main_notes_c = [
                n for n in score.notes if n.band == b and n.col == c and n.kind == "main"
            ]
            main_notes_next = [
                n for n in score.notes if n.band == b and n.col == c + 1 and n.kind == "main"
            ]
            assert len(main_notes_c) > 0
            assert len(main_notes_next) > 0

            p_curr = main_notes_c[-1].pitch_midi
            p_next = main_notes_next[0].pitch_midi

            if p_next < p_curr:
                # Descending step: the last note at column c MUST have glide_to_midi == p_next
                assert main_notes_c[-1].glide_to_midi == p_next
            else:
                assert main_notes_c[-1].glide_to_midi is None

        # Last column has no next column
        last_notes = [
            n for n in score.notes if n.band == b and n.col == score.n_cols - 1 and n.kind == "main"
        ]
        assert len(last_notes) > 0
        assert last_notes[-1].glide_to_midi is None


def test_f052_neutral_skin_has_no_glides() -> None:
    # Verify that neutral skin does NOT set glide_to_midi on descending steps
    h, w = 10, 40
    gradient = np.linspace(100.0, 0.0, w, dtype=np.float64)
    values = np.tile(gradient, (h, 1))

    legend = LegendSpec(
        vmin=0.0,
        vmax=100.0,
        units="°C",
        label="Temperature",
        kind=ColormapKind.SEQUENTIAL,
        category=VariableCategory.TEMPERATURE,
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
        source_hash="test_gradient_hash_neutral",
    )

    params = SonificationParams(skin_id="neutral", n_cols=8, n_bands=3, seed=42)
    score = sonify(field, params)

    for n in score.notes:
        assert n.glide_to_midi is None
