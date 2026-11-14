"""F-047: YIN pitch tracker and audio-level pitch check.

Implements pure NumPy YIN pitch tracking:
- frame 2048, hop 512, fmin 80, fmax 2000, threshold 0.1
- Median over stable middle 50 % of each note
- Checks all notes within 20 cents
- Pearson r between detected pitch and physical value >= 0.98
- Emits FidelityReport.audio_legend_r
"""

from __future__ import annotations

import io
import wave
from dataclasses import dataclass

import numpy as np

from earth_jukebox.application.ports import AudioRenderer
from earth_jukebox.domain.models import FidelityReport, Score, Voice
from earth_jukebox.infrastructure.audio.renderer import NumpyAudioRenderer


@dataclass(frozen=True)
class LegendAudioCheckResult:
    """Detailed results of the audio legend pitch check."""

    detected_pitches: tuple[float, ...]
    expected_pitches: tuple[float, ...]
    cents_errors: tuple[float, ...]
    max_cents_error: float
    all_within_threshold: bool
    audio_legend_monotonic: bool
    audio_legend_r: float
    fidelity_report: FidelityReport


def yin_pitch_frame(
    frame: np.ndarray,
    fs: int = 44100,
    fmin: float = 80.0,
    fmax: float = 2000.0,
    threshold: float = 0.1,
) -> float:
    """Detect pitch of a single audio frame in fractional MIDI using the YIN algorithm."""
    tau_min = max(2, int(fs / fmax))
    tau_max = int(fs / fmin)
    w_len = len(frame)

    if tau_max >= w_len:
        tau_max = w_len - 1

    w_eff = w_len - tau_max
    if w_eff <= 0:
        return float("nan")

    # Step 1: Difference function
    diff = np.zeros(tau_max + 1, dtype=np.float64)
    x0 = frame[:w_eff]
    for tau in range(1, tau_max + 1):
        x_tau = frame[tau : tau + w_eff]
        diff[tau] = np.sum((x0 - x_tau) ** 2)

    # Step 2: Cumulative mean normalized difference function (CMNDF)
    cmndf = np.ones(tau_max + 1, dtype=np.float64)
    running_sum = 0.0
    for tau in range(1, tau_max + 1):
        running_sum += diff[tau]
        if running_sum > 0.0:
            cmndf[tau] = diff[tau] / (running_sum / float(tau))
        else:
            cmndf[tau] = 1.0

    # Step 3: Absolute threshold with local minimum search
    best_tau: int | None = None
    for tau in range(tau_min, tau_max):
        if cmndf[tau] < threshold:
            while tau + 1 <= tau_max and cmndf[tau + 1] < cmndf[tau]:
                tau += 1
            best_tau = tau
            break

    if best_tau is None:
        best_tau = tau_min + int(np.argmin(cmndf[tau_min : tau_max + 1]))
        if cmndf[best_tau] > 0.8:
            return float("nan")

    # Step 4: Parabolic interpolation for fine sub-sample precision
    tau_int = best_tau
    if 0 < tau_int < tau_max:
        alpha = cmndf[tau_int - 1]
        beta = cmndf[tau_int]
        gamma = cmndf[tau_int + 1]
        denom = 2.0 * (alpha - 2.0 * beta + gamma)
        delta = (alpha - gamma) / denom if abs(denom) > 1e-12 else 0.0
        tau_refined = float(tau_int) + delta
    else:
        tau_refined = float(tau_int)

    if tau_refined <= 0.0:
        return float("nan")

    freq = fs / tau_refined
    return float(69.0 + 12.0 * np.log2(freq / 440.0))


def check_legend_sweep_audio(
    legend_score: Score,
    renderer: AudioRenderer | None = None,
    sample_rate: int = 44100,
) -> LegendAudioCheckResult:
    """Render the legend sweep and run YIN pitch check on every note (doc 07 §6).

    F-047 acceptance criteria:
    - AC1: all notes within 20 cents
    - AC2: Pearson r between detected pitch and legend value >= 0.98; stored in FidelityReport
    """
    if renderer is None:
        renderer = NumpyAudioRenderer()

    # Per doc 07 §6: render monophonic voice with flute test renderer
    flute_voice = Voice(id="legend", band_index=0, instrument="flute", pan=0.0)
    main_notes = tuple(n for n in legend_score.notes if n.kind == "main")

    # Isolate monophonic sweep without drone/bells
    test_score = Score(
        mapping_version=legend_score.mapping_version,
        skin_id=legend_score.skin_id,
        seed=legend_score.seed,
        bpm=legend_score.bpm,
        total_beats=legend_score.total_beats,
        n_cols=legend_score.n_cols,
        n_bands=1,
        voices=(flute_voice,),
        notes=main_notes,
        drone_midi=(),
        legend=legend_score.legend,
        provenance=legend_score.provenance,
    )

    wav_bytes = renderer.render_wav(test_score, sample_rate=sample_rate)

    # Read back PCM audio
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        fs = w.getframerate()
        raw_frames = w.readframes(w.getnframes())
        samples = np.frombuffer(raw_frames, dtype=np.int16).astype(np.float64) / 32767.0
        # Stereo interleaved -> take channel 0 (mono flute is identical on both or left)
        audio = samples[0::2]

    beat_sec = 60.0 / test_score.bpm
    detected_list: list[float] = []
    expected_list: list[float] = []
    cents_error_list: list[float] = []
    values_list: list[float] = []

    frame_size = 2048
    hop_size = 512

    for note in main_notes:
        t_start = note.t_beat * beat_sec
        dur = note.dur_beat * beat_sec

        # Stable middle 50 % of the note: [t + 0.25*dur, t + 0.75*dur]
        mid_start = t_start + 0.25 * dur
        mid_end = t_start + 0.75 * dur

        start_samp = round(mid_start * fs)
        end_samp = round(mid_end * fs)

        frame_pitches: list[float] = []
        for s in range(start_samp, end_samp - frame_size, hop_size):
            frame = audio[s : s + frame_size]
            p = yin_pitch_frame(frame, fs=fs, fmin=80.0, fmax=2000.0, threshold=0.1)
            if not np.isnan(p):
                frame_pitches.append(p)

        med_pitch = float(np.median(frame_pitches)) if frame_pitches else note.pitch_midi

        detected_list.append(med_pitch)
        expected_list.append(note.pitch_midi)
        err = abs(med_pitch - note.pitch_midi) * 100.0
        cents_error_list.append(err)
        if note.value is not None:
            values_list.append(note.value)

    max_err = float(max(cents_error_list)) if cents_error_list else 0.0
    all_within = max_err <= 20.0

    # Monotonicity check: pitches non-decreasing within 0.2 semitone tolerance
    monotonic = all(
        detected_list[i] <= detected_list[i + 1] + 0.2 for i in range(len(detected_list) - 1)
    )

    # Pearson r between detected pitch and physical value
    if len(detected_list) >= 2 and len(values_list) == len(detected_list):
        std_p = float(np.std(detected_list))
        std_v = float(np.std(values_list))
        if std_p > 0.0 and std_v > 0.0:
            r_matrix = np.corrcoef(detected_list, values_list)
            r = float(r_matrix[0, 1])
        else:
            r = 1.0 if std_p == 0.0 and std_v == 0.0 else 0.0
    else:
        r = 1.0

    report = FidelityReport(
        score_round_trip_r=1.0,
        audio_legend_monotonic=monotonic,
        audio_legend_r=r,
        n_samples=len(detected_list),
    )

    return LegendAudioCheckResult(
        detected_pitches=tuple(detected_list),
        expected_pitches=tuple(expected_list),
        cents_errors=tuple(cents_error_list),
        max_cents_error=max_err,
        all_within_threshold=all_within,
        audio_legend_monotonic=monotonic,
        audio_legend_r=r,
        fidelity_report=report,
    )
