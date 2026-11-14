"""F-034: Audio legend sweep use case.

Produces a 32-note Score stepping u=0->1 at 96 bpm, one voice with the category
instrument, plus an accent bell marker at the centre for diverging maps.
"""

from __future__ import annotations

import numpy as np

from earth_jukebox.domain.mapping_version import MAPPING_VERSION
from earth_jukebox.domain.models import (
    ColormapKind,
    LegendSpec,
    NoteEvent,
    Score,
    Skin,
    VariableCategory,
    Voice,
)
from earth_jukebox.domain.skins import get_skin
from earth_jukebox.domain.sonification import (
    denormalize_u,
    get_pitch_set,
    quantize_pitch,
    round_half_up,
)


def legend_score(legend: LegendSpec, skin: Skin | None = None) -> Score:
    """Generate audio legend sweep Score (32 notes stepping u=0->1)."""
    if skin is None:
        skin = get_skin("neutral")

    fallback_inst = skin.instrument_map.get(VariableCategory.GENERIC, "pad")
    inst = skin.instrument_map.get(legend.category, fallback_inst)

    legend_voice = Voice(
        id="legend",
        band_index=0,
        instrument=inst,
        pan=0.0,
    )
    voices = [legend_voice]

    notes: list[NoteEvent] = []
    n_steps = 32

    # Diverging center step
    center_step = round_half_up(0.5 * (n_steps - 1))  # 16
    has_center_bell = legend.kind is ColormapKind.DIVERGING

    if has_center_bell:
        voices.append(
            Voice(
                id="accent",
                band_index=-1,
                instrument="bell",
                pan=0.0,
            )
        )

    p_set = get_pitch_set(skin)
    center_idx = (len(p_set) - 1) // 2
    middle_tonic = p_set[center_idx]

    for k in range(n_steps):
        u = k / float(n_steps - 1)
        pitch_val = quantize_pitch(u, skin)
        phys_val = float(denormalize_u(u, legend))
        t = float(k)

        notes.append(
            NoteEvent(
                voice_id="legend",
                t_beat=t,
                dur_beat=0.9,
                pitch_midi=pitch_val,
                velocity=0.7,
                accent=False,
                col=k,
                band=0,
                value=phys_val,
                roughness=0.0,
                kind="main",
            )
        )

        if has_center_bell and k == center_step:
            notes.append(
                NoteEvent(
                    voice_id="accent",
                    t_beat=t,
                    dur_beat=0.9,
                    pitch_midi=middle_tonic + 12.0,
                    velocity=0.7,
                    accent=True,
                    col=k,
                    band=0,
                    value=phys_val,
                    roughness=0.0,
                    kind="accent_bell",
                )
            )

    # Sort notes
    notes.sort(key=lambda n: (round(n.t_beat, 6), n.voice_id, round(n.pitch_midi, 6)))

    return Score(
        mapping_version=MAPPING_VERSION,
        skin_id=skin.id,
        seed=0,
        bpm=96.0,
        total_beats=float(n_steps),
        n_cols=n_steps,
        n_bands=1,
        voices=tuple(voices),
        notes=tuple(notes),
        drone_midi=(),
        legend=legend,
        provenance={"type": "legend_sweep"},
    )


def legend_pitch_r(legend: LegendSpec, skin: Skin | None = None) -> float:
    """Compute Pearson correlation r between legend sweep values and quantized pitches (F-079)."""
    score = legend_score(legend, skin)
    main_notes = [n for n in score.notes if n.kind == "main" and n.value is not None]
    if len(main_notes) < 2:
        return 1.0

    vals = np.array([float(n.value) for n in main_notes if n.value is not None], dtype=np.float64)
    pitches = np.array([float(n.pitch_midi) for n in main_notes], dtype=np.float64)

    std_v = float(np.std(vals))
    std_p = float(np.std(pitches))
    if std_v == 0.0 or std_p == 0.0:
        return 1.0

    r_matrix = np.corrcoef(vals, pitches)
    return float(r_matrix[0, 1])
