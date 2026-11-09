"""
Unit tests for backend/pipeline.py: Primary Data Extraction Pathway (Colorbar Parsing).
"""

import os
import tempfile
import unittest
import cv2
import numpy as np
import soundfile as sf

from backend.pipeline import (
    extract_data,
    extract_data_colorbar,
    extract_data_vector_quantization,
    generate_colormap_codebook,
    detect_colorbar_bounding_box,
    build_colorbar_lut,
    apply_lut_to_image,
    ColorbarNotFoundError,
    load_image,
    preprocess_image,
)
from backend.main import run_pipeline


class TestColorbarPipeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_synthetic_colorbar_image(
        self,
        canvas_h=260,
        canvas_w=300,
        data_h=200,
        data_w=200,
        orientation="vertical",
        colormap=cv2.COLORMAP_JET,
    ):
        """
        Creates a synthetic NASA-style scientific visualization:
        - A canvas with dark background.
        - A main data viewport containing a continuous gradient (0.0 to 1.0).
        - A distinct colorbar positioned along the edge using the same colormap.
        """
        if orientation == "horizontal":
            canvas_h = 280
            canvas_w = 260

        canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)

        # Main data scalar field [0.0, 1.0]
        y_coords, x_coords = np.mgrid[0:data_h, 0:data_w]
        raw_scalar = (x_coords / float(data_w) * 0.5 + y_coords / float(data_h) * 0.5).astype(np.float32)
        raw_scalar_u8 = (raw_scalar * 255.0).astype(np.uint8)
        data_bgr = cv2.applyColorMap(raw_scalar_u8, colormap)

        data_x, data_y = 20, 20
        canvas[data_y : data_y + data_h, data_x : data_x + data_w] = data_bgr

        if orientation == "vertical":
            cb_w = 16
            cb_h = 180
            cb_x = 250
            cb_y = 30
            # Bottom is 0.0, top is 1.0
            ramp = np.linspace(255, 0, cb_h, dtype=np.uint8)[:, None]
            ramp_bar = np.repeat(ramp, cb_w, axis=1)
            canvas[cb_y : cb_y + cb_h, cb_x : cb_x + cb_w] = cv2.applyColorMap(ramp_bar, colormap)
            bbox = (cb_x, cb_y, cb_w, cb_h)
        else:
            cb_w = 180
            cb_h = 16
            cb_x = 30
            cb_y = 235
            # Left is 0.0, right is 1.0
            ramp = np.linspace(0, 255, cb_w, dtype=np.uint8)[None, :]
            ramp_bar = np.repeat(ramp, cb_h, axis=0)
            canvas[cb_y : cb_y + cb_h, cb_x : cb_x + cb_w] = cv2.applyColorMap(ramp_bar, colormap)
            bbox = (cb_x, cb_y, cb_w, cb_h)

        return canvas, bbox, (data_x, data_y, data_w, data_h), raw_scalar

    def test_extract_data_colorbar_vertical(self):
        """Test complete extraction pipeline with a vertical colorbar."""
        canvas, true_bbox, (dx, dy, dw, dh), true_scalar = self._create_synthetic_colorbar_image(
            orientation="vertical"
        )
        test_path = os.path.join(self.temp_dir.name, "test_vertical.png")
        cv2.imwrite(test_path, canvas)

        scalar_recovered, metadata = extract_data_colorbar(
            test_path, return_metadata=True
        )

        self.assertIsInstance(scalar_recovered, np.ndarray)
        self.assertEqual(scalar_recovered.shape, canvas.shape[:2])
        self.assertEqual(scalar_recovered.dtype, np.float32)

        # Verify colorbar was detected accurately
        det_x, det_y, det_w, det_h = metadata["colorbar_bbox"]
        tx, ty, tw, th = true_bbox
        self.assertAlmostEqual(det_x, tx, delta=2)
        self.assertAlmostEqual(det_y, ty, delta=2)
        self.assertAlmostEqual(det_w, tw, delta=2)
        self.assertAlmostEqual(det_h, th, delta=2)

        # Verify LUT properties
        lut_rgb = metadata["lut_rgb"]
        lut_scalars = metadata["lut_scalars"]
        self.assertEqual(lut_rgb.shape, (256, 3))
        self.assertEqual(lut_scalars.shape, (256,))
        self.assertAlmostEqual(lut_scalars[0], 0.0)
        self.assertAlmostEqual(lut_scalars[-1], 1.0)

        # Verify recovered scalar accuracy in the main data region
        recovered_data = scalar_recovered[dy : dy + dh, dx : dx + dw]
        mae = float(np.mean(np.abs(recovered_data - true_scalar)))
        self.assertLess(mae, 0.02, f"Mean absolute error {mae} exceeded 0.02")

        # Verify colorbar region is masked to 0.0
        cb_slice = scalar_recovered[det_y : det_y + det_h, det_x : det_x + det_w]
        np.testing.assert_array_equal(cb_slice, 0.0)

    def test_extract_data_colorbar_horizontal(self):
        """Test extraction pipeline with a horizontal colorbar."""
        canvas, true_bbox, (dx, dy, dw, dh), true_scalar = self._create_synthetic_colorbar_image(
            orientation="horizontal"
        )
        test_path = os.path.join(self.temp_dir.name, "test_horizontal.png")
        cv2.imwrite(test_path, canvas)

        scalar_recovered, metadata = extract_data_colorbar(
            test_path, return_metadata=True
        )

        self.assertEqual(scalar_recovered.shape, canvas.shape[:2])
        det_x, det_y, det_w, det_h = metadata["colorbar_bbox"]
        tx, ty, tw, th = true_bbox
        self.assertAlmostEqual(det_x, tx, delta=2)
        self.assertAlmostEqual(det_y, ty, delta=2)
        self.assertAlmostEqual(det_w, tw, delta=2)
        self.assertAlmostEqual(det_h, th, delta=2)

        # Verify main data area accuracy
        recovered_data = scalar_recovered[dy : dy + dh, dx : dx + dw]
        mae = float(np.mean(np.abs(recovered_data - true_scalar)))
        self.assertLess(mae, 0.02, f"Mean absolute error {mae} exceeded 0.02")

    def test_different_colormaps(self):
        """Test data extraction with Viridis and Turbo colormaps."""
        for cm in (cv2.COLORMAP_VIRIDIS, cv2.COLORMAP_TURBO):
            canvas, _, (dx, dy, dw, dh), true_scalar = self._create_synthetic_colorbar_image(
                colormap=cm
            )
            scalar_map = extract_data_colorbar(canvas)
            recovered_data = scalar_map[dy : dy + dh, dx : dx + dw]
            mae = float(np.mean(np.abs(recovered_data - true_scalar)))
            self.assertLess(mae, 0.02)

    def test_rgb_color_space(self):
        """Test extraction with RGB distance matching instead of LAB."""
        canvas, _, (dx, dy, dw, dh), true_scalar = self._create_synthetic_colorbar_image()
        scalar_map = extract_data_colorbar(canvas, color_space="RGB")
        recovered_data = scalar_map[dy : dy + dh, dx : dx + dw]
        mae = float(np.mean(np.abs(recovered_data - true_scalar)))
        self.assertLess(mae, 0.02)

    def test_mask_colorbar_false(self):
        """Test that mask_colorbar=False preserves non-zero values in the colorbar region."""
        canvas, _, _, _ = self._create_synthetic_colorbar_image()
        scalar_map, meta = extract_data_colorbar(canvas, mask_colorbar=False, return_metadata=True)
        bx, by, bw, bh = meta["colorbar_bbox"]
        cb_slice = scalar_map[by : by + bh, bx : bx + bw]
        self.assertGreater(float(np.mean(cb_slice)), 0.1)

    def test_custom_hsv_thresholds(self):
        """Test providing explicit custom HSV threshold ranges."""
        canvas, true_bbox, _, _ = self._create_synthetic_colorbar_image()
        hsv_lower = np.array([0, 30, 30], dtype=np.uint8)
        hsv_upper = np.array([180, 255, 255], dtype=np.uint8)
        _, meta = extract_data_colorbar(
            canvas, hsv_lower=hsv_lower, hsv_upper=hsv_upper, return_metadata=True
        )
        self.assertEqual(meta["colorbar_bbox"], true_bbox)

    def test_missing_colorbar_raises_error(self):
        """Test error handling when no colorbar is present in the image."""
        gray_image = np.ones((100, 100, 3), dtype=np.uint8) * 128
        test_path = os.path.join(self.temp_dir.name, "no_colorbar.png")
        cv2.imwrite(test_path, gray_image)

        with self.assertRaises(ColorbarNotFoundError):
            extract_data_colorbar(test_path)

    def test_missing_file_raises_error(self):
        """Test error handling for non-existent image paths."""
        with self.assertRaises(FileNotFoundError):
            extract_data_colorbar("non_existent_file_path_xyz.png")

    def test_invalid_input_type(self):
        """Test error handling for unsupported input types."""
        with self.assertRaises(TypeError):
            extract_data_colorbar(12345)

    def test_numpy_array_input(self):
        """Test that extract_data_colorbar directly accepts NumPy arrays."""
        canvas, _, _, _ = self._create_synthetic_colorbar_image(orientation="vertical")
        result = extract_data_colorbar(canvas)
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.shape, canvas.shape[:2])


class TestVectorQuantizationPipeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_synthetic_visualization(
        self,
        height: int = 100,
        width: int = 120,
        colormap_name: str = "jet",
    ):
        """
        Creates a synthetic NASA scientific image without any colorbar or legend.
        Returns the BGR image (OpenCV format) and the true ground-truth scalar array [0, 1].
        """
        import matplotlib
        import matplotlib.cm as cm

        # Retrieve colormap
        if hasattr(matplotlib, "colormaps") and colormap_name in matplotlib.colormaps:
            cmap = matplotlib.colormaps[colormap_name]
        else:
            cmap = cm.get_cmap(colormap_name)

        # Ground truth continuous scalar field [0.0, 1.0]
        y, x = np.mgrid[0:height, 0:width]
        true_scalar = (
            (x / float(width)) * 0.6 + (y / float(height)) * 0.4
        ).astype(np.float32)

        # Map to theoretical RGBA via matplotlib colormap
        rgba = cmap(true_scalar)
        rgb_u8 = np.clip(np.round(rgba[:, :, :3] * 255.0), 0, 255).astype(np.uint8)

        # OpenCV expects BGR format
        bgr_u8 = cv2.cvtColor(rgb_u8, cv2.COLOR_RGB2BGR)
        return bgr_u8, true_scalar

    def test_generate_colormap_codebook(self):
        """Test generation of the theoretical gradient codebook via matplotlib.cm."""
        codebook_255 = generate_colormap_codebook("jet", num_samples=256, scale_to_255=True)
        self.assertEqual(codebook_255.shape, (256, 3))
        self.assertEqual(codebook_255.dtype, np.float32)
        self.assertGreaterEqual(float(codebook_255.min()), 0.0)
        self.assertLessEqual(float(codebook_255.max()), 255.0)

        # Test normalized [0.0, 1.0]
        codebook_unit = generate_colormap_codebook("jet", num_samples=256, scale_to_255=False)
        self.assertEqual(codebook_unit.shape, (256, 3))
        self.assertGreaterEqual(float(codebook_unit.min()), 0.0)
        self.assertLessEqual(float(codebook_unit.max()), 1.0)

        # Test case-insensitivity
        cb_upper = generate_colormap_codebook("JET", num_samples=64)
        self.assertEqual(cb_upper.shape, (64, 3))

        # Test invalid colormap
        with self.assertRaises(ValueError):
            generate_colormap_codebook("completely_invalid_colormap_name")

    def test_extract_data_vector_quantization_jet(self):
        """Test vector quantization data extraction on a colormapped image without colorbar."""
        bgr_img, true_scalar = self._create_synthetic_visualization(
            height=80, width=100, colormap_name="jet"
        )
        recovered = extract_data_vector_quantization(bgr_img, colormap_name="jet")

        self.assertIsInstance(recovered, np.ndarray)
        self.assertEqual(recovered.shape, true_scalar.shape)
        self.assertEqual(recovered.dtype, np.float32)
        self.assertGreaterEqual(float(recovered.min()), 0.0)
        self.assertLessEqual(float(recovered.max()), 1.0)

        # Reconstructed scalar field should match ground truth with very low MAE (< 0.02)
        mae = float(np.mean(np.abs(recovered - true_scalar)))
        self.assertLess(mae, 0.02, f"Vector Quantization MAE {mae} exceeded 0.02")

    def test_extract_data_vector_quantization_other_colormaps(self):
        """Test vector quantization across different scientific colormaps (viridis, plasma, turbo)."""
        for cm_name in ("viridis", "plasma", "turbo"):
            bgr_img, true_scalar = self._create_synthetic_visualization(
                height=60, width=80, colormap_name=cm_name
            )
            recovered = extract_data_vector_quantization(bgr_img, colormap_name=cm_name)
            mae = float(np.mean(np.abs(recovered - true_scalar)))
            self.assertLess(mae, 0.02, f"Colormap '{cm_name}' MAE {mae} exceeded 0.02")

    def test_extract_data_vector_quantization_file_path_and_metadata(self):
        """Test VQ with image file path input and metadata dictionary return."""
        bgr_img, true_scalar = self._create_synthetic_visualization(
            height=50, width=60, colormap_name="jet"
        )
        img_path = os.path.join(self.temp_dir.name, "vq_test.png")
        cv2.imwrite(img_path, bgr_img)

        recovered, metadata = extract_data_vector_quantization(
            img_path, colormap_name="jet", return_metadata=True
        )

        self.assertEqual(metadata["colormap_name"], "jet")
        self.assertEqual(metadata["method"], "vector_quantization")
        self.assertEqual(metadata["code_book"].shape, (256, 3))
        self.assertEqual(metadata["distortion"].shape, recovered.shape)
        self.assertIn("mean_distortion", metadata)
        self.assertEqual(metadata["image_shape"], (50, 60))

        mae = float(np.mean(np.abs(recovered - true_scalar)))
        self.assertLess(mae, 0.02)

    def test_extract_data_orchestrator_colorbar_primary(self):
        """Test that extract_data uses primary colorbar pathway when a colorbar is present."""
        test_case = TestColorbarPipeline()
        canvas, _, _, _ = test_case._create_synthetic_colorbar_image(orientation="vertical")

        scalar_array, meta = extract_data(canvas, return_metadata=True)
        self.assertEqual(meta["method"], "colorbar")
        self.assertIn("colorbar_bbox", meta)
        self.assertEqual(scalar_array.shape, canvas.shape[:2])

    def test_extract_data_orchestrator_fallback_to_vq(self):
        """Test that extract_data automatically falls back to VQ when no colorbar is found."""
        bgr_img, true_scalar = self._create_synthetic_visualization(
            height=60, width=70, colormap_name="jet"
        )

        # Orchestrator with auto method
        scalar_array, meta = extract_data(bgr_img, colormap_name="jet", return_metadata=True)
        self.assertEqual(meta["method"], "vector_quantization")
        self.assertIn("fallback_from_colorbar_error", meta)

        mae = float(np.mean(np.abs(scalar_array - true_scalar)))
        self.assertLess(mae, 0.02)

    def test_extract_data_orchestrator_method_selection(self):
        """Test explicit method selection in the orchestrator ('colorbar' vs 'vq')."""
        bgr_no_cb, _ = self._create_synthetic_visualization(height=50, width=50)

        # Requesting 'colorbar' only should raise ColorbarNotFoundError when missing
        with self.assertRaises(ColorbarNotFoundError):
            extract_data(bgr_no_cb, method="colorbar")

        # Explicitly requesting 'vq' should succeed
        res = extract_data(bgr_no_cb, method="vq")
        self.assertEqual(res.shape, (50, 50))

        # Invalid method should raise ValueError
        with self.assertRaises(ValueError):
            extract_data(bgr_no_cb, method="unknown_method_xyz")

    def test_main_run_pipeline(self):
        """Test backend/main.py run_pipeline end-to-end with output saving."""
        bgr_img, true_scalar = self._create_synthetic_visualization(
            height=40, width=50, colormap_name="jet"
        )
        img_path = os.path.join(self.temp_dir.name, "main_input.png")
        cv2.imwrite(img_path, bgr_img)

        out_npy = os.path.join(self.temp_dir.name, "recovered.npy")
        scalar, meta = run_pipeline(
            img_path,
            colormap_name="jet",
            output_path=out_npy,
            return_metadata=True,
        )

        self.assertTrue(os.path.isfile(out_npy))
        loaded_scalar = np.load(out_npy)
        np.testing.assert_array_almost_equal(scalar, loaded_scalar)
        self.assertEqual(meta["method"], "vector_quantization")


class TestPreprocessImage(unittest.TestCase):
    """
    Unit tests for preprocess_image (CLAHE in LAB color space & noise reduction toggles).
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_output_format_and_range(self):
        """Verify output is a normalized 0.0 to 1.0 float32 NumPy array with matching 2D shape."""
        # Test linear ramp
        y, x = np.mgrid[0:80, 0:100]
        scalar = (x / 100.0).astype(np.float32)

        out = preprocess_image(scalar)

        self.assertIsInstance(out, np.ndarray)
        self.assertEqual(out.dtype, np.float32)
        self.assertEqual(out.shape, (80, 100))
        self.assertGreaterEqual(float(out.min()), 0.0)
        self.assertLessEqual(float(out.max()), 1.0)

    def test_clahe_boosts_local_contrast(self):
        """Verify CLAHE on L channel in LAB color space boosts contrast on low-contrast regions."""
        # Low contrast region: subtle variations around 0.5
        np.random.seed(42)
        low_contrast = (0.5 + 0.03 * np.sin(np.linspace(0, 10, 100))[:, None] * np.cos(np.linspace(0, 10, 100))[None, :]).astype(np.float32)
        orig_std = float(np.std(low_contrast))

        enhanced = preprocess_image(
            low_contrast,
            apply_clahe=True,
            apply_median_blur=False,
            apply_gaussian_blur=False,
            clahe_clip_limit=3.0,
        )

        enhanced_std = float(np.std(enhanced))
        self.assertGreater(enhanced_std, orig_std * 2.0, "CLAHE failed to significantly boost contrast.")
        self.assertGreaterEqual(float(enhanced.min()), 0.0)
        self.assertLessEqual(float(enhanced.max()), 1.0)

    def test_clahe_parameters(self):
        """Verify clahe_clip_limit and clahe_tile_grid_size affect the contrast enhancement."""
        np.random.seed(42)
        low_contrast = np.random.uniform(0.45, 0.55, (64, 64)).astype(np.float32)

        out_low_clip = preprocess_image(low_contrast, clahe_clip_limit=1.0)
        out_high_clip = preprocess_image(low_contrast, clahe_clip_limit=5.0)

        std_low = float(np.std(out_low_clip))
        std_high = float(np.std(out_high_clip))
        self.assertGreaterEqual(std_high, std_low)

    def test_clahe_disabled(self):
        """Verify apply_clahe=False leaves contrast unmodified."""
        ramp = np.linspace(0.0, 1.0, 50, dtype=np.float32).reshape(5, 10)
        out = preprocess_image(ramp, apply_clahe=False, apply_median_blur=False, apply_gaussian_blur=False)
        np.testing.assert_array_almost_equal(out, ramp, decimal=2)

    def test_median_blur_salt_and_pepper_noise(self):
        """Verify cv2.medianBlur removes salt-and-pepper impulses while preserving sharp edges."""
        # Create a step edge: left half 0.2, right half 0.8
        img = np.zeros((50, 50), dtype=np.float32)
        img[:, :25] = 0.2
        img[:, 25:] = 0.8

        # Inject salt and pepper noise
        noisy = img.copy()
        noisy[10, 10] = 1.0  # Salt
        noisy[10, 40] = 0.0  # Pepper
        noisy[25, 15] = 1.0  # Salt
        noisy[35, 35] = 0.0  # Pepper

        # Preprocess with median blur enabled (no CLAHE to isolate blur)
        denoised = preprocess_image(
            noisy,
            apply_clahe=False,
            apply_median_blur=True,
            median_ksize=3,
        )

        # Check noise at spike locations was eliminated
        self.assertAlmostEqual(denoised[10, 10], 0.2, delta=0.05)
        self.assertAlmostEqual(denoised[10, 40], 0.8, delta=0.05)
        self.assertAlmostEqual(denoised[25, 15], 0.2, delta=0.05)
        self.assertAlmostEqual(denoised[35, 35], 0.8, delta=0.05)

        # Check that the sharp boundary between col 24 and col 25 is preserved
        self.assertAlmostEqual(denoised[25, 23], 0.2, delta=0.05)
        self.assertAlmostEqual(denoised[25, 26], 0.8, delta=0.05)

    def test_gaussian_blur_texture_smoothing(self):
        """Verify cv2.GaussianBlur smooths fine-grained textures and high-frequency noise."""
        np.random.seed(123)
        clean = np.ones((60, 60), dtype=np.float32) * 0.5
        noise = np.random.normal(0, 0.08, (60, 60)).astype(np.float32)
        noisy = np.clip(clean + noise, 0.0, 1.0)
        noisy_std = float(np.std(noisy - clean))

        smoothed = preprocess_image(
            noisy,
            apply_clahe=False,
            apply_gaussian_blur=True,
            gaussian_ksize=(5, 5),
            gaussian_sigma=1.5,
        )
        smoothed_std = float(np.std(smoothed - clean))

        self.assertLess(smoothed_std, noisy_std * 0.5, "GaussianBlur failed to smooth fine-grained texture.")

    def test_combined_pipeline(self):
        """Verify combined pipeline with CLAHE, medianBlur, and GaussianBlur."""
        np.random.seed(42)
        y, x = np.mgrid[0:50, 0:50]
        base = (x / 50.0).astype(np.float32)

        # Add salt-and-pepper noise and fine texture
        noisy = base.copy()
        noisy[5, 5] = 1.0
        noisy[40, 40] = 0.0
        noisy += np.random.normal(0, 0.02, (50, 50)).astype(np.float32)
        noisy = np.clip(noisy, 0.0, 1.0)

        out = preprocess_image(
            noisy,
            apply_clahe=True,
            apply_median_blur=True,
            apply_gaussian_blur=True,
            median_ksize=3,
            gaussian_ksize=(3, 3),
        )

        self.assertIsInstance(out, np.ndarray)
        self.assertEqual(out.dtype, np.float32)
        self.assertEqual(out.shape, (50, 50))
        self.assertGreaterEqual(float(out.min()), 0.0)
        self.assertLessEqual(float(out.max()), 1.0)
        # Salt noise spike eliminated
        self.assertLess(float(out[5, 5]), 0.6)

    def test_parameter_aliases(self):
        """Verify parameter aliases (clahe, median_blur, gaussian_blur, etc.) work properly."""
        arr = np.linspace(0.0, 1.0, 900, dtype=np.float32).reshape(30, 30)

        out = preprocess_image(
            arr,
            clahe=True,
            median_blur=True,
            gaussian_blur=True,
            clip_limit=3.0,
            grid_size=(4, 4),
            median_kernel_size=3,
            gaussian_kernel_size=3,
            sigma=1.0,
        )
        self.assertEqual(out.shape, (30, 30))
        self.assertEqual(out.dtype, np.float32)

    def test_return_metadata(self):
        """Verify return_metadata=True returns a structured dictionary."""
        arr = np.random.uniform(0.2, 0.8, (40, 40)).astype(np.float32)
        res, meta = preprocess_image(
            arr,
            apply_clahe=True,
            apply_median_blur=True,
            apply_gaussian_blur=True,
            return_metadata=True,
        )

        self.assertIsInstance(meta, dict)
        self.assertTrue(meta["apply_clahe"])
        self.assertTrue(meta["apply_median_blur"])
        self.assertTrue(meta["apply_gaussian_blur"])
        self.assertEqual(meta["input_shape"], (40, 40))
        self.assertEqual(meta["output_shape"], (40, 40))
        self.assertIn("min_value", meta)
        self.assertIn("max_value", meta)
        self.assertIn("mean_value", meta)
        self.assertIn("std_value", meta)

    def test_uint8_and_3d_inputs(self):
        """Verify handling of uint8 arrays and 3D BGR arrays."""
        # 2D uint8
        u8_img = np.random.randint(0, 256, (30, 30), dtype=np.uint8)
        out_u8 = preprocess_image(u8_img)
        self.assertEqual(out_u8.dtype, np.float32)
        self.assertEqual(out_u8.shape, (30, 30))
        self.assertGreaterEqual(float(out_u8.min()), 0.0)
        self.assertLessEqual(float(out_u8.max()), 1.0)

        # 3D BGR uint8
        bgr_img = np.random.randint(0, 256, (30, 30, 3), dtype=np.uint8)
        out_bgr = preprocess_image(bgr_img)
        self.assertEqual(out_bgr.dtype, np.float32)
        self.assertEqual(out_bgr.shape, (30, 30))

        # File path
        test_path = os.path.join(self.temp_dir.name, "test_pre.png")
        cv2.imwrite(test_path, bgr_img)
        out_file = preprocess_image(test_path)
        self.assertEqual(out_file.dtype, np.float32)
        self.assertEqual(out_file.shape, (30, 30))

    def test_invalid_parameters_raise_errors(self):
        """Verify appropriate errors are raised for invalid inputs or parameters."""
        arr = np.zeros((20, 20), dtype=np.float32)

        # Invalid input type
        with self.assertRaises(TypeError):
            preprocess_image(12345)

        # Empty array
        with self.assertRaises(ValueError):
            preprocess_image(np.array([]))

        # 1D array
        with self.assertRaises(ValueError):
            preprocess_image(np.zeros(20))

        # Even median_ksize
        with self.assertRaises(ValueError):
            preprocess_image(arr, apply_median_blur=True, median_ksize=4)

        # Invalid gaussian_ksize
        with self.assertRaises(ValueError):
            preprocess_image(arr, apply_gaussian_blur=True, gaussian_ksize=(4, 4))

        # Invalid clahe_clip_limit
        with self.assertRaises(ValueError):
            preprocess_image(arr, apply_clahe=True, clahe_clip_limit=0.0)

        # Non-existent file path
        with self.assertRaises(FileNotFoundError):
            preprocess_image("non_existent_image_path_12345.png")

    def test_run_pipeline_integration_with_preprocess(self):
        """Verify backend/main.py run_pipeline works with preprocess=True."""
        canvas = np.zeros((100, 100, 3), dtype=np.uint8)
        canvas[20:80, 20:80] = 128
        test_path = os.path.join(self.temp_dir.name, "pipeline_prep.png")
        cv2.imwrite(test_path, canvas)

        scalar, meta = run_pipeline(
            test_path,
            method="vq",
            colormap_name="jet",
            preprocess=True,
            return_metadata=True,
        )
        self.assertIsInstance(scalar, np.ndarray)
        self.assertEqual(scalar.dtype, np.float32)
        self.assertEqual(scalar.shape, (100, 100))
        self.assertIn("preprocessing", meta)
        self.assertTrue(meta["preprocessing"]["apply_clahe"])

    def test_run_pipeline_integration_with_sonification(self):
        """Verify backend/main.py run_pipeline works with audio_output_path and sonification."""
        canvas = np.zeros((60, 60, 3), dtype=np.uint8)
        canvas[15:45, 15:45] = 200
        test_path = os.path.join(self.temp_dir.name, "pipeline_sonif.png")
        audio_path = os.path.join(self.temp_dir.name, "sonif.wav")
        timeline_path = os.path.join(self.temp_dir.name, "timeline.json")
        cv2.imwrite(test_path, canvas)

        scalar, meta = run_pipeline(
            test_path,
            method="vq",
            colormap_name="jet",
            preprocess=False,
            audio_output_path=audio_path,
            timeline_output_path=timeline_path,
            duration=1.0,
            return_metadata=True,
        )
        self.assertIn("sonification", meta)
        self.assertTrue(os.path.exists(audio_path))
        self.assertTrue(os.path.exists(timeline_path))
        info = sf.info(audio_path)
        self.assertEqual(info.channels, 2)
        self.assertEqual(info.samplerate, 44100)


if __name__ == "__main__":
    unittest.main()
