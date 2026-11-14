"""Unit tests for F-027, F-028, F-029, F-030, F-031."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from earth_jukebox.domain.models import Skin, SonificationParams, VariableCategory
from earth_jukebox.domain.skins import list_skins
from earth_jukebox.domain.skins.neutral import NEUTRAL_SKIN
from earth_jukebox.domain.sonification.accents import find_accented_cells
from earth_jukebox.domain.sonification.drone import compute_drone
from earth_jukebox.domain.sonification.seeding import compute_seed, get_rng


def test_f027_ac1_single_hotspot_accented() -> None:
    # AC1: on a field with a single hot spot, exactly the hot-spot cells are accented
    grid_u = np.full((5, 48), 0.5, dtype=np.float64)
    # One hot spot
    grid_u[2, 10] = 1.0
    coverage = np.ones((5, 48), dtype=np.float64)

    accented = find_accented_cells(grid_u, coverage)
    assert accented[2, 10] is True or accented[2, 10] == 1
    # Exactly one cell is accented
    assert np.sum(accented) == 1


def test_f027_ac2_accent_count_limit() -> None:
    # AC2: accent count <= ceil(5% * valid cells) + ties
    rng = np.random.default_rng(123)
    grid_u = rng.uniform(0.0, 1.0, size=(5, 48))
    coverage = np.ones((5, 48), dtype=np.float64)

    accented = find_accented_cells(grid_u, coverage)
    valid_count = 5 * 48
    max_expected = math.ceil(0.05 * valid_count)
    # With continuous uniform floats, ties are 0 with prob 1
    assert np.sum(accented) <= max_expected + 1


def test_f029_ac_all_categories_resolve() -> None:
    # AC: every VariableCategory resolves for every shipped skin
    for skin in list_skins():
        for cat in VariableCategory:
            inst = skin.instrument_map.get(cat, skin.instrument_map.get(VariableCategory.GENERIC))
            assert inst is not None, f"Skin {skin.id} missing instrument for {cat}"
            assert isinstance(inst, str)


def test_f030_ac_drone_pitches_and_brightness() -> None:
    # AC: drone pitches = tonic and tonic+7 semitones (or skin's fifth); brightness = mean u
    grid_u = np.full((5, 48), 0.654, dtype=np.float64)
    coverage = np.ones((5, 48), dtype=np.float64)

    drone_midi, drone_brightness = compute_drone(grid_u, coverage, NEUTRAL_SKIN)
    assert drone_midi == (48.0, 55.0)
    assert drone_brightness == "0.654"

    # Custom skin with different fifth
    skin = Skin(
        id="test_skin",
        name="Test",
        tonic_midi=60.0,
        scale_cents=(0.0, 300.0, 680.0, 1000.0),
        n_octaves=2,
        instrument_map={},
    )
    drone_midi2, _ = compute_drone(grid_u, coverage, skin)
    # Closest to 700 is 680 -> 6.8 semitones -> 66.8
    assert drone_midi2 == (60.0, 66.8)


def test_f031_ac1_determinism_and_seeding() -> None:
    # AC1: same inputs => identical seed; different source_hash => different seed
    params = SonificationParams()
    s1 = compute_seed("hash_abc", params)
    s2 = compute_seed("hash_abc", params)
    s3 = compute_seed("hash_xyz", params)

    assert s1 == s2
    assert s1 != s3

    # params.seed overrides
    params_override = SonificationParams(seed=999)
    assert compute_seed("hash_abc", params_override) == 999

    rng1 = get_rng(s1)
    rng2 = get_rng(s2)
    assert rng1.random() == rng2.random()


def test_f031_ac2_grep_no_forbidden_calls_in_domain() -> None:
    # AC2: grep-test: no random./time./datetime.now in domain
    domain_dir = Path("src/earth_jukebox/domain")
    py_files = list(domain_dir.glob("**/*.py"))
    assert len(py_files) > 0

    for f in py_files:
        content = f.read_text(encoding="utf-8")
        assert "import random" not in content, f"forbidden 'import random' in {f}"
        assert "from random import" not in content, f"forbidden 'from random import' in {f}"
        assert "import time" not in content, f"forbidden 'import time' in {f}"
        assert "from time import" not in content, f"forbidden 'from time import' in {f}"
        assert "datetime.now" not in content, f"forbidden 'datetime.now' in {f}"
        assert "uuid." not in content, f"forbidden 'uuid' in {f}"
