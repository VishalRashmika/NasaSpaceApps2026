# 05 — Colorbar Inversion Spec (Module IMG)

> Deep-dive for features F-001…F-013, F-100. Numbers in **[brackets]** are tunable defaults; the allowed tuning range is given. Changing a default beyond its range, or any threshold in §9, requires a Decisions-log entry and human approval.

## 1. Contract

```
recover(image: DecodedImage, legend: LegendSpec, map_box?, colorbar_box?, preset_name?) -> ScalarField
```
Mode selection (first match wins): `colorbar_box` given → COLORBAR; else `preset_name` given → PRESET; else → LUMINANCE_FALLBACK (F-013).

## 2. Colour space

All matching is done in **CIE L\*a\*b\*** (D65, from sRGB), distance **ΔE76 = Euclidean in Lab**. Convert with OpenCV on `float32` RGB in 0..1 (`cv2.cvtColor(rgb_f32, cv2.COLOR_RGB2LAB)` yields L in 0..100). Never match in RGB or HSV.

## 3. Pipeline

1. **Decode & normalise** (F-001/F-002). Work on the downscaled copy (≤ 2048 px). Convert user boxes with `scale_box`.
2. **Extract LUT** (§4/F-006) from `colorbar_box`, or from preset (F-003).
3. **Dedupe LUT**: merge consecutive entries with ΔE < 0.5 (keep the mean value) so flat bands do not create zero-length segments.
4. **Crop map region** (F-005).
5. **Convert map pixels to Lab**, flatten to (M,3).
6. **Nearest-LUT query** with `scipy.spatial.cKDTree` (k=1 first; then sub-step interpolation §5).
7. **Mask** (§6) → NaN.
8. **Assemble** `ScalarField` of the map crop's working resolution; row 0 = north.
9. **Quality** (§8).

## 4. Colorbar LUT extraction (F-006)

Input: `PixelBox`, `Orientation`, `low_at_start`.
1. Crop the box. Trim a **[2] px** border all round (outlines, antialiasing).
2. Orientation HORIZONTAL: position axis = x, thickness axis = y; VERTICAL: position = y (top→bottom), thickness = x.
3. At each position take the **per-channel median over thickness** (robust to tick marks and labels drawn on the bar).
4. **End-cap trim:** at both ends, drop up to **[3 %]** of the length while consecutive entries differ from the interior neighbour by ΔE > [20] (removes black outlines, arrows, white padding).
5. Resample to ≤ 512 entries by linear interpolation in Lab if longer than 512.
6. Order: HORIZONTAL & `low_at_start` ⇒ left=vmin. VERTICAL & `low_at_start` ⇒ **bottom**=vmin (so reverse the top→bottom array). `low_at_start=False` flips.
7. Assign `values` linearly between `vmin` and `vmax`, or log10-linearly when `legend.scale == LOG`.

Allowed tuning: border 1–4 px; cap trim 1–5 %; cap ΔE 12–30.

## 4a. Auto-detection (F-004, suggestion only)

Goal: propose candidate colorbar boxes. Heuristic (all steps vectorised):
1. Lab image; for each pixel compute ΔE to its **right** neighbour and to its **lower** neighbour.
2. "Gradient pixel" = neighbour ΔE ∈ **[0.05, 8]** (smooth, non-zero change).
3. For horizontal candidates: in each row find maximal runs of gradient pixels; keep runs of length ≥ **[12 %] of image width**. Stack adjacent rows whose runs overlap ≥ 80 % into a block; keep blocks with thickness ≥ **[6] px** and aspect ratio (length/thickness) ≥ **[5]**. Vertical candidates: same on columns.
4. Score = `0.4*cumulative_ΔE_along_run/200 (cap 1) + 0.3*unique_colours/length (cap 1) + 0.2*edge_proximity + 0.1*thickness_uniformity`. `edge_proximity` = 1 if the block lies within 25 % of an image edge, else 0.5.
5. Return the top **3** with orientation. A grey ramp is a valid candidate.
6. Return `[]` if nothing scores ≥ **[0.35]**.

The UI always shows the suggestion for confirmation; users can override with manual boxes.

## 5. Inversion with sub-step interpolation (F-008)

For each pixel with Lab vector `p`:
1. `i, d = tree.query(p)` (nearest LUT index `i`, distance `d`).
2. Pick the nearer neighbour `j ∈ {i−1, i+1}` (within bounds) by Lab distance to `p`.
3. Project `p` onto segment `L[i]→L[j]`: `t = clamp(dot(p−L[i], L[j]−L[i]) / |L[j]−L[i]|², 0, 1)`.
4. `value = values[i] + t*(values[j]−values[i])`.
5. If `d > max_delta_e` ⇒ NaN (§6).

`max_delta_e` default **[12]**, allowed **8–20** (higher for JPEG inputs, see §9).

## 6. Masking (F-009)

NaN when any of:
- **Distance:** `d > max_delta_e`.
- **Thin lines/text:** build a binary mask of "very dark or very white" pixels (L < 20 or L > 97 **and** not near a LUT end colour within ΔE 6); apply **morphological opening** with a 3×3 kernel to find *thick* regions (legitimate dark/light data, e.g. low end of viridis); pixels in the mask but **removed by opening** (thin structures ≤ 2 px) are NaN. Grey graticule lines (low chroma, C\* < 8, not near the LUT) of width ≤ 2 px are likewise NaN.
- **Dominant background cluster:** quantise non-LUT-matched pixels (d > 6) to a coarse 16-level Lab grid; if the most common cluster covers > **[5 %]** of the map and has d > 6 from the LUT, mark all its pixels NaN (ocean/land fill colours).
- Optionally **fill 1-px holes** surrounded by valid data with the median of neighbours *only* when the hole was caused by text/graticule (not by land). Keep a boolean `suppressed_line` internal mask for this.

## 7. Diverging and log legends

Diverging: LUT/value assignment is identical (value linear in position). The legend's `effective_center` is only used by sonification (doc 06 §3). Log: values assigned log10-linearly in §4.7.

## 8. Quality and confidence (F-011)

```
mean_de, p95_de   = stats of d over matched (non-masked) pixels
masked_fraction   = NaN share of map pixels
f_de   = clamp(1 − mean_de / 10, 0, 1)
f_cov  = 1.0 if masked_fraction ≤ 0.6 else clamp(1 − (masked_fraction − 0.6) / 0.35, 0, 1)
base   = 0.6*f_de + 0.4*f_cov
mode_factor = {COLORBAR: 1.0, PRESET: 0.9, LUMINANCE_FALLBACK: 0.3}
confidence = base * mode_factor
if "projection_unverified" in warnings: confidence *= 0.8
if mode == LUMINANCE_FALLBACK: confidence = min(confidence, 0.3)
```
Warnings (string codes, stable API): `high_color_distance` (mean_de > 6 or masked_fraction > 0.8), `mostly_masked` (> 0.9), `projection_unverified`, `not_data_faithful`, `diverging_center_defaulted`, `log_scale_assumed`, `lut_not_monotonic_lightness` (informational), `low_resolution` (map < 200 px wide).
`lut_is_monotonic_in_lightness` = L\* along the LUT is monotonic after ignoring ±1 L noise.

UI badge: confidence ≥ 0.8 "High", 0.5–0.8 "Medium", < 0.5 "Low".

## 9. Accuracy targets (tests; do not loosen without human approval)

RMSE of recovered vs. truth on **valid truth cells**, as % of `(vmax − vmin)`, synthetic maps (F-100), PNG:

| Colormap | RMSE ≤ | Colorbar mode LUT mean ΔE ≤ |
|---|---|---|
| viridis, plasma, inferno, magma, cividis | 2 % | 2.0 |
| Blues, Greens, YlGnBu, YlOrRd | 2 % | 2.0 |
| RdBu_r, coolwarm, BrBG | 2 % | 2.0 |
| turbo, jet | 3 % | 2.0 |

With the same maps re-encoded as **JPEG quality 85**, thresholds double and `max_delta_e` may be raised to 16.
If an agent cannot meet a threshold after reasonable effort, it records evidence in the Decisions log and **escalates**; it must not edit the threshold itself.

## 10. Limitations (document these in the UI/README, they are honest science)

- Rainbow colormaps are perceptually non-uniform; quantisation noise is larger near ambiguous hues (cyan/green).
- Shading, drop shadows, semi-transparent overlays or 3-D globes distort colours → lower confidence.
- Discrete/binned colorbars recover bin centres, not continuous values (this is correct).
- Resampled/blurred images smear edges; mixed pixels at coastlines may be mis-valued.
- Only equirectangular maps are supported (D-03).

## 11. Synthetic generator (F-100) spec

- Field: `f(lat,lon) = Σ_k a_k·exp(−((lat−lat_k)²/2σ_lat² + (lon−lon_k)²/2σ_lon²)) + b·sin(lat)`, K=4 centres drawn from `numpy.random.default_rng(seed)`; scale to [vmin,vmax].
- Land mask: two ellipses (NaN in truth), drawn in a flat neutral colour (e.g. `#c8c8c8`) not in the colormap.
- Render map at 1024×512 with matplotlib `imshow(origin="upper")` into a figure with exact pixel size; add a 1-px black graticule at 30° steps optionally; colorbar drawn as a separate axes (horizontal below or vertical right) with tick labels; return exact pixel boxes by reading axes positions in pixel space.
- Provide variants: with/without outline, with title text, with white margins.
