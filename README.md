# The Earth Jukebox

Sonification of NASA Earth Information Center (EIC) imagery inspired by the Chandra X-ray Center sonification methodology.

---

## Overview & Context

NASA's Earth Information Center (EIC) and astrophysics missions (such as the Chandra X-ray Observatory) produce stunning visual representations of complex physical phenomena. Often, publicly distributed assets exist only as **legacy RGB frames without underlying numerical metadata** (such as FITS, HDF5, or NetCDF datasets).

**The Earth Jukebox** bridges this gap by reverse-engineering quantitative data directly from visual representations to ensure scientific defensibility. It translates spatial and photometric features of Earth science imagery into intuitive, immersive, and harmonically balanced auditory experiences.

---

## Dual-Pathway Data Extraction Architecture

To recover scientifically defensible scalar values from legacy RGB raster images, the system implements a dual-pathway architecture:

```
                    +---------------------------+
                    | Legacy NASA RGB Image     |
                    +-------------+-------------+
                                  |
                                  v
                      [Colorbar Detected?]
                             /        \
                    YES     /          \     NO
                           v            v
            +-------------------+   +---------------------------+
            | Primary Pathway:  |   | Fallback Pathway:         |
            | Colorbar Parsing  |   | Vector Quantization (VQ)  |
            +---------+---------+   +-------------+-------------+
                      |                           |
                      +------------+--------------+
                                   |
                                   v
                   +-------------------------------+
                   | Normalized Scalar Array (0-1) |
                   +-------------------------------+
```

### 1. Primary Pathway: Colorbar Parsing
* **Objective:** Direct lookup table (LUT) recovery, mirroring the Chandra team's wavelength-to-energy assignments.
* **Mechanism:**
  - Converts RGB input into perceptually uniform color spaces (HSV / LAB).
  - Isolates colorbar gradient regions using thresholding (`cv2.inRange`) and contour bounding box detection (`cv2.findContours`).
  - Samples colors along the gradient axis to construct a monotonic RGB-to-scalar LUT normalized from `0.0` to `1.0`.
  - Maps pixel colors in the data frame to scalar values via minimum color-distance lookup.

### 2. Fallback Pathway: Vector Quantization (VQ)
* **Objective:** Universal data recovery when no visual colorbar or legend is present in the frame.
* **Mechanism:**
  - Reconstructs the visual palette by generating an analytical codebook (e.g., 256 RGB tuples from standard scientific colormaps such as `jet`, `viridis`, or custom NASA palettes via `matplotlib.cm`).
  - Employs nearest-neighbor classification using `scipy.cluster.vq.vq` to assign each pixel to its closest codebook index.
  - Linearly normalizes indices to a `0.0` to `1.0` continuous scalar field.

---

## Modular Separation: "Data-True" vs. "Artistic" Layers

Scientific sonification requires navigating the trade-off between absolute data fidelity (which can sound dissonant and overwhelming) and musical aesthetics (which risks obscuring scientific patterns). The Earth Jukebox decouples these concerns into two modular layers:

### The "Data-True" Layer (Physics & Morphology)
1. **Preprocessing:** Contrast Limited Adaptive Histogram Equalization (CLAHE) applied exclusively to the luminance channel ($L$) in LAB color space, alongside edge-preserving bilateral and median filtering.
2. **Morphological Separation:**
   - **Diffuse Emission Layer:** Extracted using large-scale Gaussian filtering to capture broad regional trends (e.g., cloud covers, thermal gradients, sea-surface temperature anomalies).
   - **Point Source Layer:** Residual high-frequency components isolated by subtracting the diffuse layer from the base scalar field (e.g., localized wildfire hotspots, storm convective cores).
3. **Advanced Segmentation:** Marker-based watershed segmentation (`cv2.watershed`) and distance transforms to separate touching point sources and extract centroids, spatial extent, and peak flux.

### The "Artistic" Layer (Perception & Musicality)
1. **Geometric Scanheads:** Configurable playhead geometries matching the physical symmetries of the phenomenon:
   - *Horizontal Sweep:* Left-to-right Cartesian scan ($X \rightarrow$ time/pan, $Y \rightarrow$ pitch).
   - *Vertical Sweep:* Top-to-bottom time evolution.
   - *Radar Sweep:* Polar sweep around center ($ \theta \rightarrow$ time/pan, $r \rightarrow$ pitch).
   - *Radial Expansion:* Center-outward ripple ($r \rightarrow$ time, channels $\rightarrow$ timbral registers).
2. **Perceptual Dynamic Range Compression:** Luminance-to-amplitude mapping using inverse hyperbolic sine (`arcsinh`) or logarithmic curves with noise-floor gating (< 10% luminance attenuation).
3. **Harmonic Quantization:** Snapping raw frequency calculations to tempered musical scales (e.g., pentatonic, modal, microtonal) to eliminate harsh dissonance without destroying relative ordering.
4. **Hybrid Sound Synthesis:**
   - Diffuse layers synthesized into continuous acoustic drones via additive/subtractive oscillators (`scipy.signal`).
   - Point sources mapped to discrete triggers with physically inspired samples (`assets/samples/`, e.g., ice crackle, wind whoosh, thermal pops).
5. **Duality Control:** A continuous **Science vs. Music** parameter slider in the UI:
   - *100% Science:* Continuous microtonal frequencies, raw dynamic range, unquantized pitch tracking.
   - *100% Music:* Diatonic/pentatonic quantization, polyphony throttling, rich reverberant physical samples.

---

## Repository Structure

```
.
├── backend/
│   ├── app.py              # Streamlit interactive dashboard & controls
│   ├── morphology.py       # Diffuse vs. point source separation & watershed segmentation
│   ├── pipeline.py         # Colorbar parsing, vector quantization & preprocessing
│   ├── scanner.py          # Scan geometries, coordinate generators & parameter mapping
│   └── synthesizer.py      # Audio synthesis (WAV) & JSON timeline export
├── frontend/               # Interactive web visualization (Tone.js + p5.js)
├── assets/
│   └── samples/            # Curated physical audio samples for discrete events
├── data/                   # NASA EIC imagery and sonification exports
├── requirements.txt        # Python dependency manifest
└── README.md               # Architecture documentation
```

---

## Getting Started

### Prerequisites
Python 3.10+ recommended.

### Installation
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Running the Application
```bash
streamlit run backend/app.py
```
