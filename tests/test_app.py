"""
Unit tests for backend/app.py: Streamlit Sonification Application & Science vs. Music Duality.
"""

import io
import json
import unittest
import numpy as np

from backend.app import compute_duality_parameters, generate_sample_image
from backend.pipeline import extract_data
from backend.scanner import generate_scan_path, map_parameters
from backend.synthesizer import export_json_timeline, synthesize_wav


class TestStreamlitAppDuality(unittest.TestCase):
    """Test suite for the Science vs. Music slider and parameter translation."""

    def test_pure_science_mode_at_zero(self):
        """Slider at 0 (Science): Inharmonic timbre, raw dynamic range, unquantized microtones, unlimited polyphony."""
        params = compute_duality_parameters(0)

        self.assertEqual(params["alpha"], 0.0)
        self.assertFalse(params["quantize_notes"], "Science mode must disable musical scale quantization")
        self.assertEqual(params["compression_method"], "linear", "Science mode must use raw linear dynamic range")
        self.assertEqual(params["noise_floor"], 0.0, "Science mode must have 0% noise-floor gate")
        self.assertEqual(params["diffuse_waveform"], "inharmonic", "Science mode must use inharmonic timbre")
        self.assertEqual(params["point_source_instrument"], "ping", "Science mode must use inharmonic ping sample")
        self.assertIsNone(params["max_polyphony"], "Science mode must not throttle polyphony")
        self.assertFalse(params["consolidate_notes"])

    def test_pure_music_mode_at_hundred(self):
        """Slider at 100 (Music): Rich warm timbres, quantized scales, arcsinh compression, throttled polyphony."""
        params = compute_duality_parameters(100)

        self.assertEqual(params["alpha"], 1.0)
        self.assertTrue(params["quantize_notes"], "Music mode must enforce musical scale quantization")
        self.assertEqual(params["compression_method"], "arcsinh", "Music mode must use arcsinh dynamic compression")
        self.assertAlmostEqual(params["noise_floor"], 0.10, places=3, msg="Music mode must gate <10% luminance")
        self.assertEqual(params["diffuse_waveform"], "blend", "Music mode must use rich warm pad timbre")
        self.assertEqual(params["point_source_instrument"], "pluck", "Music mode must use warm pluck sample")
        self.assertEqual(params["max_polyphony"], 4, "Music mode must throttle polyphony to top voices")
        self.assertTrue(params["consolidate_notes"], "Music mode must consolidate duplicate pitch classes")

    def test_balanced_duality_at_fifty(self):
        """Slider at 50: Balanced hybrid configuration."""
        params = compute_duality_parameters(50)

        self.assertEqual(params["alpha"], 0.5)
        self.assertTrue(params["quantize_notes"])
        self.assertEqual(params["compression_method"], "arcsinh")
        self.assertAlmostEqual(params["noise_floor"], 0.05, places=3)
        self.assertEqual(params["diffuse_waveform"], "blend")
        self.assertEqual(params["max_polyphony"], 8)
        self.assertTrue(params["consolidate_notes"])

    def test_sample_image_generation(self):
        """Verify synthetic sample image generation for rapid UI testing."""
        temp_img = generate_sample_image("temperature")
        self.assertIsInstance(temp_img, np.ndarray)
        self.assertEqual(temp_img.ndim, 3)
        self.assertEqual(temp_img.shape[2], 3)
        self.assertEqual(temp_img.dtype, np.uint8)

        cyclone_img = generate_sample_image("radar_cyclone")
        self.assertIsInstance(cyclone_img, np.ndarray)
        self.assertEqual(cyclone_img.ndim, 3)
        self.assertEqual(cyclone_img.shape[2], 3)
        self.assertEqual(cyclone_img.dtype, np.uint8)

    def test_end_to_end_science_pipeline(self):
        """Verify complete pipeline execution under Pure Science mode."""
        img = generate_sample_image("temperature")
        scalar = extract_data(img, method="auto")
        h, w = scalar.shape[:2]

        scan_path = generate_scan_path("horizontal_sweep", w, h, duration_seconds=2.0)
        science_duality = compute_duality_parameters(0)

        events = map_parameters(
            scan_path=scan_path,
            scalar_array=scalar,
            scale_name="c_major_pentatonic",
            noise_floor=science_duality["noise_floor"],
            compression_method=science_duality["compression_method"],
            compression_alpha=science_duality["compression_alpha"],
            quantize_notes=science_duality["quantize_notes"],
            max_polyphony=science_duality["max_polyphony"],
            consolidate_notes=science_duality["consolidate_notes"],
            diffuse_waveform=science_duality["diffuse_waveform"],
            point_source_instrument=science_duality["point_source_instrument"],
        )

        self.assertGreater(len(events), 0)
        # Verify inharmonic waveform tag on events
        self.assertEqual(events[0].get("waveform"), "inharmonic")

        # Verify WAV synthesis to stream
        buf = io.BytesIO()
        synthesize_wav(events, output_path=buf, diffuse_waveform=science_duality["diffuse_waveform"], duration=2.0)
        self.assertGreater(len(buf.getvalue()), 1000)

        # Verify JSON timeline blueprint export
        timeline = export_json_timeline(events, scale_name="c_major_pentatonic", scan_geometry="horizontal_sweep")
        self.assertIn("events", timeline)
        self.assertIn("metadata", timeline)

    def test_end_to_end_music_pipeline(self):
        """Verify complete pipeline execution under Pure Music mode."""
        img = generate_sample_image("temperature")
        scalar = extract_data(img, method="auto")
        h, w = scalar.shape[:2]

        scan_path = generate_scan_path("horizontal_sweep", w, h, duration_seconds=2.0)
        music_duality = compute_duality_parameters(100)

        events = map_parameters(
            scan_path=scan_path,
            scalar_array=scalar,
            scale_name="c_major_pentatonic",
            noise_floor=music_duality["noise_floor"],
            compression_method=music_duality["compression_method"],
            compression_alpha=music_duality["compression_alpha"],
            quantize_notes=music_duality["quantize_notes"],
            max_polyphony=music_duality["max_polyphony"],
            consolidate_notes=music_duality["consolidate_notes"],
            diffuse_waveform=music_duality["diffuse_waveform"],
            point_source_instrument=music_duality["point_source_instrument"],
        )

        self.assertGreater(len(events), 0)
        # Verify polyphony throttling: count events per time slice
        time_counts = {}
        for ev in events:
            if ev.get("layer") == "diffuse":
                t = round(ev["time"], 4)
                time_counts[t] = time_counts.get(t, 0) + 1

        for t, count in time_counts.items():
            self.assertLessEqual(count, 4, f"Time slice {t} exceeded polyphony throttle limit of 4")

        # Verify WAV synthesis to stream
        buf = io.BytesIO()
        synthesize_wav(events, output_path=buf, diffuse_waveform=music_duality["diffuse_waveform"], duration=2.0)
        self.assertGreater(len(buf.getvalue()), 1000)


if __name__ == "__main__":
    unittest.main()
