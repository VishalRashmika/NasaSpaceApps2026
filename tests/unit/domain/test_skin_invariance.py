"""F-054: Skin invariance test.

Acceptance criteria:
For every skin and 5 synthetic fields:
(a) the sequence of values sorted by u maps to non-decreasing pitch;
(b) note onsets/velocities/accents/voices/pans are identical across skins
    (only pitch values and instrument ids may differ).
AC: test exists, parametrised over list_skins(), passes.
"""

from __future__ import annotations

import numpy as np
import pytest

from earth_jukebox.application.use_cases.sonify import sonify
from earth_jukebox.domain.models import (
    ScalarField,
    Skin,
    SonificationParams,
)
from earth_jukebox.domain.skins import list_skins
from earth_jukebox.domain.sonification.pitch import quantize_pitch
from earth_jukebox.infrastructure.vision.synthetic import generate_map

SYNTHETIC_CMAPS: tuple[str, ...] = ("viridis", "plasma", "turbo", "RdBu_r", "Blues")


def _get_synthetic_field(cmap_name: str, seed: int = 1) -> ScalarField:
    _, truth_field, _, _, _ = generate_map(cmap=cmap_name, seed=seed)
    return truth_field


@pytest.fixture(scope="module")
def synthetic_fields() -> list[ScalarField]:
    return [_get_synthetic_field(cmap) for cmap in SYNTHETIC_CMAPS]


@pytest.mark.parametrize("skin", list_skins(), ids=lambda s: s.id)
def test_f054_ac_part_a_pitch_monotonicity_for_sorted_u(skin: Skin) -> None:
    # (a) the sequence of values sorted by u maps to non-decreasing pitch
    u_vals = np.linspace(0.0, 1.0, 101)
    pitches = [quantize_pitch(float(u), skin) for u in u_vals]

    for i in range(len(pitches) - 1):
        assert pitches[i] <= pitches[i + 1], (
            f"Skin {skin.id} non-monotonic pitch at u={u_vals[i]}: {pitches[i]} > {pitches[i + 1]}"
        )

    # Scale range check
    assert pitches[0] == skin.tonic_midi
    top_tonic = skin.tonic_midi + 12.0 * skin.n_octaves
    assert pitches[-1] == top_tonic


@pytest.mark.parametrize("skin", list_skins(), ids=lambda s: s.id)
def test_f054_ac_part_b_score_invariance_across_skins(
    skin: Skin,
    synthetic_fields: list[ScalarField],
) -> None:
    # (b) note onsets/velocities/accents/voices/pans are identical across skins
    # (only pitch values and instrument ids may differ).
    for field in synthetic_fields:
        ref_params = SonificationParams(skin_id="neutral", n_cols=32, n_bands=5, seed=123)
        ref_score = sonify(field, ref_params)

        skin_params = SonificationParams(skin_id=skin.id, n_cols=32, n_bands=5, seed=123)
        skin_score = sonify(field, skin_params)

        # Global parameters identical
        assert skin_score.bpm == ref_score.bpm
        assert skin_score.total_beats == ref_score.total_beats
        assert skin_score.n_cols == ref_score.n_cols
        assert skin_score.n_bands == ref_score.n_bands

        # Core band voice properties (id, band_index, pan) identical
        for b in range(ref_score.n_bands):
            v_ref = ref_score.voices[b]
            v_skin = skin_score.voices[b]
            assert v_skin.id == v_ref.id
            assert v_skin.band_index == v_ref.band_index
            assert v_skin.pan == v_ref.pan
            # instrument id may differ per skin

        # Accent voice identical
        v_ref_accent = next(v for v in ref_score.voices if v.id == "accent")
        v_skin_accent = next(v for v in skin_score.voices if v.id == "accent")
        assert v_skin_accent.band_index == v_ref_accent.band_index
        assert v_skin_accent.pan == v_ref_accent.pan
        assert v_skin_accent.instrument == v_ref_accent.instrument

        # Main notes: onsets, velocities, accents, voices, pans must be identical
        ref_main = [n for n in ref_score.notes if n.kind == "main"]
        skin_main = [n for n in skin_score.notes if n.kind == "main"]

        assert len(skin_main) == len(ref_main), (
            f"Skin {skin.id} produced {len(skin_main)} main notes vs {len(ref_main)} ref notes"
        )

        for i, (n_skin, n_ref) in enumerate(zip(skin_main, ref_main, strict=True)):
            assert n_skin.t_beat == n_ref.t_beat, f"Mismatch t_beat at note {i}"
            assert n_skin.dur_beat == n_ref.dur_beat, f"Mismatch dur_beat at note {i}"
            assert n_skin.velocity == n_ref.velocity, f"Mismatch velocity at note {i}"
            assert n_skin.accent == n_ref.accent, f"Mismatch accent at note {i}"
            assert n_skin.voice_id == n_ref.voice_id, f"Mismatch voice_id at note {i}"
            assert n_skin.col == n_ref.col, f"Mismatch col at note {i}"
            assert n_skin.band == n_ref.band, f"Mismatch band at note {i}"
            assert n_skin.value == n_ref.value, f"Mismatch value at note {i}"
