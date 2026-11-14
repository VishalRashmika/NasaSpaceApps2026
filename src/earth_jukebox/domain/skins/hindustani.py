"""F-052: Hindustani raga skin (Malhar family, provisional).

Per docs/08 §3:
- Sa Re ga Ma Pa Dha ni scale: (0, 200, 300, 500, 700, 900, 1000) cents
- tonic_midi = 48.0 (C3)
- n_octaves = 2 (N = 15 pitches)
- glide_descending = True (meend glides on descending steps)
- phrases = {"pakad_1": (0, -1, -2, -1, 0)}
- provisional = True (pending musician validation per docs/08 §5)
"""

from __future__ import annotations

from earth_jukebox.domain.models import Skin, VariableCategory

HINDUSTANI_SKIN = Skin(
    id="hindustani",
    name="Hindustani",
    tonic_midi=48.0,
    scale_cents=(0.0, 200.0, 300.0, 500.0, 700.0, 900.0, 1000.0),
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
    phrases={
        "pakad_1": (0, -1, -2, -1, 0),
    },
    glide_descending=True,
    provisional=True,
    tension_cents=600.0,
)
