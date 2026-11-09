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
from backend.scanner import (
    DEFAULT_CHANNEL_REGISTERS,
    MUSICAL_SCALES,
    ScanGeometry,
    ScanHead,
    compress_dynamic_range,
    frequency_to_midi,
    generate_scan_path,
    map_parameters,
    midi_to_frequency,
    quantize_to_scale,
)

__all__ = [
    # Pipeline
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
    # Morphology
    "MorphologyError",
    "SegmentationResult",
    "segment_touching_objects",
    "separate_features",
    "detect_point_sources",
    "detect_point_sources_blob",
    "detect_point_sources_contours",
    # Scanner & Sonification Engine
    "ScanHead",
    "ScanGeometry",
    "generate_scan_path",
    "map_parameters",
    "quantize_to_scale",
    "compress_dynamic_range",
    "frequency_to_midi",
    "midi_to_frequency",
    "MUSICAL_SCALES",
    "DEFAULT_CHANNEL_REGISTERS",
]
