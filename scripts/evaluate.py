#!/usr/bin/env python3
"""Evaluation report script (F-103).

Runs synthetic fixtures (F-100) and real samples (when present) across the
colormaps catalogued in docs/05 §9, evaluates:
1. Inversion error: RMSE as % of range vs. pass/fail thresholds.
2. Recovery quality: confidence and confidence badge.
3. Sonification fidelity: Score round-trip Pearson r (F-035).
4. Audio legend fidelity: YIN pitch tracker check on legend sweep (F-047).

Writes results reproducibly to docs/EVAL-REPORT.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np

from earth_jukebox.application.use_cases.audio_legend import legend_score
from earth_jukebox.application.use_cases.round_trip import fidelity_round_trip
from earth_jukebox.application.use_cases.sonify import sonify
from earth_jukebox.domain.mapping_version import MAPPING_VERSION
from earth_jukebox.domain.models import (
    ColormapKind,
    Orientation,
    SonificationParams,
)
from earth_jukebox.domain.skins.neutral import NEUTRAL_SKIN
from earth_jukebox.infrastructure.audio.renderer import NumpyAudioRenderer
from earth_jukebox.infrastructure.audio.yin import check_legend_sweep_audio
from earth_jukebox.infrastructure.colormaps.catalog import MatplotlibColormapCatalog
from earth_jukebox.infrastructure.storage.samples import FileSystemSampleRepository
from earth_jukebox.infrastructure.vision.decoder import PillowImageDecoder
from earth_jukebox.infrastructure.vision.recoverer import VisionFieldRecoverer
from earth_jukebox.infrastructure.vision.synthetic import generate_map

# Colormaps and thresholds per docs/05 §9
BENCHMARK_COLORMAPS: list[tuple[str, ColormapKind, float, float]] = [
    # Perceptually uniform (threshold 2%, LUT mean dE <= 2.0)
    ("viridis", ColormapKind.SEQUENTIAL, 2.0, 2.0),
    ("plasma", ColormapKind.SEQUENTIAL, 2.0, 2.0),
    ("inferno", ColormapKind.SEQUENTIAL, 2.0, 2.0),
    ("magma", ColormapKind.SEQUENTIAL, 2.0, 2.0),
    ("cividis", ColormapKind.SEQUENTIAL, 2.0, 2.0),
    # Sequential (threshold 2%, LUT mean dE <= 2.0)
    ("Blues", ColormapKind.SEQUENTIAL, 2.0, 2.0),
    ("Greens", ColormapKind.SEQUENTIAL, 2.0, 2.0),
    ("YlGnBu", ColormapKind.SEQUENTIAL, 2.0, 2.0),
    ("YlOrRd", ColormapKind.SEQUENTIAL, 2.0, 2.0),
    # Diverging (threshold 2%, LUT mean dE <= 2.0)
    ("RdBu_r", ColormapKind.DIVERGING, 2.0, 2.0),
    ("coolwarm", ColormapKind.DIVERGING, 2.0, 2.0),
    ("BrBG", ColormapKind.DIVERGING, 2.0, 2.0),
    # Rainbow / high-contrast (threshold 3%, LUT mean dE <= 2.0)
    ("turbo", ColormapKind.SEQUENTIAL, 3.0, 2.0),
    ("jet", ColormapKind.SEQUENTIAL, 3.0, 2.0),
]


@dataclass(frozen=True)
class SyntheticResult:
    cmap: str
    kind: str
    rmse_pct: float
    threshold_pct: float
    lut_mean_de: float
    lut_de_threshold: float
    confidence: float
    badge: str
    score_round_trip_r: float
    legend_max_cents_err: float
    legend_pitch_r: float
    passed: bool


@dataclass(frozen=True)
class RealSampleResult:
    sample_id: str
    title: str
    confidence: float
    badge: str
    recovery_mode: str
    score_round_trip_r: float
    legend_pitch_r: float


def get_confidence_badge(confidence: float) -> str:
    """UI badge per docs/05 §8: >=0.8 High, 0.5-0.8 Medium, <0.5 Low."""
    if confidence >= 0.8:
        return "High"
    if confidence >= 0.5:
        return "Medium"
    return "Low"


def evaluate_synthetic(
    colormaps: list[tuple[str, ColormapKind, float, float]] | None = None,
) -> list[SyntheticResult]:
    catalog = MatplotlibColormapCatalog()
    recoverer = VisionFieldRecoverer(catalog)
    decoder = PillowImageDecoder()
    renderer = NumpyAudioRenderer()

    cmaps_to_run = colormaps if colormaps is not None else BENCHMARK_COLORMAPS
    results: list[SyntheticResult] = []

    for cmap, kind, rmse_threshold, de_threshold in cmaps_to_run:
        # 1. Deterministic synthetic fixture (seed=42)
        png, truth_field, legend, cbar_box, map_box = generate_map(
            cmap=cmap,
            seed=42,
            orientation=Orientation.HORIZONTAL,
            kind=kind,
        )
        decoded = decoder.decode(png)

        # 2. Field recovery via colorbar inversion
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

        lut_de = field.quality.mean_delta_e

        # 3. Sonification Score round-trip fidelity
        score = sonify(field, SonificationParams(n_bands=5, n_cols=48))
        round_trip_r = fidelity_round_trip(field, score)

        # 4. Audio legend sweep + YIN pitch tracker check
        l_score = legend_score(legend, NEUTRAL_SKIN)
        yin_res = check_legend_sweep_audio(l_score, renderer=renderer, sample_rate=44100)

        passed = (
            rmse_pct <= rmse_threshold
            and lut_de <= de_threshold
            and round_trip_r >= 0.95
            and yin_res.max_cents_error <= 20.0
            and yin_res.audio_legend_r >= 0.98
        )

        results.append(
            SyntheticResult(
                cmap=cmap,
                kind=kind.value,
                rmse_pct=round(rmse_pct, 3),
                threshold_pct=rmse_threshold,
                lut_mean_de=round(lut_de, 3),
                lut_de_threshold=de_threshold,
                confidence=round(field.quality.confidence, 3),
                badge=get_confidence_badge(field.quality.confidence),
                score_round_trip_r=round(round_trip_r, 4),
                legend_max_cents_err=round(yin_res.max_cents_error, 2),
                legend_pitch_r=round(yin_res.audio_legend_r, 4),
                passed=passed,
            )
        )

    return results


def evaluate_real_samples() -> list[RealSampleResult]:
    samples_dir = Path("data/samples")
    if not samples_dir.exists():
        return []

    repo = FileSystemSampleRepository(samples_dir)
    samples = repo.list()
    if not samples:
        return []

    catalog = MatplotlibColormapCatalog()
    recoverer = VisionFieldRecoverer(catalog)
    decoder = PillowImageDecoder()
    renderer = NumpyAudioRenderer()

    results: list[RealSampleResult] = []

    for s in samples:
        try:
            image_path = samples_dir / s.id / s.image_file
            if not image_path.exists():
                continue
            decoded = decoder.decode(image_path.read_bytes())
            field = recoverer.recover(
                image=decoded,
                legend=s.legend,
                map_box=s.map_box,
                colorbar_box=s.colorbar_box,
                preset_name=s.colormap_hint,
            )
            score = sonify(field, SonificationParams(n_bands=5, n_cols=48))
            round_trip_r = fidelity_round_trip(field, score)

            l_score = legend_score(s.legend, NEUTRAL_SKIN)
            yin_res = check_legend_sweep_audio(l_score, renderer=renderer, sample_rate=44100)

            results.append(
                RealSampleResult(
                    sample_id=s.id,
                    title=s.title,
                    confidence=round(field.quality.confidence, 3),
                    badge=get_confidence_badge(field.quality.confidence),
                    recovery_mode=field.quality.mode.value,
                    score_round_trip_r=round(round_trip_r, 4),
                    legend_pitch_r=round(yin_res.audio_legend_r, 4),
                )
            )
        except Exception as e:
            print(f"Warning: could not evaluate real sample {s.id}: {e}", file=sys.stderr)

    return results


def generate_report_markdown(
    syn_results: list[SyntheticResult],
    real_results: list[RealSampleResult],
) -> str:
    all_syn_passed = all(r.passed for r in syn_results)
    mean_rmse = float(np.mean([r.rmse_pct for r in syn_results]))
    mean_round_trip = float(np.mean([r.score_round_trip_r for r in syn_results]))
    mean_legend_r = float(np.mean([r.legend_pitch_r for r in syn_results]))

    lines: list[str] = [
        "# Earth Jukebox — Technical Evaluation & Fidelity Report",
        "",
        "> Machine-generated by `python -m scripts.evaluate` (F-103).",
        f"> **Mapping Version:** `{MAPPING_VERSION}`  ",
        f"> **Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}  ",
        f"> **Status:** {'ALL THRESHOLDS PASSED' if all_syn_passed else 'SOME THRESHOLDS EXCEEDED'}",
        "",
        "## 1. Executive Summary",
        "",
        "Earth Jukebox enforces scientific data fidelity through a three-level verification pipeline:",
        "1. **Level 1 (Data Recovery):** Colorbar inversion accuracy measured against synthetic ground truth (RMSE % of physical range).",
        "2. **Level 2 (Score Round-Trip):** Pearson correlation between resampled grid data and decoded Score note events (r >= 0.95).",
        "3. **Level 3 (Audio Synthesis):** YIN pitch-tracking on synthesized legend sweep audio (max cents error <= 20c, r >= 0.98).",
        "",
        f"- **Mean Inversion RMSE:** `{mean_rmse:.3f}%` of full range (target: <= 2.0% sequential/diverging, <= 3.0% rainbow)",
        f"- **Mean Score Round-Trip Correlation (r):** `{mean_round_trip:.4f}` (target: >= 0.95)",
        f"- **Mean Audio Legend Pitch Correlation (r):** `{mean_legend_r:.4f}` (target: >= 0.98)",
        "",
        "---",
        "",
        "## 2. Synthetic Ground-Truth Benchmarks (F-100 fixtures per docs/05 §9)",
        "",
        "| Colormap | Kind | RMSE % | Limit % | LUT ΔE | Conf | Badge | Score r | Leg Max Err (c) | Leg r | Status |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]

    for r in syn_results:
        status = "**PASS**" if r.passed else "**FAIL**"
        lines.append(
            f"| `{r.cmap}` | {r.kind} | {r.rmse_pct:.3f}% | {r.threshold_pct:.1f}% | "
            f"{r.lut_mean_de:.2f} | {r.confidence:.2f} | {r.badge} | "
            f"{r.score_round_trip_r:.4f} | {r.legend_max_cents_err:.1f}c | "
            f"{r.legend_pitch_r:.4f} | {status} |"
        )

    lines.extend([
        "",
        "### Accuracy Targets & Methodology (docs/05 §9)",
        "- **Synthetic Field:** 2D continuous Gaussian blobs + sinusoidal latitude gradient, rendered at 1024×512 with exact graticule and colorbar.",
        "- **Inversion Algorithm:** CIE L*a*b* space k-d tree color matching with non-data mask segmentation.",
        "- **Acceptance Thresholds:** RMSE <= 2.0% for perceptual/sequential/diverging maps, <= 3.0% for rainbow palettes (turbo/jet).",
        "- **Colorbar LUT Mean ΔE:** Required <= 2.0 ΔE in CIE L*a*b* color difference.",
        "",
        "---",
        "",
        "## 3. Real NASA Samples Evaluation",
        "",
    ])

    if real_results:
        lines.extend([
            "| Sample ID | Title | Confidence | Badge | Mode | Score Round-Trip r | Legend Audio r |",
            "|---|---|---|---|---|---|---|",
        ])
        for s in real_results:
            lines.append(
                f"| `{s.sample_id}` | {s.title} | {s.confidence:.2f} | {s.badge} | "
                f"`{s.recovery_mode}` | {s.score_round_trip_r:.4f} | {s.legend_pitch_r:.4f} |"
            )
    else:
        lines.append(
            "_No real samples currently present in `data/samples/`. "
            "Evaluations will run automatically as NASA imagery is supplied per docs/12._"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 4. Reproducibility & Determinism",
        "",
        "- All synthetic map generators use fixed PRNG seeds (`seed=42`).",
        "- Sonification Score note events are seeded from SHA-256 hashes of input bytes.",
        "- The audio synthesis engine is purely deterministic NumPy DSP.",
        "- Running `python -m scripts.evaluate` yields identical numbers across platforms.",
        "",
    ])

    return "\n".join(lines)


def main() -> int:
    print("=" * 80)
    print("EARTH JUKEBOX — EVALUATION REPORT GENERATOR (F-103)")
    print("=" * 80)

    print("Evaluating synthetic benchmark colormaps…")
    syn_results = evaluate_synthetic()

    print(f"Evaluating real samples…")
    real_results = evaluate_real_samples()

    print(f"Generating docs/EVAL-REPORT.md…")
    md_content = generate_report_markdown(syn_results, real_results)

    report_path = Path("docs/EVAL-REPORT.md")
    report_path.write_text(md_content, encoding="utf-8")

    all_passed = all(r.passed for r in syn_results)

    print("-" * 80)
    for r in syn_results:
        stat = "PASS" if r.passed else "FAIL"
        print(
            f"{r.cmap:<10} | RMSE {r.rmse_pct:5.3f}% (<= {r.threshold_pct:.1f}%) | "
            f"LUT ΔE {r.lut_mean_de:4.2f} | Score r {r.score_round_trip_r:6.4f} | "
            f"Leg r {r.legend_pitch_r:6.4f} | [{stat}]"
        )
    print("-" * 80)
    print(f"Report written to {report_path} ({len(md_content)} bytes)")
    print("=" * 80)

    if not all_passed:
        print("ERROR: One or more colormaps exceeded error thresholds!", file=sys.stderr)
        return 1

    print("ALL BENCHMARKS PASSED SUCCESSFULLY.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
