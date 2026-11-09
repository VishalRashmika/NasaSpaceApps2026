"""
The Earth Jukebox - Pipeline Module
Scientific sonification data extraction and image processing pipeline.

This module implements the primary pathway (Colorbar Parsing) and associated
utilities for recovering quantitative scalar datasets (0.0 to 1.0) from legacy
NASA RGB imagery without underlying metadata, mirroring the Chandra X-ray Center
methodology of assigning energies to wavelengths.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import cv2
import numpy as np

try:
    from scipy.spatial import cKDTree
except ImportError:
    cKDTree = None


class PipelineError(Exception):
    """Base exception for data extraction pipeline errors."""
    pass


class ColorbarNotFoundError(ValueError, PipelineError):
    """Raised when no valid colorbar can be located in the image."""
    pass


def load_image(image_input: Union[str, Path, np.ndarray]) -> np.ndarray:
    """
    Load an image from a filesystem path or return a copy if already an ndarray.

    Args:
        image_input: File path (str or Path) or NumPy array (BGR format).

    Returns:
        np.ndarray: BGR image array with uint8 data type.

    Raises:
        FileNotFoundError: If the specified image path does not exist.
        ValueError: If cv2.imread fails to decode the image.
        TypeError: If input type is unsupported.
    """
    if isinstance(image_input, (str, Path)):
        path_str = str(image_input)
        if not os.path.isfile(path_str):
            raise FileNotFoundError(f"Image file does not exist: {path_str}")
        img = cv2.imread(path_str)
        if img is None:
            raise ValueError(f"OpenCV failed to decode image at: {path_str}")
        return img
    elif isinstance(image_input, np.ndarray):
        if image_input.ndim != 3 or image_input.shape[2] not in (3, 4):
            raise ValueError(f"Expected 3-channel (BGR) or 4-channel image array, got shape {image_input.shape}")
        if image_input.shape[2] == 4:
            # Convert BGRA to BGR
            return cv2.cvtColor(image_input, cv2.COLOR_BGRA2BGR)
        return image_input.copy()
    else:
        raise TypeError(f"Expected file path or np.ndarray, received {type(image_input).__name__}")


def detect_colorbar_bounding_box(
    image_bgr: np.ndarray,
    hsv_lower: Optional[np.ndarray] = None,
    hsv_upper: Optional[np.ndarray] = None,
    min_aspect_ratio: float = 2.5,
    min_length: int = 25,
    min_thickness: int = 3,
    max_area_ratio: float = 0.5,
) -> Tuple[int, int, int, int]:
    """
    Locate the colorbar bounding box using perceptually uniform color thresholding
    and contour geometry analysis.

    Steps:
    1. Converts BGR to HSV and LAB color spaces.
    2. Employs cv2.inRange to isolate the saturated/gradient color spectrum of the colorbar.
    3. Employs cv2.findContours to extract candidate bounding boxes.
    4. Evaluates candidates based on aspect ratio, rectangular solidity, and color
       gradient variance along the major axis.

    Args:
        image_bgr: Input image in OpenCV BGR format.
        hsv_lower: Optional lower HSV threshold array [H, S, V].
        hsv_upper: Optional upper HSV threshold array [H, S, V].
        min_aspect_ratio: Minimum ratio of max(w, h) / min(w, h) for a valid colorbar.
        min_length: Minimum dimension along the elongated axis (pixels).
        min_thickness: Minimum dimension along the narrow axis (pixels).
        max_area_ratio: Maximum area fraction of the image a colorbar can occupy.

    Returns:
        Tuple[int, int, int, int]: Bounding box (x, y, w, h).

    Raises:
        ColorbarNotFoundError: If no contour meets the colorbar criteria.
    """
    img_h, img_w = image_bgr.shape[:2]
    total_area = float(img_h * img_w)

    # 1. Convert BGR to HSV and LAB spaces
    image_hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    image_lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)

    # 2. Use cv2.inRange to threshold and isolate the colorbar gradient
    # Default HSV threshold isolates colorful gradient regions (S >= 25, V >= 25)
    if hsv_lower is None:
        hsv_lower = np.array([0, 25, 25], dtype=np.uint8)
    if hsv_upper is None:
        hsv_upper = np.array([180, 255, 255], dtype=np.uint8)

    mask = cv2.inRange(image_hsv, hsv_lower, hsv_upper)

    # Morphological closing to bridge tick marks, fine lines, or slight gradient breaks
    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mask_closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel, iterations=2)

    # 3. Use cv2.findContours to detect candidate regions
    contours, _ = cv2.findContours(mask_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # If primary mask finds nothing, attempt a fallback in LAB chroma space
    # (handles perceptual colormaps like viridis/plasma with low HSV saturation in parts)
    if not contours:
        lab_lower = np.array([10, 100, 100], dtype=np.uint8)
        lab_upper = np.array([245, 255, 255], dtype=np.uint8)
        mask_lab = cv2.inRange(image_lab, lab_lower, lab_upper)
        mask_closed = cv2.morphologyEx(mask_lab, cv2.MORPH_CLOSE, close_kernel, iterations=2)
        contours, _ = cv2.findContours(mask_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best_bbox = None
    best_score = -1.0

    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        length = max(w, h)
        thickness = min(w, h)
        aspect_ratio = float(length) / max(1.0, float(thickness))
        bbox_area = float(w * h)
        contour_area = float(cv2.contourArea(c))

        # Size and aspect ratio filters
        if aspect_ratio < min_aspect_ratio:
            continue
        if length < min_length or thickness < min_thickness:
            continue
        if bbox_area > max_area_ratio * total_area:
            continue

        # Solidity / extent: colorbars are filled rectangles
        extent = contour_area / max(1.0, bbox_area)
        if extent < 0.45:
            continue

        # Gradient variance check:
        # A legitimate colorbar has significant color variance along its elongated length,
        # distinguishing it from uniform borders or monochrome legends.
        crop = image_bgr[y : y + h, x : x + w]
        if length == h:  # vertical
            axis_samples = np.mean(crop, axis=1)  # shape (h, 3)
        else:  # horizontal
            axis_samples = np.mean(crop, axis=0)  # shape (w, 3)

        color_std = float(np.mean(np.std(axis_samples, axis=0)))
        if color_std < 5.0:
            # Skip regions that are almost monochromatic
            continue

        # Composite score favoring elongated, solid, high-variance gradient bars
        score = aspect_ratio * (extent ** 1.5) * (color_std + 10.0)

        # Bonus for edge placement (colorbars typically reside near image borders)
        is_near_edge = (
            x <= int(0.15 * img_w)
            or (x + w) >= int(0.85 * img_w)
            or y <= int(0.15 * img_h)
            or (y + h) >= int(0.85 * img_h)
        )
        if is_near_edge:
            score *= 1.3

        if score > best_score:
            best_score = score
            best_bbox = (x, y, w, h)

    if best_bbox is None:
        raise ColorbarNotFoundError("No colorbar gradient detected in the image.")

    return best_bbox


def build_colorbar_lut(
    image_bgr: np.ndarray,
    bbox: Tuple[int, int, int, int],
    direction: str = "auto",
    num_samples: int = 256,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Sample colors along the colorbar's length to construct an RGB-to-scalar LUT
    mapping monotonically from 0.0 to 1.0.

    Args:
        image_bgr: Source image array in OpenCV BGR format.
        bbox: Bounding box tuple (x, y, w, h) of the colorbar.
        direction: Progression direction of the scalar values:
            - 'auto': Bottom-to-top for vertical, Left-to-right for horizontal.
            - 'bottom_to_top': Scalar 0.0 at bottom row, 1.0 at top row.
            - 'top_to_bottom': Scalar 0.0 at top row, 1.0 at bottom row.
            - 'left_to_right': Scalar 0.0 at left column, 1.0 at right column.
            - 'right_to_left': Scalar 0.0 at right column, 1.0 at left column.
        num_samples: Number of discrete entries in the returned LUT (default: 256).

    Returns:
        Tuple[np.ndarray, np.ndarray]:
            - lut_rgb: (num_samples, 3) float32 array of RGB colors [0, 255].
            - lut_scalars: (num_samples,) float32 array of scalar values [0.0, 1.0].
    """
    x, y, w, h = bbox
    colorbar_bgr = image_bgr[y : y + h, x : x + w]
    is_vertical = h >= w

    # Sample along central portion to prevent border line or tick mark interference
    if is_vertical:
        # Avoid outer 20% margin along width
        w_margin = max(1, int(round(w * 0.20)))
        w_start = min(w_margin, w - 1)
        w_end = max(w - w_margin, w_start + 1)
        central_slice = colorbar_bgr[:, w_start:w_end, :]  # shape (h, slice_w, 3)
        raw_bgr = np.median(central_slice, axis=1)  # shape (h, 3)

        if direction in ("auto", "bottom_to_top"):
            # Scientific convention: bottom row = min scalar (0.0), top row = max scalar (1.0)
            raw_bgr = raw_bgr[::-1]
        elif direction == "top_to_bottom":
            pass  # top row = 0.0, bottom row = 1.0
        else:
            raise ValueError(f"Invalid direction '{direction}' for vertical colorbar.")
    else:
        # Avoid outer 20% margin along height
        h_margin = max(1, int(round(h * 0.20)))
        h_start = min(h_margin, h - 1)
        h_end = max(h - h_margin, h_start + 1)
        central_slice = colorbar_bgr[h_start:h_end, :, :]  # shape (slice_h, w, 3)
        raw_bgr = np.median(central_slice, axis=0)  # shape (w, 3)

        if direction in ("auto", "left_to_right"):
            # Scientific convention: left = 0.0, right = 1.0
            pass
        elif direction == "right_to_left":
            raw_bgr = raw_bgr[::-1]
        else:
            raise ValueError(f"Invalid direction '{direction}' for horizontal colorbar.")

    # Convert sampled BGR to RGB
    raw_rgb = raw_bgr[:, ::-1].astype(np.float32)

    # Interpolate along [0.0, 1.0] to produce uniformly sampled LUT of size num_samples
    num_raw = len(raw_rgb)
    s_raw = np.linspace(0.0, 1.0, num_raw, endpoint=True)
    lut_scalars = np.linspace(0.0, 1.0, num_samples, endpoint=True, dtype=np.float32)

    lut_rgb = np.zeros((num_samples, 3), dtype=np.float32)
    for ch in range(3):
        lut_rgb[:, ch] = np.interp(lut_scalars, s_raw, raw_rgb[:, ch])

    return lut_rgb, lut_scalars


def apply_lut_to_image(
    image_bgr: np.ndarray,
    lut_rgb: np.ndarray,
    lut_scalars: np.ndarray,
    colorbar_bbox: Optional[Tuple[int, int, int, int]] = None,
    mask_colorbar: bool = True,
    color_space: str = "LAB",
) -> np.ndarray:
    """
    Apply an RGB-to-scalar LUT to an image to generate a 2D scalar field [0.0, 1.0].
    Mirrors the Chandra sonification pipeline by calculating nearest-neighbor
    color distances in a perceptually uniform space.

    Args:
        image_bgr: OpenCV BGR image array.
        lut_rgb: (N, 3) array of RGB color values in [0, 255].
        lut_scalars: (N,) array of corresponding scalar values in [0.0, 1.0].
        colorbar_bbox: Optional bounding box (x, y, w, h) of the colorbar.
        mask_colorbar: If True, sets the colorbar region in the output to 0.0.
        color_space: 'LAB' (perceptually uniform Delta-E) or 'RGB'.

    Returns:
        np.ndarray: 2D float32 array of recovered quantitative scalar values in [0.0, 1.0].
    """
    img_h, img_w = image_bgr.shape[:2]

    # Convert LUT and image to the target comparison space
    if color_space.upper() == "LAB":
        lut_rgb_u8 = np.clip(np.round(lut_rgb), 0, 255).astype(np.uint8)
        lut_lab = cv2.cvtColor(lut_rgb_u8.reshape(1, -1, 3), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
        comp_img = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
        comp_lut = lut_lab
    elif color_space.upper() == "RGB":
        comp_img = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
        comp_lut = lut_rgb.astype(np.float32)
    else:
        raise ValueError(f"Unsupported color_space '{color_space}'. Choose 'LAB' or 'RGB'.")

    flat_pixels = comp_img.reshape(-1, 3)

    # Nearest-neighbor matching via SciPy cKDTree (high-performance C++ implementation)
    if cKDTree is not None:
        tree = cKDTree(comp_lut)
        _, indices = tree.query(flat_pixels, workers=-1)
    else:
        # Chunked vectorized Euclidean distance fallback
        chunk_size = 50000
        indices = np.empty(len(flat_pixels), dtype=np.int32)
        for i in range(0, len(flat_pixels), chunk_size):
            chunk = flat_pixels[i : i + chunk_size]  # (K, 3)
            # dists: (K, N)
            dists = np.sum((chunk[:, None, :] - comp_lut[None, :, :]) ** 2, axis=2)
            indices[i : i + chunk_size] = np.argmin(dists, axis=1)

    scalar_flat = lut_scalars[indices]
    scalar_2d = scalar_flat.reshape(img_h, img_w).astype(np.float32)

    # Mask colorbar area so it is not analyzed as scientific data
    if mask_colorbar and colorbar_bbox is not None:
        bx, by, bw, bh = colorbar_bbox
        scalar_2d[by : by + bh, bx : bx + bw] = 0.0

    return scalar_2d


def extract_data_colorbar(
    image_path: Union[str, Path, np.ndarray],
    hsv_lower: Optional[np.ndarray] = None,
    hsv_upper: Optional[np.ndarray] = None,
    min_aspect_ratio: float = 2.5,
    min_length: int = 25,
    min_thickness: int = 3,
    direction: str = "auto",
    num_samples: int = 256,
    mask_colorbar: bool = True,
    color_space: str = "LAB",
    return_metadata: bool = False,
) -> Union[np.ndarray, Tuple[np.ndarray, Dict[str, Any]]]:
    """
    Primary Data Extraction Pathway: Colorbar Parsing.

    Reconstructs a scientifically defensible quantitative 2D scalar field (0.0 to 1.0)
    from legacy NASA RGB imagery by parsing the visual colorbar to create a direct
    RGB-to-scalar lookup table (LUT), mirroring the Chandra X-ray Observatory sonification
    methodology.

    Pipeline Steps:
    1. Loads the image via OpenCV and converts BGR to HSV and LAB perceptually uniform spaces.
    2. Employs cv2.inRange to threshold and isolate the colorbar gradient region.
    3. Employs cv2.findContours to identify and extract the colorbar's bounding box.
    4. Samples colors along the colorbar length to build an RGB-to-scalar LUT (0.0 to 1.0).
    5. Applies the LUT to the main image area via minimum color-distance lookup,
       producing a normalized 2D NumPy array of quantitative scalar values.

    Args:
        image_path: Path to the image file or a loaded 3-channel BGR NumPy array.
        hsv_lower: Optional lower HSV threshold array [H, S, V].
        hsv_upper: Optional upper HSV threshold array [H, S, V].
        min_aspect_ratio: Minimum aspect ratio max(w,h)/min(w,h) for colorbar candidate.
        min_length: Minimum length along colorbar's major axis.
        min_thickness: Minimum thickness along colorbar's minor axis.
        direction: Direction mapping of the colorbar ('auto', 'bottom_to_top', etc.).
        num_samples: Number of entries in the synthesized LUT (default: 256).
        mask_colorbar: Whether to mask out the colorbar region in the returned scalar array.
        color_space: Color space for nearest-neighbor distance calculation ('LAB' or 'RGB').
        return_metadata: If True, returns (scalar_array, metadata_dict).

    Returns:
        np.ndarray: 2D float32 array of shape (H, W) with quantitative scalar values in [0.0, 1.0].
        (Optional) Dict[str, Any]: If return_metadata is True, returns dictionary containing
            'colorbar_bbox', 'lut_rgb', 'lut_scalars', and 'color_space'.

    Raises:
        FileNotFoundError: If the specified image path does not exist.
        ValueError: If image loading fails or inputs are invalid.
        ColorbarNotFoundError: If no colorbar gradient is detected in the image.
    """
    # 1. Load image via OpenCV
    image_bgr = load_image(image_path)

    # 2 & 3. Threshold gradient with cv2.inRange and find bounding box via cv2.findContours
    bbox = detect_colorbar_bounding_box(
        image_bgr=image_bgr,
        hsv_lower=hsv_lower,
        hsv_upper=hsv_upper,
        min_aspect_ratio=min_aspect_ratio,
        min_length=min_length,
        min_thickness=min_thickness,
    )

    # 4. Sample colors along the colorbar's length to build RGB-to-scalar LUT
    lut_rgb, lut_scalars = build_colorbar_lut(
        image_bgr=image_bgr,
        bbox=bbox,
        direction=direction,
        num_samples=num_samples,
    )

    # 5. Apply this LUT to the main image area to generate a 2D NumPy array
    scalar_array = apply_lut_to_image(
        image_bgr=image_bgr,
        lut_rgb=lut_rgb,
        lut_scalars=lut_scalars,
        colorbar_bbox=bbox,
        mask_colorbar=mask_colorbar,
        color_space=color_space,
    )

    if return_metadata:
        metadata = {
            "colorbar_bbox": bbox,
            "lut_rgb": lut_rgb,
            "lut_scalars": lut_scalars,
            "color_space": color_space,
            "image_shape": image_bgr.shape[:2],
        }
        return scalar_array, metadata

    return scalar_array
