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
from typing import Any, Dict, Optional, Tuple, Union

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

    return result


__all__ = [
    "MorphologyError",
    "separate_features",
]
