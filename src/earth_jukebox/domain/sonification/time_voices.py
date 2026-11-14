"""F-023: Time/sweep mapping and F-024: Latitude band -> voice & pan.

Mapping rules per docs/06 §5:
- t_beat = col * 1.0, total_beats = n_cols
- voices band0..band4, pans [-0.6, -0.3, 0.0, 0.3, 0.6] (north = left)
- brightness multipliers [0.6, 0.85, 1.15, 0.85, 0.6]
- accent voice: id="accent", band_index=-1, instrument="bell", pan=0.0
"""

from __future__ import annotations

from earth_jukebox.domain.models import Skin, VariableCategory, Voice

DEFAULT_BAND_PANS: tuple[float, ...] = (-0.6, -0.3, 0.0, 0.3, 0.6)
DEFAULT_BAND_BRIGHTNESS: tuple[float, ...] = (0.6, 0.85, 1.15, 0.85, 0.6)


def compute_total_beats(n_cols: int) -> float:
    """Total beats of the sonification track."""
    return float(n_cols)


def col_to_beat(col: int) -> float:
    """Map column index to start beat."""
    return col * 1.0


def build_voices(
    skin: Skin,
    category: VariableCategory,
    n_bands: int = 5,
) -> tuple[Voice, ...]:
    """Construct deterministic Voice objects for bands and accent."""
    fallback = skin.instrument_map.get(VariableCategory.GENERIC, "pad")
    instrument = skin.instrument_map.get(category, fallback)
    voices: list[Voice] = []

    for b in range(n_bands):
        pan = DEFAULT_BAND_PANS[b] if b < len(DEFAULT_BAND_PANS) else 0.0
        voices.append(
            Voice(
                id=f"band{b}",
                band_index=b,
                instrument=instrument,
                pan=pan,
            )
        )

    # Accent voice for extreme bells (doc 06 §5)
    voices.append(
        Voice(
            id="accent",
            band_index=-1,
            instrument="bell",
            pan=0.0,
        )
    )

    # Percussion voice for rhythm patterns (doc 08 §4)
    if skin.rhythm_patterns:
        voices.append(
            Voice(
                id="perc",
                band_index=-2,
                instrument="percussion",
                pan=0.0,
            )
        )

    return tuple(voices)


def get_band_brightness_str(n_bands: int = 5) -> str:
    """Return comma-separated band brightness values for Score provenance."""
    if n_bands == len(DEFAULT_BAND_BRIGHTNESS):
        return ",".join(str(b) for b in DEFAULT_BAND_BRIGHTNESS)
    # Fallback if different n_bands
    return ",".join(["1.0"] * n_bands)
