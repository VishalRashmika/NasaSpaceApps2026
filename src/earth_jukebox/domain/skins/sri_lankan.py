"""F-053: Sri Lankan skin (provisional).

Per docs/08 §4:
- scale_cents = (0.0, 200.0, 400.0, 700.0, 1000.0) (placeholder pentatonic)
- tonic_midi = 48.0 (C3)
- n_octaves = 2
- provisional = True (pending musician validation per docs/08 §5)
- lead flute, percussion voice for rhythm, others per neutral
- rhythm_patterns = {"d1": (1.0,), "d2": (1.0, 0.6), "d4": (1.0, 0.5, 0.8, 0.5)}
"""

from __future__ import annotations

from earth_jukebox.domain.models import Skin, VariableCategory

SRI_LANKAN_SKIN = Skin(
    id="sri_lankan",
    name="Sri Lankan",
    tonic_midi=48.0,
    scale_cents=(0.0, 200.0, 400.0, 700.0, 1000.0),
    n_octaves=2,
    instrument_map={
        VariableCategory.TEMPERATURE: "flute",
        VariableCategory.PRECIPITATION: "pluck",
        VariableCategory.VEGETATION: "flute",
        VariableCategory.ICE: "bell",
        VariableCategory.AEROSOL: "texture",
        VariableCategory.OCEAN: "pad",
        VariableCategory.GENERIC: "flute",
    },
    rhythm_patterns={
        "d1": (1.0,),
        "d2": (1.0, 0.6),
        "d4": (1.0, 0.5, 0.8, 0.5),
    },
    phrases={},
    glide_descending=False,
    provisional=True,
    tension_cents=200.0,
)
