"""
Unit tests for backend/morphology.py: Morphological Feature Separation (Diffuse vs. Point Sources).
"""

import unittest
import numpy as np

from backend.morphology import (
    MorphologyError,
    separate_features,
)


class TestMorphologyFeatureSeparation(unittest.TestCase):
    """Test suite for separate_features in backend/morphology.py."""

    def test_separate_features_keys_and_types(self):
        """Verify return dictionary structure, keys, array shapes, and dtypes."""
        arr = np.random.uniform(0.1, 0.9, (120, 120)).astype(np.float32)
        result = separate_features(arr)

        self.assertIsInstance(result, dict)
        self.assertIn("diffuse_layer", result)
        self.assertIn("point_source_layer", result)

        diffuse = result["diffuse_layer"]
        point_sources = result["point_source_layer"]

        self.assertIsInstance(diffuse, np.ndarray)
        self.assertIsInstance(point_sources, np.ndarray)

        self.assertEqual(diffuse.shape, arr.shape)
        self.assertEqual(point_sources.shape, arr.shape)

        self.assertEqual(diffuse.dtype, np.float32)
        self.assertEqual(point_sources.dtype, np.float32)

    def test_point_source_isolation(self):
        """
        Verify that a localized hotspot superimposed on a smooth background
        is isolated into point_source_layer, while background goes to diffuse_layer.
        """
        # 100x100 canvas with a smooth low-frequency gradient [0.1 to 0.4]
        y, x = np.mgrid[0:100, 0:100]
        background = (0.1 + 0.3 * (x / 100.0)).astype(np.float32)

        # Localized hotspot (e.g. wildfire or star) at (50, 50)
        scalar = background.copy()
        scalar[50, 50] = 1.0

        result = separate_features(scalar, kernel_size=(51, 51))
        diffuse = result["diffuse_layer"]
        point_sources = result["point_source_layer"]

        # Peak of point_source_layer should be at hotspot location (50, 50)
        self.assertAlmostEqual(float(point_sources[50, 50]), 1.0, places=5)

        # Distant background should have point_source_layer values near zero
        self.assertLess(float(point_sources[10, 10]), 0.05)
        self.assertLess(float(point_sources[90, 90]), 0.05)

        # Diffuse layer should retain the smooth background trend
        self.assertLess(float(diffuse[50, 10]), float(diffuse[50, 90]))
        # Diffuse at hotspot should be slightly blurred elevation, not 1.0
        self.assertLess(float(diffuse[50, 50]), 0.45)

    def test_clipping_negative_values(self):
        """
        Verify that sub-background depressions (where scalar < diffuse)
        are clipped to zero and do not produce negative residual values.
        """
        arr = np.full((100, 100), 0.7, dtype=np.float32)
        # Create a dark depression / crater
        arr[45:55, 45:55] = 0.1

        result = separate_features(arr, kernel_size=51)
        point_sources = result["point_source_layer"]

        # Point source layer should have no negative values anywhere
        self.assertGreaterEqual(float(point_sources.min()), 0.0)
        # At the depression, original is below blurred background, so residual is clipped to 0
        self.assertEqual(float(point_sources[50, 50]), 0.0)

    def test_normalization_range(self):
        """Verify point_source_layer is strictly normalized to [0.0, 1.0]."""
        np.random.seed(123)
        arr = np.random.uniform(0.2, 0.8, (80, 80)).astype(np.float32)
        # Add discrete bright points
        arr[20, 20] = 0.95
        arr[60, 60] = 0.99

        result = separate_features(arr, kernel_size=(31, 31))
        point_sources = result["point_source_layer"]
        diffuse = result["diffuse_layer"]

        self.assertAlmostEqual(float(point_sources.min()), 0.0, places=5)
        self.assertAlmostEqual(float(point_sources.max()), 1.0, places=5)
        self.assertGreaterEqual(float(diffuse.min()), 0.0)
        self.assertLessEqual(float(diffuse.max()), 1.0)

    def test_uniform_array_no_division_by_zero(self):
        """Verify flat/uniform images do not trigger division-by-zero or NaNs."""
        flat_arr = np.full((64, 64), 0.5, dtype=np.float32)
        result = separate_features(flat_arr)

        diffuse = result["diffuse_layer"]
        point_sources = result["point_source_layer"]

        self.assertFalse(np.isnan(diffuse).any())
        self.assertFalse(np.isnan(point_sources).any())
        self.assertFalse(np.isinf(diffuse).any())
        self.assertFalse(np.isinf(point_sources).any())

        self.assertAlmostEqual(float(diffuse.mean()), 0.5, places=4)
        self.assertEqual(float(point_sources.max()), 0.0)
        self.assertEqual(float(point_sources.min()), 0.0)

    def test_all_zeros_and_all_ones(self):
        """Verify boundary arrays of all zeros and all ones."""
        zeros_arr = np.zeros((50, 50), dtype=np.float32)
        res_zeros = separate_features(zeros_arr)
        self.assertEqual(float(res_zeros["diffuse_layer"].max()), 0.0)
        self.assertEqual(float(res_zeros["point_source_layer"].max()), 0.0)

        ones_arr = np.ones((50, 50), dtype=np.float32)
        res_ones = separate_features(ones_arr)
        self.assertAlmostEqual(float(res_ones["diffuse_layer"].min()), 1.0, places=5)
        self.assertEqual(float(res_ones["point_source_layer"].max()), 0.0)

    def test_kernel_size_parameter_formats(self):
        """Verify kernel_size accepts int, tuple, non-square, and aliases."""
        arr = np.random.uniform(0.0, 1.0, (70, 70)).astype(np.float32)

        # Integer kernel_size
        res_int = separate_features(arr, kernel_size=31)
        self.assertEqual(res_int["diffuse_layer"].shape, (70, 70))

        # Tuple kernel_size
        res_tuple = separate_features(arr, kernel_size=(31, 31))
        np.testing.assert_array_almost_equal(
            res_int["diffuse_layer"], res_tuple["diffuse_layer"]
        )

        # Non-square kernel
        res_rect = separate_features(arr, kernel_size=(25, 41))
        self.assertEqual(res_rect["diffuse_layer"].shape, (70, 70))

        # Alias ksize
        res_alias = separate_features(arr, ksize=21)
        self.assertEqual(res_alias["point_source_layer"].shape, (70, 70))

        # Alias gaussian_ksize
        res_alias2 = separate_features(arr, gaussian_ksize=(21, 21))
        np.testing.assert_array_almost_equal(
            res_alias["diffuse_layer"], res_alias2["diffuse_layer"]
        )

    def test_sigma_parameters(self):
        """Verify sigma and sigma_x / sigma_y custom parameters."""
        arr = np.zeros((80, 80), dtype=np.float32)
        arr[40, 40] = 1.0

        res_sigma1 = separate_features(arr, kernel_size=41, sigma=2.0)
        res_sigma2 = separate_features(arr, kernel_size=41, sigma=8.0)

        # Larger sigma produces more spread-out blur (lower peak at center)
        diff1_peak = float(res_sigma1["diffuse_layer"][40, 40])
        diff2_peak = float(res_sigma2["diffuse_layer"][40, 40])
        self.assertGreater(diff1_peak, diff2_peak)

    def test_input_type_conversions(self):
        """Verify handling of uint8, float64, 3D (H, W, 1), and list of lists."""
        # uint8 2D
        u8_arr = np.random.randint(0, 256, (50, 50), dtype=np.uint8)
        res_u8 = separate_features(u8_arr)
        self.assertEqual(res_u8["diffuse_layer"].dtype, np.float32)
        self.assertGreaterEqual(float(res_u8["diffuse_layer"].min()), 0.0)
        self.assertLessEqual(float(res_u8["diffuse_layer"].max()), 1.0)

        # float64 2D
        f64_arr = np.random.rand(50, 50).astype(np.float64)
        res_f64 = separate_features(f64_arr)
        self.assertEqual(res_f64["diffuse_layer"].dtype, np.float32)

        # 3D with 1 channel
        ch1_arr = np.random.rand(50, 50, 1).astype(np.float32)
        res_ch1 = separate_features(ch1_arr)
        self.assertEqual(res_ch1["diffuse_layer"].shape, (50, 50))

        # 3D BGR image
        bgr_arr = np.random.randint(0, 256, (50, 50, 3), dtype=np.uint8)
        res_bgr = separate_features(bgr_arr)
        self.assertEqual(res_bgr["diffuse_layer"].shape, (50, 50))

        # List of lists
        list_arr = [[0.1, 0.2], [0.3, 0.4]]
        res_list = separate_features(list_arr, kernel_size=1)
        self.assertEqual(res_list["diffuse_layer"].shape, (2, 2))

    def test_invalid_parameters_raise_errors(self):
        """Verify error handling for invalid inputs and kernel sizes."""
        valid_arr = np.zeros((30, 30), dtype=np.float32)

        # None input
        with self.assertRaises(TypeError):
            separate_features(None)

        # Empty array
        with self.assertRaises(ValueError):
            separate_features(np.array([]))

        # 1D array
        with self.assertRaises(ValueError):
            separate_features(np.zeros(30, dtype=np.float32))

        # 4D array
        with self.assertRaises(ValueError):
            separate_features(np.zeros((10, 10, 3, 2), dtype=np.float32))

        # Even kernel size
        with self.assertRaises(ValueError):
            separate_features(valid_arr, kernel_size=50)

        # Even element in tuple kernel size
        with self.assertRaises(ValueError):
            separate_features(valid_arr, kernel_size=(51, 50))

        # Non-positive kernel size
        with self.assertRaises(ValueError):
            separate_features(valid_arr, kernel_size=0)
        with self.assertRaises(ValueError):
            separate_features(valid_arr, kernel_size=-5)

        # Non-integer kernel size
        with self.assertRaises(ValueError):
            separate_features(valid_arr, kernel_size="invalid")

    def test_normalize_residual_false(self):
        """Verify normalize_residual=False leaves raw clipped residual."""
        arr = np.full((60, 60), 0.4, dtype=np.float32)
        # Small hotspot with peak 0.6 (diff is 0.2 above background)
        arr[30, 30] = 0.6

        res_norm = separate_features(arr, normalize_residual=True, kernel_size=31)
        res_raw = separate_features(arr, normalize_residual=False, kernel_size=31)

        # Normalized peak reaches 1.0
        self.assertAlmostEqual(float(res_norm["point_source_layer"][30, 30]), 1.0, places=5)
        # Raw peak should be around 0.2, definitely < 0.5
        self.assertLess(float(res_raw["point_source_layer"][30, 30]), 0.3)

    def test_return_metadata(self):
        """Verify return_metadata=True includes metadata dictionary."""
        arr = np.random.uniform(0.1, 0.8, (50, 50)).astype(np.float32)
        res = separate_features(arr, kernel_size=(31, 31), return_metadata=True)

        self.assertIn("metadata", res)
        meta = res["metadata"]
        self.assertEqual(meta["kernel_size"], (31, 31))
        self.assertIn("diffuse_min", meta)
        self.assertIn("diffuse_max", meta)
        self.assertIn("point_source_min", meta)
        self.assertIn("point_source_max", meta)
        self.assertIn("raw_residual_max", meta)

    def test_chandra_wildfire_analogy_simulation(self):
        """
        Simulates the Chandra / EIC use case:
        Large diffuse cloud bands (low frequency) + discrete wildfire hotspots (high frequency).
        Verifies clean separation into the two structural stems.
        """
        h, w = 150, 150
        y, x = np.mgrid[0:h, 0:w]

        # Broad atmospheric cloud band across the field
        cloud_band = (0.2 + 0.3 * np.sin(x / 20.0) * np.cos(y / 30.0)).astype(np.float32)
        cloud_band = np.clip(cloud_band, 0.0, 1.0)

        # Wildfire hotspots (discrete localized peaks)
        hotspots = np.zeros((h, w), dtype=np.float32)
        hotspot_coords = [(35, 40), (45, 110), (120, 75)]
        for cy, cx in hotspot_coords:
            # 2D Gaussian spike
            dist_sq = (y - cy) ** 2 + (x - cx) ** 2
            hotspots += 0.8 * np.exp(-dist_sq / 8.0).astype(np.float32)

        composite = np.clip(cloud_band + hotspots, 0.0, 1.0)

        result = separate_features(composite, kernel_size=(51, 51))
        diffuse = result["diffuse_layer"]
        point_sources = result["point_source_layer"]

        # Hotspots must be prominently isolated in point_sources
        for cy, cx in hotspot_coords:
            self.assertGreater(float(point_sources[cy, cx]), 0.7)

        # Inter-hotspot regions in point_sources must have very low energy
        self.assertLess(float(point_sources[80, 80]), 0.1)

        # Diffuse layer should closely correlate with the cloud band
        diffuse_diff = np.abs(diffuse - cloud_band)
        # Mean absolute difference between diffuse layer and true cloud band should be low
        self.assertLess(float(np.mean(diffuse_diff)), 0.08)

    def test_run_pipeline_integration_with_separate_morphology(self):
        """Verify run_pipeline in backend/main.py supports separate_morphology."""
        import tempfile
        import os
        import cv2
        from backend.main import run_pipeline

        with tempfile.TemporaryDirectory() as temp_dir:
            canvas = np.zeros((100, 100, 3), dtype=np.uint8)
            canvas[20:80, 20:80] = 180
            canvas[50, 50] = 255
            test_path = os.path.join(temp_dir, "pipeline_morph.png")
            cv2.imwrite(test_path, canvas)

            scalar, meta = run_pipeline(
                test_path,
                method="vq",
                colormap_name="jet",
                separate_morphology=True,
                return_metadata=True,
            )

            self.assertIsInstance(scalar, np.ndarray)
            self.assertIn("morphology", meta)
            self.assertIn("diffuse_layer", meta["morphology"])
            self.assertIn("point_source_layer", meta["morphology"])
            self.assertEqual(meta["morphology"]["diffuse_layer"].shape, (100, 100))
            self.assertEqual(meta["morphology"]["point_source_layer"].shape, (100, 100))


if __name__ == "__main__":
    unittest.main()
