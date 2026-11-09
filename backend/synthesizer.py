"""
The Earth Jukebox - Backend Audio Synthesis Engine (WAV Generation).

This module translates structured sonification events into master audio files (.wav),
mirroring the multi-layered acoustic techniques pioneered by the NASA Chandra X-ray Center
(Arcand, Russo, Santaguida et al.):

1. Continuous Diffuse Layer:
   Synthesized using scipy.signal (sine, sawtooth, triangle, and warm blended pads)
   to render large-scale background emissions (such as cloud bands, nebulae, and
   atmospheric temperature gradients) as continuous, sustained ambient drones.

2. Discrete Point Source Layer:
   Loaded using pydub from pre-recorded, physically motivated acoustic samples
   stored in assets/samples/ (e.g., "crackle" for ice fracture/sparks, "whoosh" for wind/gusts,
   "pluck" for localized hotspots/stars, "ping" for resonant beacons).
   Pitch modulation is achieved via playback rate shifting (resampling), preserving
   the physical acoustic timbre while transposing to the target musical pitch.

3. Stereo Staging & Parameter Mixing:
   Mixes continuous diffuse and discrete point source tracks based on exact event timing,
   musical pitch, velocity/amplitude, and equal-power stereo panning [-1.0, 1.0].

4. Master WAV Export:
   Exports broadcast-quality 16-bit PCM stereo WAV files using soundfile, complete with
   headroom management and dynamic range normalization.

5. JSON Timeline Export:
   Provides rich timeline blueprints for web frontends (e.g. Tone.js / p5.js).
"""

from dataclasses import dataclass, field
import io
import json
import logging
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from pydub import AudioSegment
import scipy.signal
import soundfile as sf

logger = logging.getLogger(__name__)

# Standard project paths
MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parent
DEFAULT_SAMPLES_DIR = PROJECT_ROOT / "assets" / "samples"

# Audio constants
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_DIFFUSE_WAVEFORM = "blend"
SUPPORTED_WAVEFORMS = ("sine", "sawtooth", "triangle", "square", "blend", "pad")

# Standard physical sample mappings & aliases
SAMPLE_ALIASES: Dict[str, str] = {
    # Ice / crackle / fracture
    "crackle": "crackle.wav",
    "ice": "crackle.wav",
    "ice_crackle": "crackle.wav",
    "fracture": "crackle.wav",
    "sparks": "crackle.wav",
    "fire": "crackle.wav",
    "spark": "crackle.wav",
    # Wind / atmospheric / whoosh
    "whoosh": "whoosh.wav",
    "wind": "whoosh.wav",
    "wind_whoosh": "whoosh.wav",
    "gust": "whoosh.wav",
    "air": "whoosh.wav",
    "storm": "whoosh.wav",
    "cyclone": "whoosh.wav",
    # Pluck / celestial hotspot / star / harp
    "pluck": "pluck.wav",
    "point_source_pluck": "pluck.wav",
    "hotspot": "pluck.wav",
    "star": "pluck.wav",
    "harp": "pluck.wav",
    "string": "pluck.wav",
    # Chime / ping / beacon / bell
    "ping": "ping.wav",
    "bell": "ping.wav",
    "chime": "ping.wav",
    "beacon": "ping.wav",
    "sonar": "ping.wav",
}

# Base fundamental pitch frequency (in Hz) for pre-recorded physical samples
SAMPLE_BASE_FREQUENCIES: Dict[str, float] = {
    "crackle.wav": 440.0,
    "ice_crackle.wav": 440.0,
    "whoosh.wav": 440.0,
    "wind_whoosh.wav": 440.0,
    "pluck.wav": 440.0,      # A4
    "ping.wav": 880.0,       # A5
}


class SynthesizerError(Exception):
    """Base exception for audio synthesis and file export errors."""
    pass


class SampleNotFoundError(SynthesizerError):
    """Raised when an audio sample cannot be located or loaded."""
    pass


@dataclass
class SynthesisResult:
    """Rich container holding audio synthesis results and metadata."""
    output_path: Optional[str] = None
    mixed_audio: Optional[np.ndarray] = None
    diffuse_track: Optional[np.ndarray] = None
    point_source_track: Optional[np.ndarray] = None
    sample_rate: int = DEFAULT_SAMPLE_RATE
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return str(self.output_path) if self.output_path is not None else ""

    def __fspath__(self) -> str:
        if self.output_path is None:
            raise TypeError("output_path is None, cannot be used as a filesystem path.")
        return str(self.output_path)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result summary to dictionary."""
        return {
            "output_path": self.output_path,
            "sample_rate": self.sample_rate,
            "duration_seconds": self.duration_seconds,
            "has_mixed_audio": self.mixed_audio is not None,
            "audio_shape": list(self.mixed_audio.shape) if self.mixed_audio is not None else None,
            "metadata": self.metadata,
        }


# =============================================================================
# Physical Sample Generation (Acoustic & Procedural Models)
# =============================================================================

def generate_default_samples(
    samples_dir: Optional[Union[str, Path]] = None,
    overwrite: bool = False,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> Dict[str, Path]:
    """
    Generate broadcast-quality, physically motivated audio samples in assets/samples/.

    Synthesizes:
    1. crackle.wav & ice_crackle.wav:
       Thermal ice fracture / Poisson micro-transients with resonant bandpass filtering.
    2. whoosh.wav & wind_whoosh.wav:
       Atmospheric wind gust with smooth envelope and dynamic swept bandpass resonance.
    3. pluck.wav:
       Resonant acoustic string / celestial hotspot pluck with multi-harmonic exponential decay.
    4. ping.wav:
       Inharmonic metallic chime / optical hotspot beacon.

    Args:
        samples_dir: Destination directory (defaults to assets/samples/).
        overwrite: If True, regenerates existing files.
        sample_rate: Sample rate in Hz (default: 44100).

    Returns:
        Dict[str, Path]: Mapping of sample filenames to their absolute file paths.
    """
    out_dir = Path(samples_dir) if samples_dir is not None else DEFAULT_SAMPLES_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    generated: Dict[str, Path] = {}

    # 1. Crackle (Ice crackle / micro-fracture bursts)
    crackle_path = out_dir / "crackle.wav"
    ice_path = out_dir / "ice_crackle.wav"
    if overwrite or not crackle_path.exists() or not ice_path.exists():
        dur = 0.5
        n = int(sample_rate * dur)
        raw = np.zeros(n, dtype=np.float32)
        rng = np.random.RandomState(42)
        num_clicks = 40
        for _ in range(num_clicks):
            pos = rng.randint(0, max(1, n - 250))
            burst_len = min(220, n - pos)
            t_b = np.linspace(0, burst_len / sample_rate, burst_len, endpoint=False)
            freq = rng.uniform(1800.0, 5200.0)
            decay = rng.uniform(900.0, 1600.0)
            burst = np.sin(2.0 * np.pi * freq * t_b) * np.exp(-t_b * decay)
            raw[pos : pos + burst_len] += (burst * rng.uniform(0.3, 1.0)).astype(np.float32)

        nyquist = sample_rate / 2.0
        b, a = scipy.signal.butter(2, [1200.0 / nyquist, min(0.95, 7500.0 / nyquist)], btype="band")
        crackle = scipy.signal.lfilter(b, a, raw).astype(np.float32)
        peak = np.max(np.abs(crackle))
        if peak > 0:
            crackle = (crackle / peak) * 0.85

        stereo_crackle = np.column_stack([crackle, crackle])
        sf.write(str(crackle_path), stereo_crackle, sample_rate, subtype="PCM_16")
        sf.write(str(ice_path), stereo_crackle, sample_rate, subtype="PCM_16")
        logger.info("Generated default physical sample: %s", crackle_path)

    generated["crackle.wav"] = crackle_path
    generated["ice_crackle.wav"] = ice_path

    # 2. Whoosh (Wind whoosh / atmospheric gust)
    whoosh_path = out_dir / "whoosh.wav"
    wind_path = out_dir / "wind_whoosh.wav"
    if overwrite or not whoosh_path.exists() or not wind_path.exists():
        dur_w = 0.7
        n_w = int(sample_rate * dur_w)
        t_w = np.linspace(0, dur_w, n_w, endpoint=False)
        rng_w = np.random.RandomState(101)
        noise = rng_w.normal(0, 1, n_w).astype(np.float32)
        envelope = (np.sin(np.pi * t_w / dur_w) ** 2).astype(np.float32)

        nyquist = sample_rate / 2.0
        b, a = scipy.signal.butter(2, [280.0 / nyquist, min(0.95, 1700.0 / nyquist)], btype="band")
        filtered = scipy.signal.lfilter(b, a, noise).astype(np.float32)
        whoosh = filtered * envelope
        peak = np.max(np.abs(whoosh))
        if peak > 0:
            whoosh = (whoosh / peak) * 0.85

        stereo_whoosh = np.column_stack([whoosh, whoosh])
        sf.write(str(whoosh_path), stereo_whoosh, sample_rate, subtype="PCM_16")
        sf.write(str(wind_path), stereo_whoosh, sample_rate, subtype="PCM_16")
        logger.info("Generated default physical sample: %s", whoosh_path)

    generated["whoosh.wav"] = whoosh_path
    generated["wind_whoosh.wav"] = wind_path

    # 3. Pluck (Acoustic string / celestial hotspot pluck, base 440 Hz = A4)
    pluck_path = out_dir / "pluck.wav"
    if overwrite or not pluck_path.exists():
        dur_p = 0.45
        n_p = int(sample_rate * dur_p)
        t_p = np.linspace(0, dur_p, n_p, endpoint=False)
        f0 = 440.0
        pluck = (
            0.60 * np.sin(2.0 * np.pi * f0 * 1.0 * t_p) * np.exp(-t_p * 14.0)
            + 0.30 * np.sin(2.0 * np.pi * f0 * 2.0 * t_p) * np.exp(-t_p * 24.0)
            + 0.15 * np.sin(2.0 * np.pi * f0 * 3.0 * t_p) * np.exp(-t_p * 38.0)
            + 0.08 * np.sin(2.0 * np.pi * f0 * 4.0 * t_p) * np.exp(-t_p * 58.0)
        ).astype(np.float32)
        peak = np.max(np.abs(pluck))
        if peak > 0:
            pluck = (pluck / peak) * 0.85

        stereo_pluck = np.column_stack([pluck, pluck])
        sf.write(str(pluck_path), stereo_pluck, sample_rate, subtype="PCM_16")
        logger.info("Generated default physical sample: %s", pluck_path)

    generated["pluck.wav"] = pluck_path

    # 4. Ping (Inharmonic metallic bell / beacon, base 880 Hz = A5)
    ping_path = out_dir / "ping.wav"
    if overwrite or not ping_path.exists():
        dur_ping = 0.35
        n_ping = int(sample_rate * dur_ping)
        t_ping = np.linspace(0, dur_ping, n_ping, endpoint=False)
        f_ping = 880.0
        ping = (
            0.70 * np.sin(2.0 * np.pi * f_ping * 1.000 * t_ping) * np.exp(-t_ping * 12.0)
            + 0.35 * np.sin(2.0 * np.pi * f_ping * 2.756 * t_ping) * np.exp(-t_ping * 20.0)
            + 0.15 * np.sin(2.0 * np.pi * f_ping * 5.404 * t_ping) * np.exp(-t_ping * 36.0)
        ).astype(np.float32)
        peak = np.max(np.abs(ping))
        if peak > 0:
            ping = (ping / peak) * 0.85

        stereo_ping = np.column_stack([ping, ping])
        sf.write(str(ping_path), stereo_ping, sample_rate, subtype="PCM_16")
        logger.info("Generated default physical sample: %s", ping_path)

    generated["ping.wav"] = ping_path

    return generated


# =============================================================================
# Sample Manager & Caching
# =============================================================================

class SampleManager:
    """
    Manages loading, caching, alias resolution, and retrieval of pre-recorded
    physical audio samples using pydub.
    """

    def __init__(self, samples_dir: Optional[Union[str, Path]] = None) -> None:
        self.samples_dir = Path(samples_dir) if samples_dir is not None else DEFAULT_SAMPLES_DIR
        self._cache: Dict[str, AudioSegment] = {}
        self._ensure_samples_available()

    def _ensure_samples_available(self) -> None:
        """Ensure standard physical sample directory and default files exist."""
        if not self.samples_dir.exists() or not any(self.samples_dir.glob("*.wav")):
            try:
                generate_default_samples(self.samples_dir, overwrite=False)
            except Exception as exc:
                logger.warning("Could not auto-generate default samples in %s: %exc", self.samples_dir, exc)

    def resolve_sample_path(self, identifier: Union[str, Path]) -> Optional[Path]:
        """
        Resolve a sample identifier or filename to a concrete file Path.
        Checks exact paths, filenames, aliases, and case-insensitive matches.
        """
        # 1. Direct path check
        p = Path(identifier)
        if p.is_file():
            return p.resolve()

        # Check inside self.samples_dir directly
        candidate = self.samples_dir / identifier
        if candidate.is_file():
            return candidate.resolve()

        # With .wav extension
        candidate_wav = self.samples_dir / f"{identifier}.wav"
        if candidate_wav.is_file():
            return candidate_wav.resolve()

        # 2. Alias resolution
        key = str(identifier).strip().lower().replace("-", "_").replace(" ", "_")
        if key in SAMPLE_ALIASES:
            alias_target = self.samples_dir / SAMPLE_ALIASES[key]
            if alias_target.is_file():
                return alias_target.resolve()

        # 3. Substring / keyword matching
        if self.samples_dir.is_dir():
            for f in self.samples_dir.iterdir():
                stem = f.stem.lower()
                if key == stem or key in stem or stem in key:
                    return f.resolve()

        return None

    def get_sample(
        self,
        identifier: Union[str, Path] = "pluck",
        sample_rate: int = DEFAULT_SAMPLE_RATE,
    ) -> AudioSegment:
        """
        Retrieve and cache an AudioSegment for the given sample identifier.
        Converts to stereo and resamples to target sample rate.
        """
        cache_key = f"{identifier}_{sample_rate}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        resolved_path = self.resolve_sample_path(identifier)

        if resolved_path is None or not resolved_path.is_file():
            # If standard sample missing, generate defaults and retry
            generate_default_samples(self.samples_dir, overwrite=False)
            resolved_path = self.resolve_sample_path(identifier)

        if resolved_path is None or not resolved_path.is_file():
            # Fallback to pluck.wav or crackle.wav
            for fallback in ("pluck.wav", "crackle.wav", "whoosh.wav"):
                fb_path = self.samples_dir / fallback
                if fb_path.is_file():
                    resolved_path = fb_path
                    logger.warning(
                        "Sample '%s' not found; falling back to '%s'",
                        identifier,
                        fallback,
                    )
                    break

        if resolved_path is None or not resolved_path.is_file():
            raise SampleNotFoundError(
                f"Audio sample '{identifier}' could not be located in {self.samples_dir}."
            )

        try:
            with open(resolved_path, "rb") as fh:
                segment = AudioSegment.from_file(io.BytesIO(fh.read()), format=resolved_path.suffix.lstrip(".").lower() or "wav")
        except Exception as exc:
            raise SynthesizerError(f"Failed to load audio sample from {resolved_path}: {exc}") from exc

        # Ensure target sample rate and stereo channels
        if segment.frame_rate != sample_rate:
            segment = segment.set_frame_rate(sample_rate)
        if segment.channels == 1:
            segment = segment.set_channels(2)

        self._cache[cache_key] = segment
        return segment

    def get_base_frequency(self, identifier: Union[str, Path]) -> float:
        """Return reference fundamental frequency (Hz) for a sample."""
        resolved = self.resolve_sample_path(identifier)
        if resolved is not None and resolved.name in SAMPLE_BASE_FREQUENCIES:
            return SAMPLE_BASE_FREQUENCIES[resolved.name]

        key = str(identifier).strip().lower()
        for alias, fn in SAMPLE_ALIASES.items():
            if alias in key and fn in SAMPLE_BASE_FREQUENCIES:
                return SAMPLE_BASE_FREQUENCIES[fn]

        return 440.0  # Default A4


# Global default sample manager instance
_DEFAULT_SAMPLE_MANAGER: Optional[SampleManager] = None


def get_default_sample_manager() -> SampleManager:
    """Return singleton instance of default SampleManager."""
    global _DEFAULT_SAMPLE_MANAGER
    if _DEFAULT_SAMPLE_MANAGER is None:
        _DEFAULT_SAMPLE_MANAGER = SampleManager()
    return _DEFAULT_SAMPLE_MANAGER


# =============================================================================
# Waveform Generation via scipy.signal (Continuous Diffuse Layer)
# =============================================================================

def generate_waveform(
    waveform_type: str,
    frequency: float,
    duration: float,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    phase: float = 0.0,
    apply_envelope: bool = True,
    fade_ratio: float = 0.15,
) -> np.ndarray:
    """
    Generate basic acoustic waveforms (sine, sawtooth, triangle, square, blend)
    using scipy.signal for the continuous diffuse layer.

    Args:
        waveform_type: Waveform geometry:
            - 'sine': Pure sinusoidal wave.
            - 'sawtooth': Ramp sawtooth generated via scipy.signal.sawtooth.
            - 'triangle': Symmetric triangle wave via scipy.signal.sawtooth(width=0.5).
            - 'square': Pulse wave generated via scipy.signal.square.
            - 'blend' / 'pad': Rich hybrid combining fundamental sine with warm sawtooth harmonics.
        frequency: Fundamental pitch frequency in Hz (must be > 0).
        duration: Slice duration in seconds (must be >= 0).
        sample_rate: Audio sampling rate in Hz (default: 44100).
        phase: Initial phase offset in radians.
        apply_envelope: If True, applies smooth Tukey window to prevent edge clicks.
        fade_ratio: Envelope ramp ratio (0.0 to 0.5).

    Returns:
        np.ndarray: 1D float32 array of synthesized audio samples.
    """
    if duration <= 0:
        return np.zeros(0, dtype=np.float32)

    n_samples = int(round(sample_rate * duration))
    if n_samples <= 0:
        return np.zeros(0, dtype=np.float32)

    freq = max(10.0, min(float(frequency), sample_rate * 0.45))
    t = np.linspace(0.0, duration, n_samples, endpoint=False)
    wt = 2.0 * np.pi * freq * t + phase

    wtype = str(waveform_type).lower().strip().replace("-", "_")

    if wtype in ("sine", "sin"):
        wave = np.sin(wt)
    elif wtype in ("sawtooth", "saw"):
        wave = scipy.signal.sawtooth(wt, width=1.0)
    elif wtype in ("triangle", "tri"):
        wave = scipy.signal.sawtooth(wt, width=0.5)
    elif wtype in ("square", "pulse"):
        wave = scipy.signal.square(wt, duty=0.5)
    elif wtype in ("blend", "hybrid", "pad", "diffuse", "diffuse_pad"):
        # Warm analog hybrid pad: prominent fundamental sine + gentle sawtooth overtones
        sine_comp = np.sin(wt)
        saw_comp = scipy.signal.sawtooth(wt, width=1.0)
        wave = 0.65 * sine_comp + 0.35 * saw_comp
    else:
        logger.warning("Unrecognized waveform '%s'; falling back to 'blend'.", waveform_type)
        wave = 0.65 * np.sin(wt) + 0.35 * scipy.signal.sawtooth(wt, width=1.0)

    wave = wave.astype(np.float32)

    # Smooth attack/decay window using scipy.signal.windows.tukey
    if apply_envelope and len(wave) > 0:
        alpha = min(0.5, max(0.02, 2.0 * fade_ratio))
        window = scipy.signal.windows.tukey(len(wave), alpha=alpha).astype(np.float32)
        wave = wave * window

    return wave


def synthesize_diffuse_track(
    diffuse_events: Sequence[Dict[str, Any]],
    total_duration: float,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    waveform: str = DEFAULT_DIFFUSE_WAVEFORM,
    lowpass_cutoff: Optional[float] = 7500.0,
    **kwargs: Any,
) -> np.ndarray:
    """
    Synthesize the continuous diffuse emission layer as a stereo NumPy array.
    Uses scipy.signal to generate sustained waveforms with equal-power stereo panning.

    Args:
        diffuse_events: List of diffuse event dictionaries.
        total_duration: Total audio duration in seconds.
        sample_rate: Audio sampling rate in Hz (default: 44100).
        waveform: Waveform type ('sine', 'sawtooth', 'triangle', 'square', 'blend').
        lowpass_cutoff: Optional cutoff frequency for warming Butterworth lowpass filter.

    Returns:
        np.ndarray: Stereo audio array of shape (N, 2), dtype float32.
    """
    total_samples = int(math.ceil(total_duration * sample_rate))
    if total_samples <= 0:
        total_samples = int(sample_rate * 1.0)

    left_channel = np.zeros(total_samples, dtype=np.float32)
    right_channel = np.zeros(total_samples, dtype=np.float32)

    if not diffuse_events:
        return np.column_stack([left_channel, right_channel])

    for ev in diffuse_events:
        # Time & duration
        t_sec = float(ev.get("time", ev.get("time_ms", 0.0) / 1000.0))
        dur_sec = float(ev.get("duration", ev.get("duration_ms", 100.0) / 1000.0))

        if dur_sec <= 0 or t_sec >= total_duration:
            continue

        freq = float(ev.get("frequency", ev.get("pitch", 220.0)))
        amp = float(ev.get("amplitude", ev.get("velocity", 0.5)))
        pan = float(np.clip(ev.get("pan", 0.0), -1.0, 1.0))
        wave_type = ev.get("waveform", waveform)

        if amp <= 1e-4:
            continue

        # Generate waveform via scipy.signal
        wave = generate_waveform(
            waveform_type=wave_type,
            frequency=freq,
            duration=dur_sec,
            sample_rate=sample_rate,
            apply_envelope=True,
        )

        n_slice = len(wave)
        if n_slice == 0:
            continue

        start_idx = int(round(t_sec * sample_rate))
        end_idx = min(total_samples, start_idx + n_slice)
        if start_idx >= total_samples or end_idx <= start_idx:
            continue

        valid_slice = wave[: end_idx - start_idx] * amp

        # Equal-power stereo panning
        pan_angle = (pan + 1.0) * (np.pi / 4.0)  # Maps [-1, 1] -> [0, pi/2]
        gain_left = float(np.cos(pan_angle))
        gain_right = float(np.sin(pan_angle))

        left_channel[start_idx:end_idx] += valid_slice * gain_left
        right_channel[start_idx:end_idx] += valid_slice * gain_right

    # Optional lowpass smoothing to produce warm cosmic background pads
    if lowpass_cutoff is not None and lowpass_cutoff < (sample_rate / 2.0):
        try:
            nyquist = sample_rate / 2.0
            norm_cutoff = min(0.95, max(0.01, lowpass_cutoff / nyquist))
            b, a = scipy.signal.butter(2, norm_cutoff, btype="low")
            left_channel = scipy.signal.lfilter(b, a, left_channel).astype(np.float32)
            right_channel = scipy.signal.lfilter(b, a, right_channel).astype(np.float32)
        except Exception as exc:
            logger.debug("Lowpass filter skipped: %s", exc)

    return np.column_stack([left_channel, right_channel])


# =============================================================================
# Point Source Layer Synthesis via pydub (Physical Sample Playback)
# =============================================================================

def pitch_shift_segment(
    segment: AudioSegment,
    ratio: float,
    target_sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> AudioSegment:
    """
    Transpose an AudioSegment using playback rate shifting (resampling).
    Changes playback speed and pitch simultaneously, preserving authentic physical
    sample acoustic resonance.

    Args:
        segment: Input pydub AudioSegment.
        ratio: Frequency pitch shift ratio (e.g., 2.0 = 1 octave up, 0.5 = 1 octave down).
        target_sample_rate: Desired destination sample rate in Hz.

    Returns:
        AudioSegment: Pitch-shifted and resampled AudioSegment.
    """
    if abs(ratio - 1.0) < 1e-4:
        if segment.frame_rate != target_sample_rate:
            return segment.set_frame_rate(target_sample_rate)
        return segment

    # Constrain ratio to 3 octaves down / up
    clamped_ratio = max(0.125, min(8.0, float(ratio)))
    new_frame_rate = int(round(segment.frame_rate * clamped_ratio))
    new_frame_rate = max(1000, min(192000, new_frame_rate))

    # Shift frame rate in header, then resample to target_sample_rate
    shifted = segment._spawn(segment.raw_data, overrides={"frame_rate": new_frame_rate})
    return shifted.set_frame_rate(target_sample_rate)


def pydub_to_numpy(segment: AudioSegment) -> np.ndarray:
    """
    Convert a pydub AudioSegment into a normalized float32 NumPy stereo array in [-1.0, 1.0].
    """
    samples = np.array(segment.get_array_of_samples(), dtype=np.float32)
    if segment.channels == 2:
        samples = samples.reshape((-1, 2))
    elif segment.channels == 1:
        samples = np.column_stack([samples, samples])
    else:
        samples = samples.reshape((-1, segment.channels))[:, :2]

    # Normalize by bit-depth maximum
    max_val = float(1 << (8 * segment.sample_width - 1))
    return samples / max(1.0, max_val)


def resolve_point_source_sample_name(event: Dict[str, Any]) -> str:
    """
    Determine appropriate physical sample identifier from event metadata.
    Prioritizes explicit 'sample' / 'sample_name', then 'instrument' / 'instrumentId',
    then source metadata tags (e.g. ice, wind, fire).
    """
    for key in ("sample", "sample_name"):
        if key in event and event[key]:
            return str(event[key])

    for key in ("instrument", "instrumentId"):
        if key in event and event[key]:
            inst = str(event[key]).lower()
            if any(k in inst for k in ("crackle", "ice", "spark", "fracture")):
                return "crackle"
            if any(k in inst for k in ("whoosh", "wind", "gust", "storm")):
                return "whoosh"
            if any(k in inst for k in ("ping", "bell", "chime", "beacon")):
                return "ping"
            if any(k in inst for k in ("pluck", "hotspot", "star", "point")):
                return "pluck"
            return inst

    # Check source_metadata if present
    src_meta = event.get("source_metadata")
    if isinstance(src_meta, dict):
        for k in ("tag", "feature_type", "type", "category", "label"):
            val = str(src_meta.get(k, "")).lower()
            if any(w in val for w in ("ice", "crackle", "cold", "fracture")):
                return "crackle"
            if any(w in val for w in ("wind", "whoosh", "storm", "cyclone")):
                return "whoosh"
            if any(w in val for w in ("ping", "bell", "beacon")):
                return "ping"

    return "pluck"


def synthesize_point_sources_track(
    point_source_events: Sequence[Dict[str, Any]],
    total_duration: float,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    samples_dir: Optional[Union[str, Path]] = None,
    default_sample_name: Optional[str] = None,
    **kwargs: Any,
) -> np.ndarray:
    """
    Synthesize discrete point sources by loading pre-recorded physical samples via pydub,
    pitch-shifting via playback rate, scaling volume, and stereo-panning into a master track.

    Args:
        point_source_events: List of point source event dictionaries.
        total_duration: Total audio duration in seconds.
        sample_rate: Audio sampling rate in Hz (default: 44100).
        samples_dir: Directory containing audio samples (defaults to assets/samples/).
        default_sample_name: Optional default sample override.

    Returns:
        np.ndarray: Stereo audio array of shape (N, 2), dtype float32.
    """
    total_samples = int(math.ceil(total_duration * sample_rate))
    total_ms = int(math.ceil(total_duration * 1000.0))
    if total_ms <= 0:
        total_ms = 1000

    track = AudioSegment.silent(duration=total_ms, frame_rate=sample_rate).set_channels(2)

    if not point_source_events:
        return np.zeros((total_samples, 2), dtype=np.float32)

    manager = SampleManager(samples_dir=samples_dir)

    for ev in point_source_events:
        t_sec = float(ev.get("time", ev.get("time_ms", 0.0) / 1000.0))
        if t_sec < 0.0 or t_sec >= total_duration:
            continue

        sample_name = default_sample_name or resolve_point_source_sample_name(ev)

        try:
            sample_seg = manager.get_sample(sample_name, sample_rate=sample_rate)
        except Exception as exc:
            logger.warning("Failed to get sample '%s': %s", sample_name, exc)
            continue

        # Pitch shifting via playback rate
        base_freq = manager.get_base_frequency(sample_name)
        target_freq = float(ev.get("frequency", ev.get("pitch", base_freq)))
        ratio = target_freq / max(1.0, base_freq)

        pitched = pitch_shift_segment(sample_seg, ratio=ratio, target_sample_rate=sample_rate)

        # Volume / velocity gain in dB
        vel = float(np.clip(ev.get("velocity", ev.get("amplitude", 0.8)), 0.0, 1.0))
        if vel <= 1e-4:
            continue

        gain_db = 20.0 * np.log10(max(vel, 1e-4))
        gain_db = max(-60.0, min(6.0, gain_db))
        gained = pitched.apply_gain(gain_db)

        # Stereo pan [-1.0, 1.0]
        pan_val = float(np.clip(ev.get("pan", 0.0), -1.0, 1.0))
        panned = gained.pan(pan_val)

        # Duration trimming with gentle fade-out
        dur_sec = ev.get("duration")
        if dur_sec is None and "duration_ms" in ev:
            dur_sec = ev["duration_ms"] / 1000.0
        if dur_sec is not None and dur_sec > 0:
            dur_ms = int(round(dur_sec * 1000.0))
            if 0 < dur_ms < len(panned):
                fade_ms = min(25, max(2, dur_ms // 4))
                panned = panned[:dur_ms].fade_out(fade_ms)

        pos_ms = max(0, int(round(t_sec * 1000.0)))
        track = track.overlay(panned, position=pos_ms)

    arr = pydub_to_numpy(track)

    # Pad or slice to match exact total_samples
    if arr.shape[0] < total_samples:
        arr = np.pad(arr, ((0, total_samples - arr.shape[0]), (0, 0)))
    elif arr.shape[0] > total_samples:
        arr = arr[:total_samples]

    return arr.astype(np.float32)


# =============================================================================
# Track Mixing & Headroom Management
# =============================================================================

def mix_tracks(
    diffuse_track: np.ndarray,
    point_source_track: np.ndarray,
    diffuse_gain: float = 0.70,
    point_source_gain: float = 0.80,
    master_gain: float = 1.0,
    normalize: bool = True,
    target_peak: float = 0.95,
) -> np.ndarray:
    """
    Combine continuous diffuse and discrete point source tracks into a single stereo master.

    Args:
        diffuse_track: 2D array of diffuse audio (N, 2).
        point_source_track: 2D array of point source audio (M, 2).
        diffuse_gain: Linear scaling factor for diffuse layer.
        point_source_gain: Linear scaling factor for point source layer.
        master_gain: Overall master volume gain.
        normalize: If True, scales mix peak to target_peak to maximize loudness without clipping.
        target_peak: Target peak amplitude in [0.0, 1.0] when normalize=True (default: 0.95).

    Returns:
        np.ndarray: Stereo float32 array in [-1.0, 1.0].
    """
    len_d = diffuse_track.shape[0] if diffuse_track is not None else 0
    len_p = point_source_track.shape[0] if point_source_track is not None else 0
    max_len = max(len_d, len_p)

    if max_len == 0:
        return np.zeros((DEFAULT_SAMPLE_RATE, 2), dtype=np.float32)

    # Align lengths by zero-padding
    if len_d < max_len:
        diffuse_track = np.pad(diffuse_track, ((0, max_len - len_d), (0, 0)))
    if len_p < max_len:
        point_source_track = np.pad(point_source_track, ((0, max_len - len_p), (0, 0)))

    mixed = (diffuse_gain * diffuse_track + point_source_gain * point_source_track) * master_gain
    mixed = mixed.astype(np.float32)

    peak = float(np.max(np.abs(mixed))) if mixed.size > 0 else 0.0

    if normalize and peak > 1e-5:
        mixed = mixed * (target_peak / peak)
    elif peak > 1.0:
        # Soft-knee tanh limiting if clipping without explicit normalization
        mixed = np.tanh(mixed).astype(np.float32)

    return np.clip(mixed, -1.0, 1.0)


# =============================================================================
# Primary Public API: synthesize_wav
# =============================================================================

def synthesize_wav(
    audio_events: Any,
    output_path: Optional[Union[str, Path, io.IOBase]] = None,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    diffuse_waveform: str = DEFAULT_DIFFUSE_WAVEFORM,
    diffuse_gain: float = 0.70,
    point_source_gain: float = 0.80,
    master_gain: float = 1.0,
    normalize: bool = True,
    target_peak: float = 0.95,
    samples_dir: Optional[Union[str, Path]] = None,
    duration: Optional[float] = None,
    subtype: str = "PCM_16",
    return_details: bool = False,
    **kwargs: Any,
) -> Union[str, Path, SynthesisResult, np.ndarray]:
    """
    Synthesize complete sonification audio by combining synthesized continuous waveforms
    (via scipy.signal) and pre-recorded physical samples (via pydub), exporting
    to a broadcast-quality .wav file using soundfile.

    Pipeline Steps:
    1. Parse and partition audio_events into diffuse and point source streams.
    2. Synthesize the continuous diffuse layer using scipy.signal (sine, sawtooth, pad).
    3. Load physical samples from assets/samples/ (crackle, whoosh, pluck) using pydub,
       modulate pitch via playback rate shifting, and stage stereo panning.
    4. Mix both stems with gain staging and peak normalization.
    5. Export the final mixed stereo audio as a .wav file via soundfile.

    Args:
        audio_events: Sequence of event dicts, an AudioEventList instance, or a dictionary
                      containing 'diffuse_events' and 'point_source_events'.
        output_path: Optional destination .wav file path (str, Path) or file-like buffer.
        sample_rate: Audio sample rate in Hz (default: 44100).
        diffuse_waveform: Continuous layer waveform ('sine', 'sawtooth', 'triangle', 'blend').
        diffuse_gain: Level scaling for the continuous diffuse layer (default: 0.70).
        point_source_gain: Level scaling for discrete point sources (default: 0.80).
        master_gain: Master bus volume scaling (default: 1.0).
        normalize: Whether to normalize master output to target_peak (default: True).
        target_peak: Peak amplitude ceiling when normalizing (default: 0.95).
        samples_dir: Directory containing physical samples (defaults to assets/samples/).
        duration: Optional total audio duration override in seconds.
        subtype: Soundfile encoding subtype ('PCM_16', 'PCM_24', 'FLOAT').
        return_details: If True, returns a SynthesisResult instance.
        **kwargs: Additional parameters forwarded to track synthesis.

    Returns:
        Union[str, Path, SynthesisResult, np.ndarray]:
            - If output_path is provided: returns output_path (or SynthesisResult if return_details=True).
            - If output_path is None: returns SynthesisResult if return_details=True,
              or the mixed audio NumPy array.

    Raises:
        SynthesizerError: If audio synthesis or file writing fails.
    """
    # 1. Parse and partition events
    diffuse_events: List[Dict[str, Any]] = []
    point_source_events: List[Dict[str, Any]] = []
    all_events: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}

    if hasattr(audio_events, "diffuse_events") and hasattr(audio_events, "point_source_events"):
        diffuse_events = list(audio_events.diffuse_events)
        point_source_events = list(audio_events.point_source_events)
        all_events = list(audio_events)
        metadata = dict(getattr(audio_events, "metadata", {}))
    elif isinstance(audio_events, dict):
        diffuse_events = list(audio_events.get("diffuse_events", []))
        point_source_events = list(audio_events.get("point_source_events", []))
        all_events = list(audio_events.get("events", diffuse_events + point_source_events))
        metadata = dict(audio_events.get("metadata", {}))
    elif isinstance(audio_events, (list, tuple)):
        all_events = list(audio_events)
        for ev in all_events:
            if not isinstance(ev, dict):
                continue
            layer = str(ev.get("layer", "")).lower()
            inst = str(ev.get("instrument", ev.get("instrumentId", ""))).lower()
            if layer == "diffuse" or "pad" in inst or "diffuse" in inst:
                diffuse_events.append(ev)
            elif layer == "point_source" or any(k in inst for k in ("crackle", "whoosh", "pluck", "ping", "pluck")):
                point_source_events.append(ev)
            elif "sample" in ev or "sample_name" in ev:
                point_source_events.append(ev)
            else:
                # Default to diffuse for continuous events, point source otherwise
                diffuse_events.append(ev)
    elif audio_events is None:
        all_events = []
    else:
        raise TypeError(
            f"audio_events must be a list, dict, or AudioEventList, got {type(audio_events).__name__}."
        )

    # 2. Determine total sonification duration
    if duration is not None and duration > 0:
        total_duration = float(duration)
    elif "duration_seconds" in metadata and metadata["duration_seconds"] > 0:
        total_duration = float(metadata["duration_seconds"])
    else:
        calc_max = 0.0
        for ev in all_events:
            t = float(ev.get("time", ev.get("time_ms", 0.0) / 1000.0))
            d = float(ev.get("duration", ev.get("duration_ms", 0.0) / 1000.0))
            calc_max = max(calc_max, t + d)
        total_duration = max(calc_max, 1.0) if calc_max > 0 else 1.0

    # 3. Synthesize continuous diffuse layer via scipy.signal
    diffuse_track = synthesize_diffuse_track(
        diffuse_events=diffuse_events,
        total_duration=total_duration,
        sample_rate=sample_rate,
        waveform=diffuse_waveform,
        **kwargs,
    )

    # 4. Synthesize point sources via pydub
    point_track = synthesize_point_sources_track(
        point_source_events=point_source_events,
        total_duration=total_duration,
        sample_rate=sample_rate,
        samples_dir=samples_dir,
        **kwargs,
    )

    # 5. Mix stems with headroom management
    mixed = mix_tracks(
        diffuse_track=diffuse_track,
        point_source_track=point_track,
        diffuse_gain=diffuse_gain,
        point_source_gain=point_source_gain,
        master_gain=master_gain,
        normalize=normalize,
        target_peak=target_peak,
    )

    # 6. Export WAV using soundfile
    out_target: Optional[Union[str, Path, io.IOBase]] = None
    if output_path is not None:
        if isinstance(output_path, (str, Path)):
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            try:
                sf.write(str(out_p), mixed, sample_rate, subtype=subtype)
            except Exception as exc:
                raise SynthesizerError(f"soundfile failed to write WAV to {out_p}: {exc}") from exc
            out_target = str(out_p)
            logger.info("Exported synthesized WAV to %s", out_target)
        elif hasattr(output_path, "write"):
            # File-like stream
            try:
                sf.write(output_path, mixed, sample_rate, format="WAV", subtype=subtype)
            except Exception as exc:
                raise SynthesizerError(f"soundfile failed to write WAV to stream: {exc}") from exc
            out_target = output_path
        else:
            raise TypeError(f"Unsupported output_path type: {type(output_path).__name__}")

    metadata["total_duration"] = total_duration
    metadata["sample_rate"] = sample_rate
    metadata["diffuse_waveform"] = diffuse_waveform
    metadata["num_diffuse_events"] = len(diffuse_events)
    metadata["num_point_source_events"] = len(point_source_events)

    result = SynthesisResult(
        output_path=str(out_target) if isinstance(out_target, (str, Path)) else None,
        mixed_audio=mixed,
        diffuse_track=diffuse_track,
        point_source_track=point_track,
        sample_rate=sample_rate,
        duration_seconds=total_duration,
        metadata=metadata,
    )

    if return_details:
        return result

    if output_path is not None:
        return str(output_path) if isinstance(output_path, (str, Path)) else output_path

    return mixed


# =============================================================================
# JSON Timeline Blueprint Export (Tone.js / Frontend Extensibility)
# =============================================================================

def export_json_timeline(
    audio_events: Any,
    metadata: Optional[Dict[str, Any]] = None,
    output_path: Optional[Union[str, Path]] = None,
    tuning_system: str = "12-EDO",
    scale_name: Optional[str] = None,
    scan_geometry: Optional[str] = None,
    indent: int = 2,
) -> Dict[str, Any]:
    """
    Export a rich JSON timeline blueprint for frontend sonification renderers (Tone.js, Web Audio).

    Structure:
    - metadata: Global parameters (scaleName, tuningSystem, scanGeometry, durationMs).
    - events: Ordered event list, each with:
        - time: Timestamp in milliseconds.
        - duration: Duration in milliseconds.
        - pitch: Pitch in Hz or MIDI note number.
        - velocity: Normalized volume in [0.0, 1.0].
        - pan: Stereo pan in [-1.0, 1.0].
        - instrumentId: Instrument or physical sample identifier.
        - spatialPosition: Optional (x, y) coordinates on canvas.

    Args:
        audio_events: Sequence of event dictionaries or an AudioEventList instance.
        metadata: Optional global metadata dictionary.
        output_path: Optional destination .json file path.
        tuning_system: Musical tuning system (default: '12-EDO').
        scale_name: Name of scale (e.g. 'c_major_pentatonic').
        scan_geometry: Playhead scan geometry (e.g. 'horizontal_sweep').
        indent: JSON indentation formatting.

    Returns:
        Dict[str, Any]: Formatted JSON blueprint dictionary.
    """
    events_raw: List[Dict[str, Any]] = []
    meta_src: Dict[str, Any] = {}

    if hasattr(audio_events, "metadata"):
        meta_src = dict(getattr(audio_events, "metadata", {}))
        events_raw = list(audio_events)
    elif isinstance(audio_events, dict):
        meta_src = dict(audio_events.get("metadata", {}))
        events_raw = list(audio_events.get("events", []))
    elif isinstance(audio_events, (list, tuple)):
        events_raw = list(audio_events)

    if metadata is not None:
        meta_src.update(metadata)

    resolved_scale = scale_name or meta_src.get("scale_name", meta_src.get("scaleName", "c_major_pentatonic"))
    resolved_geometry = scan_geometry or meta_src.get("geometry_type", meta_src.get("scanGeometry", "horizontal_sweep"))
    resolved_tuning = meta_src.get("tuningSystem", tuning_system)

    formatted_events: List[Dict[str, Any]] = []
    max_time_ms = 0.0

    for ev in events_raw:
        if not isinstance(ev, dict):
            continue

        t_ms = float(ev.get("time_ms", ev.get("time", 0.0) * 1000.0))
        d_ms = float(ev.get("duration_ms", ev.get("duration", 0.1) * 1000.0))
        pitch_val = float(ev.get("pitch", ev.get("frequency", ev.get("midi_note", 440.0))))
        vel_val = float(np.clip(ev.get("velocity", ev.get("amplitude", 0.8)), 0.0, 1.0))
        pan_val = float(np.clip(ev.get("pan", 0.0), -1.0, 1.0))
        inst_id = str(ev.get("instrumentId", ev.get("instrument", "default")))

        entry: Dict[str, Any] = {
            "time": round(t_ms, 2),
            "duration": round(d_ms, 2),
            "pitch": round(pitch_val, 2),
            "velocity": round(vel_val, 4),
            "pan": round(pan_val, 4),
            "instrumentId": inst_id,
        }

        if "spatialPosition" in ev and isinstance(ev["spatialPosition"], dict):
            entry["spatialPosition"] = {
                "x": round(float(ev["spatialPosition"].get("x", 0.0)), 2),
                "y": round(float(ev["spatialPosition"].get("y", 0.0)), 2),
            }
        elif "x" in ev and "y" in ev:
            entry["spatialPosition"] = {
                "x": round(float(ev["x"]), 2),
                "y": round(float(ev["y"]), 2),
            }

        if "layer" in ev:
            entry["layer"] = ev["layer"]

        formatted_events.append(entry)
        max_time_ms = max(max_time_ms, t_ms + d_ms)

    formatted_events.sort(key=lambda e: e["time"])

    dur_seconds = float(meta_src.get("duration_seconds", max_time_ms / 1000.0))

    blueprint: Dict[str, Any] = {
        "metadata": {
            "scaleName": resolved_scale,
            "tuningSystem": resolved_tuning,
            "scanGeometry": resolved_geometry,
            "durationSeconds": dur_seconds,
            "durationMs": round(dur_seconds * 1000.0, 2),
            "totalEvents": len(formatted_events),
            **{k: v for k, v in meta_src.items() if k not in ("scale_name", "scaleName", "geometry_type", "scanGeometry", "tuningSystem")},
        },
        "events": formatted_events,
    }

    if output_path is not None:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(blueprint, indent=indent), encoding="utf-8")
        logger.info("Exported JSON timeline blueprint to %s", out_p)

    return blueprint


# Ensure default physical samples are present upon module initialization
try:
    generate_default_samples(overwrite=False)
except Exception as _init_exc:
    logger.debug("Automatic initial sample generation skipped: %s", _init_exc)
