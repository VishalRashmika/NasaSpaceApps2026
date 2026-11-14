"""F-040: NumPy synth voices.

Implements the 8 closed instrument families:
- pad: 3 detuned saws (+-7 cents), lowpass 1.2 kHz * b, ADSR (0.4 / 0.3 / 0.7 / 0.8 s)
- pluck: Karplus-Strong string (deterministic seeded noise burst), damping by b; decay approx dur
- bell: additive partials at ratios 1, 2.76, 5.4, 8.93, exp decay (2 s), velocity scales brightness
- flute: sine + 2nd/3rd harm (0.3/0.1) + breath (-30 dB), 5.5 Hz vibrato 8 ct after 0.15 s
- strings: 4 detuned saws, band-limited, slow attack 0.25 s, low-pass 2.5 kHz * b, ensemble chorus
- sub: sine + 2nd harmonic, mono, slow attack
- texture: band-passed noise centred at note frequency; roughness widens the band
- percussion: skin pattern hits: membrane = decaying sine pitch-dropping 180->90 Hz + noise burst
"""

from __future__ import annotations

from typing import cast

import numpy as np
import scipy.signal

INSTRUMENT_FAMILIES: tuple[str, ...] = (
    "pad",
    "pluck",
    "bell",
    "flute",
    "strings",
    "sub",
    "texture",
    "percussion",
)


def note_seed(score_seed: int, col: int, band: int, note_index: int) -> int:
    """Deterministic integer hash for note RNG (FNV-1a variant, not Python's hash())."""
    h = 2166136261
    for val in (col & 0xFFFF, (band + 32768) & 0xFFFF, note_index & 0xFFFF):
        h = ((h ^ val) * 16777619) & 0xFFFFFFFF
    return (score_seed ^ h) & 0x7FFFFFFF


def midi_to_hz(midi: float) -> float:
    """Convert fractional MIDI note number to frequency in Hz."""
    return float(440.0 * (2.0 ** ((midi - 69.0) / 12.0)))


def _adsr_envelope(
    n_active: int,
    n_release: int,
    attack_s: float,
    decay_s: float,
    sustain_lvl: float,
    fs: int,
) -> np.ndarray:
    """Compute an ADSR envelope array in float64."""
    n_total = n_active + n_release
    if n_total <= 0:
        return np.zeros(0, dtype=np.float64)

    env = np.zeros(n_total, dtype=np.float64)
    n_a = round(attack_s * fs)
    n_d = round(decay_s * fs)

    for i in range(n_active):
        if n_a > 0 and i < n_a:
            env[i] = i / float(n_a)
        elif n_d > 0 and i < n_a + n_d:
            alpha = (i - n_a) / float(n_d)
            env[i] = 1.0 - (1.0 - sustain_lvl) * alpha
        else:
            env[i] = sustain_lvl

    s_end = env[n_active - 1] if n_active > 0 else sustain_lvl
    if n_release > 0:
        rel_curve = np.linspace(s_end, 0.0, n_release, endpoint=False)
        env[n_active:] = rel_curve

    return env


def _pitch_trajectory(
    pitch_midi: float,
    glide_to_midi: float | None,
    dur_sec: float,
    total_sec: float,
    fs: int,
) -> np.ndarray:
    """Compute instantaneous MIDI pitch over total_sec, handling linear cents glide."""
    n_total = round(total_sec * fs)
    p = np.full(n_total, pitch_midi, dtype=np.float64)

    if glide_to_midi is not None and dur_sec > 0.0:
        glide_start = 0.3 * dur_sec
        glide_dur = 0.7 * dur_sec
        t = np.arange(n_total) / float(fs)
        mask = (t >= glide_start) & (t <= dur_sec)
        if np.any(mask) and glide_dur > 0.0:
            alpha = (t[mask] - glide_start) / glide_dur
            p[mask] = pitch_midi + alpha * (glide_to_midi - pitch_midi)
        p[t > dur_sec] = glide_to_midi

    return p


def _sawtooth(phi: np.ndarray) -> np.ndarray:
    """Generate band-like saw wave from unwrapped phase in radians."""
    phase_norm = phi / (2.0 * np.pi)
    return 2.0 * (phase_norm - np.floor(phase_norm + 0.5))


def render_note(
    instrument: str,
    pitch_midi: float,
    dur_sec: float,
    velocity: float,
    glide_to_midi: float | None,
    roughness: float,
    accent: bool,
    band_brightness: float,
    seed: int,
    sample_rate: int = 44100,
) -> np.ndarray:
    """Render a single NoteEvent into a 1D float64 numpy audio array.

    F-040 acceptance criteria:
    - AC1: single A4 note -> spectral peak within 5 cents of 440 Hz
    - AC2: no clipping; no NaN/inf
    - AC3: all families render note >= 0.5 s without error
    """
    if instrument not in INSTRUMENT_FAMILIES:
        raise ValueError(
            f"Unknown instrument family '{instrument}'. Must be one of {INSTRUMENT_FAMILIES}"
        )

    fs = sample_rate
    dur = max(0.01, dur_sec)
    b = max(0.1, band_brightness)
    r = np.clip(roughness, 0.0, 1.0)
    vel = np.clip(velocity, 0.0, 1.0)
    # Velocity gain curve from doc 07 §4.3
    gain = (vel**1.5) * 0.25

    rng = np.random.default_rng(seed)

    if instrument == "pad":
        rel_s = 0.8
        total_sec = dur + rel_s
        n_total = round(total_sec * fs)
        n_active = round(dur * fs)
        n_release = n_total - n_active

        # 3 detuned saws (+-7 cents + r * 12 cents detune spread)
        spread = 7.0 + r * 12.0
        cents_offsets = (-spread, 0.0, spread)
        weights = (0.25, 0.5, 0.25)

        p_traj = _pitch_trajectory(pitch_midi, glide_to_midi, dur, total_sec, fs)
        raw_pad = np.zeros(n_total, dtype=np.float64)

        for c_off, w in zip(cents_offsets, weights, strict=True):
            f_traj = 440.0 * (2.0 ** ((p_traj + c_off - 69.0) / 12.0))
            phi = 2.0 * np.pi * np.cumsum(f_traj) / float(fs)
            raw_pad += w * _sawtooth(phi)

        cutoff = np.clip(1200.0 * b * (1.0 + r), 80.0, 0.45 * fs)
        sos = scipy.signal.butter(2, cutoff, btype="low", fs=fs, output="sos")
        filtered_pad = scipy.signal.sosfilt(sos, raw_pad)

        env = _adsr_envelope(n_active, n_release, 0.4, 0.3, 0.7, fs)
        return cast(np.ndarray, gain * env * filtered_pad)

    elif instrument == "pluck":
        # Extended Karplus-Strong string synthesis with fractional allpass delay
        f0 = midi_to_hz(pitch_midi)
        rel_s = 0.5
        total_sec = dur + rel_s
        n_total = round(total_sec * fs)

        loop_delay = fs / max(20.0, f0)
        delay_needed = loop_delay - 0.5
        n_int = max(2, int(np.floor(delay_needed)))
        d_frac = delay_needed - n_int
        allpass_c = (1.0 - d_frac) / (1.0 + d_frac) if d_frac > 1e-4 else 0.0

        noise_len = max(2, round(loop_delay))
        noise_burst = rng.uniform(-1.0, 1.0, noise_len)
        noise_burst -= np.mean(noise_burst)
        # Apply smooth Hann on the noise burst to prevent harsh edge
        noise_burst *= np.hanning(noise_len)
        noise_burst -= np.mean(noise_burst)

        out = np.zeros(n_total, dtype=np.float64)
        out[: min(noise_len, n_total)] = noise_burst[: min(noise_len, n_total)]

        decay_target = dur
        rho = np.exp(-3.0 / max(0.1, f0 * decay_target)) * min(1.0, 0.998 * (b**0.1))
        rho = float(np.clip(rho, 0.85, 0.998))

        v_prev = 0.0
        w_prev = 0.0
        for n in range(noise_len, n_total):
            idx_1 = n - n_int
            idx_2 = n - n_int - 1
            sample_1 = out[idx_1] if idx_1 >= 0 else 0.0
            sample_2 = out[idx_2] if idx_2 >= 0 else 0.0
            v = 0.5 * rho * (sample_1 + sample_2)
            w = allpass_c * v + v_prev - allpass_c * w_prev
            v_prev = v
            w_prev = w
            out[n] = w

        return cast(np.ndarray, gain * out)

    elif instrument == "bell":
        # Additive partials at ratios 1, 2.76, 5.4, 8.93, exp decay (2s)
        total_sec = max(dur, 2.0)
        n_total = round(total_sec * fs)
        t = np.arange(n_total) / float(fs)

        p_traj = _pitch_trajectory(pitch_midi, glide_to_midi, dur, total_sec, fs)
        f_traj = 440.0 * (2.0 ** ((p_traj - 69.0) / 12.0))
        phi_base = 2.0 * np.pi * np.cumsum(f_traj) / float(fs)

        ratios = (1.0, 2.76, 5.4, 8.93)
        base_amps = (1.0, 0.55 * (0.5 + 0.5 * vel), 0.35 * (0.3 + 0.7 * vel), 0.2 * vel)
        taus = (2.0, 1.5, 1.0, 0.7)

        bell_sig = np.zeros(n_total, dtype=np.float64)
        sum_amp = 0.0
        for ratio, amp, tau in zip(ratios, base_amps, taus, strict=True):
            freq_partial = ratio * f_traj
            if (freq_partial < 0.45 * fs).any():
                scaled_amp = amp * (1.0 + r if ratio > 1.0 else 1.0)
                sum_amp += scaled_amp
                bell_sig += scaled_amp * np.sin(ratio * phi_base) * np.exp(-t / tau)

        if sum_amp > 0:
            bell_sig /= sum_amp

        return cast(np.ndarray, gain * bell_sig)

    elif instrument == "flute":
        # Sine + 2nd/3rd harm (0.3/0.1) + breath (-30 dB), 5.5 Hz vibrato 8 ct after 0.15 s
        rel_s = 0.1
        total_sec = dur + rel_s
        n_total = round(total_sec * fs)
        n_active = round(dur * fs)
        n_release = n_total - n_active
        t = np.arange(n_total) / float(fs)

        p_traj = _pitch_trajectory(pitch_midi, glide_to_midi, dur, total_sec, fs)

        # Vibrato after 0.15s: 5.5 Hz depth 8 cents
        vibrato_ramp = np.clip((t - 0.15) / 0.1, 0.0, 1.0)
        vibrato_cents = 8.0 * vibrato_ramp * np.sin(2.0 * np.pi * 5.5 * np.maximum(0.0, t - 0.15))
        p_total = p_traj + vibrato_cents / 100.0

        f_total = 440.0 * (2.0 ** ((p_total - 69.0) / 12.0))
        phi = 2.0 * np.pi * np.cumsum(f_total) / float(fs)

        harm1 = np.sin(phi)
        harm2 = 0.3 * np.sin(2.0 * phi)
        harm3 = 0.1 * np.sin(3.0 * phi)
        flute_tone = (harm1 + harm2 + harm3) / 1.4

        # Breath noise (-30 dB relative to signal)
        noise_raw = rng.standard_normal(n_total)
        f_mid = midi_to_hz(pitch_midi)
        bp_low = np.clip(f_mid * 0.7, 50.0, 0.4 * fs)
        bp_high = np.clip(f_mid * 1.4, bp_low + 20.0, 0.45 * fs)
        sos_noise = scipy.signal.butter(2, [bp_low, bp_high], btype="bandpass", fs=fs, output="sos")
        breath = scipy.signal.sosfilt(sos_noise, noise_raw)
        # -30 dB factor = 0.0316
        breath_gain = 0.0316 * (1.0 + r)
        combined = flute_tone + breath_gain * breath

        env = _adsr_envelope(n_active, n_release, 0.08, 0.05, 0.9, fs)
        return cast(np.ndarray, gain * env * combined)

    elif instrument == "strings":
        # 4 detuned saws, band-limited, slow attack 0.25 s, low-pass 2.5 kHz * b, ensemble chorus
        rel_s = 0.3
        total_sec = dur + rel_s
        n_total = round(total_sec * fs)
        n_active = round(dur * fs)
        n_release = n_total - n_active

        spread = 8.0 + r * 12.0
        str_offsets = (-spread, 0.0, 0.0, spread)
        str_weights = (0.2, 0.3, 0.3, 0.2)

        p_traj = _pitch_trajectory(pitch_midi, glide_to_midi, dur, total_sec, fs)
        strings_sig = np.zeros(n_total, dtype=np.float64)

        for off, w in zip(str_offsets, str_weights, strict=True):
            f_traj = 440.0 * (2.0 ** ((p_traj + off - 69.0) / 12.0))
            phi = 2.0 * np.pi * np.cumsum(f_traj) / float(fs)
            strings_sig += w * _sawtooth(phi)

        cutoff = np.clip(2500.0 * b * (1.0 + r), 100.0, 0.45 * fs)
        sos = scipy.signal.butter(2, cutoff, btype="low", fs=fs, output="sos")
        filtered_strings = scipy.signal.sosfilt(sos, strings_sig)

        # Ensemble chorus (2 delayed copies at ~12ms and ~19ms)
        d1 = round(0.012 * fs)
        d2 = round(0.019 * fs)
        chorus = np.copy(filtered_strings)
        if d1 < n_total:
            chorus[d1:] += 0.15 * filtered_strings[:-d1]
        if d2 < n_total:
            chorus[d2:] += 0.15 * filtered_strings[:-d2]
        chorus /= 1.3

        env = _adsr_envelope(n_active, n_release, 0.25, 0.2, 0.85, fs)
        return cast(np.ndarray, gain * env * chorus)

    elif instrument == "sub":
        # Sine + 2nd harmonic, mono, slow attack
        rel_s = 0.15
        total_sec = dur + rel_s
        n_total = round(total_sec * fs)
        n_active = round(dur * fs)
        n_release = n_total - n_active

        p_traj = _pitch_trajectory(pitch_midi, glide_to_midi, dur, total_sec, fs)
        f_traj = 440.0 * (2.0 ** ((p_traj - 69.0) / 12.0))
        phi = 2.0 * np.pi * np.cumsum(f_traj) / float(fs)

        sub_sig = (np.sin(phi) + 0.25 * np.sin(2.0 * phi)) / 1.25
        env = _adsr_envelope(n_active, n_release, 0.15, 0.1, 0.9, fs)
        return cast(np.ndarray, gain * env * sub_sig)

    elif instrument == "texture":
        # Band-passed noise centred at note frequency; roughness widens the band
        rel_s = 0.15
        total_sec = dur + rel_s
        n_total = round(total_sec * fs)
        n_active = round(dur * fs)
        n_release = n_total - n_active

        noise = rng.standard_normal(n_total)
        f_center = midi_to_hz(pitch_midi)
        bw = max(30.0, 0.2 * f_center * (1.0 + 3.0 * r))
        low = np.clip(f_center - 0.5 * bw, 40.0, 0.42 * fs)
        high = np.clip(f_center + 0.5 * bw, low + 10.0, 0.45 * fs)

        sos = scipy.signal.butter(2, [low, high], btype="bandpass", fs=fs, output="sos")
        filtered_noise = scipy.signal.sosfilt(sos, noise)

        env = _adsr_envelope(n_active, n_release, 0.1, 0.1, 0.8, fs)
        return cast(np.ndarray, gain * env * filtered_noise)

    elif instrument == "percussion":
        # Skin pattern hits: membrane = decaying sine pitch-dropping 180->90 Hz + noise burst
        total_sec = max(dur, 0.3)
        n_total = round(total_sec * fs)
        t = np.arange(n_total) / float(fs)

        # Pitch drop 180 -> 90 Hz
        f_drop = 90.0 + 90.0 * np.exp(-t / 0.03)
        phi_drop = 2.0 * np.pi * np.cumsum(f_drop) / float(fs)
        membrane = np.sin(phi_drop) * np.exp(-t / 0.12)

        # Noise burst
        noise = rng.standard_normal(n_total) * np.exp(-t / 0.02)
        noise_lvl = 0.25 + (0.35 if accent else 0.1) * vel
        hit = 0.75 * membrane + noise_lvl * noise

        return cast(np.ndarray, gain * hit)

    # Should not reach here
    return np.zeros(0, dtype=np.float64)
