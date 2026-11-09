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
    "minor_pentatonic": [0, 3, 5, 7, 10],
    "major": [0, 2, 4, 5, 7, 9, 11],
    "natural_minor": [0, 2, 3, 5, 7, 8, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "chromatic": list(range(12)),
    "blues": [0, 3, 5, 6, 7, 10],
    "whole_tone": [0, 2, 4, 6, 8, 10],
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


def quantize_to_scale(
    frequencies_or_midi: Union[float, np.ndarray],
    scale_name: str = "c_major_pentatonic",
    root_midi: int = 48,
    num_octaves: int = 4,
    input_is_freq: bool = True,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Snap continuous audio frequencies or MIDI numbers to the nearest note in a musical scale.

    Args:
        frequencies_or_midi: Input continuous frequencies (Hz) or MIDI note numbers.
        scale_name: Name of predefined scale in MUSICAL_SCALES.
        root_midi: Base MIDI note for the scale root (e.g., 48 = C3, 60 = C4).
        num_octaves: Number of octaves to build in the scale note array.
        input_is_freq: True if inputs are Hz, False if inputs are MIDI note numbers.

    Returns:
        Tuple[np.ndarray, np.ndarray]: (quantized_frequencies_hz, quantized_midi_notes)
    """
    scale_key = scale_name.lower().strip().replace("-", "_")
    if scale_key not in MUSICAL_SCALES:
        valid_scales = list(MUSICAL_SCALES.keys())
        raise ValueError(f"Unknown scale '{scale_name}'. Supported scales: {valid_scales}")

    pitch_classes = MUSICAL_SCALES[scale_key]
    scale_notes = []
    for octave in range(num_octaves + 1):
        for pc in pitch_classes:
            note = root_midi + octave * 12 + pc
            if note <= 127:
                scale_notes.append(note)
    scale_notes = np.unique(np.array(scale_notes, dtype=np.float64))

    # Convert inputs to MIDI notes
    arr = np.atleast_1d(np.asarray(frequencies_or_midi, dtype=np.float64))
    if input_is_freq:
        midi_inputs = frequency_to_midi(arr)
    else:
        midi_inputs = arr

    # Snap each input to nearest note in scale
    # Using searchsorted or absolute difference
    diffs = np.abs(midi_inputs[:, np.newaxis] - scale_notes[np.newaxis, :])
    nearest_idx = np.argmin(diffs, axis=1)
    quantized_midi = scale_notes[nearest_idx]
    quantized_freq = midi_to_frequency(quantized_midi)

    if np.isscalar(frequencies_or_midi):
        return quantized_freq[0], quantized_midi[0]
    return quantized_freq, quantized_midi


def compress_dynamic_range(
    intensity: Union[float, np.ndarray],
    method: str = "arcsinh",
    alpha: float = 10.0,
    gamma: float = 1.0,
    noise_floor: float = 0.10,
) -> np.ndarray:
    """
    Apply perceptual dynamic range compression and noise-floor gating.

    Args:
        intensity: Normalized pixel luminance / scalar values in [0.0, 1.0].
        method: Compression curve: 'arcsinh' (astronomical standard), 'log', or 'linear'.
        alpha: Scaling factor for arcsinh or log compression.
        gamma: Power-law curve exponent (v ** gamma).
        noise_floor: Threshold below which amplitude is gated to 0.0 (default 10% luminance).

    Returns:
        np.ndarray: Compressed amplitude values in [0.0, 1.0].
    """
    v = np.clip(np.asarray(intensity, dtype=np.float64), 0.0, 1.0)

    if method == "arcsinh":
        denom = np.arcsinh(alpha) if alpha > 0 else 1.0
        compressed = np.arcsinh(alpha * v) / denom
    elif method == "log":
        denom = np.log1p(alpha) if alpha > 0 else 1.0
        compressed = np.log1p(alpha * v) / denom
    elif method == "linear":
        compressed = v
    else:
        raise ValueError(f"Unknown compression method: '{method}'. Choose 'arcsinh', 'log', or 'linear'.")

    # Power-law curve
    if gamma != 1.0:
        compressed = np.power(compressed, gamma)

    # Noise-floor gate: mute if below luminance threshold
    if noise_floor > 0.0:
        compressed = np.where(v < noise_floor, 0.0, compressed)

    return np.clip(compressed, 0.0, 1.0)


def map_parameters(
    scan_path: np.ndarray,
    scalar_array: np.ndarray,
    point_sources: Optional[List[Dict[str, Any]]] = None,
    scale_name: str = "c_major_pentatonic",
    base_freq: float = 130.81,  # C3
    max_freq: float = 1046.50,  # C6
    noise_floor: float = 0.10,
    compression_method: str = "arcsinh",
    compression_alpha: float = 10.0,
    scan_geometry: Union[str, ScanGeometry] = ScanGeometry.HORIZONTAL_SWEEP,
) -> Dict[str, Any]:
    """
    Translate visual and morphological features into a structured list of sonification audio events.

    Mappings:
    1. Volume: Pixel intensity -> amplitude via arcsinh/log compression and noise-floor gate (< 10%).
    2. Pitch: Vertical/radial position -> frequency, quantized to musical scale (e.g. C pentatonic).
    3. Pan: Horizontal/angle position -> stereo pan in [-1.0, 1.0].
    4. Timbre/Events:
       - Point sources -> discrete, short-duration events (pluck/percussive).
       - Diffuse layer -> continuous, sustained events (ambient pad).

    Args:
        scan_path: (N, 3) array of (x, y, time) coordinates.
        scalar_array: 2D normalized scalar array [0.0, 1.0].
        point_sources: Optional list of point source metadata dictionaries from detect_point_sources.
        scale_name: Musical scale for quantization (default: 'c_major_pentatonic').
        base_freq: Lower bound frequency in Hz.
        max_freq: Upper bound frequency in Hz.
        noise_floor: Amplitude gating floor (default: 0.10).
        compression_method: 'arcsinh', 'log', or 'linear'.
        compression_alpha: Compression curve factor.
        scan_geometry: Geometry used for path generation.

    Returns:
        Dict[str, Any]: Structured dictionary containing:
            - 'diffuse_events': List of continuous pad events across time slices.
            - 'point_source_events': List of discrete triggers for detected hotspots.
            - 'metadata': Synthesis configuration parameters.
    """
    if not isinstance(scan_path, np.ndarray) or scan_path.ndim != 2 or scan_path.shape[1] < 3:
        raise ValueError("scan_path must be a NumPy array of shape (N, >=3).")
    if not isinstance(scalar_array, np.ndarray) or scalar_array.ndim != 2:
        raise ValueError("scalar_array must be a 2D NumPy array.")

    h, w = scalar_array.shape
    geom = ScanGeometry.from_string(scan_geometry)
    scanner = ScanHead(geometry_type=geom, width=w, height=h, duration_seconds=float(np.max(scan_path[:, 2])))

    # 1. Sample image luminance along scan path
    luminance = scanner.sample_image(scalar_array, scan_path=scan_path)

    # 2. Volume mapping with dynamic range compression and noise-floor gate
    amplitude = compress_dynamic_range(
        luminance,
        method=compression_method,
        alpha=compression_alpha,
        noise_floor=noise_floor,
    )

    # 3. Stereo pan mapping
    pan = scanner.map_pan(scan_path=scan_path)

    # 4. Pitch mapping
    pitch_norm = scanner.map_pitch_normalized(scan_path=scan_path)
    raw_freq = base_freq * ((max_freq / base_freq) ** pitch_norm)
    quantized_freq, quantized_midi = quantize_to_scale(
        raw_freq,
        scale_name=scale_name,
        root_midi=int(np.round(frequency_to_midi(base_freq))),
    )

    # 5. Build continuous diffuse events (grouped by time step or sampled slices)
    times = scan_path[:, 2]
    unique_times, time_indices = np.unique(times, return_inverse=True)

    diffuse_events: List[Dict[str, Any]] = []
    # Duration per slice is difference between consecutive times
    if len(unique_times) > 1:
        step_dt = float(np.median(np.diff(unique_times)))
    else:
        step_dt = 0.1

    for idx, t in enumerate(unique_times):
        mask = (time_indices == idx)
        slice_amp = amplitude[mask]
        slice_pan = pan[mask]
        slice_freq = quantized_freq[mask]
        slice_midi = quantized_midi[mask]

        # Only retain audible events (above noise floor)
        audible = slice_amp > 0.0
        if not np.any(audible):
            continue

        for amp, p, f, m in zip(slice_amp[audible], slice_pan[audible], slice_freq[audible], slice_midi[audible]):
            diffuse_events.append({
                "time": float(t),
                "duration": step_dt,
                "frequency": float(f),
                "midi_note": int(m),
                "velocity": float(amp),
                "pan": float(p),
                "instrument": "diffuse_pad",
                "layer": "diffuse",
            })

    # 6. Build discrete point source triggers
    point_source_events: List[Dict[str, Any]] = []
    if point_sources:
        duration_sec = float(np.max(unique_times)) if len(unique_times) > 0 else 10.0
        for ps in point_sources:
            px = ps.get("x", ps.get("center_x", w / 2.0))
            py = ps.get("y", ps.get("center_y", h / 2.0))
            flux = ps.get("flux", ps.get("peak_flux", 1.0))
            radius = ps.get("radius", 3.0)

            # Determine time when scanhead crosses (px, py)
            if geom == ScanGeometry.HORIZONTAL_SWEEP:
                t_event = (px / max(1.0, w - 1.0)) * duration_sec
                p_val = (2.0 * px / max(1.0, w - 1.0)) - 1.0
                norm_p = 1.0 - (py / max(1.0, h - 1.0))
            elif geom == ScanGeometry.VERTICAL_SWEEP:
                t_event = (py / max(1.0, h - 1.0)) * duration_sec
                p_val = (2.0 * px / max(1.0, w - 1.0)) - 1.0
                norm_p = 1.0 - (py / max(1.0, h - 1.0))
            elif geom == ScanGeometry.RADAR_SWEEP:
                cx, cy = scanner.center
                dx = px - cx
                dy = py - cy
                angle = np.arctan2(dx, -dy) % (2.0 * np.pi)  # 0 at top, clockwise
                t_event = (angle / (2.0 * np.pi)) * duration_sec
                p_val = np.sin(angle)
                norm_p = np.clip(np.hypot(dx, dy) / scanner.radius_max, 0.0, 1.0)
            elif geom == ScanGeometry.RADIAL_EXPANSION:
                cx, cy = scanner.center
                dist = np.hypot(px - cx, py - cy)
                t_event = np.clip(dist / scanner.radius_max, 0.0, 1.0) * duration_sec
                p_val = np.clip((px - cx) / scanner.radius_max, -1.0, 1.0)
                norm_p = np.clip(dist / scanner.radius_max, 0.0, 1.0)
            else:
                t_event = 0.0
                p_val = 0.0
                norm_p = 0.5

            # Event pitch
            f_raw = base_freq * ((max_freq / base_freq) ** norm_p)
            q_freq, q_midi = quantize_to_scale(
                f_raw,
                scale_name=scale_name,
                root_midi=int(np.round(frequency_to_midi(base_freq))),
            )

            # Event volume and duration
            vel = float(compress_dynamic_range(flux, method=compression_method, alpha=compression_alpha, noise_floor=0.0))
            dur_ms = float(np.clip(radius * 30.0, 50.0, 400.0)) / 1000.0

            point_source_events.append({
                "time": float(t_event),
                "duration": dur_ms,
                "frequency": float(q_freq),
                "midi_note": int(q_midi),
                "velocity": float(vel),
                "pan": float(np.clip(p_val, -1.0, 1.0)),
                "instrument": "point_source_pluck",
                "layer": "point_source",
                "source_metadata": ps,
            })

        # Sort point events chronologically
        point_source_events.sort(key=lambda ev: ev["time"])

    return {
        "diffuse_events": diffuse_events,
        "point_source_events": point_source_events,
        "metadata": {
            "geometry_type": geom.value,
            "scale_name": scale_name,
            "base_freq_hz": base_freq,
            "max_freq_hz": max_freq,
            "num_diffuse_events": len(diffuse_events),
            "num_point_source_events": len(point_source_events),
            "duration_seconds": float(np.max(unique_times)) if len(unique_times) > 0 else 0.0,
        },
    }
