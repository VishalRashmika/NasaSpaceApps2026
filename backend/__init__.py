"""
The Earth Jukebox - Backend Package.
"""

from backend.morphology import (
    MorphologyError,
    SegmentationResult,
    detect_point_sources,
    detect_point_sources_blob,
    detect_point_sources_contours,
    segment_touching_objects,
    separate_features,
)
from backend.pipeline import (
    ColorbarNotFoundError,
    PipelineError,
    apply_lut_to_image,
    build_colorbar_lut,
    detect_colorbar_bounding_box,
    extract_data,
    extract_data_colorbar,
    extract_data_vector_quantization,
    generate_colormap_codebook,
    load_image,
    preprocess_image,
)

__all__ = [
    "extract_data",
    "extract_data_colorbar",
    "extract_data_vector_quantization",
    "generate_colormap_codebook",
    "load_image",
    "preprocess_image",
    "detect_colorbar_bounding_box",
    "build_colorbar_lut",
    "apply_lut_to_image",
    "ColorbarNotFoundError",
    "PipelineError",
    "MorphologyError",
    "SegmentationResult",
    "segment_touching_objects",
    "separate_features",
    "detect_point_sources",
    "detect_point_sources_blob",
    "detect_point_sources_contours",
]
