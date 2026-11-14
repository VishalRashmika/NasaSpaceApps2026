"""Unit tests for F-103 (Evaluation report script)."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.evaluate import (
    BENCHMARK_COLORMAPS,
    evaluate_synthetic,
    generate_report_markdown,
)


def test_f103_ac1_ac2_evaluation_report_fast() -> None:
    # Test generation and thresholds for 3 key colormaps (sequential, diverging, rainbow)
    # Full 14-colormap run is tested in test_f103_ac1_ac2_full_benchmark (slow) and scripts.evaluate
    sample_cmaps = [
        BENCHMARK_COLORMAPS[0],
        BENCHMARK_COLORMAPS[9],
        BENCHMARK_COLORMAPS[12],
    ]  # viridis, RdBu_r, turbo
    results = evaluate_synthetic(sample_cmaps)

    for r in results:
        assert r.passed, (
            f"Colormap {r.cmap} failed benchmark: RMSE {r.rmse_pct}% > {r.threshold_pct}%"
        )
        assert r.rmse_pct <= r.threshold_pct
        assert r.lut_mean_de <= r.lut_de_threshold
        assert r.score_round_trip_r >= 0.95
        assert r.legend_pitch_r >= 0.98
        assert r.legend_max_cents_err <= 20.0
        assert r.badge in ("High", "Medium", "Low")

    md = generate_report_markdown(results, [])
    assert "# Earth Jukebox — Technical Evaluation & Fidelity Report" in md
    assert "viridis" in md
    assert "ALL THRESHOLDS PASSED" in md


def test_f103_eval_report_file_exists() -> None:
    report_file = Path("docs/EVAL-REPORT.md")
    assert report_file.exists(), "docs/EVAL-REPORT.md must exist after evaluate script runs"
    content = report_file.read_text(encoding="utf-8")
    assert "viridis" in content
    assert "ALL THRESHOLDS PASSED" in content


@pytest.mark.slow
def test_f103_ac1_ac2_full_benchmark() -> None:
    results = evaluate_synthetic()
    assert len(results) == len(BENCHMARK_COLORMAPS)
    assert all(r.passed for r in results)
