"""F-091: Per-frame phrases use case.

Each frame -> recovered field (same legend) -> Score phrase;
phrases concatenated with a 1-beat rest.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

import numpy as np

from earth_jukebox.application.ports import FieldRecoverer
from earth_jukebox.application.use_cases.sonify import sonify
from earth_jukebox.domain.errors import InvalidImageError
from earth_jukebox.domain.models import (
    DecodedImage,
    GeoExtent,
    LegendSpec,
    NoteEvent,
    PixelBox,
    ScalarField,
    Score,
    SonificationParams,
)
from earth_jukebox.domain.skins import get_skin
from earth_jukebox.domain.sonification import (
    compute_inter_frame_change_from_fields,
    compute_tension_drone,
)


def concatenate_phrases(
    phrases: Sequence[Score],
    fields: Sequence[ScalarField],
    skin_id: str = "neutral",
) -> Score:
    """Concatenate per-frame Score phrases with 1-beat rests and harmonic tension (F-091, F-092)."""
    if len(phrases) == 0:
        raise InvalidImageError("no phrases to concatenate")

    if len(phrases) == 1:
        return phrases[0]

    first = phrases[0]
    phrase_beats = first.total_beats
    rest_beats = 1.0
    f_count = len(phrases)

    all_notes: list[NoteEvent] = []
    bpms: list[float] = []

    for k, phrase in enumerate(phrases):
        offset_beat = k * (phrase_beats + rest_beats)
        bpms.append(phrase.bpm)
        for note in phrase.notes:
            shifted_note = dataclasses.replace(
                note,
                t_beat=round(note.t_beat + offset_beat, 6),
            )
            all_notes.append(shifted_note)

    # Sort notes by (t_beat, voice_id, pitch_midi)
    all_notes.sort(key=lambda n: (round(n.t_beat, 6), n.voice_id, round(n.pitch_midi, 6)))

    total_beats = round((f_count - 1) * (phrase_beats + rest_beats) + phrase_beats, 6)
    avg_bpm = round(float(np.mean(bpms)), 2)

    # F-092 Harmonic tension
    mean_change = compute_inter_frame_change_from_fields(fields)
    skin = get_skin(skin_id)
    drone_pitches, tension_pitch = compute_tension_drone(skin, mean_change)

    provenance = dict(first.provenance)
    provenance["time_mode"] = "true"
    provenance["n_frames"] = str(f_count)
    provenance["frame_beats"] = str(phrase_beats)
    provenance["rest_beats"] = str(rest_beats)
    provenance["inter_frame_change"] = f"{mean_change:.4f}"
    if tension_pitch is not None:
        provenance["drone_tension_pitch"] = f"{tension_pitch:.2f}"

    return Score(
        mapping_version=first.mapping_version,
        skin_id=first.skin_id,
        seed=first.seed,
        bpm=avg_bpm,
        total_beats=total_beats,
        n_cols=first.n_cols,
        n_bands=first.n_bands,
        voices=first.voices,
        notes=tuple(all_notes),
        drone_midi=drone_pitches,
        legend=first.legend,
        provenance=provenance,
    )


def sonify_animation(
    frames: Sequence[DecodedImage],
    legend: LegendSpec,
    recoverer: FieldRecoverer,
    map_box: PixelBox | None = None,
    colorbar_box: PixelBox | None = None,
    preset_name: str | None = None,
    params: SonificationParams | None = None,
    extent: GeoExtent | None = None,
) -> Score:
    """Sonify a sequence of frames into a time-mode Score (F-091)."""
    if len(frames) == 0:
        raise InvalidImageError("no frames provided for animation sonification")

    params = params or SonificationParams()

    fields: list[ScalarField] = []
    phrases: list[Score] = []

    for frame in frames:
        field = recoverer.recover(
            image=frame,
            legend=legend,
            map_box=map_box,
            colorbar_box=colorbar_box,
            preset_name=preset_name,
        )
        if extent is not None:
            field = dataclasses.replace(field, extent=extent)

        fields.append(field)
        phrase = sonify(field, params)
        phrases.append(phrase)

    return concatenate_phrases(phrases, fields, skin_id=params.skin_id)
