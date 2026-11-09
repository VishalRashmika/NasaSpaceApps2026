"""
Unit tests for backend/scanner.py: Chandra-Style Geometric Playheads & Scan Path Generation.
"""

import unittest
import numpy as np

from backend.scanner import (
    DEFAULT_CHANNEL_REGISTERS,
    MUSICAL_SCALES,
    ScanGeometry,
    ScanHead,
    compress_dynamic_range,
    frequency_to_midi,
    generate_scan_path,
    map_parameters,
    midi_to_frequency,
    quantize_to_scale,
)


class TestScanHeadHorizontalSweep(unittest.TestCase):
    """Test suite for horizontal sweep (Left-to-Right)."""

    def setUp(self):
        self.width = 120
        self.height = 80
        self.duration = 6.0

    def test_horizontal_sweep_shape_and_dtype(self):
        """Verify output shape (N, 3), dtype float64, and coordinate bounds."""
        coords = generate_scan_path("horizontal_sweep", self.width, self.height, self.duration)

        self.assertIsInstance(coords, np.ndarray)
        self.assertEqual(coords.dtype, np.float64)
        self.assertEqual(coords.ndim, 2)
        self.assertEqual(coords.shape[1], 3)
        # Default num_steps = width, samples_per_step = height
        self.assertEqual(coords.shape[0], self.width * self.height)

    def test_horizontal_sweep_time_and_x_progression(self):
        """Verify that time and X progress monotonically from left (0) to right (width - 1)."""
        head = ScanHead("horizontal_sweep", self.width, self.height, self.duration)
        coords = head.generate_path()

        x = coords[:, 0]
        y = coords[:, 1]
        t = coords[:, 2]

        # Time range
        self.assertAlmostEqual(t.min(), 0.0, places=5)
        self.assertAlmostEqual(t.max(), self.duration, places=5)

        # X coordinate range
        self.assertAlmostEqual(x.min(), 0.0, places=5)
        self.assertAlmostEqual(x.max(), float(self.width - 1), places=5)

        # Y coordinate range
        self.assertAlmostEqual(y.min(), 0.0, places=5)
        self.assertAlmostEqual(y.max(), float(self.height - 1), places=5)

        # At time 0, all X coords should be 0.0
        t0_mask = np.isclose(t, 0.0)
        self.assertTrue(np.allclose(x[t0_mask], 0.0))

        # At time duration, all X coords should be width - 1
        tend_mask = np.isclose(t, self.duration)
        self.assertTrue(np.allclose(x[tend_mask], float(self.width - 1)))

    def test_horizontal_sweep_custom_steps(self):
        """Verify custom num_steps and samples_per_step."""
        num_steps = 15
        samples_per_step = 25
        coords = generate_scan_path(
            "horizontal_sweep",
            self.width,
            self.height,
            self.duration,
            num_steps=num_steps,
            samples_per_step=samples_per_step,
        )
        self.assertEqual(coords.shape, (num_steps * samples_per_step, 3))


class TestScanHeadVerticalSweep(unittest.TestCase):
    """Test suite for vertical sweep (Top-to-Bottom)."""

    def setUp(self):
        self.width = 90
        self.height = 110
        self.duration = 5.0

    def test_vertical_sweep_shape_and_dtype(self):
        """Verify output shape (N, 3), dtype float64, and coordinate bounds."""
        coords = generate_scan_path("vertical_sweep", self.width, self.height, self.duration)

        self.assertIsInstance(coords, np.ndarray)
        self.assertEqual(coords.dtype, np.float64)
        self.assertEqual(coords.ndim, 2)
        self.assertEqual(coords.shape[1], 3)
        # Default num_steps = height, samples_per_step = width
        self.assertEqual(coords.shape[0], self.height * self.width)

    def test_vertical_sweep_time_and_y_progression(self):
        """Verify that time and Y progress monotonically from top (0) to bottom (height - 1)."""
        head = ScanHead("vertical_sweep", self.width, self.height, self.duration)
        coords = head.generate_path()

        x = coords[:, 0]
        y = coords[:, 1]
        t = coords[:, 2]

        # Time range
        self.assertAlmostEqual(t.min(), 0.0, places=5)
        self.assertAlmostEqual(t.max(), self.duration, places=5)

        # Y coordinate range
        self.assertAlmostEqual(y.min(), 0.0, places=5)
        self.assertAlmostEqual(y.max(), float(self.height - 1), places=5)

        # X coordinate range
        self.assertAlmostEqual(x.min(), 0.0, places=5)
        self.assertAlmostEqual(x.max(), float(self.width - 1), places=5)

        # At time 0, all Y coords should be 0.0 (top)
        t0_mask = np.isclose(t, 0.0)
        self.assertTrue(np.allclose(y[t0_mask], 0.0))

        # At time duration, all Y coords should be height - 1 (bottom)
        tend_mask = np.isclose(t, self.duration)
        self.assertTrue(np.allclose(y[tend_mask], float(self.height - 1)))


class TestScanHeadRadarSweep(unittest.TestCase):
    """Test suite for radar sweep (Clockwise polar rotation from center)."""

    def setUp(self):
        self.width = 101
        self.height = 101
        self.duration = 4.0

    def test_radar_sweep_shape_and_quadrants(self):
        """Verify clockwise rotation starting from 12 o'clock through 4 clock positions."""
        num_steps = 4  # 4 angular steps: 12 o'clock, 3 o'clock, 6 o'clock, 9 o'clock
        samples_per_step = 10
        coords = generate_scan_path(
            "radar_sweep",
            self.width,
            self.height,
            self.duration,
            num_steps=num_steps,
            samples_per_step=samples_per_step,
        )

        self.assertEqual(coords.shape, (num_steps * samples_per_step, 3))
        cx = (self.width - 1) / 2.0
        cy = (self.height - 1) / 2.0

        # Step 0 (t=0.0): 12 o'clock (straight UP: x = cx, y <= cy)
        step0_coords = coords[0:samples_per_step]
        self.assertTrue(np.allclose(step0_coords[:, 0], cx))
        self.assertTrue(np.all(step0_coords[:, 1] <= cy + 1e-5))

        # Step 1 (t=T/4): 3 o'clock (straight RIGHT: x >= cx, y = cy)
        step1_coords = coords[samples_per_step: 2 * samples_per_step]
        self.assertTrue(np.all(step1_coords[:, 0] >= cx - 1e-5))
        self.assertTrue(np.allclose(step1_coords[:, 1], cy))

        # Step 2 (t=T/2): 6 o'clock (straight DOWN: x = cx, y >= cy)
        step2_coords = coords[2 * samples_per_step: 3 * samples_per_step]
        self.assertTrue(np.allclose(step2_coords[:, 0], cx))
        self.assertTrue(np.all(step2_coords[:, 1] >= cy - 1e-5))

        # Step 3 (t=3T/4): 9 o'clock (straight LEFT: x <= cx, y = cy)
        step3_coords = coords[3 * samples_per_step: 4 * samples_per_step]
        self.assertTrue(np.all(step3_coords[:, 0] <= cx + 1e-5))
        self.assertTrue(np.allclose(step3_coords[:, 1], cy))

    def test_radar_sweep_custom_center_and_radius(self):
        """Verify custom center and maximum radius parameters."""
        custom_center = (40.0, 60.0)
        custom_radius = 25.0
        coords = generate_scan_path(
            "radar_sweep",
            self.width,
            self.height,
            self.duration,
            center=custom_center,
            radius_max=custom_radius,
            num_steps=8,
            samples_per_step=5,
        )

        # Max distance from custom_center should not exceed custom_radius
        dists = np.hypot(coords[:, 0] - custom_center[0], coords[:, 1] - custom_center[1])
        self.assertLessEqual(np.max(dists), custom_radius + 1e-5)


class TestScanHeadRadialExpansion(unittest.TestCase):
    """Test suite for radial expansion (Concentric ripples outward from center)."""

    def setUp(self):
        self.width = 101
        self.height = 101
        self.duration = 4.0

    def test_radial_expansion_radius_equals_time(self):
        """Verify that ripple radius expands linearly with time: r(t) = (t/T) * R_max."""
        num_steps = 11
        samples_per_step = 16
        coords = generate_scan_path(
            "radial_expansion",
            self.width,
            self.height,
            self.duration,
            num_steps=num_steps,
            samples_per_step=samples_per_step,
        )

        self.assertEqual(coords.shape, (num_steps * samples_per_step, 3))
        cx = (self.width - 1) / 2.0
        cy = (self.height - 1) / 2.0
        rmax = (self.width - 1) / 2.0

        # At t=0 (step 0), all points should be at center (radius 0)
        step0_coords = coords[0:samples_per_step]
        self.assertTrue(np.allclose(step0_coords[:, 0], cx))
        self.assertTrue(np.allclose(step0_coords[:, 1], cy))
        self.assertAlmostEqual(step0_coords[0, 2], 0.0)

        # For each time step, check that radial distance from center is constant for all angles
        for i in range(num_steps):
            slice_coords = coords[i * samples_per_step: (i + 1) * samples_per_step]
            t_slice = slice_coords[0, 2]
            expected_radius = (t_slice / self.duration) * rmax
            actual_radii = np.hypot(slice_coords[:, 0] - cx, slice_coords[:, 1] - cy)
            self.assertTrue(
                np.allclose(actual_radii, expected_radius, atol=1e-4),
                f"Step {i}: expected radius {expected_radius}, got {actual_radii.mean()}",
            )


class TestScanHeadClassAndAPIs(unittest.TestCase):
    """Test suite for ScanHead methods, aliases, validation, and image sampling."""

    def test_scan_geometry_aliases(self):
        """Verify that case-insensitive strings and aliases resolve correctly."""
        aliases = [
            ("horizontal", ScanGeometry.HORIZONTAL_SWEEP),
            ("HORIZONTAL_SWEEP", ScanGeometry.HORIZONTAL_SWEEP),
            ("vertical", ScanGeometry.VERTICAL_SWEEP),
            ("VERTICAL-SWEEP", ScanGeometry.VERTICAL_SWEEP),
            ("radar", ScanGeometry.RADAR_SWEEP),
            ("polar", ScanGeometry.RADAR_SWEEP),
            ("radial", ScanGeometry.RADIAL_EXPANSION),
            ("ripple", ScanGeometry.RADIAL_EXPANSION),
            ("radial_ripple", ScanGeometry.RADIAL_EXPANSION),
        ]
        for alias, expected in aliases:
            resolved = ScanGeometry.from_string(alias)
            self.assertEqual(resolved, expected)

    def test_unknown_geometry_raises(self):
        """Verify that unknown geometry names raise ValueError."""
        with self.assertRaises(ValueError):
            generate_scan_path("diagonal_sweep", 100, 100, 5.0)

        with self.assertRaises(TypeError):
            ScanGeometry.from_string(12345)  # type: ignore

    def test_invalid_dimensions_raise(self):
        """Verify invalid dimensions or negative duration raise ValueError."""
        with self.assertRaises(ValueError):
            ScanHead("horizontal_sweep", width=0, height=100, duration_seconds=5.0)

        with self.assertRaises(ValueError):
            ScanHead("horizontal_sweep", width=100, height=-5, duration_seconds=5.0)

        with self.assertRaises(ValueError):
            ScanHead("horizontal_sweep", width=100, height=100, duration_seconds=0.0)

        with self.assertRaises(ValueError):
            ScanHead("horizontal_sweep", width=100, height=100, duration_seconds=5.0, num_steps=0)

    def test_from_image_constructor(self):
        """Verify ScanHead.from_image initializes dimensions from 2D and 3D images."""
        img2d = np.zeros((40, 60), dtype=np.float32)
        head2d = ScanHead.from_image(img2d, "horizontal_sweep", duration_seconds=3.0)
        self.assertEqual(head2d.width, 60)
        self.assertEqual(head2d.height, 40)
        self.assertEqual(head2d.duration_seconds, 3.0)

        img3d = np.zeros((75, 50, 3), dtype=np.uint8)
        head3d = ScanHead.from_image(img3d, "radar_sweep", duration_seconds=8.0)
        self.assertEqual(head3d.width, 50)
        self.assertEqual(head3d.height, 75)

    def test_map_pan_range(self):
        """Verify stereo pan values are strictly within [-1.0, 1.0]."""
        for geom in ["horizontal_sweep", "vertical_sweep", "radar_sweep", "radial_expansion"]:
            head = ScanHead(geom, width=50, height=50, duration_seconds=2.0)
            coords = head.generate_path()
            pan = head.map_pan(coords)
            self.assertEqual(len(pan), len(coords))
            self.assertTrue(np.all(pan >= -1.0 - 1e-6))
            self.assertTrue(np.all(pan <= 1.0 + 1e-6))

    def test_map_pitch_normalized_range(self):
        """Verify normalized pitch values are strictly within [0.0, 1.0]."""
        for geom in ["horizontal_sweep", "vertical_sweep", "radar_sweep", "radial_expansion"]:
            head = ScanHead(geom, width=50, height=50, duration_seconds=2.0)
            coords = head.generate_path()
            pitch = head.map_pitch_normalized(coords)
            self.assertEqual(len(pitch), len(coords))
            self.assertTrue(np.all(pitch >= 0.0 - 1e-6))
            self.assertTrue(np.all(pitch <= 1.0 + 1e-6))

    def test_sample_image_bilinear_and_nearest(self):
        """Verify pixel sampling along coordinate paths."""
        img = np.arange(100, dtype=np.float32).reshape((10, 10)) / 100.0
        head = ScanHead("horizontal_sweep", width=10, height=10, duration_seconds=1.0)
        coords = head.generate_path()

        sampled_bilinear = head.sample_image(img, coords, interpolation="bilinear")
        sampled_nearest = head.sample_image(img, coords, interpolation="nearest")

        self.assertEqual(sampled_bilinear.shape, (len(coords),))
        self.assertEqual(sampled_nearest.shape, (len(coords),))
        self.assertTrue(np.all(sampled_bilinear >= 0.0))
        self.assertTrue(np.all(sampled_bilinear <= 1.0))

    def test_channel_registers_rgb(self):
        """Verify Chandra RGB channel registers (Red=Low, Green=Mid, Blue=High)."""
        head = ScanHead("radial_expansion", width=50, height=50, duration_seconds=2.0)
        registers = head.get_channel_registers()

        self.assertIn("red", registers)
        self.assertIn("green", registers)
        self.assertIn("blue", registers)

        # Frequencies should increase from Red -> Green -> Blue
        self.assertLess(registers["red"]["freq_range_hz"][0], registers["green"]["freq_range_hz"][0])
        self.assertLess(registers["green"]["freq_range_hz"][0], registers["blue"]["freq_range_hz"][0])


class TestParameterMappingAndQuantization(unittest.TestCase):
    """Test suite for musical quantization, dynamic range compression, and map_parameters."""

    def test_midi_frequency_roundtrip(self):
        """Verify roundtrip conversion between frequency in Hz and MIDI note numbers."""
        test_freqs = [130.81, 220.0, 440.0, 880.0, 1046.5]
        for f in test_freqs:
            midi = frequency_to_midi(f)
            recovered_f = midi_to_frequency(midi)
            self.assertAlmostEqual(f, recovered_f, places=2)

    def test_quantize_to_scale_c_major_pentatonic(self):
        """Verify that frequencies snap to C major pentatonic pitch classes."""
        c_penta_pitch_classes = {0, 2, 4, 7, 9}  # C, D, E, G, A
        test_freqs = [200.0, 275.0, 330.0, 450.0, 600.0, 800.0]

        q_freq, q_midi = quantize_to_scale(test_freqs, scale_name="c_major_pentatonic")
        for m in q_midi:
            pc = int(m) % 12
            self.assertIn(pc, c_penta_pitch_classes)

    def test_compress_dynamic_range_arcsinh_and_noise_floor(self):
        """Verify arcsinh compression and noise floor luminance gating."""
        intensities = np.array([0.05, 0.09, 0.10, 0.25, 0.50, 1.0])
        compressed = compress_dynamic_range(intensities, method="arcsinh", noise_floor=0.10)

        # Intensities < 0.10 should be muted (0.0)
        self.assertEqual(compressed[0], 0.0)
        self.assertEqual(compressed[1], 0.0)
        # Intensity >= 0.10 should be non-zero and monotonic
        self.assertGreater(compressed[2], 0.0)
        self.assertLess(compressed[2], compressed[3])
        self.assertLess(compressed[3], compressed[4])
        self.assertAlmostEqual(compressed[5], 1.0, places=4)

    def test_map_parameters_full_pipeline(self):
        """Verify map_parameters generates diffuse events and point source triggers."""
        # 40x40 scalar array with smooth background
        scalar = np.full((40, 40), 0.3, dtype=np.float32)
        # Add a bright point source
        scalar[20, 20] = 0.95

        coords = generate_scan_path("horizontal_sweep", 40, 40, 4.0, num_steps=10, samples_per_step=10)
        point_sources = [{"x": 20.0, "y": 20.0, "flux": 0.95, "radius": 4.0}]

        result = map_parameters(
            scan_path=coords,
            scalar_array=scalar,
            point_sources=point_sources,
            scale_name="c_major_pentatonic",
            scan_geometry="horizontal_sweep",
        )

        self.assertIn("diffuse_events", result)
        self.assertIn("point_source_events", result)
        self.assertIn("metadata", result)

        diffuse = result["diffuse_events"]
        points = result["point_source_events"]

        self.assertGreater(len(diffuse), 0)
        self.assertEqual(len(points), 1)

        # Verify point source event structure
        p_event = points[0]
        self.assertIn("time", p_event)
        self.assertIn("duration", p_event)
        self.assertIn("frequency", p_event)
        self.assertIn("midi_note", p_event)
        self.assertIn("velocity", p_event)
        self.assertIn("pan", p_event)
        self.assertEqual(p_event["instrument"], "point_source_pluck")
        self.assertEqual(p_event["layer"], "point_source")


if __name__ == "__main__":
    unittest.main()
