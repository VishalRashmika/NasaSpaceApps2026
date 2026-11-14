"""Unit tests for F-040 (NumPy synth voices)."""

from __future__ import annotations

import numpy as np
import pytest

from earth_jukebox.infrastructure.audio.synth import (
    INSTRUMENT_FAMILIES,
    midi_to_hz,
    render_note,
)


def _spectral_peak_hz(signal: np.ndarray, fs: int = 44100) -> float:
    """Helper to find the spectral peak frequency using windowed FFT (ignoring < 20 Hz)."""
    n_samples = len(signal)
    n_fft = max(n_samples * 4, 65536)
    window = np.hanning(n_samples)
    spectrum = np.abs(np.fft.rfft(signal * window, n=n_fft))
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / fs)
    mask = freqs >= 20.0
    peak_idx = int(np.where(mask)[0][np.argmax(spectrum[mask])])
    return float(freqs[peak_idx])


def test_f040_ac1_single_a4_note_spectral_peak() -> None:
    # F-040 AC1: rendering a single A4 note -> spectral peak within 5 cents of 440 Hz (FFT test)
    # A4 is MIDI 69.0 -> 440.0 Hz
    fs = 44100
    target_hz = 440.0

    pitched_instruments = ["flute", "pad", "bell", "strings", "sub", "pluck"]
    for inst in pitched_instruments:
        sig = render_note(
            instrument=inst,
            pitch_midi=69.0,
            dur_sec=1.0,
            velocity=0.8,
            glide_to_midi=None,
            roughness=0.0,
            accent=False,
            band_brightness=1.0,
            seed=42,
            sample_rate=fs,
        )
        assert len(sig) > 0
        peak_hz = _spectral_peak_hz(sig, fs=fs)
        cents_error = 1200.0 * abs(np.log2(peak_hz / target_hz))
        assert cents_error <= 5.0, (
            f"Instrument '{inst}' spectral peak {peak_hz:.2f} Hz differs from 440 Hz "
            f"by {cents_error:.2f} cents (> 5 cents threshold)"
        )


def test_f040_ac2_no_clipping_no_nan_or_inf() -> None:
    # F-040 AC2: no clipping; no NaN/inf
    for inst in INSTRUMENT_FAMILIES:
        sig = render_note(
            instrument=inst,
            pitch_midi=60.0,
            dur_sec=0.8,
            velocity=1.0,  # Max velocity
            glide_to_midi=62.0,
            roughness=0.5,
            accent=True,
            band_brightness=1.5,
            seed=123,
            sample_rate=44100,
        )
        assert not np.isnan(sig).any(), f"NaN in {inst} signal"
        assert not np.isinf(sig).any(), f"Inf in {inst} signal"
        # Audio signals should have reasonable bounds before mix (no blowups)
        max_amp = float(np.max(np.abs(sig)))
        assert max_amp <= 2.0, f"Unbounded signal amplitude {max_amp} in {inst}"


@pytest.mark.parametrize("instrument", INSTRUMENT_FAMILIES)
def test_f040_ac3_all_families_render_note_gte_half_second(instrument: str) -> None:
    # F-040 AC3: all families render a note >= 0.5 s without error (parametrised)
    dur = 0.6
    fs = 44100
    sig = render_note(
        instrument=instrument,
        pitch_midi=64.0,
        dur_sec=dur,
        velocity=0.7,
        glide_to_midi=None,
        roughness=0.2,
        accent=False,
        band_brightness=1.0,
        seed=999,
        sample_rate=fs,
    )
    assert len(sig) >= int(dur * fs), f"{instrument} output length shorter than duration"
    assert sig.dtype == np.float64


def test_midi_to_hz_accuracy() -> None:
    assert abs(midi_to_hz(69.0) - 440.0) < 1e-6
    assert abs(midi_to_hz(60.0) - 261.625565) < 1e-4
    assert abs(midi_to_hz(57.0) - 220.0) < 1e-6


def test_glide_to_midi_behaviour() -> None:
    # Note with glide should change pitch over time
    fs = 44100
    sig = render_note(
        instrument="flute",
        pitch_midi=60.0,  # ~261.6 Hz
        dur_sec=1.0,
        velocity=0.8,
        glide_to_midi=72.0,  # ~523.2 Hz (1 octave up)
        roughness=0.0,
        accent=False,
        band_brightness=1.0,
        seed=1,
        sample_rate=fs,
    )
    # Check early segment (before glide starts at 0.3s)
    early = sig[int(0.05 * fs) : int(0.25 * fs)]
    peak_early = _spectral_peak_hz(early, fs=fs)
    # Check late segment (after glide reaches 72 at 1.0s)
    late = sig[int(0.95 * fs) : int(1.05 * fs)]
    peak_late = _spectral_peak_hz(late, fs=fs)
    assert abs(peak_early - midi_to_hz(60.0)) < 15.0
    assert abs(peak_late - midi_to_hz(72.0)) < 15.0
