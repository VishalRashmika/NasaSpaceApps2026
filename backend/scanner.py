"""
The Earth Jukebox - Scan Geometries Engine & Parameter Mapping.

This module translates 2D scientific visualizations into 1D time-domain audio streams,
mirroring the playhead geometries and perceptual sonification techniques pioneered by
the NASA Chandra X-ray Center sonification team (Arcand, Russo, Santaguida et al.).

Playhead Geometries:
--------------------
1. horizontal_sweep:
   Left-to-right Cartesian scanhead.
   - Time: progresses linearly with horizontal position X (t in [0, duration]).
   - Pitch: maps vertical position Y (top = high pitch, bottom = low pitch).
   - Stereo Pan: maps horizontal position X (-1.0 Left to +1.0 Right).
   - Best suited for: Panoramic Earth swaths, Galactic Plane, rectangular satellite imagery.

2. vertical_sweep:
   Top-to-bottom Cartesian scanhead.
   - Time: progresses linearly with vertical position Y (t in [0, duration]).
   - Pitch: maps vertical position Y as playhead descends.
   - Stereo Pan: maps horizontal position X across each row (-1.0 Left to +1.0 Right).
   - Best suited for: Atmospheric column profiles, vertical cross-sections, elevation maps.

3. radar_sweep:
   Clockwise polar ray rotating from the image center (12 o'clock).
   - Time: progresses linearly with sweep angle θ in [0, 2π].
   - Pitch: maps radial distance r from center (center = low pitch, outer perimeter = high pitch).
   - Stereo Pan: maps horizontal offset from center or sin(θ) (-1.0 Left to +1.0 Right).
   - Best suited for: Circular remnants, cyclone eyes, impact craters, rotationally symmetric structures.

4. radial_expansion:
   Concentric circular ripple expanding outward from the image center.
   - Time: progresses linearly with ripple radius r (Radius = time).
   - Stereo Pan: maps angular position around the ripple perimeter (-1.0 Left to +1.0 Right).
   - Pitch: RGB channels / spectral bands map to distinct pitch registers
     (Red = low register, Green = mid register, Blue = high register).
   - Best suited for: Shockwaves, blast ripples, explosion wavefronts, radial diffusion.
"""

from enum import Enum
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)


class ScanGeometry(str, Enum):
    """Supported scan playhead geometries."""
    HORIZONTAL_SWEEP = "horizontal_sweep"
    VERTICAL_SWEEP = "vertical_sweep"
    RADAR_SWEEP = "radar_sweep"
    RADIAL_EXPANSION = "radial_expansion"

    @classmethod
    def from_string(cls, name: Union[str, "ScanGeometry"]) -> "ScanGeometry":
        """
        Normalize and resolve a string or Enum to a ScanGeometry member.
        Supports case-insensitivity, whitespace, hyphens, and common aliases.
        """
        if isinstance(name, ScanGeometry):
            return name
        if not isinstance(name, str):
            raise TypeError(f"geometry_type must be a string or ScanGeometry, got {type(name).__name__}.")

        normalized = name.strip().lower().replace("-", "_").replace(" ", "_")

        # Map aliases
        aliases = {
            "horizontal": cls.HORIZONTAL_SWEEP,
            "horizontal_sweep": cls.HORIZONTAL_SWEEP,
            "h_sweep": cls.HORIZONTAL_SWEEP,
            "vertical": cls.VERTICAL_SWEEP,
            "vertical_sweep": cls.VERTICAL_SWEEP,
            "v_sweep": cls.VERTICAL_SWEEP,
            "radar": cls.RADAR_SWEEP,
            "radar_sweep": cls.RADAR_SWEEP,
            "polar": cls.RADAR_SWEEP,
            "radial": cls.RADIAL_EXPANSION,
            "radial_expansion": cls.RADIAL_EXPANSION,
            "ripple": cls.RADIAL_EXPANSION,
            "radial_ripple": cls.RADIAL_EXPANSION,
        }

        if normalized in aliases:
            return aliases[normalized]

        valid_names = [e.value for e in cls]
        raise ValueError(
            f"Unknown scan geometry: '{name}'. Supported geometries: {valid_names} "
            f"(aliases: {list(aliases.keys())})."
        )


# Predefined musical scale pitch classes (semitone intervals relative to root note C = 0)
MUSICAL_SCALES: Dict[str, List[int]] = {
    "c_major_pentatonic": [0, 2, 4, 7, 9],
    "major_pentatonic": [0, 2, 4, 7, 9],
    "pentatonic": [0, 2, 4, 7, 9],
    "c_pentatonic": [0, 2, 4, 7, 9],
    "minor_pentatonic": [0, 3, 5, 7, 10],
    "c_minor_pentatonic": [0, 3, 5, 7, 10],
    "major": [0, 2, 4, 5, 7, 9, 11],
    "c_major": [0, 2, 4, 5, 7, 9, 11],
    "natural_minor": [0, 2, 3, 5, 7, 8, 10],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "c_minor": [0, 2, 3, 5, 7, 8, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "melodic_minor": [0, 2, 3, 5, 7, 9, 11],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "chromatic": list(range(12)),
    "blues": [0, 3, 5, 6, 7, 10],
    "whole_tone": [0, 2, 4, 6, 8, 10],
    "hirajoshi": [0, 2, 3, 7, 8],
    "in_sen": [0, 1, 5, 7, 10],
    "pelog": [0, 1, 3, 7, 8],
    "slendro": [0, 2, 5, 7, 9],
}

# Chandra Multiwavelength / RGB Energy Band Pitch Registers (for radial_expansion)
DEFAULT_CHANNEL_REGISTERS: Dict[str, Dict[str, Any]] = {
    "red": {
        "band": "Low Energy / Infrared / Optical",
        "description": "Lowest frequency register (Bass / C3-C4)",
        "freq_range_hz": (130.81, 261.63),
        "midi_range": (48, 60),
        "base_midi": 48,
    },
    "green": {
        "band": "Medium Energy / Optical / Soft X-Ray",
        "description": "Mid frequency register (Tenor-Alto / C4-C5)",
        "freq_range_hz": (261.63, 523.25),
        "midi_range": (60, 72),
        "base_midi": 60,
    },
    "blue": {
        "band": "High Energy / Hard X-Ray",
        "description": "High frequency register (Soprano / C5-C6)",
        "freq_range_hz": (523.25, 1046.50),
        "midi_range": (72, 84),
        "base_midi": 72,
    },
}


class ScanHead:
    """
    Playhead coordinate generator for NASA Chandra-style sonification.

    Translates 2D visual coordinate space (width x height) into time-synchronized
    trajectory coordinates (x, y, time) for 4 physical symmetry geometries.
    """

    CHANNEL_REGISTERS = DEFAULT_CHANNEL_REGISTERS

    def __init__(
        self,
        geometry_type: Union[str, ScanGeometry] = ScanGeometry.HORIZONTAL_SWEEP,
        width: int = 512,
        height: int = 512,
        duration_seconds: float = 10.0,
        num_steps: Optional[int] = None,
        samples_per_step: Optional[int] = None,
        center: Optional[Tuple[float, float]] = None,
        radius_max: Optional[float] = None,
        clip_to_bounds: bool = True,
        pitch_top_high: bool = True,
        fps: Optional[float] = None,
        **kwargs: Any,
    ):
        """
        Initialize the ScanHead playhead.

        Args:
            geometry_type: Scan path geometry ('horizontal_sweep', 'vertical_sweep',
                           'radar_sweep', 'radial_expansion').
            width: Width of the image canvas in pixels (must be >= 1).
            height: Height of the image canvas in pixels (must be >= 1).
            duration_seconds: Sonification duration in seconds (must be > 0).
            num_steps: Optional number of discrete time steps. If None, derived from
                       fps, dimension, or optimal geometric resolution.
            samples_per_step: Optional number of spatial samples per time step.
            center: Optional (x, y) center for radar and radial expansion.
                    Defaults to ((width - 1) / 2.0, (height - 1) / 2.0).
            radius_max: Optional maximum radius for radar and radial expansion.
                        Defaults to min(width - 1, height - 1) / 2.0.
            clip_to_bounds: Whether to constrain sampled (x, y) coordinates to image bounds.
            pitch_top_high: If True, top of image (y=0) corresponds to highest pitch.
            fps: Optional frame rate to calculate num_steps = int(round(fps * duration_seconds)).
            **kwargs: Extra parameters reserved for extensibility.
        """
        self._validate_dimensions(width, height, duration_seconds)

        self.geometry_type = ScanGeometry.from_string(geometry_type)
        self.width = int(width)
        self.height = int(height)
        self.duration_seconds = float(duration_seconds)
        self.clip_to_bounds = bool(clip_to_bounds)
        self.pitch_top_high = bool(pitch_top_high)
        self.fps = float(fps) if fps is not None and fps > 0 else None

        # Resolve time steps
        if num_steps is not None:
            if num_steps < 1:
                raise ValueError("num_steps must be an integer >= 1.")
            self.num_steps = int(num_steps)
        elif self.fps is not None:
            self.num_steps = max(1, int(round(self.fps * self.duration_seconds)))
        else:
            self.num_steps = self._default_num_steps()

        # Resolve samples per step
        if samples_per_step is not None:
            if samples_per_step < 1:
                raise ValueError("samples_per_step must be an integer >= 1.")
            self.samples_per_step = int(samples_per_step)
        else:
            self.samples_per_step = self._default_samples_per_step()

        # Center coordinates
        if center is not None:
            if len(center) != 2:
                raise ValueError("center must be a sequence of 2 elements (x, y).")
            self.center = (float(center[0]), float(center[1]))
        else:
            self.center = ((self.width - 1) / 2.0, (self.height - 1) / 2.0)

        # Maximum radius
        if radius_max is not None:
            if radius_max <= 0:
                raise ValueError("radius_max must be positive.")
            self.radius_max = float(radius_max)
        else:
            self.radius_max = max(1.0, min(self.width - 1, self.height - 1) / 2.0)

        self.extra_kwargs = kwargs

    @staticmethod
    def _validate_dimensions(width: int, height: int, duration_seconds: float) -> None:
        """Validate canvas dimensions and duration."""
        if not isinstance(width, (int, np.integer)) or width <= 0:
            raise ValueError(f"width must be a positive integer, got {width}.")
        if not isinstance(height, (int, np.integer)) or height <= 0:
            raise ValueError(f"height must be a positive integer, got {height}.")
        if not isinstance(duration_seconds, (int, float, np.floating)) or duration_seconds <= 0:
            raise ValueError(f"duration_seconds must be a positive number, got {duration_seconds}.")

    def _default_num_steps(self) -> int:
        """Derive sensible default time steps per geometry."""
        if self.geometry_type == ScanGeometry.HORIZONTAL_SWEEP:
            return self.width
        elif self.geometry_type == ScanGeometry.VERTICAL_SWEEP:
            return self.height
        elif self.geometry_type == ScanGeometry.RADAR_SWEEP:
            return max(self.width, self.height)
        elif self.geometry_type == ScanGeometry.RADIAL_EXPANSION:
            return max(2, int(np.ceil(min(self.width, self.height) / 2.0)))
        return max(self.width, self.height)

    def _default_samples_per_step(self) -> int:
        """Derive sensible default spatial samples per step per geometry."""
        if self.geometry_type == ScanGeometry.HORIZONTAL_SWEEP:
            return self.height
        elif self.geometry_type == ScanGeometry.VERTICAL_SWEEP:
            return self.width
        elif self.geometry_type == ScanGeometry.RADAR_SWEEP:
            return max(2, int(np.ceil(min(self.width, self.height) / 2.0)))
        elif self.geometry_type == ScanGeometry.RADIAL_EXPANSION:
            return max(self.width, self.height)
        return max(self.width, self.height)

    # -------------------------------------------------------------------------
    # Core Scan Path Generators
    # -------------------------------------------------------------------------

    def horizontal_sweep(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
        duration_seconds: Optional[float] = None,
        num_steps: Optional[int] = None,
        samples_per_step: Optional[int] = None,
        **kwargs: Any,
    ) -> np.ndarray:
        """
        Generate coordinates for a horizontal sweep (Left-to-Right).
        Mapping:
        - X = time and stereo pan (-1.0 Left to +1.0 Right)
        - Y = pitch (top = high pitch, bottom = low pitch)

        Returns:
            np.ndarray: Array of shape (N, 3) where columns are (x, y, time).
        """
        w = int(width) if width is not None else self.width
        h = int(height) if height is not None else self.height
        dur = float(duration_seconds) if duration_seconds is not None else self.duration_seconds
        self._validate_dimensions(w, h, dur)

        n_steps = int(num_steps) if num_steps is not None else (self.num_steps if width is None else w)
        s_step = int(samples_per_step) if samples_per_step is not None else (self.samples_per_step if height is None else h)

        if n_steps < 1 or s_step < 1:
            raise ValueError("num_steps and samples_per_step must be >= 1.")

        # X positions and times
        if n_steps == 1:
            x_vals = np.array([0.0], dtype=np.float64)
            t_vals = np.array([0.0], dtype=np.float64)
        else:
            x_vals = np.linspace(0.0, float(w - 1), n_steps, dtype=np.float64)
            t_vals = np.linspace(0.0, dur, n_steps, dtype=np.float64)

        # Y positions along the vertical playhead line
        if s_step == 1:
            y_vals = np.array([0.0], dtype=np.float64)
        else:
            y_vals = np.linspace(0.0, float(h - 1), s_step, dtype=np.float64)

        # Vectorized grid generation: (n_steps, s_step)
        X = np.repeat(x_vals[:, np.newaxis], s_step, axis=1)
        T = np.repeat(t_vals[:, np.newaxis], s_step, axis=1)
        Y = np.repeat(y_vals[np.newaxis, :], n_steps, axis=0)

        coords = np.column_stack([X.ravel(), Y.ravel(), T.ravel()]).astype(np.float64)
        return coords

    def vertical_sweep(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
        duration_seconds: Optional[float] = None,
        num_steps: Optional[int] = None,
        samples_per_step: Optional[int] = None,
        **kwargs: Any,
    ) -> np.ndarray:
        """
        Generate coordinates for a vertical sweep (Top-to-Bottom).
        Mapping:
        - Y = time and base pitch
        - X = stereo pan (-1.0 Left to +1.0 Right)

        Returns:
            np.ndarray: Array of shape (N, 3) where columns are (x, y, time).
        """
        w = int(width) if width is not None else self.width
        h = int(height) if height is not None else self.height
        dur = float(duration_seconds) if duration_seconds is not None else self.duration_seconds
        self._validate_dimensions(w, h, dur)

        n_steps = int(num_steps) if num_steps is not None else (self.num_steps if height is None else h)
        s_step = int(samples_per_step) if samples_per_step is not None else (self.samples_per_step if width is None else w)

        if n_steps < 1 or s_step < 1:
            raise ValueError("num_steps and samples_per_step must be >= 1.")

        # Y positions and times
        if n_steps == 1:
            y_vals = np.array([0.0], dtype=np.float64)
            t_vals = np.array([0.0], dtype=np.float64)
        else:
            y_vals = np.linspace(0.0, float(h - 1), n_steps, dtype=np.float64)
            t_vals = np.linspace(0.0, dur, n_steps, dtype=np.float64)

        # X positions along the horizontal playhead line
        if s_step == 1:
            x_vals = np.array([0.0], dtype=np.float64)
        else:
            x_vals = np.linspace(0.0, float(w - 1), s_step, dtype=np.float64)

        # Vectorized grid generation: (n_steps, s_step)
        Y = np.repeat(y_vals[:, np.newaxis], s_step, axis=1)
        T = np.repeat(t_vals[:, np.newaxis], s_step, axis=1)
        X = np.repeat(x_vals[np.newaxis, :], n_steps, axis=0)

        coords = np.column_stack([X.ravel(), Y.ravel(), T.ravel()]).astype(np.float64)
        return coords

    def radar_sweep(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
        duration_seconds: Optional[float] = None,
        num_steps: Optional[int] = None,
        samples_per_step: Optional[int] = None,
        center: Optional[Tuple[float, float]] = None,
        radius_max: Optional[float] = None,
        clip_to_bounds: Optional[bool] = None,
        **kwargs: Any,
    ) -> np.ndarray:
        """
        Generate coordinates for a radar sweep (Clockwise rotation from center).
        Mapping:
        - Angle θ = time and stereo pan (sin(θ) from -1.0 Left to +1.0 Right)
        - Radial distance r = pitch (center = low pitch, outer perimeter = high pitch)

        Starting angle is 12 o'clock (straight up), rotating clockwise:
        12 o'clock (t=0) -> 3 o'clock (t=T/4) -> 6 o'clock (t=T/2) -> 9 o'clock (t=3T/4) -> 12 o'clock (t=T).

        Returns:
            np.ndarray: Array of shape (N, 3) where columns are (x, y, time).
        """
        w = int(width) if width is not None else self.width
        h = int(height) if height is not None else self.height
        dur = float(duration_seconds) if duration_seconds is not None else self.duration_seconds
        self._validate_dimensions(w, h, dur)

        n_steps = int(num_steps) if num_steps is not None else (self.num_steps if width is None else max(w, h))
        s_step = int(samples_per_step) if samples_per_step is not None else (
            self.samples_per_step if width is None else max(2, int(np.ceil(min(w, h) / 2.0)))
        )

        if n_steps < 1 or s_step < 1:
            raise ValueError("num_steps and samples_per_step must be >= 1.")

        # Center
        if center is not None:
            cx, cy = float(center[0]), float(center[1])
        elif width is not None or height is not None:
            cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
        else:
            cx, cy = self.center

        # Maximum radius
        if radius_max is not None:
            if radius_max <= 0:
                raise ValueError("radius_max must be positive.")
            rmax = float(radius_max)
        elif width is not None or height is not None:
            rmax = max(1.0, min(w - 1, h - 1) / 2.0)
        else:
            rmax = self.radius_max

        do_clip = self.clip_to_bounds if clip_to_bounds is None else bool(clip_to_bounds)

        # Angle from 12 o'clock rotating clockwise:
        # θ starts at 0 (straight up), reaches 2π after 1 full revolution
        if n_steps == 1:
            angles = np.array([0.0], dtype=np.float64)
            t_vals = np.array([0.0], dtype=np.float64)
        else:
            angles = np.linspace(0.0, 2.0 * np.pi, n_steps, endpoint=False, dtype=np.float64)
            t_vals = np.linspace(0.0, dur, n_steps, dtype=np.float64)

        # Radial distances from center to rmax
        if s_step == 1:
            r_vals = np.array([0.0], dtype=np.float64)
        else:
            r_vals = np.linspace(0.0, rmax, s_step, dtype=np.float64)

        # Vectorized polar to Cartesian:
        # shape: (n_steps, s_step)
        T = np.repeat(t_vals[:, np.newaxis], s_step, axis=1)
        ANG = np.repeat(angles[:, np.newaxis], s_step, axis=1)
        RAD = np.repeat(r_vals[np.newaxis, :], n_steps, axis=0)

        # Clockwise from 12 o'clock:
        # At θ=0:   x = cx, y = cy - r (top)
        # At θ=π/2: x = cx + r, y = cy (right)
        # At θ=π:   x = cx, y = cy + r (bottom)
        # At θ=3π/2: x = cx - r, y = cy (left)
        X = cx + RAD * np.sin(ANG)
        Y = cy - RAD * np.cos(ANG)

        if do_clip:
            X = np.clip(X, 0.0, float(w - 1))
            Y = np.clip(Y, 0.0, float(h - 1))

        coords = np.column_stack([X.ravel(), Y.ravel(), T.ravel()]).astype(np.float64)
        return coords

    def radial_expansion(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
        duration_seconds: Optional[float] = None,
        num_steps: Optional[int] = None,
        samples_per_step: Optional[int] = None,
        center: Optional[Tuple[float, float]] = None,
        radius_max: Optional[float] = None,
        clip_to_bounds: Optional[bool] = None,
        **kwargs: Any,
    ) -> np.ndarray:
        """
        Generate coordinates for a radial expansion sweep (Outward ripple).
        Mapping:
        - Radius r = time (ripple expands linearly with time: r(t) = (t / T) * R_max)
        - Angle θ around perimeter = stereo pan (-1.0 Left to +1.0 Right)
        - RGB Channels / multi-bands = distinct pitch registers
          (Red = Low / Bass, Green = Mid / Tenor, Blue = High / Soprano)

        Returns:
            np.ndarray: Array of shape (N, 3) where columns are (x, y, time).
        """
        w = int(width) if width is not None else self.width
        h = int(height) if height is not None else self.height
        dur = float(duration_seconds) if duration_seconds is not None else self.duration_seconds
        self._validate_dimensions(w, h, dur)

        n_steps = int(num_steps) if num_steps is not None else (
            self.num_steps if width is None else max(2, int(np.ceil(min(w, h) / 2.0)))
        )
        s_step = int(samples_per_step) if samples_per_step is not None else (
            self.samples_per_step if width is None else max(w, h)
        )

        if n_steps < 1 or s_step < 1:
            raise ValueError("num_steps and samples_per_step must be >= 1.")

        # Center
        if center is not None:
            cx, cy = float(center[0]), float(center[1])
        elif width is not None or height is not None:
            cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
        else:
            cx, cy = self.center

        # Maximum radius
        if radius_max is not None:
            if radius_max <= 0:
                raise ValueError("radius_max must be positive.")
            rmax = float(radius_max)
        elif width is not None or height is not None:
            rmax = max(1.0, min(w - 1, h - 1) / 2.0)
        else:
            rmax = self.radius_max

        do_clip = self.clip_to_bounds if clip_to_bounds is None else bool(clip_to_bounds)

        # Radius expands with time: r(t) = (t / duration) * rmax
        if n_steps == 1:
            t_vals = np.array([0.0], dtype=np.float64)
            r_vals = np.array([0.0], dtype=np.float64)
        else:
            t_vals = np.linspace(0.0, dur, n_steps, dtype=np.float64)
            r_vals = np.linspace(0.0, rmax, n_steps, dtype=np.float64)

        # Angular perimeter samples
        if s_step == 1:
            angles = np.array([0.0], dtype=np.float64)
        else:
            angles = np.linspace(0.0, 2.0 * np.pi, s_step, endpoint=False, dtype=np.float64)

        # Vectorized circle generation: (n_steps, s_step)
        T = np.repeat(t_vals[:, np.newaxis], s_step, axis=1)
        RAD = np.repeat(r_vals[:, np.newaxis], s_step, axis=1)
        ANG = np.repeat(angles[np.newaxis, :], n_steps, axis=0)

        # Concentric ripple expansion:
        X = cx + RAD * np.cos(ANG)
        Y = cy + RAD * np.sin(ANG)

        if do_clip:
            X = np.clip(X, 0.0, float(w - 1))
            Y = np.clip(Y, 0.0, float(h - 1))

        coords = np.column_stack([X.ravel(), Y.ravel(), T.ravel()]).astype(np.float64)
        return coords

    def generate_path(self, **kwargs: Any) -> np.ndarray:
        """
        Generate coordinate path for the instance's configured geometry.

        Returns:
            np.ndarray: Array of shape (N, 3) where columns are (x, y, time).
        """
        merged_kwargs = {**self.extra_kwargs, **kwargs}
        if self.geometry_type == ScanGeometry.HORIZONTAL_SWEEP:
            return self.horizontal_sweep(**merged_kwargs)
        elif self.geometry_type == ScanGeometry.VERTICAL_SWEEP:
            return self.vertical_sweep(**merged_kwargs)
        elif self.geometry_type == ScanGeometry.RADAR_SWEEP:
            return self.radar_sweep(**merged_kwargs)
        elif self.geometry_type == ScanGeometry.RADIAL_EXPANSION:
            return self.radial_expansion(**merged_kwargs)
        else:
            raise ValueError(f"Unsupported geometry type: {self.geometry_type}")

    def generate(self, **kwargs: Any) -> np.ndarray:
        """Alias for generate_path()."""
        return self.generate_path(**kwargs)

    # -------------------------------------------------------------------------
    # Mapping Utilities & Image Sampling
    # -------------------------------------------------------------------------

    def map_pan(self, scan_path: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Compute stereo pan in [-1.0, 1.0] for each coordinate in a scan path.

        - Horizontal / Vertical sweeps: mapped from X position.
        - Radar sweep: mapped from horizontal position or sin(θ).
        - Radial expansion: mapped from horizontal offset relative to center.

        Args:
            scan_path: (N, 3) coordinates array. If None, generated via generate_path().

        Returns:
            np.ndarray: 1D array of length N containing pan values in [-1.0, 1.0].
        """
        if scan_path is None:
            scan_path = self.generate_path()
        if scan_path.ndim != 2 or scan_path.shape[1] < 2:
            raise ValueError("scan_path must be a 2D array of shape (N, >=2).")

        x = scan_path[:, 0]

        if self.geometry_type in (ScanGeometry.HORIZONTAL_SWEEP, ScanGeometry.VERTICAL_SWEEP):
            if self.width <= 1:
                return np.zeros(len(x), dtype=np.float64)
            pan = (2.0 * x / (self.width - 1.0)) - 1.0
        elif self.geometry_type == ScanGeometry.RADAR_SWEEP:
            # Pan based on horizontal offset from center normalized by radius_max
            cx = self.center[0]
            if self.radius_max <= 0:
                return np.zeros(len(x), dtype=np.float64)
            pan = (x - cx) / self.radius_max
        elif self.geometry_type == ScanGeometry.RADIAL_EXPANSION:
            cx = self.center[0]
            if self.radius_max <= 0:
                return np.zeros(len(x), dtype=np.float64)
            pan = (x - cx) / self.radius_max
        else:
            pan = (2.0 * x / max(1.0, self.width - 1.0)) - 1.0

        return np.clip(pan, -1.0, 1.0).astype(np.float64)

    def map_pitch_normalized(self, scan_path: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Compute normalized pitch [0.0, 1.0] for each coordinate in a scan path.

        - Horizontal / Vertical sweeps: mapped from vertical position Y.
          By default, top of image (y=0) is highest pitch (1.0).
        - Radar sweep: mapped from radial distance from center.
        - Radial expansion: base normalized position (0.0 center to 1.0 perimeter).

        Args:
            scan_path: (N, 3) coordinates array. If None, generated via generate_path().

        Returns:
            np.ndarray: 1D array of length N with pitch positions in [0.0, 1.0].
        """
        if scan_path is None:
            scan_path = self.generate_path()
        if scan_path.ndim != 2 or scan_path.shape[1] < 2:
            raise ValueError("scan_path must be a 2D array of shape (N, >=2).")

        x = scan_path[:, 0]
        y = scan_path[:, 1]

        if self.geometry_type in (ScanGeometry.HORIZONTAL_SWEEP, ScanGeometry.VERTICAL_SWEEP):
            if self.height <= 1:
                return np.full(len(y), 0.5, dtype=np.float64)
            norm_y = y / (self.height - 1.0)
            if self.pitch_top_high:
                return np.clip(1.0 - norm_y, 0.0, 1.0).astype(np.float64)
            return np.clip(norm_y, 0.0, 1.0).astype(np.float64)

        elif self.geometry_type == ScanGeometry.RADAR_SWEEP:
            cx, cy = self.center
            r = np.hypot(x - cx, y - cy)
            if self.radius_max <= 0:
                return np.zeros(len(r), dtype=np.float64)
            return np.clip(r / self.radius_max, 0.0, 1.0).astype(np.float64)

        elif self.geometry_type == ScanGeometry.RADIAL_EXPANSION:
            cx, cy = self.center
            r = np.hypot(x - cx, y - cy)
            if self.radius_max <= 0:
                return np.zeros(len(r), dtype=np.float64)
            return np.clip(r / self.radius_max, 0.0, 1.0).astype(np.float64)

        norm_y = y / max(1.0, self.height - 1.0)
        return np.clip(1.0 - norm_y, 0.0, 1.0).astype(np.float64)

    def sample_image(
        self,
        image: np.ndarray,
        scan_path: Optional[np.ndarray] = None,
        interpolation: str = "bilinear",
    ) -> np.ndarray:
        """
        Sample pixel values from a 2D scalar array or 3D multi-channel image along the scan path.

        Args:
            image: 2D array (H, W) or 3D array (H, W, C).
            scan_path: (N, 3) coordinates array. If None, generated via generate_path().
            interpolation: 'bilinear' (default) or 'nearest'.

        Returns:
            np.ndarray: Sampled intensities of shape (N,) for 2D, or (N, C) for 3D.
        """
        if not isinstance(image, np.ndarray):
            raise TypeError("image must be a NumPy array.")
        if image.ndim not in (2, 3):
            raise ValueError(f"image must be 2D or 3D, got ndim={image.ndim}.")

        h, w = image.shape[:2]
        if scan_path is None:
            scan_path = self.generate_path(width=w, height=h)

        x_coords = np.clip(scan_path[:, 0], 0.0, float(w - 1))
        y_coords = np.clip(scan_path[:, 1], 0.0, float(h - 1))

        if interpolation == "nearest":
            xi = np.round(x_coords).astype(np.int64)
            yi = np.round(y_coords).astype(np.int64)
            return image[yi, xi]

        # Bilinear interpolation
        x0 = np.floor(x_coords).astype(np.int64)
        x1 = np.clip(x0 + 1, 0, w - 1)
        y0 = np.floor(y_coords).astype(np.int64)
        y1 = np.clip(y0 + 1, 0, h - 1)

        wx = (x_coords - x0)
        wy = (y_coords - y0)

        if image.ndim == 2:
            ia = image[y0, x0]
            ib = image[y0, x1]
            ic = image[y1, x0]
            id_ = image[y1, x1]

            top = ia * (1.0 - wx) + ib * wx
            bottom = ic * (1.0 - wx) + id_ * wx
            return (top * (1.0 - wy) + bottom * wy).astype(np.float32)
        else:
            # 3D image (H, W, C)
            wx = wx[:, np.newaxis]
            wy = wy[:, np.newaxis]
            ia = image[y0, x0]
            ib = image[y0, x1]
            ic = image[y1, x0]
            id_ = image[y1, x1]

            top = ia * (1.0 - wx) + ib * wx
            bottom = ic * (1.0 - wx) + id_ * wx
            return (top * (1.0 - wy) + bottom * wy).astype(np.float32)

    def get_channel_registers(self) -> Dict[str, Dict[str, Any]]:
        """Return multi-channel / RGB pitch register mapping definitions."""
        return self.CHANNEL_REGISTERS.copy()

    def get_metadata(self) -> Dict[str, Any]:
        """Return rich metadata characterizing the scan configuration."""
        return {
            "geometry_type": self.geometry_type.value,
            "width": self.width,
            "height": self.height,
            "duration_seconds": self.duration_seconds,
            "num_steps": self.num_steps,
            "samples_per_step": self.samples_per_step,
            "total_points": self.num_steps * self.samples_per_step,
            "center": self.center,
            "radius_max": self.radius_max,
            "clip_to_bounds": self.clip_to_bounds,
            "pitch_top_high": self.pitch_top_high,
            "fps": self.fps,
            "channel_registers": self.get_channel_registers(),
        }

    @classmethod
    def from_image(
        cls,
        image: np.ndarray,
        geometry_type: Union[str, ScanGeometry] = ScanGeometry.HORIZONTAL_SWEEP,
        duration_seconds: float = 10.0,
        **kwargs: Any,
    ) -> "ScanHead":
        """
        Convenience constructor initializing ScanHead dimensions from an image array.

        Args:
            image: 2D or 3D NumPy array.
            geometry_type: Scan path geometry.
            duration_seconds: Sonification duration in seconds.
            **kwargs: Forwarded to ScanHead.__init__.

        Returns:
            ScanHead: Initialized ScanHead instance.
        """
        if not isinstance(image, np.ndarray) or image.ndim < 2:
            raise ValueError("image must be a NumPy array with at least 2 dimensions.")
        height, width = image.shape[:2]
        return cls(
            geometry_type=geometry_type,
            width=width,
            height=height,
            duration_seconds=duration_seconds,
            **kwargs,
        )


# -----------------------------------------------------------------------------
# Standalone Top-Level API: generate_scan_path
# -----------------------------------------------------------------------------

def generate_scan_path(
    geometry_type: Union[str, ScanGeometry],
    width: int,
    height: int,
    duration_seconds: float,
    **kwargs: Any,
) -> np.ndarray:
    """
    Generate coordinate paths (x, y, time) for scientific image sonification.

    Args:
        geometry_type: Scan path geometry:
            - 'horizontal_sweep': Left-to-right (Y=pitch, X=time/pan)
            - 'vertical_sweep': Top-to-bottom (X=stereo pan, Y=pitch)
            - 'radar_sweep': Clockwise rotation from center (Angle=time/pan, Radius=pitch)
            - 'radial_expansion': Outward ripple (Radius=time, RGB channels=pitch registers)
        width: Canvas width in pixels (must be >= 1).
        height: Canvas height in pixels (must be >= 1).
        duration_seconds: Sonification duration in seconds (must be > 0).
        **kwargs: Optional parameters:
            - num_steps (int): Number of time steps.
            - samples_per_step (int): Number of spatial samples per time slice.
            - center (Tuple[float, float]): Playhead center for radar/radial.
            - radius_max (float): Maximum radius for radar/radial.
            - clip_to_bounds (bool): Constrain coordinates to image bounds.
            - fps (float): Calculate num_steps = int(round(fps * duration_seconds)).

    Returns:
        np.ndarray: Array of shape (N, 3) where columns are (x, y, time).
    """
    scanner = ScanHead(
        geometry_type=geometry_type,
        width=width,
        height=height,
        duration_seconds=duration_seconds,
        **kwargs,
    )
    return scanner.generate_path()


# -----------------------------------------------------------------------------
# Parameter Mapping and Musical Quantization (Task #9 Support)
# -----------------------------------------------------------------------------

def frequency_to_midi(freq_hz: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """Convert acoustic frequency in Hz to fractional MIDI note number."""
    f = np.asarray(freq_hz, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        midi = 69.0 + 12.0 * np.log2(np.maximum(f, 1e-6) / 440.0)
    return float(midi) if np.isscalar(freq_hz) else midi


def midi_to_frequency(midi_note: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """Convert MIDI note number to acoustic frequency in Hz."""
    m = np.asarray(midi_note, dtype=np.float64)
    freq = 440.0 * (2.0 ** ((m - 69.0) / 12.0))
    return float(freq) if np.isscalar(midi_note) else freq


def get_scale_midi_notes(
    scale_name: str = "c_major_pentatonic",
    root_midi: int = 48,
    min_midi: int = 0,
    max_midi: int = 127,
    num_octaves: Optional[int] = None,
) -> np.ndarray:
    """
    Build a sorted NumPy array of valid MIDI notes for a predefined musical scale.

    Args:
        scale_name: Scale identifier in MUSICAL_SCALES.
        root_midi: Root MIDI note number (e.g., 48 = C3, 60 = C4).
        min_midi: Lower MIDI note boundary (default: 0).
        max_midi: Upper MIDI note boundary (default: 127).
        num_octaves: Optional octave range restriction.

    Returns:
        np.ndarray: Sorted unique array of MIDI note numbers.
    """
    scale_key = scale_name.lower().strip().replace("-", "_").replace(" ", "_")
    if scale_key not in MUSICAL_SCALES:
        # Check aliases
        for k in MUSICAL_SCALES:
            if scale_key in (k.replace("_", ""), k.replace("major_", ""), k.replace("minor_", "")):
                scale_key = k
                break
        else:
            valid_scales = list(MUSICAL_SCALES.keys())
            raise ValueError(f"Unknown scale '{scale_name}'. Supported scales: {valid_scales}")

    pitch_classes = set(MUSICAL_SCALES[scale_key])
    root_pc = int(root_midi) % 12

    if num_octaves is not None and num_octaves > 0:
        low = max(0, root_midi)
        high = min(127, root_midi + num_octaves * 12)
    else:
        low = max(0, min_midi)
        high = min(127, max_midi)

    scale_notes = [
        note for note in range(low, high + 1)
        if ((note - root_pc) % 12) in pitch_classes
    ]
    if not scale_notes:
        scale_notes = [root_midi]
    return np.array(scale_notes, dtype=np.float64)


def quantize_to_scale(
    frequencies_or_midi: Union[float, np.ndarray, Sequence[float]],
    scale_name: str = "c_major_pentatonic",
    root_midi: int = 48,
    num_octaves: Optional[int] = None,
    input_is_freq: bool = True,
    **kwargs: Any,
) -> Tuple[Union[float, np.ndarray], Union[float, np.ndarray]]:
    """
    Snap continuous audio frequencies or MIDI numbers to the nearest note in a musical scale.

    Args:
        frequencies_or_midi: Input continuous frequencies (Hz) or MIDI note numbers.
        scale_name: Name of predefined scale in MUSICAL_SCALES (e.g. 'c_major_pentatonic').
        root_midi: Base MIDI note for the scale root (e.g., 48 = C3, 60 = C4).
        num_octaves: Optional number of octaves to build in the scale note array.
        input_is_freq: True if inputs are Hz, False if inputs are MIDI note numbers.
        **kwargs: Additional parameters forwarded to get_scale_midi_notes.

    Returns:
        Tuple[Union[float, np.ndarray], Union[float, np.ndarray]]: (quantized_frequencies_hz, quantized_midi_notes)
    """
    scale_notes = get_scale_midi_notes(
        scale_name=scale_name,
        root_midi=root_midi,
        num_octaves=num_octaves,
        **kwargs,
    )

    is_scalar = np.isscalar(frequencies_or_midi)
    arr = np.atleast_1d(np.asarray(frequencies_or_midi, dtype=np.float64))

    if input_is_freq:
        midi_inputs = frequency_to_midi(arr)
    else:
        midi_inputs = arr

    # Snap each input to nearest note in scale using absolute difference
    diffs = np.abs(midi_inputs[:, np.newaxis] - scale_notes[np.newaxis, :])
    nearest_idx = np.argmin(diffs, axis=1)
    quantized_midi = scale_notes[nearest_idx]
    quantized_freq = midi_to_frequency(quantized_midi)

    if is_scalar:
        return float(quantized_freq[0]), float(quantized_midi[0])
    return quantized_freq, quantized_midi


def compress_dynamic_range(
    intensity: Union[float, np.ndarray, Sequence[float]],
    method: str = "arcsinh",
    alpha: float = 10.0,
    gamma: float = 1.0,
    noise_floor: float = 0.10,
) -> Union[float, np.ndarray]:
    """
    Apply perceptual dynamic range compression and noise-floor gating.

    1. Volume compression: arcsinh or logarithmic compression to manage astronomical dynamic range.
    2. Power-law curve: adjusts perceptual contrast / loudness curve (v ** gamma).
    3. Noise-floor gate: mutes signals below luminance threshold (default: < 10% luminance).

    Args:
        intensity: Normalized pixel luminance / scalar values in [0.0, 1.0].
        method: Compression curve: 'arcsinh' (astronomical standard), 'log', or 'linear'.
        alpha: Scaling factor for arcsinh or log compression (controls steepness of dark boost).
        gamma: Power-law curve exponent (v ** gamma).
        noise_floor: Threshold below which amplitude is gated to 0.0 (default 10% luminance).

    Returns:
        Union[float, np.ndarray]: Compressed amplitude values in [0.0, 1.0].
    """
    is_scalar = np.isscalar(intensity) or (isinstance(intensity, np.ndarray) and intensity.ndim == 0)
    arr = np.asarray(intensity, dtype=np.float64)
    v = np.clip(arr, 0.0, 1.0)

    method_clean = str(method).lower().strip().replace("-", "_")

    if method_clean in ("arcsinh", "asinh"):
        denom = np.arcsinh(alpha) if alpha > 0 else 1.0
        compressed = np.arcsinh(alpha * v) / denom
    elif method_clean in ("log", "logarithmic", "log1p"):
        denom = np.log1p(alpha) if alpha > 0 else 1.0
        compressed = np.log1p(alpha * v) / denom
    elif method_clean in ("linear", "none", "identity"):
        compressed = v
    else:
        raise ValueError(f"Unknown compression method: '{method}'. Choose 'arcsinh', 'log', or 'linear'.")

    # Power-law curve (applied after compression curve)
    if gamma != 1.0 and gamma > 0:
        compressed = np.power(np.maximum(compressed, 0.0), gamma)

    # Noise-floor gate: mute if below luminance threshold (< 10% luminance)
    if noise_floor > 0.0:
        compressed = np.where(v < noise_floor, 0.0, compressed)

    result = np.clip(compressed, 0.0, 1.0)
    if is_scalar:
        return float(result.item() if hasattr(result, "item") else result)
    return result


class AudioEventList(list):
    """
    Structured list of audio events for NASA Chandra-style sonification.

    Inherits from list to provide standard sequence iteration, indexing, and serialization,
    while also supporting dictionary-style lookup for:
        - ['diffuse_events']: list of continuous sustained pad events
        - ['point_source_events']: list of discrete percussive/pluck trigger events
        - ['metadata']: global sonification synthesis configuration metadata
        - ['events']: reference to all combined events in chronological order
    """

    def __init__(
        self,
        events: Sequence[Dict[str, Any]],
        diffuse_events: Optional[List[Dict[str, Any]]] = None,
        point_source_events: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(events)
        self.diffuse_events: List[Dict[str, Any]] = list(diffuse_events) if diffuse_events is not None else []
        self.point_source_events: List[Dict[str, Any]] = list(point_source_events) if point_source_events is not None else []
        self.metadata: Dict[str, Any] = dict(metadata) if metadata is not None else {}
        self._dict: Dict[str, Any] = {
            "events": self,
            "diffuse_events": self.diffuse_events,
            "point_source_events": self.point_source_events,
            "metadata": self.metadata,
        }

    @property
    def events(self) -> List[Dict[str, Any]]:
        """Return all events."""
        return list(self)

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, str):
            if key in self._dict:
                return self._dict[key]
            raise KeyError(f"Key '{key}' not found. Available keys: {list(self._dict.keys())}")
        return super().__getitem__(key)

    def __contains__(self, key: Any) -> bool:
        if isinstance(key, str):
            return key in self._dict
        return super().__contains__(key)

    def get(self, key: str, default: Any = None) -> Any:
        return self._dict.get(key, default)

    def keys(self):
        return self._dict.keys()

    def values(self):
        return self._dict.values()

    def items(self):
        return self._dict.items()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to standard Python dictionary."""
        return {
            "events": list(self),
            "diffuse_events": self.diffuse_events,
            "point_source_events": self.point_source_events,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"<AudioEventList total_events={len(self)} "
            f"diffuse={len(self.diffuse_events)} point_sources={len(self.point_source_events)}>"
        )


def infer_scan_geometry(scan_path: np.ndarray, width: int, height: int) -> ScanGeometry:
    """
    Infer scan geometry from scan path coordinate progression.
    """
    if len(scan_path) < 2:
        return ScanGeometry.HORIZONTAL_SWEEP

    times = scan_path[:, 2]
    t0_mask = np.isclose(times, times[0], atol=1e-5)
    t0_coords = scan_path[t0_mask]

    x0 = t0_coords[:, 0]
    y0 = t0_coords[:, 1]

    cx = (width - 1) / 2.0
    cy = (height - 1) / 2.0

    # If all points at t0 are at or very near center
    if np.allclose(x0, cx, atol=1.5) and np.allclose(y0, cy, atol=1.5):
        return ScanGeometry.RADIAL_EXPANSION

    # If x0 is constant 0 and y0 spans 0 to height-1 -> horizontal sweep
    if np.allclose(x0, 0.0, atol=1.0) and (y0.max() - y0.min() > 1.0):
        return ScanGeometry.HORIZONTAL_SWEEP

    # If y0 is constant 0 and x0 spans 0 to width-1 -> vertical sweep
    if np.allclose(y0, 0.0, atol=1.0) and (x0.max() - x0.min() > 1.0):
        return ScanGeometry.VERTICAL_SWEEP

    # If x0 is near cx and y0 is <= cy -> radar sweep (12 o'clock ray)
    if np.allclose(x0, cx, atol=2.0) and np.all(y0 <= cy + 1.0):
        return ScanGeometry.RADAR_SWEEP

    return ScanGeometry.HORIZONTAL_SWEEP


def map_parameters(
    scan_path: np.ndarray,
    scalar_array: Union[np.ndarray, Dict[str, Any]],
    point_sources: Optional[Union[List[Dict[str, Any]], np.ndarray, Dict[str, Any]]] = None,
    diffuse_layer: Optional[np.ndarray] = None,
    scale_name: str = "c_major_pentatonic",
    base_freq: float = 130.81,  # C3
    max_freq: float = 1046.50,  # C6
    noise_floor: float = 0.10,
    compression_method: str = "arcsinh",
    compression_alpha: float = 10.0,
    gamma: float = 1.0,
    scan_geometry: Optional[Union[str, ScanGeometry]] = None,
    return_dict: bool = False,
    consolidate_notes: bool = False,
    quantize_notes: bool = True,
    max_polyphony: Optional[int] = None,
    diffuse_waveform: Optional[str] = None,
    point_source_instrument: Optional[str] = None,
    **kwargs: Any,
) -> Union[AudioEventList, Dict[str, Any]]:
    """
    Translate visual and morphological features into a structured list of sonification audio events.

    Mappings:
    1. Volume: Pixel intensity -> amplitude via arcsinh/log compression and power-law curve,
       gated by noise-floor (mute if < 10% luminance).
    2. Pitch: Vertical/radial position -> base frequency, quantized to musical scale (e.g. C pentatonic)
       using a MIDI note array.
    3. Pan: Horizontal/angle position -> stereo pan in [-1.0, 1.0].
    4. Timbre/Events:
       - point_sources -> discrete, short-duration events (pluck/percussive triggers).
       - diffuse_layer -> continuous, sustained events (ambient pad).

    Args:
        scan_path: (N, 3) array of (x, y, time) coordinates.
        scalar_array: 2D normalized scalar array [0.0, 1.0], or morphological features dict.
        point_sources: Optional list of point source metadata dictionaries from detect_point_sources,
                       or 2D residual array.
        diffuse_layer: Optional separate 2D array representing diffuse background.
        scale_name: Musical scale for quantization (default: 'c_major_pentatonic').
        base_freq: Lower bound frequency in Hz (default: 130.81 Hz = C3).
        max_freq: Upper bound frequency in Hz (default: 1046.50 Hz = C6).
        noise_floor: Amplitude gating floor (default: 0.10, mutes < 10% luminance).
        compression_method: 'arcsinh', 'log', or 'linear'.
        compression_alpha: Compression curve factor.
        gamma: Power-law curve exponent (v ** gamma).
        scan_geometry: Scan geometry type. If None, inferred from scan_path.
        return_dict: If True, returns standard dict; if False, returns AudioEventList.
        consolidate_notes: If True, consolidates duplicate MIDI notes per time slice.
        **kwargs: Additional parameters for extensibility.

    Returns:
        Union[AudioEventList, Dict[str, Any]]: Structured list/dict of audio events containing:
            - 'events': All audio events sorted chronologically.
            - 'diffuse_events': Continuous sustained pad events.
            - 'point_source_events': Discrete triggers for detected hotspots.
            - 'metadata': Synthesis configuration parameters.
    """
    # 0. Resolve diffuse layer and point sources
    diffuse_arr = None
    if diffuse_layer is not None:
        diffuse_arr = diffuse_layer
    elif isinstance(scalar_array, dict):
        diffuse_arr = scalar_array.get("diffuse_layer", scalar_array.get("scalar_array"))
        if diffuse_arr is None and "point_source_layer" in scalar_array:
            diffuse_arr = scalar_array["point_source_layer"]
        if point_sources is None:
            point_sources = scalar_array.get("point_sources", scalar_array.get("point_source_layer"))
    else:
        diffuse_arr = scalar_array

    if diffuse_arr is None or not isinstance(diffuse_arr, np.ndarray) or diffuse_arr.ndim not in (2, 3):
        raise ValueError("scalar_array or diffuse_layer must be a 2D or 3D NumPy array.")

    h, w = diffuse_arr.shape[:2]

    # Resolve point sources if provided as residual array or dict
    if isinstance(point_sources, dict):
        point_sources = point_sources.get("point_sources", [])
    elif isinstance(point_sources, np.ndarray) and point_sources.ndim == 2:
        try:
            from backend.morphology import detect_point_sources
            point_sources = detect_point_sources(point_sources)
        except Exception as exc:
            logger.warning(f"Failed to auto-detect point sources from array: {exc}")
            point_sources = []
    elif point_sources is None:
        point_sources = []

    # Validate scan_path
    if not isinstance(scan_path, np.ndarray) or scan_path.ndim != 2 or scan_path.shape[1] < 3:
        raise ValueError("scan_path must be a NumPy array of shape (N, >=3).")
    if len(scan_path) == 0:
        raise ValueError("scan_path cannot be empty.")

    # Resolve geometry
    if scan_geometry is not None:
        geom = ScanGeometry.from_string(scan_geometry)
    else:
        geom = infer_scan_geometry(scan_path, w, h)

    dur_path = float(np.max(scan_path[:, 2])) if len(scan_path) > 0 else 10.0
    duration_sec = dur_path if dur_path > 0 else 10.0
    scanner = ScanHead(geometry_type=geom, width=w, height=h, duration_seconds=duration_sec)

    # 1. Sample luminance along scan path
    sampled = scanner.sample_image(diffuse_arr, scan_path=scan_path)
    if sampled.ndim == 2 and sampled.shape[1] == 3:
        luminance = 0.299 * sampled[:, 0] + 0.587 * sampled[:, 1] + 0.114 * sampled[:, 2]
    else:
        luminance = sampled

    # 2. Volume mapping: arcsinh/log compression followed by power-law and noise-floor gate (<10%)
    amplitude = compress_dynamic_range(
        luminance,
        method=compression_method,
        alpha=compression_alpha,
        gamma=gamma,
        noise_floor=noise_floor,
    )

    # 3. Stereo pan mapping: -1.0 (Left) to 1.0 (Right)
    pan = scanner.map_pan(scan_path=scan_path)
    pan = np.clip(pan, -1.0, 1.0)

    # 4. Pitch mapping: vertical/radial position to base frequency and musical quantization
    pitch_norm = scanner.map_pitch_normalized(scan_path=scan_path)
    raw_freq = base_freq * ((max_freq / base_freq) ** pitch_norm)
    root_midi = int(np.round(frequency_to_midi(base_freq)))
    quantized_freq, quantized_midi = quantize_to_scale(
        raw_freq,
        scale_name=scale_name,
        root_midi=root_midi,
    )

    if not quantize_notes:
        eff_freq = raw_freq
        eff_midi = frequency_to_midi(raw_freq)
    else:
        eff_freq = quantized_freq
        eff_midi = quantized_midi

    # 5. Build continuous diffuse events (grouped by time step or sampled slices)
    times = scan_path[:, 2]
    unique_times, time_indices = np.unique(times, return_inverse=True)

    if len(unique_times) > 1:
        step_dt = float(np.median(np.diff(unique_times)))
    else:
        step_dt = 0.1

    diffuse_events: List[Dict[str, Any]] = []

    for idx, t in enumerate(unique_times):
        mask = (time_indices == idx)
        slice_amp = amplitude[mask]
        slice_pan = pan[mask]
        slice_freq = eff_freq[mask]
        slice_midi = eff_midi[mask]
        slice_x = scan_path[mask, 0]
        slice_y = scan_path[mask, 1]

        # Only retain audible events (above noise floor gate)
        audible = slice_amp > 0.0
        if not np.any(audible):
            continue

        aud_amp = slice_amp[audible]
        aud_pan = slice_pan[audible]
        aud_freq = slice_freq[audible]
        aud_midi = slice_midi[audible]
        aud_x = slice_x[audible]
        aud_y = slice_y[audible]

        # Polyphony throttling: limit active concurrent voices to top loudest notes
        if max_polyphony is not None and max_polyphony > 0 and len(aud_amp) > max_polyphony:
            top_idx = np.argsort(aud_amp)[::-1][:max_polyphony]
            aud_amp = aud_amp[top_idx]
            aud_pan = aud_pan[top_idx]
            aud_freq = aud_freq[top_idx]
            aud_midi = aud_midi[top_idx]
            aud_x = aud_x[top_idx]
            aud_y = aud_y[top_idx]

        if consolidate_notes:
            # Keep strongest event per unique MIDI note
            seen_notes: Dict[int, int] = {}
            for i, m in enumerate(aud_midi):
                m_int = int(np.round(m))
                if m_int not in seen_notes or aud_amp[i] > aud_amp[seen_notes[m_int]]:
                    seen_notes[m_int] = i

            for i in seen_notes.values():
                ev = {
                    "time": float(t),
                    "time_ms": float(t * 1000.0),
                    "duration": step_dt,
                    "duration_ms": float(step_dt * 1000.0),
                    "frequency": float(aud_freq[i]),
                    "pitch": float(aud_freq[i]),
                    "midi_note": int(np.round(aud_midi[i])) if quantize_notes else float(aud_midi[i]),
                    "velocity": float(aud_amp[i]),
                    "amplitude": float(aud_amp[i]),
                    "pan": float(aud_pan[i]),
                    "instrument": "diffuse_pad",
                    "instrumentId": "diffuse_pad",
                    "layer": "diffuse",
                    "spatialPosition": {"x": float(aud_x[i]), "y": float(aud_y[i])},
                    "x": float(aud_x[i]),
                    "y": float(aud_y[i]),
                }
                if diffuse_waveform is not None:
                    ev["waveform"] = diffuse_waveform
                diffuse_events.append(ev)
        else:
            for amp, p, f, m, x_val, y_val in zip(aud_amp, aud_pan, aud_freq, aud_midi, aud_x, aud_y):
                ev = {
                    "time": float(t),
                    "time_ms": float(t * 1000.0),
                    "duration": step_dt,
                    "duration_ms": float(step_dt * 1000.0),
                    "frequency": float(f),
                    "pitch": float(f),
                    "midi_note": int(np.round(m)) if quantize_notes else float(m),
                    "velocity": float(amp),
                    "amplitude": float(amp),
                    "pan": float(p),
                    "instrument": "diffuse_pad",
                    "instrumentId": "diffuse_pad",
                    "layer": "diffuse",
                    "spatialPosition": {"x": float(x_val), "y": float(y_val)},
                    "x": float(x_val),
                    "y": float(y_val),
                }
                if diffuse_waveform is not None:
                    ev["waveform"] = diffuse_waveform
                diffuse_events.append(ev)

    # 6. Build discrete point source triggers
    point_source_events: List[Dict[str, Any]] = []
    if point_sources:
        dur_total = duration_sec if duration_sec > 0 else 10.0
        for ps in point_sources:
            px = float(ps.get("x", ps.get("center_x", w / 2.0)))
            py = float(ps.get("y", ps.get("center_y", h / 2.0)))
            flux = float(ps.get("flux", ps.get("peak_flux", ps.get("intensity", 1.0))))
            radius = float(ps.get("radius", ps.get("area", 3.0)))

            # Determine crossing time and stereo pan based on playhead geometry
            if geom == ScanGeometry.HORIZONTAL_SWEEP:
                t_event = (px / max(1.0, w - 1.0)) * dur_total
                p_val = (2.0 * px / max(1.0, w - 1.0)) - 1.0
                norm_p = 1.0 - (py / max(1.0, h - 1.0)) if scanner.pitch_top_high else (py / max(1.0, h - 1.0))
            elif geom == ScanGeometry.VERTICAL_SWEEP:
                t_event = (py / max(1.0, h - 1.0)) * dur_total
                p_val = (2.0 * px / max(1.0, w - 1.0)) - 1.0
                norm_p = 1.0 - (py / max(1.0, h - 1.0)) if scanner.pitch_top_high else (py / max(1.0, h - 1.0))
            elif geom == ScanGeometry.RADAR_SWEEP:
                cx, cy = scanner.center
                dx = px - cx
                dy = py - cy
                angle = np.arctan2(dx, -dy) % (2.0 * np.pi)
                t_event = (angle / (2.0 * np.pi)) * dur_total
                p_val = np.clip(dx / max(1e-5, scanner.radius_max), -1.0, 1.0)
                norm_p = np.clip(np.hypot(dx, dy) / max(1e-5, scanner.radius_max), 0.0, 1.0)
            elif geom == ScanGeometry.RADIAL_EXPANSION:
                cx, cy = scanner.center
                dist = np.hypot(px - cx, py - cy)
                t_event = np.clip(dist / max(1e-5, scanner.radius_max), 0.0, 1.0) * dur_total
                p_val = np.clip((px - cx) / max(1e-5, scanner.radius_max), -1.0, 1.0)
                norm_p = np.clip(dist / max(1e-5, scanner.radius_max), 0.0, 1.0)
            else:
                t_event = (px / max(1.0, w - 1.0)) * dur_total
                p_val = (2.0 * px / max(1.0, w - 1.0)) - 1.0
                norm_p = 1.0 - (py / max(1.0, h - 1.0))

            # Pitch mapping
            f_raw = base_freq * ((max_freq / base_freq) ** float(norm_p))
            if quantize_notes:
                q_freq, q_midi = quantize_to_scale(
                    f_raw,
                    scale_name=scale_name,
                    root_midi=root_midi,
                )
                ev_freq = float(q_freq)
                ev_midi = int(q_midi)
            else:
                ev_freq = float(f_raw)
                ev_midi = float(frequency_to_midi(f_raw))

            # Volume and duration
            vel = float(compress_dynamic_range(flux, method=compression_method, alpha=compression_alpha, gamma=gamma, noise_floor=0.0))
            dur_sec = float(np.clip(radius * 0.03, 0.05, 0.4))
            inst_name = point_source_instrument or "point_source_pluck"

            point_source_events.append({
                "time": float(t_event),
                "time_ms": float(t_event * 1000.0),
                "duration": dur_sec,
                "duration_ms": float(dur_sec * 1000.0),
                "frequency": ev_freq,
                "pitch": ev_freq,
                "midi_note": ev_midi,
                "velocity": float(vel),
                "amplitude": float(vel),
                "pan": float(np.clip(p_val, -1.0, 1.0)),
                "instrument": inst_name,
                "instrumentId": inst_name,
                "layer": "point_source",
                "spatialPosition": {"x": float(px), "y": float(py)},
                "x": float(px),
                "y": float(py),
                "source_metadata": ps,
            })

        point_source_events.sort(key=lambda ev: ev["time"])

    # Merge all events chronologically
    all_events = sorted(
        diffuse_events + point_source_events,
        key=lambda ev: (ev["time"], 0 if ev["layer"] == "diffuse" else 1),
    )

    metadata = {
        "geometry_type": geom.value,
        "scale_name": scale_name,
        "base_freq_hz": base_freq,
        "max_freq_hz": max_freq,
        "noise_floor": noise_floor,
        "compression_method": compression_method,
        "compression_alpha": compression_alpha,
        "gamma": gamma,
        "num_diffuse_events": len(diffuse_events),
        "num_point_source_events": len(point_source_events),
        "total_events": len(all_events),
        "duration_seconds": float(np.max(unique_times)) if len(unique_times) > 0 else (duration_sec if point_sources else 0.0),
    }

    event_list = AudioEventList(
        events=all_events,
        diffuse_events=diffuse_events,
        point_source_events=point_source_events,
        metadata=metadata,
    )

    if return_dict:
        return event_list.to_dict()
    return event_list
