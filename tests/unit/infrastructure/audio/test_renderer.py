"""Unit tests for F-042 (WAV writer)."""

from __future__ import annotations

import hashlib
import io
import wave

from earth_jukebox.domain.models import ColormapKind, LegendSpec, NoteEvent, Score, Voice
from earth_jukebox.infrastructure.audio.renderer import NumpyAudioRenderer


def _make_test_score(bpm: float = 96.0, total_beats: float = 8.0) -> Score:
    voice = Voice(id="test_voice", band_index=0, instrument="flute", pan=0.0)
    notes = tuple(
        NoteEvent(
            voice_id="test_voice",
            t_beat=float(i),
            dur_beat=0.8,
            pitch_midi=60.0 + i,
            velocity=0.7,
            accent=(i == 0),
            col=i,
            band=0,
            value=float(i),
        )
        for i in range(int(total_beats))
    )
    return Score(
        mapping_version="1.0.0",
        skin_id="neutral",
        seed=42,
        bpm=bpm,
        total_beats=total_beats,
        n_cols=int(total_beats),
        n_bands=1,
        voices=(voice,),
        notes=notes,
        drone_midi=(48.0,),
        legend=LegendSpec(
            vmin=0.0, vmax=10.0, units="K", label="Temp", kind=ColormapKind.SEQUENTIAL
        ),
        provenance={"drone_brightness": "0.5"},
    )


def test_f042_ac1_valid_header_and_duration() -> None:
    # F-042 AC1: valid header; duration = total_beats*60/bpm + tail (<= 2 s) +- 50 ms
    renderer = NumpyAudioRenderer()
    bpm = 100.0
    total_beats = 10.0
    score = _make_test_score(bpm=bpm, total_beats=total_beats)

    wav_bytes = renderer.render_wav(score, sample_rate=44100)
    assert len(wav_bytes) > 44  # Valid WAV header is at least 44 bytes

    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        assert w.getnchannels() == 2
        assert w.getsampwidth() == 2  # 16-bit
        assert w.getframerate() == 44100
        n_frames = w.getnframes()
        duration_sec = n_frames / float(w.getframerate())

    # expected duration = total_beats * 60 / bpm + 1.5s tail (1.5 <= 2.0s)
    expected_sec = (total_beats * 60.0 / bpm) + 1.5
    assert abs(duration_sec - expected_sec) <= 0.050, (
        f"Duration {duration_sec:.3f} differs from expected {expected_sec:.3f} by > 50 ms"
    )


def test_f042_ac2_byte_identical_across_runs() -> None:
    # F-042 AC2: byte-identical across runs (F-102 determinism)
    renderer = NumpyAudioRenderer()
    score = _make_test_score(bpm=96.0, total_beats=6.0)

    run1_bytes = renderer.render_wav(score, sample_rate=44100)
    run2_bytes = renderer.render_wav(score, sample_rate=44100)

    hash1 = hashlib.sha256(run1_bytes).hexdigest()
    hash2 = hashlib.sha256(run2_bytes).hexdigest()

    assert hash1 == hash2, "Audio render is not byte-identical across runs"
    assert run1_bytes == run2_bytes
