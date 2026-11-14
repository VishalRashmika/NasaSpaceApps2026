# Earth Jukebox — Technical Methodology

> Mathematical formulations, algorithmic workflows, and sonification design.  
> **Mapping Specification:** `docs/06-SONIFICATION-MAPPING-SPEC.md` (`MAPPING_VERSION = 1.0.0`)  
> **Evaluation & Accuracy:** `docs/EVAL-REPORT.md`

---

## 1. Data Recovery via Colorbar Inversion (Module IMG)

Rather than treating digital imagery as RGB matrices, Earth Jukebox extracts physical scalar fields from NASA visualizations through a four-stage inversion pipeline:

```
Image Bytes ──▶ Normalisation (EXIF, RGB sRGB, area downscale)
                    │
                    ├── Colorbar Region ──▶ Median LUT Extraction (CIE L*a*b*, <= 512 steps)
                    │
                    └── Map Region ───────▶ cKDTree Inversion in Lab Space ──▶ ScalarField (NaN = Masked)
```

### 1.1 CIE L*a*b* Lookup Table (LUT) Extraction
Given user-defined or auto-detected bounding coordinates for the legend colorbar, the system trims outer border artifacts and computes the median color profile perpendicular to the gradient orientation. This profile is resampled to $K \le 512$ discrete sample points and transformed from sRGB into perceptual CIE $L^*a^*b^*$ color space:
$$\Delta E_{ab}^* = \sqrt{(\Delta L^*)^2 + (\Delta a^*)^2 + (\Delta b^*)^2}$$
Orientations honour the directionality defined by `low_at_start`.

### 1.2 Nearest-Color Inversion via k-d Tree
For each pixel coordinate $(x, y)$ in the map region:
1. The pixel color is converted to CIE $L^*a^*b^*$.
2. SciPy's spatial `cKDTree` executes a nearest-neighbor query against the LUT entries with sub-step linear interpolation between adjacent samples.
3. The normalized index $t \in [0, 1]$ is scaled to physical units $v$ using the legend definition:
   - Linear scale: $v = v_{\min} + t \cdot (v_{\max} - v_{\min})$
   - Logarithmic scale: $\log_{10} v = \log_{10} v_{\min} + t \cdot (\log_{10} v_{\max} - \log_{10} v_{\min})$
   - Diverging scale: Piecewise linear scaling anchored symmetrically around the specified center $c$.

### 1.3 Non-Data Masking & Confidence Scoring
Pixels representing geographic borders, continents, background graticules, or typography are masked to `NaN`:
- **Distance Threshold:** Pixels with nearest LUT distance $\Delta E > 20.0$ are flagged as non-data.
- **Background Clustering:** Iterative histogram analysis segments high-frequency background masks (black space, pure white borders).
- **Thin Line Detection:** Morphological filters isolate hairline vector overlays.

Overall recovery confidence $C \in [0, 1]$ is evaluated as:
$$C = \text{coverage} \times \exp\left(-\frac{\text{median}(\Delta E)}{10}\right)$$
Categorized into High ($C \ge 0.85$), Medium ($0.65 \le C < 0.85$), and Low ($C < 0.65$) quality badges.

---

## 2. The Fixed Sonification Mapping Specification (Module SON)

The mapping between physical data and audio parameters is versioned and completely documented (`MAPPING_VERSION = 1.0.0`). The intermediate representation is the `Score` dataclass, containing deterministic `NoteEvent` structures.

### 2.1 Complete Sonification Mapping Table

| Parameter Key | Data Property | Sound Parameter | Musical Implementation |
|---|---|---|---|
| `value->pitch` | Cell mean value $u \in [0, 1]$ | **Pitch (MIDI)** | Scale-quantized across 2 octaves ($N = 2L + 1$ pitches, middle tonic center). |
| `longitude->time` | Column index $x \in [0, n_{\text{cols}}-1]$ | **Time / Beat** | $t_{\text{beat}} = x$; playhead sweeps West to East at constant tempo. |
| `latitude_band->voice_pan` | Band index $y \in [0, 4]$ (North to South) | **Voice & Stereo Pan** | 5 voices panned $[-0.6, -0.3, 0.0, 0.3, 0.6]$; brightness scaled by latitude. |
| `local_variability->rhythm_density` | Local 4-neighbor spatial gradient $g$ | **Rhythm Density** | Subdivisions per beat: 1 note (low), 2 notes (medium), or 4 notes (turbulent). |
| `local_variability->roughness` | Local spatial gradient $g$ | **Timbre / Roughness** | Filter cutoff shift $\times (1 + r)$ and detuning $+r \cdot 12$ cents. |
| `global_variability->tempo` | Standard deviation $\sigma(u)$ | **Tempo (BPM)** | $\text{BPM} = 72 + 48 \cdot \min(1, 3.5 \cdot \sigma(u)) \in [72, 120]$. |
| `extremes->accent` | Top 5% of $|u - 0.5|$ | **Dynamic Accent** | Velocity $+0.25$, doubling with high bell voice ($+12$ semitones). |
| `masked->silence` | Valid data coverage $< 0.25$ | **Rest / Silence** | No note is scheduled; missing data is represented as silence, never filler. |
| `category->instrument` | Variable category | **Instrument Family** | Temperature $\to$ `strings`, Precipitation $\to$ `pluck`, Vegetation $\to$ `flute`, Ice $\to$ `bell`. |
| `global_mean->drone_brightness` | Spatial mean $\bar{u}$ | **Harmonic Drone Bed** | Root tonic + fifth ($T, T+7$); low-pass filter cutoff scaled by $\bar{u}$. |

---

## 3. Pitch Quantization & Middle-Tonic Invariance

To guarantee that diverging datasets (e.g. temperature anomalies) center symmetrically on a neutral reference tone, scale quantization maps normalized $u \in [0, 1]$ to an odd number of discrete pitches $N = 2L + 1$:
$$P = \left[ T + 12\cdot o + \frac{c_k}{100} \;\middle|\; o \in \{0, 1\}, k \in \{0, \dots, L-1\} \right] \cup \{T + 24\}$$
where $T$ is the root tonic MIDI pitch, $c_k$ is the cent offset of scale degree $k$, and $L$ is the number of notes per octave:
$$\text{index} = \left\lfloor u \cdot (N - 1) + 0.5 \right\rfloor$$
When $u = 0.5$, $\text{index} = L$, which is exactly the tonic pitch one octave above root ($T + 12$).

---

## 4. Multi-Frame Time Mode (Module TIM)

In Time Mode, multi-frame visualizations (animated GIFs, MP4 satellite sequences) are extracted into up to 24 discrete temporal frames:
1. **Phrase Segmentation:** Each frame $f$ is sonified into an independent score phrase of length $B$ beats. Subsequent frames are concatenated with an exact 1-beat rest:
   $$t_{\text{start}}(f) = f \cdot (B + 1.0)$$
2. **Harmonic Tension Calculation:** The normalized physical difference across consecutive frames is evaluated:
   $$\Delta_{\text{frame}} = \frac{1}{|\Omega|} \sum_{i \in \Omega} |u_{f}(i) - u_{f-1}(i)|$$
3. When $\Delta_{\text{frame}} > 0$, the drone harmonic bed activates a tension pitch (second or tritone degree defined by the skin) with microtonal frequency scaling proportional to $\Delta_{\text{frame}}$.

---

## 5. Cultural Skin Invariance (Module SKN)

Cultural music skins alter the aesthetic rendering while leaving the underlying information layer invariant:
- **Neutral:** Western major pentatonic scale $(0, 200, 400, 700, 900)$ cents.
- **Hindustani (Bhairav / Malhar):** 7-note microtonal scale with descending *meend* glides connecting consecutive notes.
- **Sri Lankan (Vannam / Hewisi):** 5-note scale with lead flute and indigenous *beraya* drum rhythmic motifs tied to data variability.

**Mathematical Invariance (F-054):**
For any scalar field $F$, across all skins $S_a$ and $S_b$:
1. Value-to-pitch monotonicity: $u_1 \le u_2 \implies \text{pitch}(u_1) \le \text{pitch}(u_2)$.
2. Identical event timing: Onset beat times, note durations, accents, and spatial stereo pans are strictly identical.
