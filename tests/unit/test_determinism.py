"""Tests for F-102 (Determinism & golden tests)."""

from __future__ import annotations

import json
from pathlib import Path

from earth_jukebox.application.use_cases.sonify import sonify
from earth_jukebox.domain.mapping_version import MAPPING_VERSION
from earth_jukebox.domain.sonification.score_serde import score_to_json
from earth_jukebox.infrastructure.vision.synthetic import generate_map

GOLDEN_PATH = Path("tests/golden/score_golden.json")


def test_f102_ac1_determinism_two_runs_identical() -> None:
    # AC1: two runs of the sonify pipeline give byte-identical Score JSON
    fixtures = ["viridis", "turbo", "RdBu_r"]
    for cmap in fixtures:
        _, field, _, _, _ = generate_map(cmap=cmap, seed=123, map_width=120, map_height=60)
        score1 = sonify(field)
        score2 = sonify(field)

        json1 = score_to_json(score1)
        json2 = score_to_json(score2)
        assert json1 == json2, f"Pipeline not deterministic for fixture {cmap}"


def test_f102_ac2_golden_score_matches() -> None:
    # AC2: golden Score JSON committed in tests/golden/; test fails on any diff
    assert GOLDEN_PATH.exists(), f"Golden file missing at {GOLDEN_PATH}"
    golden_text = GOLDEN_PATH.read_text(encoding="utf-8")
    golden_data = json.loads(golden_text)

    # Test asserts the golden's mapping_version equals MAPPING_VERSION
    assert golden_data["mapping_version"] == MAPPING_VERSION

    # Re-run on fixed synthetic fixture
    _, field, _, _, _ = generate_map(cmap="viridis", seed=42, map_width=240, map_height=120)
    score = sonify(field)
    current_json = score_to_json(score)

    assert current_json == golden_text, (
        "Current sonify output differs from tests/golden/score_golden.json. "
        "Any change requires bumping MAPPING_VERSION per doc 06."
    )
