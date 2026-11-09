"""
Unit tests for backend/pipeline.py: Primary Data Extraction Pathway (Colorbar Parsing).
"""

import os
import tempfile
import unittest
import numpy as np
import cv2

from backend.pipeline import (
    extract_data_colorbar,
    detect_colorbar_bounding_box,
    build_colorbar_lut,
    apply_lut_to_image,
    ColorbarNotFoundError,
    load_image,
)


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


if __name__ == "__main__":
    unittest.main()
