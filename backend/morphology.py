"""
The Earth Jukebox - Morphological Feature Separation Module.

This module separates quantitative 2D scalar datasets into distinct structural
categories, mirroring the Chandra X-ray Center sonification methodology:
1. Diffuse Emission (large-scale background, e.g. cloud bands, nebulae, atmospheric gradients).
2. Point Sources (high-frequency localized events, e.g. wildfire hotspots, stars, urban clusters).

By isolating high-frequency localized features from continuous low-frequency
backgrounds, sonification engines can map each layer to dedicated audio stems
(e.g., continuous ambient synth pads for diffuse emission vs. discrete percussive
or melodic triggers for point sources), preventing auditory clutter and masking.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class MorphologyError(ValueError):
    """Exception raised for errors during morphological analysis and feature separation."""
    pass


def _prepare_scalar_array(scalar_input: Any) -> np.ndarray:
    """
    Validate and normalize input into a 2D float32 scalar array in [0.0, 1.0].

    Args:
        scalar_input: Input scalar array or convertible array-like structure.

    Returns:
        np.ndarray: 2D float32 array normalized to [0.0, 1.0].

    Raises:
        TypeError: If scalar_input is None or cannot be cast to a NumPy array.
        ValueError: If scalar_input is empty, not 2D, or has incompatible channels.
    """
    if scalar_input is None:
        raise TypeError("scalar_array cannot be None.")

    if not isinstance(scalar_input, np.ndarray):
        try:
            arr = np.asarray(scalar_input, dtype=np.float32)
        except Exception as e:
            raise TypeError(
                f"scalar_array must be a NumPy array or convertible sequence, got {type(scalar_input).__name__}."
            ) from e
    else:
        arr = scalar_input.copy()

    if arr.size == 0:
        raise ValueError("scalar_array cannot be empty.")

    # Handle 3D inputs with single channel or standard color channels
    if arr.ndim == 3:
        if arr.shape[2] == 1:
            arr = arr.squeeze(axis=2)
        elif arr.shape[2] == 4:
            # BGRA image
            if np.issubdtype(arr.dtype, np.integer):
                bgr = cv2.cvtColor(np.clip(arr, 0, 255).astype(np.uint8), cv2.COLOR_BGRA2BGR)
                arr = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
            else:
                bgr = cv2.cvtColor((np.clip(arr, 0.0, 1.0) * 255.0).astype(np.uint8), cv2.COLOR_BGRA2BGR)
                arr = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        elif arr.shape[2] == 3:
            # BGR image
            if np.issubdtype(arr.dtype, np.integer):
                arr = cv2.cvtColor(np.clip(arr, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
            else:
                arr = cv2.cvtColor((np.clip(arr, 0.0, 1.0) * 255.0).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        else:
            raise ValueError(f"Unsupported 3D array shape: {arr.shape}. Expected 2D or (H, W, 1/3/4).")

    if arr.ndim != 2:
        raise ValueError(f"Expected 2D scalar array, got shape {arr.shape} with {arr.ndim} dimensions.")

    # Convert integers to float32 [0.0, 1.0]
    if np.issubdtype(arr.dtype, np.integer):
        max_int_val = float(np.iinfo(arr.dtype).max) if hasattr(np.iinfo(arr.dtype), "max") else 255.0
        # For standard uint8 visualizations
        divisor = 255.0 if max_int_val == 255.0 else max_int_val
        arr = (np.clip(arr, 0, max_int_val).astype(np.float32)) / divisor
    else:
        arr = arr.astype(np.float32)

    # Normalize or clip floating-point data to [0.0, 1.0]
    min_v = float(np.min(arr))
    max_v = float(np.max(arr))

    if min_v >= -1e-4 and max_v <= 1.0 + 1e-4:
        arr = np.clip(arr, 0.0, 1.0)
    else:
        logger.debug("Input scalar array range [%.4f, %.4f] outside [0.0, 1.0]; normalizing.", min_v, max_v)
        if max_v > min_v:
            arr = (arr - min_v) / (max_v - min_v)
        else:
            arr = np.zeros_like(arr, dtype=np.float32)

    return arr.astype(np.float32)


def _validate_kernel_size(kernel_size: Union[int, Tuple[int, int]]) -> Tuple[int, int]:
    """
    Validate Gaussian blur kernel dimensions.

    Args:
        kernel_size: Integer or 2-tuple of integers defining filter width and height.

    Returns:
        Tuple[int, int]: Validated (k_width, k_height).

    Raises:
        ValueError: If kernel dimensions are not positive odd integers.
    """
    if isinstance(kernel_size, (int, np.integer)):
        ksize = (int(kernel_size), int(kernel_size))
    elif isinstance(kernel_size, (tuple, list)) and len(kernel_size) == 2:
        try:
            ksize = (int(kernel_size[0]), int(kernel_size[1]))
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"kernel_size elements must be integers, got {kernel_size}."
            ) from e
    else:
        raise ValueError(
            f"kernel_size must be an integer or a 2-tuple of integers, got {type(kernel_size).__name__}."
        )

    if ksize[0] <= 0 or ksize[1] <= 0:
        raise ValueError(f"Kernel size elements must be strictly positive, got {ksize}.")

    if ksize[0] % 2 == 0 or ksize[1] % 2 == 0:
        raise ValueError(
            f"Kernel size elements must be positive odd integers (e.g., 51x51), got {ksize}."
        )

    return ksize


def separate_features(
    scalar_array: np.ndarray,
    kernel_size: Union[int, Tuple[int, int]] = (51, 51),
    sigma: float = 0.0,
    normalize_residual: bool = True,
    clip_diffuse: bool = True,
    return_metadata: bool = False,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Separate visual scalar data into diffuse background and localized point sources.

    Mirroring the Chandra X-ray Center sonification methodology (which separates
    extended nebulae emissions from stellar point sources to prevent auditory clutter):
    1. Applies a large-radius Gaussian blur (default 51x51 kernel) to extract the
       smooth, large-scale "diffuse emission" (e.g., cloud bands, atmospheric haze).
    2. Subtracts the diffuse array from the original scalar field to isolate the
       high-frequency "point sources" (residual image, e.g., wildfire hotspots, storms).
    3. Clips negative values (sub-background depressions) and normalizes the residual
       image back to 0.0 - 1.0.
    4. Returns a dictionary containing both 'diffuse_layer' and 'point_source_layer'.

    Args:
        scalar_array: 2D quantitative scalar array with values normalized in [0.0, 1.0].
        kernel_size: Gaussian kernel size as int or (width, height) tuple (default: (51, 51)).
                     Elements must be positive odd integers.
        sigma: Standard deviation for Gaussian kernel. If 0.0 (default), OpenCV
               computes sigma automatically from kernel_size.
        normalize_residual: Whether to rescale the residual image to 0.0 - 1.0 (default: True).
        clip_diffuse: Whether to clip the diffuse layer to [0.0, 1.0] (default: True).
        return_metadata: If True, includes a 'metadata' dictionary in the returned dictionary.
        **kwargs: Additional parameters and aliases:
            - ksize / gaussian_ksize: Alias for kernel_size.
            - sigma_x / sigma_y: Explicit standard deviations along X and Y axes.

    Returns:
        Dict[str, Any]: Dictionary containing:
            - "diffuse_layer": np.ndarray (float32) of large-scale diffuse background.
            - "point_source_layer": np.ndarray (float32) of isolated point sources in [0.0, 1.0].
            - (Optional) "metadata": Dict with extraction parameters and layer statistics.

    Raises:
        TypeError: If scalar_array is None or cannot be parsed as a NumPy array.
        ValueError: If scalar_array is empty, not 2D, or kernel_size is invalid.
    """
    # Check for parameter aliases
    if "ksize" in kwargs:
        kernel_size = kwargs["ksize"]
    elif "gaussian_ksize" in kwargs:
        kernel_size = kwargs["gaussian_ksize"]

    sigma_x = float(kwargs.get("sigma_x", sigma))
    sigma_y = float(kwargs.get("sigma_y", kwargs.get("sigma_x", sigma)))

    # Step 0: Validate and normalize input scalar array
    norm_scalar = _prepare_scalar_array(scalar_array)
    ksize = _validate_kernel_size(kernel_size)

    # Step 1: Apply large-radius Gaussian blur to extract diffuse emission
    diffuse_layer = cv2.GaussianBlur(
        norm_scalar,
        ksize,
        sigmaX=sigma_x,
        sigmaY=sigma_y,
        borderType=cv2.BORDER_DEFAULT,
    )
    if clip_diffuse:
        diffuse_layer = np.clip(diffuse_layer, 0.0, 1.0)
    diffuse_layer = diffuse_layer.astype(np.float32)

    # Step 2: Subtract blurred array from original to isolate high-frequency point sources
    residual = norm_scalar - diffuse_layer

    # Step 3: Clip negative values and normalize the residual image back to 0.0 - 1.0
    residual_clipped = np.clip(residual, 0.0, None)

    if normalize_residual:
        max_val = float(np.max(residual_clipped))
        if max_val > 1e-12:
            point_source_layer = (residual_clipped / max_val).astype(np.float32)
        else:
            # Entire residual is flat/zero (e.g. constant scalar input)
            point_source_layer = np.zeros_like(residual_clipped, dtype=np.float32)
    else:
        point_source_layer = residual_clipped.astype(np.float32)

    point_source_layer = np.clip(point_source_layer, 0.0, 1.0).astype(np.float32)

    # Step 4: Return dictionary containing diffuse_layer and point_source_layer
    result: Dict[str, Any] = {
        "diffuse_layer": diffuse_layer,
        "point_source_layer": point_source_layer,
    }

    if return_metadata:
        result["metadata"] = {
            "kernel_size": ksize,
            "sigma_x": sigma_x,
            "sigma_y": sigma_y,
            "normalize_residual": normalize_residual,
            "clip_diffuse": clip_diffuse,
            "diffuse_min": float(diffuse_layer.min()),
            "diffuse_max": float(diffuse_layer.max()),
            "diffuse_mean": float(np.mean(diffuse_layer)),
            "point_source_min": float(point_source_layer.min()),
            "point_source_max": float(point_source_layer.max()),
            "point_source_mean": float(np.mean(point_source_layer)),
            "raw_residual_max": float(np.max(residual_clipped)),
        }

    if kwargs.get("detect_point_sources", False) or kwargs.get("detect_sources", False):
        result["point_sources"] = detect_point_sources(point_source_layer, **kwargs)

    return result


def _normalize_threshold_pair(
    min_t: float,
    max_t: float,
) -> Tuple[float, float]:
    """
    Validate and normalize min/max threshold values into 8-bit [0, 255] scale.

    Args:
        min_t: Minimum threshold (accepts [0.0, 1.0] or [0, 255]).
        max_t: Maximum threshold (accepts [0.0, 1.0] or [0, 255]).

    Returns:
        Tuple[float, float]: Validated (min_thresh_u8, max_thresh_u8) on [1.0, 255.0].

    Raises:
        ValueError: If min_t >= max_t or values are invalid.
    """
    min_val = float(min_t)
    max_val = float(max_t)

    # Detect if thresholds were provided on normalized [0.0, 1.0] scale
    if 0.0 < max_val <= 1.0:
        max_val = max_val * 255.0
    if 0.0 < min_val < 1.0:
        min_val = min_val * 255.0

    min_val = max(1.0, min_val)
    max_val = min(255.0, max_val)

    if min_val >= max_val:
        raise ValueError(
            f"min_threshold ({min_t}) must be strictly less than max_threshold ({max_t})."
        )

    return float(min_val), float(max_val)


def _sort_point_sources(
    sources: List[Dict[str, Any]],
    sort_by: Optional[str] = None,
    descending: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """
    Sort a list of detected point source dictionaries by a specified attribute.

    Args:
        sources: List of point source metadata dictionaries.
        sort_by: Field name to sort by ('flux', 'area', 'radius', 'perimeter', 'x', 'y').
        descending: Sort descending if True. Defaults to True for photometric/size metrics,
                    False (ascending) for spatial coordinates (x, y).

    Returns:
        List[Dict[str, Any]]: Sorted list of dictionaries.
    """
    if not sort_by:
        return sources

    key = str(sort_by).strip().lower()
    if descending is None:
        reverse = key not in ("x", "y")
    else:
        reverse = bool(descending)

    return sorted(sources, key=lambda s: s.get(key, 0.0), reverse=reverse)


def detect_point_sources_blob(
    residual_image: Any,
    min_threshold: float = 20.0,
    max_threshold: float = 250.0,
    filter_by_area: bool = True,
    min_area: float = 1.0,
    max_area: float = 5000.0,
    filter_by_circularity: bool = False,
    min_circularity: float = 0.5,
    max_circularity: float = 1.0,
    sort_by: Optional[str] = None,
    descending: Optional[bool] = None,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """
    Detect compact, circular point sources using OpenCV's SimpleBlobDetector.

    Configures cv2.SimpleBlobDetector with minThreshold, maxThreshold, and filterByArea
    to isolate localized emission spikes, stellar objects, and wildfire hotspots.

    Args:
        residual_image: 2D quantitative residual scalar array in [0.0, 1.0] or 8-bit image.
        min_threshold: Minimum intensity threshold for blob detection (default: 20.0 / ~0.08).
        max_threshold: Maximum intensity threshold for blob detection (default: 250.0 / ~0.98).
        filter_by_area: Whether to filter candidate blobs by pixel area (default: True).
        min_area: Minimum blob area in pixels (default: 1.0).
        max_area: Maximum blob area in pixels (default: 5000.0).
        filter_by_circularity: Whether to enforce circularity for compact shapes (default: False).
        min_circularity: Minimum circularity ratio (4 * pi * area / perim^2) in [0.0, 1.0].
        max_circularity: Maximum circularity ratio (default: 1.0).
        sort_by: Optional attribute to sort detections by ('flux', 'area', 'radius', 'x', 'y').
        descending: Sort direction (default: True for photometric metrics, False for spatial).
        **kwargs: Additional parameter overrides:
            - minThreshold / maxThreshold: Aliases for min_threshold / max_threshold.
            - filterByArea / minArea / maxArea: Aliases for area parameters.
            - filterByCircularity / minCircularity: Aliases for circularity parameters.
            - threshold_step / thresholdStep: Threshold increment for detector (default: 5.0).
            - min_repeatability / minRepeatability: Detections required per blob (default: 1).
            - min_dist_between_blobs / minDistBetweenBlobs: Minimum distance in px (default: 2.0).
            - blob_color / blobColor: Target blob color (default: 255 for bright point sources).
            - filter_by_convexity / filterByConvexity: Whether to filter by convexity (default: False).
            - filter_by_inertia / filterByInertia: Whether to filter by inertia ratio (default: False).

    Returns:
        List[Dict[str, Any]]: List of metadata dictionaries for each detected point source.
    """
    # Parameter aliases
    min_threshold = kwargs.get("minThreshold", min_threshold)
    max_threshold = kwargs.get("maxThreshold", max_threshold)
    filter_by_area = kwargs.get("filterByArea", filter_by_area)
    min_area = kwargs.get("minArea", min_area)
    max_area = kwargs.get("maxArea", max_area)
    filter_by_circularity = kwargs.get("filterByCircularity", filter_by_circularity)
    min_circularity = kwargs.get("minCircularity", min_circularity)
    max_circularity = kwargs.get("maxCircularity", max_circularity)

    norm_scalar = _prepare_scalar_array(residual_image)
    h, w = norm_scalar.shape

    min_thresh_cv, max_thresh_cv = _normalize_threshold_pair(min_threshold, max_threshold)

    min_a = float(min_area)
    max_a = float(max_area) if max_area is not None else float(h * w)
    if min_a > max_a:
        raise ValueError(f"min_area ({min_a}) must be less than or equal to max_area ({max_a}).")

    img_u8 = np.clip(norm_scalar * 255.0, 0, 255).astype(np.uint8)

    params = cv2.SimpleBlobDetector_Params()
    # Point sources in residual imagery are bright features on zero/dark backgrounds
    params.filterByColor = bool(kwargs.get("filterByColor", kwargs.get("filter_by_color", True)))
    params.blobColor = int(kwargs.get("blobColor", kwargs.get("blob_color", 255)))

    # Thresholding configuration
    params.minThreshold = float(min_thresh_cv)
    params.maxThreshold = float(max_thresh_cv)
    params.thresholdStep = float(kwargs.get("thresholdStep", kwargs.get("threshold_step", 5.0)))
    params.minRepeatability = int(kwargs.get("minRepeatability", kwargs.get("min_repeatability", 1)))
    params.minDistBetweenBlobs = float(
        kwargs.get("minDistBetweenBlobs", kwargs.get("min_dist_between_blobs", 2.0))
    )

    # Area filtering
    params.filterByArea = bool(filter_by_area)
    params.minArea = float(min_a)
    params.maxArea = float(max_a)

    # Circularity filtering
    params.filterByCircularity = bool(filter_by_circularity)
    if params.filterByCircularity:
        params.minCircularity = float(min_circularity)
        params.maxCircularity = float(max_circularity)

    # Convexity and inertia filters (disabled by default to avoid rejecting small rasterized spots)
    params.filterByConvexity = bool(
        kwargs.get("filterByConvexity", kwargs.get("filter_by_convexity", False))
    )
    if params.filterByConvexity:
        params.minConvexity = float(kwargs.get("minConvexity", kwargs.get("min_convexity", 0.8)))
        params.maxConvexity = float(kwargs.get("maxConvexity", kwargs.get("max_convexity", 1.0)))

    params.filterByInertia = bool(
        kwargs.get("filterByInertia", kwargs.get("filter_by_inertia", False))
    )
    if params.filterByInertia:
        params.minInertiaRatio = float(kwargs.get("minInertiaRatio", kwargs.get("min_inertia_ratio", 0.1)))
        params.maxInertiaRatio = float(kwargs.get("maxInertiaRatio", kwargs.get("max_inertia_ratio", 1.0)))

    detector = cv2.SimpleBlobDetector_create(params)
    keypoints = detector.detect(img_u8)

    point_sources: List[Dict[str, Any]] = []
    for kp in keypoints:
        cx, cy = float(kp.pt[0]), float(kp.pt[1])
        radius = float(kp.size / 2.0)
        if radius <= 0:
            radius = 1.0

        area = float(np.pi * (radius ** 2))
        perimeter = float(2.0 * np.pi * radius)

        # Extract peak intensity (flux) within the circular footprint
        y_min = max(0, int(np.floor(cy - radius)))
        y_max = min(h, int(np.ceil(cy + radius)) + 1)
        x_min = max(0, int(np.floor(cx - radius)))
        x_max = min(w, int(np.ceil(cx + radius)) + 1)

        patch = norm_scalar[y_min:y_max, x_min:x_max]
        if patch.size > 0:
            yy, xx = np.ogrid[y_min:y_max, x_min:x_max]
            dist_sq = (xx - cx) ** 2 + (yy - cy) ** 2
            mask = dist_sq <= max(1.0, radius) ** 2
            if np.any(mask):
                flux = float(np.max(patch[mask]))
            else:
                flux = float(np.max(patch))
        else:
            flux = float(
                norm_scalar[int(np.clip(round(cy), 0, h - 1)), int(np.clip(round(cx), 0, w - 1))]
            )

        point_sources.append({
            "x": cx,
            "y": cy,
            "radius": radius,
            "flux": flux,
            "area": area,
            "perimeter": perimeter,
            "center": (cx, cy),
            "peak_intensity": flux,
            "method": "blob",
        })

    return _sort_point_sources(point_sources, sort_by=sort_by, descending=descending)


def detect_point_sources_contours(
    residual_image: Any,
    threshold: Optional[Union[float, str]] = None,
    min_area: float = 1.0,
    max_area: Optional[float] = None,
    filter_by_area: bool = True,
    sort_by: Optional[str] = None,
    descending: Optional[bool] = None,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """
    Detect irregularly shaped point sources using cv2.findContours on a thresholded residual image.

    Calculates exact geometric area, perimeter, centroid, and peak intensity (flux)
    for asymmetric point sources (e.g. non-circular emission clouds, touching clusters).

    Args:
        residual_image: 2D quantitative residual scalar array in [0.0, 1.0] or 8-bit image.
        threshold: Binarization threshold. If None, derived from min_threshold (~20/255).
                   Accepts float in [0.0, 1.0], [0, 255], or 'otsu' for Otsu thresholding.
        min_area: Minimum contour area in pixels (default: 1.0).
        max_area: Maximum contour area in pixels (default: None, unbounded).
        filter_by_area: Whether to filter contours by area (default: True).
        sort_by: Optional attribute to sort detections by ('flux', 'area', 'radius', 'x', 'y').
        descending: Sort direction (default: True for photometric metrics, False for spatial).
        **kwargs: Additional parameter overrides:
            - minArea / maxArea / filterByArea: Aliases for area parameters.
            - min_threshold / minThreshold: Fallback threshold value if threshold is None.
            - filter_by_circularity / filterByCircularity: Whether to filter by circularity.
            - min_circularity / max_circularity: Circularity bounds if circularity filtering enabled.

    Returns:
        List[Dict[str, Any]]: List of metadata dictionaries for each detected point source.
    """
    min_area = kwargs.get("minArea", min_area)
    max_area = kwargs.get("maxArea", max_area)
    filter_by_area = kwargs.get("filterByArea", filter_by_area)

    norm_scalar = _prepare_scalar_array(residual_image)
    h, w = norm_scalar.shape
    img_u8 = np.clip(norm_scalar * 255.0, 0, 255).astype(np.uint8)

    min_a = float(min_area)
    max_a = float(max_area) if max_area is not None else float(h * w)
    if min_a > max_a:
        raise ValueError(f"min_area ({min_a}) must be less than or equal to max_area ({max_a}).")

    # Determine binarization threshold
    if threshold is None:
        thresh_candidate = kwargs.get("min_threshold", kwargs.get("minThreshold", 20.0))
        if 0.0 < float(thresh_candidate) <= 1.0:
            thresh_u8 = float(thresh_candidate) * 255.0
        else:
            thresh_u8 = float(thresh_candidate)
        thresh_u8 = max(1.0, min(254.0, thresh_u8))
        _, binary = cv2.threshold(img_u8, thresh_u8, 255, cv2.THRESH_BINARY)
    elif isinstance(threshold, str) and threshold.lower() == "otsu":
        _, binary = cv2.threshold(img_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        thresh_val = float(threshold)
        if 0.0 < thresh_val <= 1.0:
            thresh_u8 = thresh_val * 255.0
        else:
            thresh_u8 = thresh_val
        thresh_u8 = max(1.0, min(254.0, thresh_u8))
        _, binary = cv2.threshold(img_u8, thresh_u8, 255, cv2.THRESH_BINARY)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    point_sources: List[Dict[str, Any]] = []
    filter_by_circ = bool(kwargs.get("filter_by_circularity", kwargs.get("filterByCircularity", False)))
    min_circ = float(kwargs.get("min_circularity", kwargs.get("minCircularity", 0.5)))
    max_circ = float(kwargs.get("max_circularity", kwargs.get("maxCircularity", 1.0)))

    for cnt in contours:
        raw_area = float(cv2.contourArea(cnt))
        # Fallback for degenerate single-pixel or line-segment contours
        area = raw_area if raw_area > 0.0 else float(max(1.0, len(cnt)))

        perimeter = float(cv2.arcLength(cnt, closed=True))
        if perimeter <= 0.0:
            perimeter = float(4.0 * np.sqrt(area))

        if filter_by_area:
            if area < min_a or area > max_a:
                continue

        if filter_by_circ:
            circularity = (4.0 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0.0
            if circularity < min_circ or circularity > max_circ:
                continue

        # Centroid from moments
        M = cv2.moments(cnt)
        if M["m00"] != 0:
            cx = float(M["m10"] / M["m00"])
            cy = float(M["m01"] / M["m00"])
        else:
            cx = float(np.mean(cnt[:, 0, 0]))
            cy = float(np.mean(cnt[:, 0, 1]))

        # Minimum enclosing circle for radius
        _, min_enc_r = cv2.minEnclosingCircle(cnt)
        radius = float(min_enc_r)
        if radius <= 0:
            radius = float(np.sqrt(area / np.pi)) if area > 0 else 1.0

        # Peak intensity (flux) within contour mask
        xb, yb, wb, hb = cv2.boundingRect(cnt)
        if wb > 0 and hb > 0:
            local_mask = np.zeros((hb, wb), dtype=np.uint8)
            cv2.drawContours(local_mask, [cnt - [xb, yb]], -1, 255, -1)
            local_patch = norm_scalar[yb:yb + hb, xb:xb + wb]
            if np.any(local_mask > 0):
                flux = float(np.max(local_patch[local_mask > 0]))
            else:
                flux = float(np.max(local_patch))
        else:
            flux = float(
                norm_scalar[int(np.clip(round(cy), 0, h - 1)), int(np.clip(round(cx), 0, w - 1))]
            )

        point_sources.append({
            "x": cx,
            "y": cy,
            "radius": radius,
            "flux": flux,
            "area": area,
            "perimeter": perimeter,
            "center": (cx, cy),
            "peak_intensity": flux,
            "method": "contours",
        })

    return _sort_point_sources(point_sources, sort_by=sort_by, descending=descending)


def detect_point_sources(
    residual_image: Any,
    method: str = "blob",
    min_threshold: float = 20.0,
    max_threshold: float = 250.0,
    filter_by_area: bool = True,
    min_area: float = 1.0,
    max_area: float = 5000.0,
    filter_by_circularity: bool = False,
    min_circularity: float = 0.5,
    max_circularity: float = 1.0,
    threshold: Optional[Union[float, str]] = None,
    sort_by: Optional[str] = None,
    descending: Optional[bool] = None,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """
    Detect isolated point sources in a residual scalar image and extract their
    spatial and photometric metadata (x, y, flux, radius, area, perimeter).

    Supports two complementary detection pathways:
    1. 'blob' (default): Uses cv2.SimpleBlobDetector configured with minThreshold,
       maxThreshold, and filterByArea to find compact, circular blobs (e.g. stars,
       wildfire hotspots, discrete emission spikes).
    2. 'contours': Uses cv2.findContours on a thresholded residual image to detect
       irregularly shaped point sources and calculate their exact geometric area
       and perimeter.

    Args:
        residual_image: 2D quantitative residual scalar array, typically the 'point_source_layer'
                        from separate_features() normalized in [0.0, 1.0], or 8-bit image.
        method: Detection method: 'blob' (default) or 'contours'.
        min_threshold: Minimum intensity threshold for blob detection or binarization.
                       Accepts either normalized [0.0, 1.0] or 8-bit [0, 255] values (default: 20.0).
        max_threshold: Maximum intensity threshold for blob detection.
                       Accepts either normalized [0.0, 1.0] or 8-bit [0, 255] values (default: 250.0).
        filter_by_area: Whether to filter point sources by pixel area (default: True).
        min_area: Minimum area in pixels (default: 1.0).
        max_area: Maximum area in pixels (default: 5000.0).
        filter_by_circularity: Whether to enforce circularity for blob detection (default: False).
        min_circularity: Minimum circularity ratio [0.0, 1.0] (default: 0.5).
        max_circularity: Maximum circularity ratio (default: 1.0).
        threshold: Explicit binarization threshold for the 'contours' method. If None,
                   derived from min_threshold. Pass 'otsu' for automatic Otsu thresholding.
        sort_by: Optional key to sort returned point sources by ('flux', 'area', 'radius', 'x', 'y').
        descending: Sort direction when sort_by is specified (default: True for flux/area).
        **kwargs: Parameter aliases and OpenCV-specific overrides:
            - minThreshold / maxThreshold: Aliases for min_threshold / max_threshold.
            - filterByArea / minArea / maxArea: Aliases for area parameters.
            - filterByCircularity / minCircularity: Aliases for circularity parameters.
            - threshold_step / thresholdStep: Threshold increment for SimpleBlobDetector.
            - min_repeatability / minRepeatability: Minimum repeatability count (default: 1).
            - min_dist_between_blobs / minDistBetweenBlobs: Minimum distance in pixels (default: 2.0).
            - blob_color / blobColor: Target blob color (default: 255 for bright point sources).

    Returns:
        List[Dict[str, Any]]: List of metadata dictionaries for each detected point source,
        containing:
            - "x": float, horizontal center coordinate (sub-pixel precision).
            - "y": float, vertical center coordinate (sub-pixel precision).
            - "radius": float, detected or enclosing radius in pixels.
            - "flux": float, peak intensity in [0.0, 1.0] within the point source.
            - "area": float, geometric area in pixels squared.
            - "perimeter": float, contour or circular perimeter in pixels.
            - "center": Tuple[float, float], (x, y) coordinate pair.
            - "peak_intensity": float, alias for "flux".
            - "method": str, detection method used ('blob' or 'contours').

    Raises:
        TypeError: If residual_image is None or cannot be parsed as a NumPy array.
        ValueError: If residual_image is empty, not 2D, or parameters are invalid.
        MorphologyError: If detection method is unrecognized.
    """
    if residual_image is None:
        raise TypeError("residual_image cannot be None.")

    method_clean = str(method).strip().lower()
    if method_clean in ("blob", "blobs", "blob_detector", "simple_blob"):
        return detect_point_sources_blob(
            residual_image=residual_image,
            min_threshold=min_threshold,
            max_threshold=max_threshold,
            filter_by_area=filter_by_area,
            min_area=min_area,
            max_area=max_area,
            filter_by_circularity=filter_by_circularity,
            min_circularity=min_circularity,
            max_circularity=max_circularity,
            sort_by=sort_by,
            descending=descending,
            **kwargs,
        )
    elif method_clean in ("contours", "contour", "find_contours"):
        return detect_point_sources_contours(
            residual_image=residual_image,
            threshold=threshold,
            min_area=min_area,
            max_area=max_area,
            filter_by_area=filter_by_area,
            sort_by=sort_by,
            descending=descending,
            min_threshold=min_threshold,
            max_threshold=max_threshold,
            filter_by_circularity=filter_by_circularity,
            min_circularity=min_circularity,
            max_circularity=max_circularity,
            **kwargs,
        )
    else:
        raise ValueError(
            f"Unknown point source detection method: '{method}'. Supported methods: 'blob', 'contours'."
        )


__all__ = [
    "MorphologyError",
    "separate_features",
    "detect_point_sources",
    "detect_point_sources_blob",
    "detect_point_sources_contours",
]
