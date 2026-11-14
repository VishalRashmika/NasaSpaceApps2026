"""Unit tests for F-047 (Audio-level pitch check)."""

from __future__ import annotations

import numpy as np

from earth_jukebox.application.use_cases.audio_legend import legend_score
from earth_jukebox.domain.models import ColormapKind, LegendSpec
from earth_jukebox.domain.skins.neutral import NEUTRAL_SKIN
from earth_jukebox.infrastructure.audio.renderer import NumpyAudioRenderer
from earth_jukebox.infrastructure.audio.yin import check_legend_sweep_audio, yin_pitch_frame


def test_yin_frame_pure_tones() -> None:
    # Test single-frame pitch detection on standard frequencies
    fs = 44100
    t = np.arange(2048) / fs

    # A4 = 440 Hz -> MIDI 69.0
    sig_a4 = np.sin(2.0 * np.pi * 440.0 * t)
    pitch_a4 = yin_pitch_frame(sig_a4, fs=fs)
    assert not np.isnan(pitch_a4)
    assert abs(pitch_a4 - 69.0) * 100.0 < 5.0  # < 5 cents

    # C4 = 261.6256 Hz -> MIDI 60.0
    sig_c4 = np.sin(2.0 * np.pi * 261.625565 * t)
    pitch_c4 = yin_pitch_frame(sig_c4, fs=fs)
    assert not np.isnan(pitch_c4)
    assert abs(pitch_c4 - 60.0) * 100.0 < 5.0


def test_f047_ac1_legend_sweep_all_notes_within_twenty_cents() -> None:
    # F-047 AC1: all notes within 20 cents on rendered legend sweep
    legend = LegendSpec(
        vmin=0.0,
        vmax=100.0,
        units="%",
        label="Humidity",
        kind=ColormapKind.SEQUENTIAL,
    )
    score = legend_score(legend, NEUTRAL_SKIN)
    renderer = NumpyAudioRenderer()

    result = check_legend_sweep_audio(score, renderer=renderer, sample_rate=44100)

    assert result.all_within_threshold, (
        f"Max cents error {result.max_cents_error:.2f} exceeds 20 cents threshold"
    )
    assert result.max_cents_error <= 20.0
    assert len(result.detected_pitches) == 32
    assert all(e <= 20.0 for e in result.cents_errors)


def test_f047_ac2_audio_legend_pearson_r_gte_point_nine_eight() -> None:
    # F-047 AC2: Pearson r between detected pitch and legend value >= 0.98;
    # result stored in FidelityReport.audio_legend_r
    legend = LegendSpec(
        vmin=-5.0,
        vmax=5.0,
        center=0.0,
        units="°C",
        label="Temperature Anomaly",
        kind=ColormapKind.DIVERGING,
    )
    score = legend_score(legend, NEUTRAL_SKIN)
    renderer = NumpyAudioRenderer()

    result = check_legend_sweep_audio(score, renderer=renderer, sample_rate=44100)

    assert result.audio_legend_r >= 0.98, (
        f"Audio legend Pearson r {result.audio_legend_r:.4f} is below 0.98"
    )
    assert result.fidelity_report.audio_legend_r == result.audio_legend_r
    assert result.fidelity_report.audio_legend_monotonic is True
