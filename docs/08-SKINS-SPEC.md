# 08 — Skins Spec (Module SKN)

## 1. Principle

A skin is **data** (`domain.models.Skin`): a scale, an instrument map, rhythm patterns and ornament phrases. It never changes *what* is encoded. Invariance rules (tested by F-054):

- Onset times, durations, velocities, accents, voice ids and pans are **identical across skins** for the same field.
- Pitch is a **monotonic non-decreasing** function of value in every skin (rank order preserved).
- Only `pitch_midi`, `glide_to_midi`, instrument ids, and *ornament-kind* notes may differ.

This is what keeps cultural flavour from diluting the information.

Registration: `domain/skins/` (one module per skin, each exposing a `Skin`), registry functions `get_skin`, `list_skins`.

## 2. Neutral skin (default, F-051)

| Field | Value |
|---|---|
| id / name | `neutral` / "Neutral (scientific)" |
| tonic_midi | 48 (C3) |
| scale_cents | `(0, 200, 400, 700, 900)` (major pentatonic) |
| n_octaves | 2 → pitches C3…C5, **N = 11** pitches (`2·5+1`) |
| instruments | per doc 06 §6 |
| ornaments | default grace note (doc 06 §9) |

## 3. Hindustani skin (F-052) — **PROVISIONAL, needs musician validation**

> ⚠ The note sets below are **provisional placeholders chosen by the spec author, who is not a substitute for a Hindustani musician.** The skin ships labelled "(provisional)" in the UI until the team musician fills the "Validated?" column. Ragas also involve microtonal shruti, characteristic phrases and time/season associations that a 12-tone table cannot capture; the machinery below lets the musician supply cents offsets (e.g. `294.0`) without code changes.

Because pitch must depend only on value (P2), **direction-dependent scales (aroha/avaroha) are not used for pitch**. Instead the raga character is carried by (a) the single scale set, (b) **pakad phrases** inserted as ornaments on accented cells, (c) **meend (glide)** on descending steps.

| Skin id | Intended association (tradition) | Provisional scale_cents (Sa = 0) | Validated? |
|---|---|---|---|
| `hindustani_malhar` | Rain / monsoon (Malhar family, e.g. Miyan ki Malhar, Megh) | `(0, 200, 300, 500, 700, 900, 1000)` — Sa Re ga Ma Pa Dha ni (provisional, Kafi-like) | **TO BE VALIDATED** |
| `hindustani_deepak` | Heat (legend of Raga Deepak) — stretch | **musician to supply**; until then not shipped | **TO BE VALIDATED** |

- `tonic_midi = 48` (C3 as Sa; the musician may prefer another Sa — change one number).
- `n_octaves = 2`, N = 2·7+1 = 15 for the 7-note provisional set.
- `glide_descending = True`: when the pitch of a cell is lower than the previous column's pitch in the same band, the previous note gets `glide_to_midi = <this note's pitch>` (meend). Pitch of the *next* note is unchanged (invariance holds).
- `phrases`: `{"pakad_1": (0, -1, -2, -1, 0)}` etc. = scale-degree **offsets relative to the accented cell's degree**; placed as `kind="ornament"` notes, 0.125 beat each, ending right before the accented note (musician to supply real pakad phrases; provisional values are neutral shapes).
- Instruments: precipitation → `pluck` (sitar-like pluck timbre variant), temperature → `strings`, others as neutral; `flute` (bansuri-like) available.

**Suggested skin per variable (UI hint, no code branching):** precipitation → `hindustani_malhar`; others → `neutral`.

## 4. Sri Lankan skin (F-053) — **PROVISIONAL**

> ⚠ Same caveat. The team's own knowledge of Sri Lankan traditional music is the authority here. The provisional scale and patterns are *placeholders that make the machinery testable*, **not** claims about Sinhala/Tamil musical tradition.

| Field | Provisional value | Validated? |
|---|---|---|
| id | `sri_lankan` | |
| scale_cents | `(0, 200, 400, 700, 1000)` (placeholder pentatonic) | **TO BE VALIDATED** |
| instruments | lead `flute` (stand-in for horane / flute timbre), `percussion` voice for rhythm (stand-in for geta bera / rabana / thammattama), others per neutral | |
| rhythm_patterns | keyed `"d1"`, `"d2"`, `"d4"` = onset weights per subdivision for density classes 1/2/4, e.g. `d1=(1.0,)`, `d2=(1.0,0.6)`, `d4=(1.0,0.5,0.8,0.5)` (placeholders) | **TO BE VALIDATED** |

- The `percussion` voice is an **extra voice** `perc` (`band_index=-2`, pan 0) that plays the pattern for each *main* note onset's density class. It adds texture but **no new information** (it mirrors density). F-054 treats `perc` notes as `kind="ornament"`.
- Sample-based voices (doc 07 §6a): the team may record geta bera / rabana / flute hits and drop them into `data/audio/sri_lankan/`.

## 5. Human validation procedure (do this, agent cannot)

1. The musician reviews tables in §3 and §4; fills in real `scale_cents`, phrases, patterns in the "Validated?" column or in a PR to these tables, then sets `provisional=False` in the skin file via an agent request: *"update skin X from the validated table in docs/08"*.
2. Listen A/B with the neutral skin on the same image; confirm the data trend is still audible (pitch goes up when value goes up).
3. Record the musician's name/credit and any sources in `docs/SUBMISSION/CREDITS.md`.

## 6. Scalability to other weather/variables

New variable ⇒ add a `VariableCategory` only if its instrument family differs (doc 06 §6); otherwise reuse `generic`. New skin ⇒ add one `Skin` data module, a row in docs/08, and run the F-054 invariance test — no engine changes. This is the answer to "how does the Malhar idea scale to other weather": the raga is a *skin*, selectable per variable; the data mapping underneath never changes.
