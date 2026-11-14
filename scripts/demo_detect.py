"""Exit demo script for Phase 2: Auto-detection & real-image hardening (docs/04 section 2).

Runs colorbar auto-detection and data recovery on benchmark layouts (and real samples when present).
Prints detected box vs ground-truth box IoU, recovery quality confidence badge, and inversion RMSE.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from earth_jukebox.domain.models import ColormapKind, Orientation, PixelBox
from earth_jukebox.infrastructure.colormaps.catalog import MatplotlibColormapCatalog
from earth_jukebox.infrastructure.storage.samples import FileSystemSampleRepository
from earth_jukebox.infrastructure.vision.autodetect import (
    _compute_iou,
    detect_colorbar,
)
from earth_jukebox.infrastructure.vision.decoder import PillowImageDecoder
from earth_jukebox.infrastructure.vision.recoverer import VisionFieldRecoverer
from earth_jukebox.infrastructure.vision.synthetic import generate_map

SYNTHETIC_LAYOUTS = [
    {
        "id": "syn-viridis-h",
        "cmap": "viridis",
        "kind": ColormapKind.SEQUENTIAL,
        "orientation": Orientation.HORIZONTAL,
        "with_margin": True,
        "with_outline": False,
        "with_title": True,
        "rmse_limit": 2.0,
    },
    {
        "id": "syn-viridis-v",
        "cmap": "viridis",
        "kind": ColormapKind.SEQUENTIAL,
        "orientation": Orientation.VERTICAL,
        "with_margin": True,
        "with_outline": False,
        "with_title": True,
        "rmse_limit": 2.0,
    },
    {
        "id": "syn-turbo-h",
        "cmap": "turbo",
        "kind": ColormapKind.SEQUENTIAL,
        "orientation": Orientation.HORIZONTAL,
        "with_margin": False,
        "with_outline": False,
        "with_title": False,
        "rmse_limit": 3.0,
    },
    {
        "id": "syn-rdbu-v",
        "cmap": "RdBu_r",
        "kind": ColormapKind.DIVERGING,
        "orientation": Orientation.VERTICAL,
        "with_margin": False,
        "with_outline": False,
        "with_title": False,
        "rmse_limit": 2.0,
    },
    {
        "id": "syn-plasma-h",
        "cmap": "plasma",
        "kind": ColormapKind.SEQUENTIAL,
        "orientation": Orientation.HORIZONTAL,
        "with_margin": True,
        "with_outline": True,
        "with_title": True,
        "rmse_limit": 2.0,
    },
    {
        "id": "syn-blues-v",
        "cmap": "Blues",
        "kind": ColormapKind.SEQUENTIAL,
        "orientation": Orientation.VERTICAL,
        "with_margin": True,
        "with_outline": True,
        "with_title": True,
        "rmse_limit": 2.0,
    },
    {
        "id": "syn-magma-h",
        "cmap": "magma",
        "kind": ColormapKind.SEQUENTIAL,
        "orientation": Orientation.HORIZONTAL,
        "with_margin": False,
        "with_outline": True,
        "with_title": False,
        "rmse_limit": 2.0,
    },
    {
        "id": "syn-coolwarm-v",
        "cmap": "coolwarm",
        "kind": ColormapKind.DIVERGING,
        "orientation": Orientation.VERTICAL,
        "with_margin": False,
        "with_outline": True,
        "with_title": False,
        "rmse_limit": 2.0,
    },
]


def _confidence_badge(confidence: float) -> str:
    """Format confidence score into UI badge text (docs/05 §8)."""
    if confidence >= 0.8:
        return "High"
    if confidence >= 0.5:
        return "Medium"
    return "Low"


def run_demo() -> bool:
    print("=" * 85)
    print("EARTH JUKEBOX — PHASE 2 EXIT DEMO: AUTO-DETECTION & REAL-IMAGE HARDENING")
    print("=" * 85)

    decoder = PillowImageDecoder()
    catalog = MatplotlibColormapCatalog()
    recoverer = VisionFieldRecoverer(catalog)

    # 1. Real samples check (if present in data/samples)
    repo = FileSystemSampleRepository(Path("data/samples"))
    real_samples = repo.list()
    if real_samples:
        print(f"\n[REAL SAMPLES] Evaluated {len(real_samples)} samples from data/samples:")
        print(
            f"{'Sample ID':<25} | {'Orient':<10} | {'IoU':<6} | {'Score':<6} | "
            f"{'Badge':<7} | {'RMSE %':<8} | {'Status'}"
        )
        print("-" * 85)
        for meta in real_samples:
            img_bytes = repo.image_bytes(meta.id)
            decoded = decoder.decode(img_bytes)
            cands = detect_colorbar(decoded)
            top = cands[0] if cands else None

            iou = _compute_iou(top.box, meta.colorbar_box) if top and meta.colorbar_box else 0.0
            score_str = f"{top.score:.3f}" if top else "N/A"
            orient_str = top.orientation.value if top else "N/A"

            # Check if truth data exists in sample dir
            sample_dir = Path("data/samples") / meta.id
            truth_path = sample_dir / "truth.npy"
            rmse_str = "N/A"
            if top:
                recovered_field = recoverer.recover(
                    image=decoded,
                    legend=meta.legend,
                    map_box=meta.map_box,
                    colorbar_box=top.box,
                    preset_name=None,
                )
                badge = _confidence_badge(recovered_field.quality.confidence)
                if truth_path.exists():
                    truth_arr = np.load(truth_path)
                    valid = (~np.isnan(truth_arr)) & (~np.isnan(recovered_field.values))
                    if np.any(valid):
                        rmse = float(
                            np.sqrt(
                                np.mean((recovered_field.values[valid] - truth_arr[valid]) ** 2)
                            )
                        )
                        rmse_pct = rmse / (meta.legend.vmax - meta.legend.vmin) * 100.0
                        rmse_str = f"{rmse_pct:5.2f}%"
            else:
                badge = "N/A"

            status = "PASS" if iou >= 0.5 or not meta.colorbar_box else "WARN"
            print(
                f"{meta.id:<25} | {orient_str:<10} | {iou:5.3f} | {score_str:<6} | "
                f"{badge:<7} | {rmse_str:<8} | {status}"
            )
    else:
        print(
            "\n[REAL SAMPLES] No real samples present in data/samples/ (Pending Human Input H-1..H-3)."
        )
        print("                Benchmarking on 8 diverse synthetic layouts per docs/04 §2.")

    # 2. Synthetic benchmark layouts
    print("\n[SYNTHETIC BENCHMARKS] 8 layouts (horizontal/vertical, margins, outlines, colormaps):")
    print(
        f"{'Layout ID':<16} | {'Orient':<10} | {'IoU':<6} | {'Score':<6} | "
        f"{'Badge':<7} | {'RMSE %':<8} | {'Limit':<6} | {'Status'}"
    )
    print("-" * 85)

    all_passed = True
    for i, cfg in enumerate(SYNTHETIC_LAYOUTS):
        png_bytes, truth_field, legend, true_cbar, map_box = generate_map(
            cmap=cfg["cmap"],
            seed=i + 1,
            orientation=cfg["orientation"],
            kind=cfg["kind"],
            with_margin=cfg["with_margin"],
            with_outline=cfg["with_outline"],
            with_title=cfg["with_title"],
        )
        decoded = decoder.decode(png_bytes)
        cands = detect_colorbar(decoded)
        top = cands[0] if cands else None

        if top is None:
            print(
                f"{cfg['id']:<16} | {'N/A':<10} | 0.000 | N/A    | Low     | N/A      | {cfg['rmse_limit']}% | FAIL"
            )
            all_passed = False
            continue

        iou = _compute_iou(top.box, true_cbar)

        # Recover field using detected colorbar box
        recovered_field = recoverer.recover(
            image=decoded,
            legend=legend,
            map_box=map_box,
            colorbar_box=top.box,
            preset_name=None,
        )

        truth_arr = truth_field.values
        rec_arr = recovered_field.values
        valid = (~np.isnan(truth_arr)) & (~np.isnan(rec_arr))
        rmse = float(np.sqrt(np.mean((rec_arr[valid] - truth_arr[valid]) ** 2)))
        rmse_pct = rmse / (legend.vmax - legend.vmin) * 100.0

        badge = _confidence_badge(recovered_field.quality.confidence)
        passed = (iou >= 0.8) and (rmse_pct <= cfg["rmse_limit"])
        if not passed:
            all_passed = False

        status = "PASS" if passed else "FAIL"
        print(
            f"{cfg['id']:<16} | {top.orientation.value:<10} | {iou:5.3f} | {top.score:5.3f} | "
            f"{badge:<7} | {rmse_pct:5.3f}% | {cfg['rmse_limit']:4.1f}% | {status}"
        )

    print("-" * 85)
    print(f"Overall Exit Demo Result: {'PASSED' if all_passed else 'FAILED'}")
    print("=" * 85)
    return all_passed


if __name__ == "__main__":
    success = run_demo()
    sys.exit(0 if success else 1)
