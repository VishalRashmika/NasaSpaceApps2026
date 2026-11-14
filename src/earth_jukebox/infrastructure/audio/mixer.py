"""F-041: Audio mixer, equal-power pan, and soft limiter.

Rules (docs/07 §4):
- seconds = t_beat * 60 / bpm
- Equal-power pan: L = g * cos((pan + 1) * pi / 4), R = g * sin((pan + 1) * pi / 4)
- Drone: sine+triangle pair at drone_midi, gain 0.05, brightness scales low-pass 400-1200 Hz
- Sum all voices in float64
- Fade-in 50 ms, fade-out 500 ms
- Soft limiter: tanh(x / 0.89) * 0.89 (guarantees peak <= 0.89 / -1 dBFS)
- Reserve a tail of 1.5 s after note ends for decays
"""

from __future__ import annotations

import contextlib
from typing import cast

import numpy as np
import scipy.signal

from earth_jukebox.domain.models import Score, Voice
from earth_jukebox.infrastructure.audio.synth import note_seed, render_note


def _parse_brightness_list(brightness_str: str | None) -> list[float]:
    """Parse comma-separated band brightness floats from provenance."""
    if not brightness_str:
        return []
    result = []
    for part in brightness_str.split(","):
        with contextlib.suppress(ValueError):
            result.append(float(part.strip()))
    return result


def _render_drone(
    drone_midi: tuple[float, ...],
    n_samples: int,
    brightness: float,
    sample_rate: int,
) -> np.ndarray:
    """Render drone bed: sine+triangle pair at drone_midi, gain 0.05, low-pass 400-1200 Hz."""
    if not drone_midi or n_samples <= 0:
        return np.zeros(n_samples, dtype=np.float64)

    fs = float(sample_rate)
    t = np.arange(n_samples) / fs
    drone_sum = np.zeros(n_samples, dtype=np.float64)

    for midi in drone_midi:
        freq = 440.0 * (2.0 ** ((midi - 69.0) / 12.0))
        phi = 2.0 * np.pi * freq * t
        sine_wave = np.sin(phi)
        saw = 2.0 * ((phi / (2.0 * np.pi)) - np.floor(phi / (2.0 * np.pi) + 0.5))
        tri_wave = 2.0 * np.abs(saw) - 1.0
        drone_sum += 0.5 * (sine_wave + tri_wave)

    drone_sum = (drone_sum / float(len(drone_midi))) * 0.05

    # Filter with low-pass 400-1200 Hz scaled by brightness
    b_clamped = float(np.clip(brightness, 0.0, 1.0))
    cutoff = np.clip(400.0 + 800.0 * b_clamped, 50.0, 0.45 * fs)
    sos = scipy.signal.butter(2, cutoff, btype="low", fs=sample_rate, output="sos")
    filtered = scipy.signal.sosfilt(sos, drone_sum)
    return cast(np.ndarray, filtered)


def mix_score(score: Score, sample_rate: int = 44100) -> np.ndarray:
    """Mix Score notes and drone into a stereo (2, n_samples) float64 audio buffer.

    F-041 acceptance criteria:
    - AC1: peak <= 0.89 (-1 dBFS) for a dense 5-voice score
    - AC2: a hard-left voice has right-channel RMS <= 1 % of left
    """
    bpm = max(1.0, score.bpm)
    beat_sec = 60.0 / bpm

    # Calculate track length: total_beats + 1.5 s tail (docs/07 §4.6 and F-042 AC1)
    total_sec = (score.total_beats * beat_sec) + 1.5
    n_samples = round(total_sec * sample_rate)

    left = np.zeros(n_samples, dtype=np.float64)
    right = np.zeros(n_samples, dtype=np.float64)

    # Voice lookup
    voice_map: dict[str, Voice] = {v.id: v for v in score.voices}

    # Band brightness lookup from score provenance
    band_brightness_list = _parse_brightness_list(score.provenance.get("band_brightness"))

    # Render each note
    for idx, note in enumerate(score.notes):
        voice = voice_map.get(note.voice_id)
        instrument = voice.instrument if voice else "pad"
        pan = voice.pan if voice else 0.0

        dur_sec = note.dur_beat * beat_sec
        t_sec = note.t_beat * beat_sec

        # Determine band brightness
        b_val = 1.0
        if 0 <= note.band < len(band_brightness_list):
            b_val = band_brightness_list[note.band]

        seed = note_seed(score.seed, note.col, note.band, idx)
        note_audio = render_note(
            instrument=instrument,
            pitch_midi=note.pitch_midi,
            dur_sec=dur_sec,
            velocity=note.velocity,
            glide_to_midi=note.glide_to_midi,
            roughness=note.roughness,
            accent=note.accent,
            band_brightness=b_val,
            seed=seed,
            sample_rate=sample_rate,
        )

        # Equal-power pan (doc 07 §4.4)
        pan_clamped = float(np.clip(pan, -1.0, 1.0))
        theta = (pan_clamped + 1.0) * (np.pi / 4.0)
        pan_l = float(np.cos(theta))
        pan_r = float(np.sin(theta))

        start_idx = round(t_sec * sample_rate)
        end_idx = min(n_samples, start_idx + len(note_audio))
        chunk_len = max(0, end_idx - start_idx)

        if chunk_len > 0:
            left[start_idx : start_idx + chunk_len] += pan_l * note_audio[:chunk_len]
            right[start_idx : start_idx + chunk_len] += pan_r * note_audio[:chunk_len]

    # Drone bed
    if score.drone_midi:
        drone_bright_str = score.provenance.get("drone_brightness", "0.5")
        try:
            drone_b = float(drone_bright_str)
        except ValueError:
            drone_b = 0.5

        drone_mono = _render_drone(
            score.drone_midi,
            n_samples=n_samples,
            brightness=drone_b,
            sample_rate=sample_rate,
        )
        # Pan centre for drone: pan=0 -> cos(pi/4)=sin(pi/4)=sqrt(2)/2
        drone_pan = float(np.cos(np.pi / 4.0))
        left += drone_pan * drone_mono
        right += drone_pan * drone_mono

    # Fade-in 50 ms and fade-out 500 ms (doc 07 §4.6)
    n_fade_in = min(n_samples, round(0.05 * sample_rate))
    n_fade_out = min(n_samples, round(0.5 * sample_rate))

    if n_fade_in > 0:
        ramp_in = np.linspace(0.0, 1.0, n_fade_in, endpoint=True)
        left[:n_fade_in] *= ramp_in
        right[:n_fade_in] *= ramp_in

    if n_fade_out > 0:
        ramp_out = np.linspace(1.0, 0.0, n_fade_out, endpoint=True)
        left[-n_fade_out:] *= ramp_out
        right[-n_fade_out:] *= ramp_out

    # Soft limiter: tanh(x / 0.89) * 0.89 (doc 07 §4.6)
    left_limited = np.tanh(left / 0.89) * 0.89
    right_limited = np.tanh(right / 0.89) * 0.89

    return np.stack([left_limited, right_limited], axis=0)
