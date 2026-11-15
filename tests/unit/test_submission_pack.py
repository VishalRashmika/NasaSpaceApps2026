"""Unit tests for F-105: Submission Pack and compliance."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUBMISSION_DIR = ROOT / "docs" / "SUBMISSION"
EVAL_REPORT = ROOT / "docs" / "EVAL-REPORT.md"


def test_f105_submission_pack_files_exist() -> None:
    required_files = [
        "01-PROJECT-SUMMARY.md",
        "02-METHODOLOGY.md",
        "03-AI-TOOL-DISCLOSURE.md",
        "04-DATA-CREDITS.md",
        "05-DEMO-SCRIPT.md",
        "06-SCREENSHOTS-AND-ASSETS.md",
        "07-ACCESSIBILITY-STATEMENT.md",
    ]
    for filename in required_files:
        filepath = SUBMISSION_DIR / filename
        assert filepath.is_file(), f"Missing submission pack file: {filename}"
        assert filepath.stat().st_size > 100, f"Submission file {filename} is too short"


def test_f105_summary_numbers_link_to_eval_report() -> None:
    # F-105 AC: every claim of a number in the summary links to a line in EVAL-REPORT.md
    summary_text = (SUBMISSION_DIR / "01-PROJECT-SUMMARY.md").read_text(encoding="utf-8")
    eval_lines = EVAL_REPORT.read_text(encoding="utf-8").splitlines()

    # Find markdown links to EVAL-REPORT.md#L<line_number>
    pattern = r"\[([^\]]+)\]\((?:file:///[^\)]+/)?docs/EVAL-REPORT\.md#L(\d+)\)"
    matches = re.findall(pattern, summary_text)
    assert len(matches) >= 3, f"Expected at least 3 metric links in summary, found {len(matches)}"

    for text_claim, line_str in matches:
        line_num = int(line_str)
        assert 1 <= line_num <= len(eval_lines), f"Line L{line_num} out of bounds in EVAL-REPORT.md"
        target_line = eval_lines[line_num - 1]

        # Extract numeric components from the claim (e.g. '0.326%' -> '0.326', '0.9914' -> '0.9914')
        numbers = re.findall(r"\d+\.\d+", text_claim)
        assert numbers, f"No number found in claim '{text_claim}'"
        for num in numbers:
            assert num in target_line, (
                f"Claimed number '{num}' from '{text_claim}' not found "
                f"in EVAL-REPORT.md line {line_num}: '{target_line}'"
            )


def test_f105_credits_include_bundled_samples() -> None:
    # F-105 AC: credits include every bundled sample's credit
    credits_text = (SUBMISSION_DIR / "04-DATA-CREDITS.md").read_text(encoding="utf-8")
    samples_dir = ROOT / "data" / "samples"

    if samples_dir.exists():
        for sample_path in samples_dir.iterdir():
            if sample_path.is_dir() and not sample_path.name.startswith("_"):
                meta_file = sample_path / "meta.json"
                if meta_file.exists():
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    credit = meta.get("credit")
                    if credit:
                        assert credit in credits_text, (
                            f"Sample '{sample_path.name}' credit '{credit}' "
                            f"missing from 04-DATA-CREDITS.md"
                        )


def test_f105_methodology_renders_mapping_table() -> None:
    methodology_text = (SUBMISSION_DIR / "02-METHODOLOGY.md").read_text(encoding="utf-8")
    # All 10 mapping keys from F-033 must be present
    required_keys = [
        "value->pitch",
        "longitude->time",
        "latitude_band->voice_pan",
        "local_variability->rhythm_density",
        "local_variability->roughness",
        "global_variability->tempo",
        "extremes->accent",
        "masked->silence",
        "category->instrument",
        "global_mean->drone_brightness",
    ]
    for key in required_keys:
        assert key in methodology_text, f"Missing mapping key in methodology table: {key}"


def test_f105_readme_is_concise_and_links_submission() -> None:
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert len(readme_text) > 200, "README.md must not be empty"
    assert "docs/SUBMISSION/" in readme_text, "README.md does not reference docs/SUBMISSION/"
