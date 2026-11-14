"""Unit tests for F-050 (Skin registry) and F-051 (Neutral skin)."""

from __future__ import annotations

import pytest

from earth_jukebox.domain.errors import NotFoundError
from earth_jukebox.domain.models import Skin, VariableCategory
from earth_jukebox.domain.skins import get_skin, list_skins, register_skin
from earth_jukebox.domain.skins.neutral import NEUTRAL_SKIN


def test_f050_ac_unknown_id_raises_not_found() -> None:
    # F-050 AC: unknown id -> NotFoundError
    with pytest.raises(NotFoundError) as exc_info:
        get_skin("non_existent_skin")
    assert "non_existent_skin" in str(exc_info.value)


def test_f050_ac_all_skins_scale_cents_valid() -> None:
    # F-050 AC: every skin's scale_cents[0] == 0, ascending, < 1200
    skins = list_skins()
    assert len(skins) >= 1
    for skin in skins:
        assert isinstance(skin, Skin)
        assert len(skin.scale_cents) > 0, f"skin {skin.id} has empty scale_cents"
        assert skin.scale_cents[0] == 0.0, f"skin {skin.id} scale_cents[0] != 0"
        for i in range(len(skin.scale_cents) - 1):
            assert skin.scale_cents[i] < skin.scale_cents[i + 1], (
                f"skin {skin.id} scale_cents not strictly ascending"
            )
        assert all(0.0 <= c < 1200.0 for c in skin.scale_cents), (
            f"skin {skin.id} has cents >= 1200 or < 0"
        )


def test_f050_register_validation() -> None:
    with pytest.raises(ValueError, match="empty scale_cents"):
        register_skin(
            Skin(
                id="bad1",
                name="Bad",
                tonic_midi=60,
                scale_cents=(),
                n_octaves=2,
                instrument_map={},
            )
        )
    with pytest.raises(ValueError, match=r"scale_cents\[0\] must be 0.0"):
        register_skin(
            Skin(
                id="bad2",
                name="Bad",
                tonic_midi=60,
                scale_cents=(100.0, 200.0),
                n_octaves=2,
                instrument_map={},
            )
        )
    with pytest.raises(ValueError, match="strictly ascending"):
        register_skin(
            Skin(
                id="bad3",
                name="Bad",
                tonic_midi=60,
                scale_cents=(0.0, 200.0, 200.0),
                n_octaves=2,
                instrument_map={},
            )
        )
    with pytest.raises(ValueError, match=r"must be in \[0.0, 1200.0\)"):
        register_skin(
            Skin(
                id="bad4",
                name="Bad",
                tonic_midi=60,
                scale_cents=(0.0, 1200.0),
                n_octaves=2,
                instrument_map={},
            )
        )


def test_f051_ac_neutral_skin_properties() -> None:
    # F-051: Major pentatonic across 2 octaves from C3 (tonic_midi=48.0)
    neutral = get_skin("neutral")
    assert neutral is NEUTRAL_SKIN
    assert neutral.id == "neutral"
    assert neutral.tonic_midi == 48.0
    assert neutral.scale_cents == (0.0, 200.0, 400.0, 700.0, 900.0)
    assert neutral.n_octaves == 2
    assert neutral.provisional is False

    # Instruments mapping per doc 08 §2 & doc 06 §6
    expected_instruments = {
        VariableCategory.TEMPERATURE: "strings",
        VariableCategory.PRECIPITATION: "pluck",
        VariableCategory.VEGETATION: "flute",
        VariableCategory.ICE: "bell",
        VariableCategory.AEROSOL: "texture",
        VariableCategory.OCEAN: "pad",
        VariableCategory.GENERIC: "pad",
    }
    for cat, inst in expected_instruments.items():
        assert neutral.instrument_map[cat] == inst
