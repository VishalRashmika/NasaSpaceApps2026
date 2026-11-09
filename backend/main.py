"""
The Earth Jukebox - Pipeline Orchestrator and CLI Entrypoint.

This module coordinates data extraction from NASA Earth Information Center (EIC)
visualizations, orchestrating the dual-pathway extraction architecture:
1. Primary Pathway: Colorbar Parsing (direct RGB-to-scalar LUT recovery).
2. Fallback Pathway: Vector Quantization (reverse-engineering artist palette via scipy.cluster.vq).

Architectural Note on Alternative Approaches:
---------------------------------------------
The 'unmap' package (https://github.com/stefanv/unmap) offers an alternative
approach for inverse colormap lookup by computing distances in perceptual color spaces.
In this pipeline, we implement Vector Quantization via scipy.cluster.vq as our universal,
dependency-free fallback to ensure robust nearest-neighbor data recovery across any
scientific colormap without requiring external C-extensions.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from backend.morphology import (
    detect_point_sources,
    separate_features,
)
from backend.pipeline import (
    ColorbarNotFoundError,
    PipelineError,
    extract_data,
    extract_data_colorbar,
    extract_data_vector_quantization,
    generate_colormap_codebook,
    load_image,
    preprocess_image,
)

logger = logging.getLogger("earth_jukebox.main")


def run_pipeline(
    image_path: Union[str, Path, np.ndarray],
    colormap_name: str = "jet",
    output_path: Optional[Union[str, Path]] = None,
    method: str = "auto",
    preprocess: bool = False,
    separate_morphology: bool = False,
    return_metadata: bool = False,
    **kwargs: Any,
) -> Union[np.ndarray, Tuple[np.ndarray, Dict[str, Any]]]:
    """
    Execute the data recovery pipeline on an image.
    Tries the colorbar method first, falling back to vector quantization if it fails.

    Args:
        image_path: Path to the input scientific visualization image, or loaded array.
        colormap_name: Theoretical colormap to use for VQ fallback (default: 'jet').
        output_path: Optional file path to save the recovered scalar array (.npy or .csv).
        method: Extraction pathway: 'auto' (default), 'colorbar', or 'vq'.
        preprocess: Whether to apply CLAHE and noise reduction preprocessing.
        separate_morphology: Whether to separate diffuse emission and point source features.
        return_metadata: Whether to return extraction metadata.
        **kwargs: Additional keyword arguments forwarded to extract_data, preprocess_image,
                  and separate_features.

    Returns:
        np.ndarray: Recovered 2D scalar array [0.0, 1.0].
        (Optional) Dict[str, Any]: Extraction metadata dictionary.
    """
    result = extract_data(
        image_path=image_path,
        colormap_name=colormap_name,
        method=method,
        return_metadata=True,
        **kwargs,
    )
    scalar_array, metadata = result

    if preprocess:
        scalar_array, prep_meta = preprocess_image(
            scalar_array,
            return_metadata=True,
            **kwargs,
        )
        metadata["preprocessing"] = prep_meta

    if separate_morphology or kwargs.get("separate_features", False):
        morph_layers = separate_features(scalar_array, return_metadata=True, **kwargs)
        if kwargs.get("detect_point_sources", False) or kwargs.get("detect_sources", False):
            point_sources = detect_point_sources(morph_layers["point_source_layer"], **kwargs)
            morph_layers["point_sources"] = point_sources
        metadata["morphology"] = morph_layers

    if output_path is not None:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        if out_p.suffix == ".npy":
            np.save(str(out_p), scalar_array)
        elif out_p.suffix in (".csv", ".txt"):
            np.savetxt(str(out_p), scalar_array, delimiter=",")
        else:
            np.save(str(out_p) + ".npy", scalar_array)
        logger.info("Saved extracted scalar array to %s", output_path)

    if return_metadata:
        return scalar_array, metadata
    return scalar_array


def main() -> None:
    """Command-line interface for the data extraction pipeline orchestrator."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        description="The Earth Jukebox - Quantitative Data Recovery Pipeline Orchestrator"
    )
    parser.add_argument("image", help="Path to input NASA scientific visualization image")
    parser.add_argument(
        "--colormap",
        default="jet",
        help="Colormap name for Vector Quantization fallback (default: 'jet')",
    )
    parser.add_argument(
        "--method",
        choices=["auto", "colorbar", "vq"],
        default="auto",
        help="Extraction pathway: 'auto' tries colorbar then falls back to VQ (default: 'auto')",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Optional output path for extracted scalar array (.npy)",
    )
    parser.add_argument(
        "--preprocess",
        action="store_true",
        help="Apply CLAHE contrast adjustment and noise reduction preprocessing",
    )
    parser.add_argument(
        "--separate-features",
        action="store_true",
        help="Separate scalar field into diffuse background and point sources",
    )
    parser.add_argument(
        "--detect-sources",
        action="store_true",
        help="Detect isolated point sources and extract spatial/photometric metadata",
    )
    args = parser.parse_args()

    try:
        scalar, meta = run_pipeline(
            image_path=args.image,
            colormap_name=args.colormap,
            output_path=args.output,
            method=args.method,
            preprocess=args.preprocess,
            separate_morphology=args.separate_features or args.detect_sources,
            detect_point_sources=args.detect_sources,
            return_metadata=True,
        )
        print(
            f"Extraction successful! Method: {meta.get('method')} | "
            f"Shape: {scalar.shape} | Range: [{scalar.min():.4f}, {scalar.max():.4f}]"
        )
    except Exception as e:
        print(f"Error executing pipeline: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
