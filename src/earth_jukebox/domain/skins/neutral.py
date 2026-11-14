"""F-051: Neutral skin (scientific default).

Major pentatonic (0, 200, 400, 700, 900) across 2 octaves from C3 (N = 11 pitches, doc 08 §2).
Instrument families per doc 06 §6.
"""

from __future__ import annotations

from earth_jukebox.domain.models import Skin, VariableCategory

NEUTRAL_SKIN = Skin(
    id="neutral",
    name="Neutral (scientific)",
    tonic_midi=48.0,
    scale_cents=(0.0, 200.0, 400.0, 700.0, 900.0),
    n_octaves=2,
    instrument_map={
        VariableCategory.TEMPERATURE: "strings",
        VariableCategory.PRECIPITATION: "pluck",
        VariableCategory.VEGETATION: "flute",
        VariableCategory.ICE: "bell",
        VariableCategory.AEROSOL: "texture",
        VariableCategory.OCEAN: "pad",
        VariableCategory.GENERIC: "pad",
    },
    rhythm_patterns={},
    phrases={},
    glide_descending=False,
    provisional=False,
    tension_cents=200.0,
)
