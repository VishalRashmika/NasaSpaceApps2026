"""F-032: Score assembly use case.

Orchestrates F-020...F-031 to produce a Score dataclass from a ScalarField.
"""

from __future__ import annotations

import numpy as np

from earth_jukebox.domain.mapping_version import MAPPING_VERSION
from earth_jukebox.domain.models import NoteEvent, ScalarField, Score, SonificationParams
from earth_jukebox.domain.skins import get_skin
from earth_jukebox.domain.sonification import (
    MIN_COVERAGE_FOR_DATA,
    build_voices,
    col_to_beat,
    compute_bpm,
    compute_drone,
    compute_local_variability,
    compute_seed,
    compute_total_beats,
    denormalize_u,
    find_accented_cells,
    get_band_brightness_str,
    get_pitch_set,
    get_rng,
    normalize_value,
    pitch_to_degree_index,
    quantize_pitch,
    resample_field,
)


def sonify(field: ScalarField, params: SonificationParams | None = None) -> Score:
    """Sonify a ScalarField into a Score intermediate representation."""
    if params is None:
        params = SonificationParams()

    # Time mode multi-frame 3D field (F-091)
    if field.values.ndim == 3:
        import dataclasses

        from earth_jukebox.application.use_cases.time_mode import concatenate_phrases

        n_f = field.values.shape[0]
        sub_fields = [dataclasses.replace(field, values=field.values[k]) for k in range(n_f)]
        phrases = [sonify(f, params) for f in sub_fields]
        return concatenate_phrases(phrases, sub_fields, skin_id=params.skin_id)

    skin = get_skin(params.skin_id)
    n_bands = params.n_bands
    n_cols = params.n_cols

    # 1. Resample field to grid (F-020)
    grid = resample_field(field.values, n_bands=n_bands, n_cols=n_cols)
    means = grid.means
    coverage = grid.coverage

    # 2. Normalisation (F-021)
    grid_u = normalize_value(means, field.legend)

    # Check if completely masked (F-028 AC1)
    valid_mask = (coverage >= MIN_COVERAGE_FOR_DATA) & (~np.isnan(grid_u))
    all_masked = not np.any(valid_mask)

    # 3. Variability & Tempo (F-025, F-026)
    density_grid, roughness_grid = compute_local_variability(grid_u, coverage)
    bpm = compute_bpm(grid_u, coverage)

    # 4. Extremes accents (F-027)
    accented_mask = find_accented_cells(grid_u, coverage)

    # 5. Deterministic seeding (F-031)
    seed = compute_seed(field.source_hash, params)
    rng = get_rng(seed)

    # 6. Voices (F-024, F-029)
    voices = build_voices(skin, field.legend.category, n_bands=n_bands)

    # 7. Drone (F-030)
    drone_midi, drone_brightness = compute_drone(grid_u, coverage, skin)

    # 8. Note generation (F-023, F-025, F-027, F-028, F-031)
    notes: list[NoteEvent] = []
    p_set = get_pitch_set(skin)
    center_idx = (len(p_set) - 1) // 2

    for c in range(n_cols):
        t_base = col_to_beat(c)

        for r in range(n_bands):
            if not valid_mask[r, c]:
                # Rest / silence (F-028)
                continue

            u_val = float(grid_u[r, c])
            pitch_val = quantize_pitch(u_val, skin)
            phys_val = float(denormalize_u(u_val, field.legend))
            is_accented = bool(accented_mask[r, c])
            d = int(density_grid[r, c])
            rough = float(roughness_grid[r, c])
            base_vel = 0.5 + 0.3 * float(coverage[r, c])
            main_vel = min(1.0, base_vel + 0.25) if is_accented else base_vel

            # Ornament check for accented cells (F-031, F-052)
            if is_accented and rng.random() < 0.5:
                curr_idx = pitch_to_degree_index(pitch_val, skin)
                if skin.phrases:
                    # Pakad phrase templates (F-052)
                    phrase_keys = sorted(skin.phrases.keys())
                    phrase_key = phrase_keys[int(rng.integers(0, len(phrase_keys)))]
                    phrase = skin.phrases[phrase_key]
                    m_notes = len(phrase)
                    for j, offset in enumerate(phrase):
                        orn_t = t_base - (m_notes - j) * 0.125
                        if orn_t < 0.0:
                            continue
                        deg_idx = int(np.clip(curr_idx + offset, 0, len(p_set) - 1))
                        orn_pitch = p_set[deg_idx]
                        notes.append(
                            NoteEvent(
                                voice_id=f"band{r}",
                                t_beat=round(orn_t, 6),
                                dur_beat=0.125,
                                pitch_midi=orn_pitch,
                                velocity=round(min(1.0, (main_vel + 0.05) * 0.6), 6),
                                accent=False,
                                col=c,
                                band=r,
                                value=phys_val,
                                roughness=round(rough, 6),
                                kind="ornament",
                            )
                        )
                else:
                    if curr_idx > center_idx:
                        orn_pitch = p_set[curr_idx - 1]
                    elif curr_idx < center_idx:
                        orn_pitch = p_set[curr_idx + 1]
                    else:
                        orn_pitch = p_set[curr_idx]
                    orn_t = max(0.0, t_base - 0.125)
                    notes.append(
                        NoteEvent(
                            voice_id=f"band{r}",
                            t_beat=round(orn_t, 6),
                            dur_beat=0.125,
                            pitch_midi=orn_pitch,
                            velocity=round(min(1.0, (main_vel + 0.05) * 0.6), 6),
                            accent=False,
                            col=c,
                            band=r,
                            value=phys_val,
                            roughness=round(rough, 6),
                            kind="ornament",
                        )
                    )

            # Check descending glide to next column in the same band (F-052 AC3)
            glide_target: float | None = None
            if skin.glide_descending and c + 1 < n_cols and valid_mask[r, c + 1]:
                next_u = float(grid_u[r, c + 1])
                next_pitch = quantize_pitch(next_u, skin)
                if next_pitch < pitch_val:
                    glide_target = next_pitch

            # Main notes
            dur = 0.9 / d
            for k in range(d):
                t = t_base + k / d
                vel = min(1.0, main_vel + 0.05) if k == 0 else min(1.0, main_vel * (0.85**k))
                glide = glide_target if (k == d - 1) else None
                notes.append(
                    NoteEvent(
                        voice_id=f"band{r}",
                        t_beat=round(t, 6),
                        dur_beat=round(dur, 6),
                        pitch_midi=pitch_val,
                        velocity=round(vel, 6),
                        accent=is_accented,
                        col=c,
                        band=r,
                        value=phys_val,
                        glide_to_midi=glide,
                        roughness=round(rough, 6),
                        kind="main",
                    )
                )

            # Accent bell note doubling one octave up
            if is_accented:
                for k in range(d):
                    t = t_base + k / d
                    vel = min(1.0, main_vel + 0.05) if k == 0 else min(1.0, main_vel * (0.85**k))
                    notes.append(
                        NoteEvent(
                            voice_id="accent",
                            t_beat=round(t, 6),
                            dur_beat=round(dur, 6),
                            pitch_midi=pitch_val + 12.0,
                            velocity=round(vel, 6),
                            accent=True,
                            col=c,
                            band=r,
                            value=phys_val,
                            roughness=round(rough, 6),
                            kind="accent_bell",
                        )
                    )

        # Percussion rhythm patterns accompaniment (F-053 AC2)
        if skin.rhythm_patterns:
            col_valid = valid_mask[:, c]
            if np.any(col_valid):
                d_col = int(np.max(density_grid[col_valid, c]))
                pattern = skin.rhythm_patterns.get(f"d{d_col}")
                if pattern:
                    n_sub = len(pattern)
                    is_col_accented = bool(np.any(accented_mask[col_valid, c]))
                    for k_sub, weight in enumerate(pattern):
                        if weight <= 0.0:
                            continue
                        t_sub = t_base + k_sub / n_sub
                        dur_sub = 0.5 / n_sub
                        sub_accent = is_col_accented and (k_sub == 0)
                        sub_vel = min(1.0, (0.7 if sub_accent else 0.5) * weight)
                        notes.append(
                            NoteEvent(
                                voice_id="perc",
                                t_beat=round(t_sub, 6),
                                dur_beat=round(dur_sub, 6),
                                pitch_midi=45.0,
                                velocity=round(sub_vel, 6),
                                accent=sub_accent,
                                col=c,
                                band=-2,
                                value=None,
                                roughness=0.0,
                                kind="ornament",
                            )
                        )

    # Sort notes by (t_beat, voice_id, pitch_midi)
    notes.sort(key=lambda n: (round(n.t_beat, 6), n.voice_id, round(n.pitch_midi, 6)))

    # Provenance
    warnings = list(field.quality.warnings)
    if all_masked:
        warnings.append("all_cells_masked")

    provenance = {
        "recovery_mode": field.quality.mode.value,
        "confidence": f"{field.quality.confidence:.2f}",
        "warnings": ",".join(warnings),
        "band_brightness": get_band_brightness_str(n_bands),
        "drone_brightness": drone_brightness,
    }

    return Score(
        mapping_version=MAPPING_VERSION,
        skin_id=skin.id,
        seed=seed,
        bpm=bpm,
        total_beats=compute_total_beats(n_cols),
        n_cols=n_cols,
        n_bands=n_bands,
        voices=voices,
        notes=tuple(notes),
        drone_midi=drone_midi,
        legend=field.legend,
        provenance=provenance,
    )
