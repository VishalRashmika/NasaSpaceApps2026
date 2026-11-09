"""
Unit tests for backend/morphology.py: Morphological Feature Separation (Diffuse vs. Point Sources).
"""

import unittest
import numpy as np

from backend.morphology import (
    MorphologyError,
    detect_point_sources,
    detect_point_sources_blob,
    detect_point_sources_contours,
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


class TestDetectPointSources(unittest.TestCase):
    """Test suite for detect_point_sources, detect_point_sources_blob, and detect_point_sources_contours."""

    def test_detect_point_sources_blob_keys_and_types(self):
        """Verify returned list of dictionaries structure, keys, and standard Python types."""
        # Create an image with a clear circular spot
        img = np.zeros((100, 100), dtype=np.float32)
        y, x = np.mgrid[0:100, 0:100]
        img += 0.9 * np.exp(-((x - 50) ** 2 + (y - 50) ** 2) / 12.0).astype(np.float32)

        results = detect_point_sources(img, method="blob")
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

        ps = results[0]
        self.assertIsInstance(ps, dict)

        # Expected keys from requirements
        for key in ["x", "y", "radius", "flux", "area", "perimeter", "center", "peak_intensity", "method"]:
            self.assertIn(key, ps)

        self.assertIsInstance(ps["x"], float)
        self.assertIsInstance(ps["y"], float)
        self.assertIsInstance(ps["radius"], float)
        self.assertIsInstance(ps["flux"], float)
        self.assertIsInstance(ps["area"], float)
        self.assertIsInstance(ps["perimeter"], float)
        self.assertIsInstance(ps["center"], tuple)
        self.assertEqual(len(ps["center"]), 2)
        self.assertEqual(ps["method"], "blob")

    def test_detect_point_sources_spatial_and_photometric_accuracy(self):
        """
        Verify that detected (x, y), radius, and peak flux match ground truth
        for multiple discrete point sources.
        """
        img = np.zeros((150, 150), dtype=np.float32)
        y, x = np.mgrid[0:150, 0:150]

        # Ground truth point sources: (cx, cy), peak intensity, sigma_sq
        targets = [
            (40.0, 45.0, 0.95, 10.0),
            (110.0, 100.0, 0.80, 15.0),
        ]

        for cx, cy, peak, sig_sq in targets:
            img += peak * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / sig_sq).astype(np.float32)
        img = np.clip(img, 0.0, 1.0)

        results = detect_point_sources(img, method="blob", min_threshold=0.1, max_threshold=1.0)
        self.assertEqual(len(results), 2)

        # Match each detected source to nearest ground truth target
        for cx, cy, peak, _ in targets:
            matched = min(results, key=lambda s: (s["x"] - cx) ** 2 + (s["y"] - cy) ** 2)
            dist = np.sqrt((matched["x"] - cx) ** 2 + (matched["y"] - cy) ** 2)
            self.assertLess(dist, 1.5, f"Centroid ({matched['x']}, {matched['y']}) should match ({cx}, {cy})")
            self.assertAlmostEqual(matched["flux"], peak, delta=0.08)
            self.assertGreater(matched["radius"], 1.0)

    def test_detect_point_sources_contours_irregular_shapes(self):
        """
        Verify cv2.findContours alternative correctly calculates area and perimeter
        for irregularly shaped point sources.
        """
        img = np.zeros((120, 120), dtype=np.float32)

        # Irregular L-shaped / bean point source
        img[30:50, 30:45] = 0.85
        img[45:60, 30:60] = 0.90
        img[40, 35] = 0.98  # peak

        results = detect_point_sources(img, method="contours", threshold=0.2)
        self.assertGreater(len(results), 0)

        ps = results[0]
        self.assertEqual(ps["method"], "contours")
        self.assertIn("area", ps)
        self.assertIn("perimeter", ps)

        # Area and perimeter must be positive and non-zero
        self.assertGreater(ps["area"], 50.0)
        self.assertGreater(ps["perimeter"], 20.0)
        # Peak intensity must reflect the peak inside the shape
        self.assertAlmostEqual(ps["flux"], 0.98, places=2)
        # Center should be inside the bounding box
        self.assertTrue(30 <= ps["x"] <= 60)
        self.assertTrue(30 <= ps["y"] <= 60)

    def test_filter_by_area(self):
        """Verify min_area and max_area filtering."""
        import cv2

        img = np.zeros((120, 120), dtype=np.float32)
        # Tiny 2x2 spot (area ~1.5)
        img[20:22, 20:22] = 0.9
        # Large disc of radius 12 (area ~450)
        cv2.circle(img, (80, 80), 12, 0.85, -1)

        # With min_area=50: the tiny spot is filtered out, only large disc is kept
        res_large = detect_point_sources(img, method="blob", min_area=50.0)
        self.assertEqual(len(res_large), 1)
        self.assertGreater(res_large[0]["x"], 60)

        # With max_area=10: large disc is filtered out, tiny spot is kept
        res_tiny = detect_point_sources(img, method="blob", min_area=0.5, max_area=10.0)
        self.assertEqual(len(res_tiny), 1)
        self.assertLess(res_tiny[0]["x"], 30)

    def test_threshold_formats_and_aliases(self):
        """Verify normalized [0.0, 1.0] thresholds, 8-bit [0, 255] thresholds, and camelCase aliases."""
        img = np.zeros((100, 100), dtype=np.float32)
        y, x = np.mgrid[0:100, 0:100]
        img += 0.9 * np.exp(-((x - 50) ** 2 + (y - 50) ** 2) / 10.0).astype(np.float32)

        # Normalized float thresholds
        res1 = detect_point_sources(img, min_threshold=0.1, max_threshold=0.95)
        self.assertEqual(len(res1), 1)

        # 8-bit uint8 thresholds
        res2 = detect_point_sources(img, min_threshold=25.0, max_threshold=240.0)
        self.assertEqual(len(res2), 1)

        # camelCase parameter aliases
        res3 = detect_point_sources(
            img,
            minThreshold=25.0,
            maxThreshold=240.0,
            filterByArea=True,
            minArea=2.0,
            maxArea=5000.0,
        )
        self.assertEqual(len(res3), 1)

    def test_contours_threshold_modes(self):
        """Verify contours threshold parameter with float value and 'otsu'."""
        img = np.zeros((100, 100), dtype=np.float32)
        img[30:60, 30:60] = 0.85

        # Explicit threshold
        res_explicit = detect_point_sources(img, method="contours", threshold=0.3)
        self.assertEqual(len(res_explicit), 1)

        # Otsu's threshold
        res_otsu = detect_point_sources(img, method="contours", threshold="otsu")
        self.assertEqual(len(res_otsu), 1)

    def test_empty_and_flat_images(self):
        """Verify all-zeros and uniform images return empty lists."""
        zeros_img = np.zeros((80, 80), dtype=np.float32)
        self.assertEqual(detect_point_sources(zeros_img, method="blob"), [])
        self.assertEqual(detect_point_sources(zeros_img, method="contours"), [])

        flat_img = np.full((80, 80), 0.5, dtype=np.float32)
        # Uniform field has no localized point sources
        self.assertEqual(detect_point_sources(flat_img, method="blob"), [])

    def test_sorting_options(self):
        """Verify sorting by flux, x, area."""
        img = np.zeros((100, 100), dtype=np.float32)
        # 3 spots with varying flux and x coordinates
        img[30:35, 20:25] = 0.50  # x=22, flux=0.5
        img[30:35, 70:75] = 0.95  # x=72, flux=0.95
        img[30:35, 45:50] = 0.75  # x=47, flux=0.75

        # Sort by flux (descending)
        by_flux = detect_point_sources(img, method="blob", sort_by="flux")
        fluxes = [s["flux"] for s in by_flux]
        self.assertEqual(fluxes, sorted(fluxes, reverse=True))

        # Sort by x (ascending)
        by_x = detect_point_sources(img, method="blob", sort_by="x")
        xs = [s["x"] for s in by_x]
        self.assertEqual(xs, sorted(xs))

    def test_invalid_inputs_and_error_handling(self):
        """Verify exception handling for invalid inputs and parameters."""
        valid_img = np.zeros((50, 50), dtype=np.float32)

        # None input
        with self.assertRaises(TypeError):
            detect_point_sources(None)

        # Empty array
        with self.assertRaises(ValueError):
            detect_point_sources(np.array([]))

        # 1D array
        with self.assertRaises(ValueError):
            detect_point_sources(np.zeros(50, dtype=np.float32))

        # Unknown method
        with self.assertRaises(ValueError):
            detect_point_sources(valid_img, method="unsupported_method")

        # min_threshold >= max_threshold
        with self.assertRaises(ValueError):
            detect_point_sources(valid_img, min_threshold=200, max_threshold=50)

        # min_area > max_area
        with self.assertRaises(ValueError):
            detect_point_sources(valid_img, min_area=500, max_area=50)

    def test_separate_features_detect_sources_integration(self):
        """Verify separate_features seamlessly integrates with detect_point_sources."""
        h, w = 100, 100
        y, x = np.mgrid[0:h, 0:w]
        background = (0.2 + 0.1 * (x / 100.0)).astype(np.float32)
        hotspot = 0.9 * np.exp(-((x - 50) ** 2 + (y - 50) ** 2) / 8.0).astype(np.float32)
        composite = np.clip(background + hotspot, 0.0, 1.0)

        res = separate_features(composite, kernel_size=(51, 51), detect_sources=True)
        self.assertIn("point_sources", res)
        self.assertIsInstance(res["point_sources"], list)
        self.assertGreater(len(res["point_sources"]), 0)

        ps = res["point_sources"][0]
        self.assertAlmostEqual(ps["x"], 50.0, delta=1.5)
        self.assertAlmostEqual(ps["y"], 50.0, delta=1.5)
        self.assertGreater(ps["flux"], 0.8)

    def test_direct_helper_functions(self):
        """Verify detect_point_sources_blob and detect_point_sources_contours directly."""
        img = np.zeros((80, 80), dtype=np.float32)
        img[38:43, 38:43] = 0.9

        blobs = detect_point_sources_blob(img)
        self.assertIsInstance(blobs, list)
        self.assertGreater(len(blobs), 0)
        self.assertEqual(blobs[0]["method"], "blob")

        contours = detect_point_sources_contours(img)
        self.assertIsInstance(contours, list)
        self.assertGreater(len(contours), 0)
        self.assertEqual(contours[0]["method"], "contours")

    def test_run_pipeline_with_detect_sources(self):
        """Verify run_pipeline with detect_sources=True extracts point sources into metadata."""
        import tempfile
        import os
        import cv2
        from backend.main import run_pipeline

        with tempfile.TemporaryDirectory() as temp_dir:
            canvas = np.zeros((100, 100, 3), dtype=np.uint8)
            canvas[20:80, 20:80] = 120
            # Hotspot
            cv2.circle(canvas, (50, 50), 4, (255, 255, 255), -1)
            test_path = os.path.join(temp_dir, "pipeline_sources.png")
            cv2.imwrite(test_path, canvas)

            scalar, meta = run_pipeline(
                test_path,
                method="vq",
                colormap_name="jet",
                separate_morphology=True,
                detect_sources=True,
                return_metadata=True,
            )

            self.assertIn("morphology", meta)
            self.assertIn("point_sources", meta["morphology"])
            sources = meta["morphology"]["point_sources"]
            self.assertIsInstance(sources, list)
            self.assertGreater(len(sources), 0)
            self.assertIn("x", sources[0])
            self.assertIn("y", sources[0])
            self.assertIn("flux", sources[0])
            self.assertIn("radius", sources[0])


if __name__ == "__main__":
    unittest.main()
