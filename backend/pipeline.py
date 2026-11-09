"""
The Earth Jukebox - Pipeline Module
Scientific sonification data extraction and image processing pipeline.

This module implements the dual-pathway architecture for recovering quantitative
scalar datasets (0.0 to 1.0) from legacy NASA RGB imagery without underlying metadata,
mirroring the Chandra X-ray Center methodology of assigning energies to wavelengths:
1. Primary Pathway: Colorbar Parsing (direct RGB-to-scalar LUT recovery).
2. Fallback Pathway: Vector Quantization (reverse-engineering artist palette via scipy.cluster.vq).
"""

import logging
import os
import warnings
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import cv2
import matplotlib
import matplotlib.cm as cm
import numpy as np
from scipy.cluster.vq import vq

try:
    from scipy.spatial import cKDTree
except ImportError:
    cKDTree = None

logger = logging.getLogger(__name__)


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


# =============================================================================
# Fallback Data Extraction Pathway: Vector Quantization
# =============================================================================
# Architectural Note: Universal Palette Recovery & The 'unmap' Package
# -----------------------------------------------------------------------------
# When NASA imagery lacks an explicit visual colorbar/legend, recovering
# quantitative scalar data requires reverse-engineering the artist's colormap
# gradient (nearest-neighbor palette matching).
#
# Potential Alternative:
# The 'unmap' package (https://github.com/stefanv/unmap or similar colormap unmapping tools)
# provides an alternative approach for inverse colormap lookup by computing distances in
# perceptual color spaces (such as CAM02-UCS or CIELAB) against known scientific palettes.
#
# In this pipeline, we implement Vector Quantization via scipy.cluster.vq as our universal,
# dependency-free fallback pathway. This treats data recovery as a nearest-neighbor
# classification problem, directly matching each pixel to its closest code book entry.
# =============================================================================


def generate_colormap_codebook(
    colormap_name: str = "jet",
    num_samples: int = 256,
    scale_to_255: bool = True,
) -> np.ndarray:
    """
    Programmatically generate a "code book" of RGB tuples representing the theoretical
    gradient of colormap_name using matplotlib.cm.

    Args:
        colormap_name: Name of the matplotlib colormap (e.g., 'jet', 'viridis', 'plasma').
        num_samples: Number of discrete entries in the code book (default: 256).
        scale_to_255: If True, scale RGB values to [0.0, 255.0] to match standard uint8 pixels.
                      If False, keep values normalized in [0.0, 1.0].

    Returns:
        np.ndarray: float32 array of shape (num_samples, 3) representing RGB tuples.

    Raises:
        ValueError: If colormap_name is invalid or cannot be resolved.
    """
    if num_samples < 1:
        raise ValueError(f"num_samples must be >= 1, received {num_samples}")

    cmap = None
    candidates = [colormap_name]
    if isinstance(colormap_name, str):
        candidates.append(colormap_name.lower())

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for name in candidates:
            if hasattr(matplotlib, "colormaps"):
                try:
                    cmap = matplotlib.colormaps[name]
                    break
                except (KeyError, ValueError):
                    pass
            try:
                cmap = cm.get_cmap(name)
                break
            except Exception:
                pass

    if cmap is None:
        raise ValueError(f"Unknown or unsupported colormap '{colormap_name}'.")

    # Generate theoretical gradient values along [0.0, 1.0]
    scalars = np.linspace(0.0, 1.0, num_samples, endpoint=True)
    rgba = cmap(scalars)
    rgb = rgba[:, :3].astype(np.float32)

    if scale_to_255:
        rgb = rgb * 255.0

    return rgb


def extract_data_vector_quantization(
    image_path: Union[str, Path, np.ndarray],
    colormap_name: str = "jet",
    num_samples: int = 256,
    return_metadata: bool = False,
) -> Union[np.ndarray, Tuple[np.ndarray, Dict[str, Any]]]:
    """
    Fallback Data Extraction Pathway: Vector Quantization.

    Treats quantitative data recovery as a nearest-neighbor classification problem,
    reverse-engineering the artist's palette by matching image pixels to the closest
    entry in a synthetic theoretical colormap code book.

    Note: The 'unmap' package provides an alternative inverse colormap lookup method.
    Here, vector quantization via scipy.cluster.vq serves as our universal, lightweight
    fallback.

    Pipeline Steps:
    1. Programmatically generate a "code book" of 256 RGB tuples representing the
       theoretical gradient of colormap_name using matplotlib.cm.
    2. Reshape the input image into a flat list of pixel RGB values.
    3. Use scipy.cluster.vq.vq to match every pixel to the closest code book entry.
    4. Map the resulting indices linearly to a normalized 0.0 - 1.0 scalar array
       and reshape to original dimensions.

    Args:
        image_path: Path to the image file or loaded 3-channel BGR NumPy array.
        colormap_name: Colormap name to reverse-engineer (default: 'jet').
        num_samples: Number of entries in the synthetic code book (default: 256).
        return_metadata: If True, returns (scalar_array, metadata_dict).

    Returns:
        np.ndarray: 2D float32 array of shape (H, W) with quantitative scalar values in [0.0, 1.0].
        (Optional) Dict[str, Any]: If return_metadata is True, returns dictionary containing
            'colormap_name', 'code_book', 'distortion', 'mean_distortion', 'image_shape',
            and 'method'.

    Raises:
        FileNotFoundError: If the specified image path does not exist.
        ValueError: If colormap_name is unknown or image decoding fails.
        TypeError: If input type is unsupported.
    """
    # 1. Programmatically generate code book of 256 RGB tuples using matplotlib.cm
    code_book = generate_colormap_codebook(
        colormap_name=colormap_name,
        num_samples=num_samples,
        scale_to_255=True,
    )

    # 2. Reshape input image into a flat list of pixel RGB values
    image_bgr = load_image(image_path)
    img_h, img_w = image_bgr.shape[:2]

    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    flat_pixels = image_rgb.reshape(-1, 3).astype(np.float32)

    # If input array was already float in [0.0, 1.0], scale to match code book [0.0, 255.0]
    if image_rgb.dtype != np.uint8 and image_rgb.max() <= 1.0:
        flat_pixels = flat_pixels * 255.0

    # 3. Use scipy.cluster.vq.vq to match every pixel to the closest code book entry
    indices, distortion = vq(flat_pixels, code_book)

    # 4. Map resulting indices linearly to normalized 0.0 - 1.0 scalar array and reshape
    if num_samples > 1:
        scalar_flat = indices.astype(np.float32) / float(num_samples - 1)
    else:
        scalar_flat = np.zeros(len(indices), dtype=np.float32)

    scalar_2d = scalar_flat.reshape(img_h, img_w).astype(np.float32)

    if return_metadata:
        metadata = {
            "colormap_name": colormap_name,
            "code_book": code_book,
            "distortion": distortion.reshape(img_h, img_w).astype(np.float32),
            "mean_distortion": float(np.mean(distortion)),
            "image_shape": (img_h, img_w),
            "method": "vector_quantization",
        }
        return scalar_2d, metadata

    return scalar_2d


# =============================================================================
# Pipeline Orchestrator: Dual-Pathway Extraction
# =============================================================================


def extract_data(
    image_path: Union[str, Path, np.ndarray],
    colormap_name: str = "jet",
    num_samples: int = 256,
    method: str = "auto",
    mask_colorbar: bool = True,
    color_space: str = "LAB",
    return_metadata: bool = False,
    **colorbar_kwargs: Any,
) -> Union[np.ndarray, Tuple[np.ndarray, Dict[str, Any]]]:
    """
    Pipeline Orchestrator: Dual-Pathway Quantitative Data Extraction.

    Attempts the primary pathway (Colorbar Parsing) first. If no colorbar exists
    or detection fails, automatically falls back to Vector Quantization (reverse-engineering
    the artist's palette).

    Note: The 'unmap' package (https://github.com/stefanv/unmap) provides an alternative
    inversion approach; vector quantization via scipy.cluster.vq is our native, lightweight
    fallback solution.

    Args:
        image_path: Path to the image file or loaded NumPy array.
        colormap_name: Colormap name for Vector Quantization fallback (default: 'jet').
        num_samples: Number of entries in synthetic LUT / code book (default: 256).
        method: Extraction pathway:
            - 'auto': Try colorbar first; fall back to VQ if missing/undetected (default).
            - 'colorbar': Use only colorbar parsing (raises ColorbarNotFoundError if absent).
            - 'vq' or 'vector_quantization': Use only vector quantization.
        mask_colorbar: Whether to mask out colorbar area when using colorbar parsing.
        color_space: Distance comparison space for colorbar lookup ('LAB' or 'RGB').
        return_metadata: If True, returns (scalar_array, metadata_dict).
        **colorbar_kwargs: Extra keyword arguments forwarded to detect_colorbar_bounding_box.

    Returns:
        np.ndarray: 2D float32 array of shape (H, W) in [0.0, 1.0].
        (Optional) Dict[str, Any]: Extraction metadata dictionary.
    """
    method_lower = method.lower()
    if method_lower not in ("auto", "colorbar", "vq", "vector_quantization"):
        raise ValueError(
            f"Unknown extraction method '{method}'. Choose 'auto', 'colorbar', or 'vq'."
        )

    # If VQ is explicitly requested, invoke directly
    if method_lower in ("vq", "vector_quantization"):
        return extract_data_vector_quantization(
            image_path=image_path,
            colormap_name=colormap_name,
            num_samples=num_samples,
            return_metadata=return_metadata,
        )

    # Primary pathway: Colorbar parsing
    try:
        scalar_array, metadata = extract_data_colorbar(
            image_path=image_path,
            num_samples=num_samples,
            mask_colorbar=mask_colorbar,
            color_space=color_space,
            return_metadata=True,
            **colorbar_kwargs,
        )
        metadata["method"] = "colorbar"
        if return_metadata:
            return scalar_array, metadata
        return scalar_array

    except ColorbarNotFoundError as err:
        if method_lower == "colorbar":
            raise

        logger.info(
            "Colorbar not detected (%s). Falling back to Vector Quantization (colormap='%s').",
            err,
            colormap_name,
        )

        scalar_array, metadata = extract_data_vector_quantization(
            image_path=image_path,
            colormap_name=colormap_name,
            num_samples=num_samples,
            return_metadata=True,
        )
        metadata["fallback_from_colorbar_error"] = str(err)
        if return_metadata:
            return scalar_array, metadata
        return scalar_array


# =============================================================================
# Image Preprocessing and Enhancement: CLAHE & Noise Reduction
# =============================================================================


def preprocess_image(
    scalar_array: Union[str, Path, np.ndarray],
    apply_clahe: bool = True,
    apply_median_blur: bool = False,
    apply_gaussian_blur: bool = False,
    clahe_clip_limit: float = 2.0,
    clahe_tile_grid_size: Tuple[int, int] = (8, 8),
    median_ksize: int = 3,
    gaussian_ksize: Union[int, Tuple[int, int]] = (5, 5),
    gaussian_sigma: float = 0.0,
    blur_order: str = "before",
    return_metadata: bool = False,
    **kwargs: Any,
) -> Union[np.ndarray, Tuple[np.ndarray, Dict[str, Any]]]:
    """
    Preprocess and enhance scientific visualization scalar data prior to morphological analysis.

    Applies Contrast Limited Adaptive Histogram Equalization (CLAHE) to the L (luminance)
    channel in the LAB color space to preserve data integrity while boosting local contrast.
    Provides configurable toggles for noise reduction:
    - cv2.medianBlur: Removes salt-and-pepper / impulse noise while strictly preserving sharp edges.
    - cv2.GaussianBlur: Smooths fine-grained textures and high-frequency noise.

    Args:
        scalar_array: Input 2D scalar array [0.0, 1.0], 3D BGR image array, or image file path.
        apply_clahe: Whether to apply CLAHE to L (luminance) in LAB color space (default: True).
        apply_median_blur: Toggle for median blur salt-and-pepper noise reduction (default: False).
        apply_gaussian_blur: Toggle for Gaussian blur fine texture smoothing (default: False).
        clahe_clip_limit: Contrast clipping threshold for CLAHE (default: 2.0).
        clahe_tile_grid_size: Tile grid dimensions for adaptive equalization (default: (8, 8)).
        median_ksize: Kernel aperture size for cv2.medianBlur; must be odd >= 3 (default: 3).
        gaussian_ksize: Gaussian kernel size; positive odd int or (w, h) tuple (default: (5, 5)).
        gaussian_sigma: Gaussian kernel sigma in X direction; 0 means auto (default: 0.0).
        blur_order: Noise reduction execution order relative to CLAHE: 'before' or 'after' (default: 'before').
        return_metadata: Whether to return a metadata dictionary alongside the array (default: False).
        **kwargs: Parameter aliases (clahe, enable_clahe, median_blur, enable_median_blur,
                 gaussian_blur, enable_gaussian_blur, clip_limit, tile_grid_size, grid_size,
                 median_kernel_size, gaussian_kernel_size, sigma, sigma_x).

    Returns:
        np.ndarray: Normalized 0.0 to 1.0 float32 NumPy array.
        (Optional) Dict[str, Any]: Preprocessing metadata if return_metadata=True.

    Raises:
        TypeError: If input is not an ndarray or valid file path.
        ValueError: If array is empty, dimensions invalid, or parameters out of range.
        FileNotFoundError: If image file path does not exist.
    """
    # Parameter aliases
    if "clahe" in kwargs:
        apply_clahe = bool(kwargs.pop("clahe"))
    if "enable_clahe" in kwargs:
        apply_clahe = bool(kwargs.pop("enable_clahe"))
    if "median_blur" in kwargs:
        apply_median_blur = bool(kwargs.pop("median_blur"))
    if "enable_median_blur" in kwargs:
        apply_median_blur = bool(kwargs.pop("enable_median_blur"))
    if "gaussian_blur" in kwargs:
        apply_gaussian_blur = bool(kwargs.pop("gaussian_blur"))
    if "enable_gaussian_blur" in kwargs:
        apply_gaussian_blur = bool(kwargs.pop("enable_gaussian_blur"))
    if "clip_limit" in kwargs:
        clahe_clip_limit = float(kwargs.pop("clip_limit"))
    if "tile_grid_size" in kwargs:
        clahe_tile_grid_size = kwargs.pop("tile_grid_size")
    if "grid_size" in kwargs:
        clahe_tile_grid_size = kwargs.pop("grid_size")
    if "median_kernel_size" in kwargs:
        median_ksize = int(kwargs.pop("median_kernel_size"))
    if "gaussian_kernel_size" in kwargs:
        gaussian_ksize = kwargs.pop("gaussian_kernel_size")
    if "sigma" in kwargs:
        gaussian_sigma = float(kwargs.pop("sigma"))
    if "sigma_x" in kwargs:
        gaussian_sigma = float(kwargs.pop("sigma_x"))

    # Load from path if string or Path
    if isinstance(scalar_array, (str, Path)):
        img = load_image(scalar_array)
    elif isinstance(scalar_array, np.ndarray):
        img = scalar_array.copy()
    else:
        raise TypeError(
            f"Expected np.ndarray or image path, received {type(scalar_array).__name__}"
        )

    if img.size == 0:
        raise ValueError("Input scalar_array cannot be empty.")

    # Clean non-finite values for float arrays
    if np.issubdtype(img.dtype, np.floating):
        img = np.nan_to_num(img, nan=0.0, posinf=1.0, neginf=0.0)

    # Validate array dimensions
    if img.ndim == 1:
        raise ValueError(f"Input must be 2D or 3D array, got 1D array of shape {img.shape}.")
    elif img.ndim == 3:
        if img.shape[2] == 1:
            img = img.squeeze(axis=2)
        elif img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        elif img.shape[2] != 3:
            raise ValueError(f"Unsupported number of channels: {img.shape[2]}")
    elif img.ndim > 3:
        raise ValueError(f"Expected 2D or 3D array, got {img.ndim}D array of shape {img.shape}.")

    # Parameter validation
    if apply_median_blur:
        if not isinstance(median_ksize, int) or median_ksize % 2 == 0 or median_ksize < 3:
            raise ValueError(
                f"median_ksize must be an odd integer >= 3, got {median_ksize}."
            )

    if apply_gaussian_blur:
        if isinstance(gaussian_ksize, int):
            gk = (gaussian_ksize, gaussian_ksize)
        elif isinstance(gaussian_ksize, (tuple, list)) and len(gaussian_ksize) == 2:
            gk = (int(gaussian_ksize[0]), int(gaussian_ksize[1]))
        else:
            raise ValueError(
                f"gaussian_ksize must be an integer or 2-tuple of positive odd integers, got {gaussian_ksize}."
            )
        if gk[0] % 2 == 0 or gk[1] % 2 == 0 or gk[0] < 1 or gk[1] < 1:
            raise ValueError(
                f"gaussian_ksize elements must be positive odd integers, got {gk}."
            )
        gaussian_ksize = gk

    if apply_clahe:
        if isinstance(clahe_tile_grid_size, (tuple, list)) and len(clahe_tile_grid_size) == 2:
            clahe_tile_grid_size = (int(clahe_tile_grid_size[0]), int(clahe_tile_grid_size[1]))
        else:
            raise ValueError(
                f"clahe_tile_grid_size must be a 2-tuple of positive integers, got {clahe_tile_grid_size}."
            )
        if clahe_tile_grid_size[0] < 1 or clahe_tile_grid_size[1] < 1:
            raise ValueError(
                f"clahe_tile_grid_size elements must be positive integers, got {clahe_tile_grid_size}."
            )
        if clahe_clip_limit <= 0:
            raise ValueError(f"clahe_clip_limit must be > 0, got {clahe_clip_limit}.")

    blur_order_lower = blur_order.lower()
    if blur_order_lower not in ("before", "after"):
        raise ValueError(f"blur_order must be 'before' or 'after', got '{blur_order}'.")

    # Step 1: Normalize input to standard representation
    if img.ndim == 3:
        # 3-channel BGR image
        if np.issubdtype(img.dtype, np.floating):
            if img.min() >= -1e-4 and img.max() <= 1.0 + 1e-4:
                bgr_u8 = np.clip(np.round(img * 255.0), 0, 255).astype(np.uint8)
            else:
                min_v, max_v = float(img.min()), float(img.max())
                if max_v > min_v:
                    bgr_u8 = np.clip(np.round(((img - min_v) / (max_v - min_v)) * 255.0), 0, 255).astype(np.uint8)
                else:
                    bgr_u8 = np.zeros(img.shape[:2] + (3,), dtype=np.uint8)
        else:
            bgr_u8 = np.clip(img, 0, 255).astype(np.uint8)
    else:
        # 2D scalar array
        if np.issubdtype(img.dtype, np.floating):
            if img.min() >= -1e-4 and img.max() <= 1.0 + 1e-4:
                norm_2d = np.clip(img.astype(np.float32), 0.0, 1.0)
            else:
                min_v, max_v = float(img.min()), float(img.max())
                if max_v > min_v:
                    norm_2d = ((img - min_v) / (max_v - min_v)).astype(np.float32)
                else:
                    norm_2d = np.zeros_like(img, dtype=np.float32)
        else:
            norm_2d = (np.clip(img, 0, 255).astype(np.float32)) / 255.0

        gray_u8 = np.clip(np.round(norm_2d * 255.0), 0, 255).astype(np.uint8)
        bgr_u8 = cv2.cvtColor(gray_u8, cv2.COLOR_GRAY2BGR)

    def _execute_noise_reduction(bgr: np.ndarray) -> np.ndarray:
        out = bgr
        if apply_median_blur:
            out = cv2.medianBlur(out, median_ksize)
        if apply_gaussian_blur:
            out = cv2.GaussianBlur(out, gaussian_ksize, float(gaussian_sigma))
        return out

    # Noise reduction before CLAHE (standard denoising practice)
    if blur_order_lower == "before":
        bgr_u8 = _execute_noise_reduction(bgr_u8)

    # Step 2: Apply CLAHE to L (luminance) channel in LAB color space
    if apply_clahe:
        # Convert BGR to LAB color space
        lab = cv2.cvtColor(bgr_u8, cv2.COLOR_BGR2LAB)
        l_chan, a_chan, b_chan = cv2.split(lab)

        # Apply CLAHE strictly to L channel to enhance contrast without altering chroma
        clahe = cv2.createCLAHE(
            clipLimit=float(clahe_clip_limit),
            tileGridSize=clahe_tile_grid_size,
        )
        l_enhanced = clahe.apply(l_chan)

        # Merge enhanced L channel back with original A and B channels
        lab_enhanced = cv2.merge([l_enhanced, a_chan, b_chan])
        bgr_u8 = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

    # Noise reduction after CLAHE if requested
    if blur_order_lower == "after":
        bgr_u8 = _execute_noise_reduction(bgr_u8)

    # Step 3: Convert to normalized 0.0 to 1.0 float32 scalar NumPy array
    gray_out = cv2.cvtColor(bgr_u8, cv2.COLOR_BGR2GRAY)
    output_scalar = (gray_out.astype(np.float32) / 255.0).astype(np.float32)
    output_scalar = np.clip(output_scalar, 0.0, 1.0)

    if return_metadata:
        metadata = {
            "apply_clahe": apply_clahe,
            "clahe_clip_limit": clahe_clip_limit if apply_clahe else None,
            "clahe_tile_grid_size": clahe_tile_grid_size if apply_clahe else None,
            "apply_median_blur": apply_median_blur,
            "median_ksize": median_ksize if apply_median_blur else None,
            "apply_gaussian_blur": apply_gaussian_blur,
            "gaussian_ksize": gaussian_ksize if apply_gaussian_blur else None,
            "gaussian_sigma": gaussian_sigma if apply_gaussian_blur else None,
            "blur_order": blur_order_lower,
            "input_shape": img.shape,
            "output_shape": output_scalar.shape,
            "min_value": float(output_scalar.min()),
            "max_value": float(output_scalar.max()),
            "mean_value": float(np.mean(output_scalar)),
            "std_value": float(np.std(output_scalar)),
        }
        return output_scalar, metadata

    return output_scalar


