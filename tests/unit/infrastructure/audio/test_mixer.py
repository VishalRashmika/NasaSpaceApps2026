"""Unit tests for F-041 (Mixer, pan, limiter)."""

from __future__ import annotations

import numpy as np

from earth_jukebox.domain.models import ColormapKind, LegendSpec, NoteEvent, Score, Voice
from earth_jukebox.infrastructure.audio.mixer import mix_score


def _make_dense_score(n_voices: int = 5, n_notes_per_voice: int = 20) -> Score:
    """Create a dense multi-voice Score with overlapping loud notes."""
    voices = tuple(
        Voice(
            id=f"voice{i}",
            band_index=i,
            instrument="strings" if i % 2 == 0 else "pad",
            pan=(i / (n_voices - 1) * 2.0 - 1.0) if n_voices > 1 else 0.0,
        )
        for i in range(n_voices)
    )

    notes = []
    # 20 beats, multiple simultaneous notes in all voices at velocity 1.0
    for beat in range(n_notes_per_voice):
        for i, voice in enumerate(voices):
            notes.append(
                NoteEvent(
                    voice_id=voice.id,
                    t_beat=float(beat),
                    dur_beat=1.5,  # overlapping
                    pitch_midi=48.0 + (i * 4) + (beat % 7),
                    velocity=1.0,
                    accent=True,
                    col=beat,
                    band=voice.band_index,
                    value=float(beat),
                    roughness=0.3,
                )
            )

    return Score(
        mapping_version="1.0.0",
        skin_id="neutral",
        seed=12345,
        bpm=120.0,
        total_beats=float(n_notes_per_voice),
        n_cols=n_notes_per_voice,
        n_bands=n_voices,
        voices=voices,
        notes=tuple(notes),
        drone_midi=(48.0, 55.0),
        legend=LegendSpec(
            vmin=0.0,
            vmax=100.0,
            units="%",
            label="Dense",
            kind=ColormapKind.SEQUENTIAL,
        ),
        provenance={"band_brightness": "1.0,1.0,1.0,1.0,1.0", "drone_brightness": "0.5"},
    )


def test_f041_ac1_soft_limiter_peak_lte_minus_one_dbfs() -> None:
    # F-041 AC1: peak <= 0.89 (-1 dBFS) for a dense 5-voice score
    score = _make_dense_score(n_voices=5, n_notes_per_voice=15)
    stereo = mix_score(score, sample_rate=44100)

    assert stereo.ndim == 2
    assert stereo.shape[0] == 2  # (2, n_samples)
    left, right = stereo[0], stereo[1]

    peak_left = float(np.max(np.abs(left)))
    peak_right = float(np.max(np.abs(right)))
    peak_total = max(peak_left, peak_right)

    # Soft limiter ceiling is 0.89
    assert peak_total <= 0.89 + 1e-6, f"Peak {peak_total} exceeds 0.89 (-1 dBFS)"
    assert not np.isnan(stereo).any()
    assert not np.isinf(stereo).any()


def test_f041_ac2_hard_left_voice_right_channel_rms_lte_one_percent() -> None:
    # F-041 AC2: a hard-left voice has right-channel RMS <= 1 % of left
    voice_left = Voice(id="left_only", band_index=0, instrument="flute", pan=-1.0)
    note = NoteEvent(
        voice_id="left_only",
        t_beat=1.0,
        dur_beat=2.0,
        pitch_midi=60.0,
        velocity=0.9,
        accent=False,
        col=0,
        band=0,
        value=10.0,
    )
    score = Score(
        mapping_version="1.0.0",
        skin_id="neutral",
        seed=42,
        bpm=120.0,
        total_beats=4.0,
        n_cols=4,
        n_bands=1,
        voices=(voice_left,),
        notes=(note,),
        drone_midi=(),  # No drone to isolate the voice pan test
        legend=LegendSpec(
            vmin=0.0,
            vmax=10.0,
            units="m",
            label="Pan",
            kind=ColormapKind.SEQUENTIAL,
        ),
        provenance={},
    )
    stereo = mix_score(score, sample_rate=44100)
    left, right = stereo[0], stereo[1]

    # Measure RMS during the sounding note (seconds 0.5 to 1.5)
    fs = 44100
    segment_l = left[int(0.6 * fs) : int(1.4 * fs)]
    segment_r = right[int(0.6 * fs) : int(1.4 * fs)]

    rms_l = float(np.sqrt(np.mean(segment_l**2)))
    rms_r = float(np.sqrt(np.mean(segment_r**2)))

    assert rms_l > 0.001, "Left channel should be audible"
    ratio = rms_r / rms_l
    assert ratio <= 0.01, f"Right channel RMS ratio {ratio:.4f} > 0.01 threshold (1%)"


def test_f041_fade_in_fade_out_and_tail() -> None:
    # Verify fade-in starts at 0, fade-out ends at 0, duration includes tail
    score = _make_dense_score(n_voices=1, n_notes_per_voice=4)
    stereo = mix_score(score, sample_rate=44100)
    left, right = stereo[0], stereo[1]

    # At t=0, amplitude should be 0 due to fade-in
    assert abs(left[0]) < 1e-6
    assert abs(right[0]) < 1e-6

    # At the end, amplitude should be 0 due to fade-out
    assert abs(left[-1]) < 1e-6
    assert abs(right[-1]) < 1e-6

    # Total duration = total_beats * (60 / bpm) + 1.5
    expected_sec = 4.0 * (60.0 / 120.0) + 1.5  # 2.0 + 1.5 = 3.5s
    actual_sec = len(left) / 44100.0
    assert abs(actual_sec - expected_sec) < 0.05
