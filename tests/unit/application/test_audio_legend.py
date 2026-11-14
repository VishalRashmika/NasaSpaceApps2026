"""Unit tests for F-034 (Audio legend sweep)."""

from __future__ import annotations

import math

from earth_jukebox.application.use_cases.audio_legend import legend_pitch_r, legend_score
from earth_jukebox.domain.models import ColormapKind, LegendSpec, ScaleType, Skin, VariableCategory
from earth_jukebox.domain.skins.neutral import NEUTRAL_SKIN


def test_f034_ac1_ac2_legend_sweep_sequential() -> None:
    # AC1: notes' pitches non-decreasing, distinct pitches where scale allows
    # AC2: value of first/last note = vmin/vmax
    vmin, vmax = 0.0, 100.0
    legend = LegendSpec(
        vmin=vmin,
        vmax=vmax,
        units="%",
        label="Humidity",
        kind=ColormapKind.SEQUENTIAL,
        category=VariableCategory.PRECIPITATION,
        scale=ScaleType.LINEAR,
    )
    score = legend_score(legend, NEUTRAL_SKIN)

    assert score.n_cols == 32
    assert score.total_beats == 32.0
    assert score.bpm == 96.0
    assert len(score.voices) == 1
    assert score.voices[0].id == "legend"
    assert score.voices[0].instrument == "pluck"  # precipitation instrument

    main_notes = [n for n in score.notes if n.kind == "main"]
    assert len(main_notes) == 32

    # AC1: non-decreasing pitch
    for i in range(len(main_notes) - 1):
        assert main_notes[i].pitch_midi <= main_notes[i + 1].pitch_midi

    # Neutral skin has 11 pitches across 2 octaves, all 11 should appear
    distinct_pitches = {n.pitch_midi for n in main_notes}
    assert len(distinct_pitches) == 11

    # AC2: first note = vmin, last note = vmax
    assert main_notes[0].value is not None
    assert main_notes[-1].value is not None
    assert math.isclose(main_notes[0].value, vmin, abs_tol=1e-5)
    assert math.isclose(main_notes[-1].value, vmax, abs_tol=1e-5)


def test_f034_ac1_scale_with_many_degrees() -> None:
    # AC1: >= 12 distinct pitches where scale allows (e.g. 7-note scale with N=15)
    heptatonic_skin = Skin(
        id="hepta",
        name="Heptatonic",
        tonic_midi=48.0,
        scale_cents=(0.0, 200.0, 300.0, 500.0, 700.0, 900.0, 1100.0),
        n_octaves=2,
        instrument_map={},
    )
    legend = LegendSpec(
        vmin=-10.0,
        vmax=10.0,
        units="m",
        label="Sea Level",
        kind=ColormapKind.SEQUENTIAL,
    )
    score = legend_score(legend, heptatonic_skin)
    main_notes = [n for n in score.notes if n.kind == "main"]
    distinct_pitches = {n.pitch_midi for n in main_notes}
    # N = 2 * 7 + 1 = 15 pitches, >= 12
    assert len(distinct_pitches) >= 12


def test_f034_diverging_centre_bell_marker() -> None:
    # Diverging legends have a tonic marker (bell) at the centre
    legend = LegendSpec(
        vmin=-5.0,
        vmax=5.0,
        center=0.0,
        units="C",
        label="Anomaly",
        kind=ColormapKind.DIVERGING,
    )
    score = legend_score(legend, NEUTRAL_SKIN)

    bell_notes = [n for n in score.notes if n.kind == "accent_bell"]
    assert len(bell_notes) >= 1
    assert any(v.id == "accent" and v.instrument == "bell" for v in score.voices)
    # Bell note is at the center (beat 16)
    assert bell_notes[0].t_beat == 16.0


def test_f079_legend_pitch_correlation() -> None:
    # F-079: legend pitch correlation r >= 0.98 for sequential and diverging
    legend_seq = LegendSpec(
        vmin=0.0,
        vmax=100.0,
        units="%",
        label="Cloud Cover",
        kind=ColormapKind.SEQUENTIAL,
    )
    r_seq = legend_pitch_r(legend_seq, NEUTRAL_SKIN)
    assert r_seq >= 0.98

    legend_div = LegendSpec(
        vmin=-50.0,
        vmax=50.0,
        center=0.0,
        units="m",
        label="Elevation Anomaly",
        kind=ColormapKind.DIVERGING,
    )
    r_div = legend_pitch_r(legend_div, NEUTRAL_SKIN)
    assert r_div >= 0.98
