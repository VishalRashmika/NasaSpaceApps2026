# 06 — Sonification Mapping Spec (Module SON) — `MAPPING_VERSION = 1.0.0`

> The **fixed information layer** (P1). Pure functions in `domain/`. Any change to what a given field sounds like ⇒ bump `MAPPING_VERSION`, update this doc, log a Decision, regenerate the golden test (F-102).

## 1. Grid

`ScalarField (H×W)` → grid of `n_bands × n_cols` (defaults **5 × 48**). Row blocks are equal splits of H (band 0 = north); column blocks equal splits of W (col 0 = west). Each cell holds `mean` (nan-aware) and `coverage` (non-NaN share). Cells with `coverage < 0.25` are **rests** (F-028).

## 2. The fixed mapping table

*(F-033's manifest must expose exactly these keys.)*

| Key | Data property | Sound parameter | Rule (section) |
|---|---|---|---|
| `value->pitch` | Cell mean value `u` | **Pitch** (scale-quantised, 2 octaves) | §4 |
| `longitude->time` | Column index (W→E) | **Time** (1 column = 1 beat; playhead sweeps west→east) | §5 |
| `latitude_band->voice_pan` | Band index (N→S) | **Voice id, pan, brightness** (not pitch) | §5 |
| `local_variability->rhythm_density` | Local gradient `g` | Notes per beat: 1 / 2 / 4 | §7 |
| `local_variability->roughness` | Local gradient `g` | `NoteEvent.roughness` (filter/detune amount) | §7 |
| `global_variability->tempo` | Std of valid `u` | **BPM** 72…120 | §8 |
| `extremes->accent` | Top 5 % of \|u−0.5\| | Velocity +0.25, bell doubling +12 st, optional ornament | §9 |
| `masked->silence` | coverage < 0.25 | **Rest** | §1 |
| `category->instrument` | `VariableCategory` | Instrument family (from skin) | §6 |
| `global_mean->drone_brightness` | Mean `u` over valid cells | Drone brightness hint (provenance) | §10 |

## 3. Normalisation (F-021)

- Sequential, linear: `u = clamp((v − vmin)/(vmax − vmin), 0, 1)`.
- Sequential, log: `u = clamp((log10 v − log10 vmin)/(log10 vmax − log10 vmin), 0, 1)` (v ≤ 0 → treated as vmin).
- Diverging (centre `c = effective_center`): `u = 0.5·(v − vmin)/(c − vmin)` for `v < c`; `u = 0.5 + 0.5·(v − c)/(vmax − c)` for `v ≥ c`, clamped. (If `c == vmin` or `c == vmax`, the degenerate half is skipped.)

## 4. Pitch (F-022)

Given a skin with `tonic_midi = T`, `scale_cents = (c_0=0,…,c_{L−1})`, **`n_octaves = 2`** (required by mapping 1.0.0):

```
P = [ T + 12*o + c_k/100  for o in 0..1  for k in 0..L-1 ] + [ T + 24 ]     # N = 2L + 1 pitches, ascending
idx = round_half_up(u * (N − 1))
pitch_midi = P[idx]
```
Centre `u = 0.5` ⇒ `idx = L` ⇒ the **tonic one octave above T** (for diverging data this is the "zero line"). Because `N` is odd, the mapping is symmetric for diverging data. Rounding is `floor(x + 0.5)` (deterministic, no banker's rounding).

**P2 invariant:** pitch depends only on `u` and the skin, never on band, column or neighbours.

## 5. Time, voices, pan (F-023, F-024)

- `t_beat = col` (one beat per column). `total_beats = n_cols`. Seconds = `beat × 60 / bpm`.
- Voices `band0..band4`, one per band, `band_index = 0..4` (N→S), instrument from skin by category.
- Pan (north left → south right): `[-0.6, -0.3, 0.0, 0.3, 0.6]`. This is spatial separation, not information.
- Brightness multiplier per band (renderer hint, doc 07 §3): `[0.6, 0.85, 1.15, 0.85, 0.6]` (polar bands darker, tropics brighter, for a 5-band global map). Stored as `Score.provenance["band_brightness"]` (comma-separated).
- One extra voice `accent` (`band_index = -1`, instrument `bell`, pan 0) for accent bells.

## 6. Category → instrument (F-029)

| Category | Neutral-skin family | Rationale |
|---|---|---|
| temperature | `strings` | warm, sustained |
| precipitation | `pluck` | droplets |
| vegetation | `flute` | breath, growth |
| ice | `bell` | crystalline |
| aerosol | `texture` | grainy air |
| ocean | `pad` | broad, slow |
| generic | `pad` | neutral |

Other skins override the family ids (e.g. Sri Lankan: precipitation → `percussion`-led patterns). Instrument family ids are the closed set from docs/07 §3.

## 7. Local variability (F-025)

For each valid cell: `g = mean(|u − u_nbr|)` over valid 4-neighbours (0 if none). Over valid cells compute `p50`, `p85` of `g`.
- Density: `g ≤ p50 → 1`, `p50 < g ≤ p85 → 2`, `g > p85 → 4` notes per beat. (Flat field ⇒ all 1.)
- A cell with density `d` emits `d` notes of equal length `0.9/d` beats at beat offsets `k/d`, **same pitch**, kind `main`.
- Roughness: `roughness = clamp(g / max(g over valid cells), 0, 1)` (0 if max = 0).
- Velocity: `0.5 + 0.3·coverage`; first note of the cell +0.05; subsequent repeats ×0.85 each.

## 8. Tempo (F-026)

`s = clamp(std(u over valid grid cells) / 0.30, 0, 1)`; `bpm = 72 + 48·s`, rounded to 2 decimals.

## 9. Extremes, accents, ornaments (F-027, F-031)

`e = |u − 0.5|`. `thr = percentile(e over valid cells, 95)`. A cell is **accented** iff `e ≥ thr` and `e > 0`.
- Its main notes get `accent=True`, velocity `+0.25` (cap 1.0).
- A `kind="accent_bell"` note on voice `accent` with the same pitch `+12`, same time/duration/velocity.
- Ornament (seeded): with `rng.random() < 0.5` (draw in row-major cell order, **one draw per accented cell regardless**), add a grace note `kind="ornament"` of `0.125` beat before the cell's first note (so it starts at `t − 0.125`, clamped at ≥ 0), one scale step toward the centre pitch, velocity ×0.6. Skins with `phrases` replace this by the skin's phrase (doc 08).
- Ornaments and bells are **never decoded** by F-035 (only `kind == "main"`).

## 10. Drone (F-030)

`drone_midi = (T, T + fifth)` where `fifth` = the scale degree of the skin closest to 700 cents, expressed in semitones (`c/100`). Renderer plays them at constant low level for the whole duration. Brightness hint = mean `u` (3 decimals) stored in `provenance["drone_brightness"]`.

## 11. Determinism (F-031)

```
seed = int(sha256(f"{source_hash}|{canonical_params_json}|{MAPPING_VERSION}").hexdigest()[:8], 16)
rng  = numpy.random.default_rng(seed)
```
`canonical_params_json` = `SonificationParams` as JSON with sorted keys. If `params.seed` is not None it overrides. This is the ONLY randomness. Forbidden in `domain/`: `random`, `time`, `datetime.now`, `uuid`, `os.urandom`.

## 12. Legend sweep (F-034)

32 notes, one per beat at 96 bpm, `u = k/31`, voice `legend`, instrument from the category; `value` = inverse-normalised `u` (so the first/last note's value equal vmin/vmax). For diverging legends add a `bell` note at the centre (`kind="accent_bell"`) sounding together with the note nearest `u=0.5`.

## 13. Round-trip decoder (F-035)

`decode_score(score) → grid (n_bands × n_cols)`: take notes with `kind=="main"` and voice band*, group by `(band, col)`, take the median `pitch_midi`, invert `P` to `idx → u = idx/(N−1)`, then to a value with the inverse of §3 using `score.legend`. Cells with no notes → NaN. `fidelity_round_trip` = Pearson r between decoded and the field's grid means over cells valid in both. It uses **Score data only**.

## 14. Text description (F-036) — template

> "{label} ({units}), {kind}: values range about {min}–{max}. Highest values are mostly in the {where_high}; lowest in the {where_low}. {masked_pct}% of the map has no data and is silent. Lower values sound lower in pitch; the track moves from west to east. Five voices from north to south pan left to right. {caveat}"

`where_high/low`: the band (named by latitude range, e.g. "tropics, 18°N–18°S") and longitude third (western/central/eastern) containing the max/min grid cell (ties → first in row-major order). `caveat`: "These values are approximate, recovered from the image's colour legend." if confidence < 0.7; "This sound is not data-faithful: no colour legend was used." in luminance fallback; else empty. ≤ 120 words.
