"""Exit demo script for Phase 1: Data recovery core (docs/04 section 2).

Generates 3 synthetic maps (viridis, turbo, RdBu_r), recovers each via colorbar inversion,
prints the RMSE table vs doc 05 section 9 thresholds, and saves side-by-side PNG figures.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from earth_jukebox.domain.models import ColormapKind, Orientation
from earth_jukebox.infrastructure.colormaps.catalog import MatplotlibColormapCatalog
from earth_jukebox.infrastructure.vision.decoder import PillowImageDecoder
from earth_jukebox.infrastructure.vision.recoverer import VisionFieldRecoverer
from earth_jukebox.infrastructure.vision.synthetic import generate_map

DEMO_CONFIGS = [
    ("viridis", ColormapKind.SEQUENTIAL, 2.0),
    ("turbo", ColormapKind.SEQUENTIAL, 3.0),
    ("RdBu_r", ColormapKind.DIVERGING, 2.0),
]


def run_demo() -> bool:
    cache_dir = Path("data/cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    catalog = MatplotlibColormapCatalog()
    recoverer = VisionFieldRecoverer(catalog)
    decoder = PillowImageDecoder()

    print("=" * 80)
    print("EARTH JUKEBOX — PHASE 1 EXIT DEMO: DATA RECOVERY CORE")
    print("=" * 80)
    print(
        f"{'Colormap':<12} | {'Mode':<10} | {'Conf':<6} | {'RMSE %':<8} | {'Limit':<6} | {'Status'}"
    )
    print("-" * 80)

    all_passed = True
    results: list[dict[str, str | float | bool]] = []

    for cmap, kind, threshold in DEMO_CONFIGS:
        png, truth_field, legend, cbar_box, map_box = generate_map(
            cmap=cmap,
            seed=42,
            orientation=Orientation.HORIZONTAL,
            kind=kind,
        )
        decoded = decoder.decode(png)

        field = recoverer.recover(
            image=decoded,
            legend=legend,
            map_box=map_box,
            colorbar_box=cbar_box,
            preset_name=None,
        )

        truth = truth_field.values
        recovered = field.values
        valid = (~np.isnan(truth)) & (~np.isnan(recovered))

        rmse = float(np.sqrt(np.mean((recovered[valid] - truth[valid]) ** 2)))
        rmse_pct = rmse / (legend.vmax - legend.vmin) * 100.0
        passed = rmse_pct <= threshold
        if not passed:
            all_passed = False

        status = "PASS" if passed else "FAIL"
        print(
            f"{cmap:<12} | {field.quality.mode.value:<10} | "
            f"{field.quality.confidence:.2f}   | {rmse_pct:6.3f}% | "
            f"{threshold:4.1f}% | {status}"
        )

        results.append(
            {
                "cmap": cmap,
                "mode": field.quality.mode.value,
                "conf": field.quality.confidence,
                "rmse_pct": rmse_pct,
                "limit": threshold,
                "passed": passed,
            }
        )

        # Save side-by-side figure: Original | Recovered | Absolute Error %
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        map_crop = decoded.rgb[map_box.y : map_box.y + map_box.h, map_box.x : map_box.x + map_box.w]

        axes[0].imshow(map_crop)
        axes[0].set_title(f"Original ({cmap})")
        axes[0].axis("off")

        # Recovered
        cmap_obj = matplotlib.colormaps.get_cmap(cmap).copy()
        cmap_obj.set_bad(color="gray")
        im1 = axes[1].imshow(
            recovered,
            cmap=cmap_obj,
            vmin=legend.vmin,
            vmax=legend.vmax,
            origin="upper",
        )
        axes[1].set_title("Recovered Scalar Field")
        axes[1].axis("off")
        fig.colorbar(im1, ax=axes[1], orientation="horizontal", fraction=0.046, pad=0.04)

        # Error
        error_pct = np.full_like(truth, np.nan)
        error_pct[valid] = (
            np.abs(recovered[valid] - truth[valid]) / (legend.vmax - legend.vmin) * 100.0
        )
        im2 = axes[2].imshow(
            error_pct, cmap="magma", vmin=0, vmax=max(5.0, threshold), origin="upper"
        )
        axes[2].set_title("Error (% of Range)")
        axes[2].axis("off")
        fig.colorbar(im2, ax=axes[2], orientation="horizontal", fraction=0.046, pad=0.04)

        fig.tight_layout()
        save_path = cache_dir / f"demo_recover_{cmap}.png"
        fig.savefig(save_path, dpi=120)
        plt.close(fig)

    print("-" * 80)
    print(f"Overall Exit Demo Result: {'PASSED' if all_passed else 'FAILED'}")
    print("=" * 80)
    return all_passed


if __name__ == "__main__":
    success = run_demo()
    sys.exit(0 if success else 1)
