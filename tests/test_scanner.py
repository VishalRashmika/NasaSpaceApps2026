"""
Unit tests for backend/scanner.py: Chandra-Style Geometric Playheads & Scan Path Generation.
"""

import unittest
import numpy as np

from backend.scanner import (
    DEFAULT_CHANNEL_REGISTERS,
    MUSICAL_SCALES,
    AudioEventList,
    ScanGeometry,
    ScanHead,
    compress_dynamic_range,
    frequency_to_midi,
    generate_scan_path,
    get_scale_midi_notes,
    infer_scan_geometry,
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

    def test_compress_dynamic_range_methods_and_power_law(self):
        """Verify logarithmic, arcsinh, and power-law gamma adjustments."""
        v = 0.5
        # Arcsinh vs Log vs Linear
        c_arcsinh = compress_dynamic_range(v, method="arcsinh", alpha=10.0, noise_floor=0.0)
        c_log = compress_dynamic_range(v, method="log", alpha=10.0, noise_floor=0.0)
        c_linear = compress_dynamic_range(v, method="linear", noise_floor=0.0)

        self.assertIsInstance(c_arcsinh, float)
        self.assertIsInstance(c_log, float)
        self.assertAlmostEqual(c_linear, 0.5)
        self.assertGreater(c_arcsinh, 0.0)
        self.assertGreater(c_log, 0.0)

        # Power-law curve: gamma > 1 suppresses midtones, gamma < 1 expands midtones
        c_gamma2 = compress_dynamic_range(v, method="linear", gamma=2.0, noise_floor=0.0)
        c_gamma05 = compress_dynamic_range(v, method="linear", gamma=0.5, noise_floor=0.0)
        self.assertAlmostEqual(c_gamma2, 0.25)
        self.assertAlmostEqual(c_gamma05, np.sqrt(0.5))

        # Invalid method raises ValueError
        with self.assertRaises(ValueError):
            compress_dynamic_range(v, method="unsupported_curve")

    def test_musical_quantization_various_scales(self):
        """Verify quantization across multiple scales and note array generation."""
        # Minor pentatonic: [0, 3, 5, 7, 10]
        c_min_pc = {0, 3, 5, 7, 10}
        test_freqs = [150.0, 220.0, 350.0, 500.0, 750.0]
        q_freq, q_midi = quantize_to_scale(test_freqs, scale_name="minor_pentatonic")
        for m in q_midi:
            self.assertIn(int(m) % 12, c_min_pc)

        # Blues scale: [0, 3, 5, 6, 7, 10]
        blues_pc = {0, 3, 5, 6, 7, 10}
        _, q_blues = quantize_to_scale(test_freqs, scale_name="blues")
        for m in q_blues:
            self.assertIn(int(m) % 12, blues_pc)

        # Check get_scale_midi_notes
        notes = get_scale_midi_notes("c_major_pentatonic", root_midi=48, min_midi=48, max_midi=60)
        expected_pc = {0, 2, 4, 7, 9}
        for n in notes:
            self.assertIn(int(n) % 12, expected_pc)
            self.assertGreaterEqual(n, 48)
            self.assertLessEqual(n, 60)

        # Unknown scale raises ValueError
        with self.assertRaises(ValueError):
            quantize_to_scale(440.0, scale_name="nonexistent_scale")

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

    def test_audio_event_list_interface(self):
        """Verify AudioEventList dual list-and-dict interface."""
        scalar = np.full((30, 30), 0.5, dtype=np.float32)
        coords = generate_scan_path("horizontal_sweep", 30, 30, 3.0, num_steps=5, samples_per_step=5)
        point_sources = [{"x": 15.0, "y": 15.0, "flux": 0.9, "radius": 3.0}]

        result = map_parameters(coords, scalar, point_sources=point_sources)

        # 1. Standard list behavior
        self.assertIsInstance(result, list)
        self.assertIsInstance(result, AudioEventList)
        self.assertGreater(len(result), 0)
        self.assertIsInstance(result[0], dict)

        # Can iterate like a list
        iter_count = 0
        for ev in result:
            self.assertIn("time", ev)
            iter_count += 1
        self.assertEqual(iter_count, len(result))

        # 2. Dictionary key lookup behavior
        self.assertIn("diffuse_events", result)
        self.assertIn("point_source_events", result)
        self.assertIn("metadata", result)
        self.assertIn("events", result)

        self.assertEqual(len(result["point_source_events"]), 1)
        self.assertEqual(len(result["diffuse_events"]) + len(result["point_source_events"]), len(result))

        # 3. Attribute access
        self.assertEqual(result.point_source_events, result["point_source_events"])
        self.assertEqual(result.metadata["geometry_type"], "horizontal_sweep")

        # 4. to_dict conversion
        d = result.to_dict()
        self.assertIsInstance(d, dict)
        self.assertIn("events", d)
        self.assertIn("metadata", d)

        # 5. return_dict option
        dict_result = map_parameters(coords, scalar, return_dict=True)
        self.assertIsInstance(dict_result, dict)

    def test_map_parameters_volume_noise_floor_gate(self):
        """Verify noise-floor gate mutes all luminance below 10%."""
        # Half dark (< 0.10) and half bright (0.50)
        scalar = np.full((20, 20), 0.05, dtype=np.float32)
        scalar[10:, :] = 0.50

        coords = generate_scan_path("horizontal_sweep", 20, 20, 2.0, num_steps=6, samples_per_step=6)
        result = map_parameters(coords, scalar, noise_floor=0.10)

        # Diffuse events should only exist for pixels where y >= 10 (luminance = 0.50)
        for ev in result["diffuse_events"]:
            self.assertGreater(ev["velocity"], 0.0)
            self.assertGreaterEqual(ev["y"], 9.0)

    def test_map_parameters_pitch_and_pan_mapping(self):
        """Verify pitch and pan mapping along the scanhead."""
        h, w = 30, 30
        scalar = np.full((h, w), 0.8, dtype=np.float32)
        coords = generate_scan_path("horizontal_sweep", w, h, 3.0, num_steps=5, samples_per_step=5)

        result = map_parameters(
            coords,
            scalar,
            base_freq=130.81,  # C3
            max_freq=1046.50,  # C6
            scale_name="c_major_pentatonic",
        )

        diffuse = result["diffuse_events"]
        self.assertGreater(len(diffuse), 0)

        # Check field presence in each event
        for ev in diffuse:
            self.assertIn("time", ev)
            self.assertIn("time_ms", ev)
            self.assertIn("duration", ev)
            self.assertIn("duration_ms", ev)
            self.assertIn("frequency", ev)
            self.assertIn("pitch", ev)
            self.assertIn("midi_note", ev)
            self.assertIn("velocity", ev)
            self.assertIn("amplitude", ev)
            self.assertIn("pan", ev)
            self.assertIn("instrument", ev)
            self.assertIn("instrumentId", ev)
            self.assertIn("layer", ev)
            self.assertIn("spatialPosition", ev)
            self.assertEqual(ev["layer"], "diffuse")
            self.assertEqual(ev["instrument"], "diffuse_pad")
            self.assertGreaterEqual(ev["pan"], -1.0)
            self.assertLessEqual(ev["pan"], 1.0)
            self.assertGreaterEqual(ev["frequency"], 100.0)
            self.assertLessEqual(ev["frequency"], 1200.0)
            # Pitch class in C major pentatonic
            self.assertIn(ev["midi_note"] % 12, {0, 2, 4, 7, 9})

    def test_map_parameters_all_geometries_point_source_timing(self):
        """Verify point source crossing time calculation across all 4 geometries."""
        w, h = 50, 50
        scalar = np.full((h, w), 0.2, dtype=np.float32)
        pt = [{"x": 25.0, "y": 25.0, "flux": 0.9, "radius": 3.0}]
        duration = 10.0

        for geom in ["horizontal_sweep", "vertical_sweep", "radar_sweep", "radial_expansion"]:
            coords = generate_scan_path(geom, w, h, duration, num_steps=6, samples_per_step=6)
            res = map_parameters(coords, scalar, point_sources=pt, scan_geometry=geom)

            points = res["point_source_events"]
            self.assertEqual(len(points), 1)
            p_ev = points[0]
            self.assertEqual(p_ev["instrument"], "point_source_pluck")
            self.assertEqual(p_ev["layer"], "point_source")
            self.assertGreaterEqual(p_ev["time"], 0.0)
            self.assertLessEqual(p_ev["time"], duration + 0.1)

    def test_map_parameters_diffuse_layer_and_dict_inputs(self):
        """Verify passing diffuse_layer directly and passing morphology dict."""
        diffuse = np.full((25, 25), 0.4, dtype=np.float32)
        residual = np.zeros((25, 25), dtype=np.float32)
        residual[12, 12] = 0.9  # Point source

        coords = generate_scan_path("horizontal_sweep", 25, 25, 2.5, num_steps=5, samples_per_step=5)

        # 1. Passing diffuse_layer as explicit kwarg
        res1 = map_parameters(coords, scalar_array=diffuse, diffuse_layer=diffuse)
        self.assertGreater(len(res1["diffuse_events"]), 0)

        # 2. Passing morphological separation dictionary
        morph_dict = {
            "diffuse_layer": diffuse,
            "point_source_layer": residual,
            "point_sources": [{"x": 12.0, "y": 12.0, "flux": 0.9, "radius": 3.0}],
        }
        res2 = map_parameters(coords, scalar_array=morph_dict)
        self.assertGreater(len(res2["diffuse_events"]), 0)
        self.assertEqual(len(res2["point_source_events"]), 1)

    def test_map_parameters_consolidate_notes(self):
        """Verify consolidate_notes groups duplicate MIDI notes per time slice."""
        scalar = np.full((20, 20), 0.5, dtype=np.float32)
        coords = generate_scan_path("horizontal_sweep", 20, 20, 2.0, num_steps=4, samples_per_step=50)

        # Without consolidation: 4 * 50 = 200 events
        res_raw = map_parameters(coords, scalar, consolidate_notes=False)
        # With consolidation: at most unique scale notes per slice
        res_cons = map_parameters(coords, scalar, consolidate_notes=True)

        self.assertGreater(len(res_raw["diffuse_events"]), len(res_cons["diffuse_events"]))
        self.assertGreater(len(res_cons["diffuse_events"]), 0)

    def test_map_parameters_edge_cases_and_serialization(self):
        """Verify edge cases: all-dark image, json serialization, and input validation."""
        import json

        w, h = 20, 20
        coords = generate_scan_path("horizontal_sweep", w, h, 2.0, num_steps=3, samples_per_step=3)

        # 1. All-dark image below noise floor (e.g. 0.05 < 0.10)
        dark_img = np.full((h, w), 0.05, dtype=np.float32)
        res_dark = map_parameters(coords, dark_img, noise_floor=0.10)
        self.assertEqual(len(res_dark["diffuse_events"]), 0)
        self.assertEqual(len(res_dark), 0)

        # 2. JSON serialization of AudioEventList directly and to_dict()
        bright_img = np.full((h, w), 0.5, dtype=np.float32)
        pt = [{"center_x": 10.0, "center_y": 10.0, "peak_flux": 0.9, "area": 5.0}]
        res = map_parameters(coords, bright_img, point_sources=pt)

        json_str_list = json.dumps(res)
        self.assertIsInstance(json_str_list, str)
        parsed_list = json.loads(json_str_list)
        self.assertEqual(len(parsed_list), len(res))

        json_str_dict = json.dumps(res.to_dict())
        self.assertIsInstance(json_str_dict, str)
        parsed_dict = json.loads(json_str_dict)
        self.assertIn("events", parsed_dict)
        self.assertIn("diffuse_events", parsed_dict)
        self.assertIn("point_source_events", parsed_dict)
        self.assertIn("metadata", parsed_dict)

        # 3. Input validation errors
        with self.assertRaises(ValueError):
            map_parameters(np.array([1, 2]), bright_img)  # 1D scan path
        with self.assertRaises(ValueError):
            map_parameters(coords, "not_an_array")  # Invalid scalar array
        with self.assertRaises(ValueError):
            map_parameters(coords, bright_img, scale_name="invalid_scale")

    def test_infer_scan_geometry(self):
        """Verify automatic geometry inference from scan paths."""
        w, h = 30, 30
        h_path = generate_scan_path("horizontal_sweep", w, h, 2.0)
        v_path = generate_scan_path("vertical_sweep", w, h, 2.0)
        r_path = generate_scan_path("radar_sweep", w, h, 2.0)
        rad_path = generate_scan_path("radial_expansion", w, h, 2.0)

        self.assertEqual(infer_scan_geometry(h_path, w, h), ScanGeometry.HORIZONTAL_SWEEP)
        self.assertEqual(infer_scan_geometry(v_path, w, h), ScanGeometry.VERTICAL_SWEEP)
        self.assertEqual(infer_scan_geometry(r_path, w, h), ScanGeometry.RADAR_SWEEP)
        self.assertEqual(infer_scan_geometry(rad_path, w, h), ScanGeometry.RADIAL_EXPANSION)

    def test_non_western_and_modal_scales(self):
        """Verify non-Western and modal scales (Hirajoshi, In Sen, Pelog, Slendro, Dorian)."""
        test_freq = 440.0  # A4 = MIDI 69
        for scale in ["hirajoshi", "in_sen", "pelog", "slendro", "dorian", "mixolydian"]:
            q_freq, q_midi = quantize_to_scale(test_freq, scale_name=scale)
            self.assertIsInstance(q_freq, float)
            self.assertIsInstance(q_midi, float)
            self.assertGreater(q_freq, 0.0)


if __name__ == "__main__":
    unittest.main()
