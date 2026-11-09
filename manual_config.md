# The Earth Jukebox — Developer Manual Configuration Guide

This document serves as the centralized reference guide for human developers, sound designers, and data scientists finalizing the configuration of **The Earth Jukebox** after code generation. It covers external audio assets, colorbar visual thresholds, microtonal tuning tables, computer vision morphology tuning, and external NASA API integrations.

---

## Table of Contents

1. [Audio Assets Configuration (`assets/samples/`)](#1-audio-assets-configuration)
2. [Colorbar Detection & Hex/HSV/LAB Threshold Calibration (`backend/pipeline.py`)](#2-colorbar-detection--hexhsvlab-threshold-calibration)
3. [Tone.js & TuneJS Microtonal Scala (`.scl`) Tables (`frontend/`)](#3-tonejs--tunejs-microtonal-scala-scl-tables)
4. [Computer Vision & Watershed Performance Tuning (`backend/morphology.py`)](#4-computer-vision--watershed-performance-tuning)
5. [API Keys & External NASA EIC Integration (`.env`)](#5-api-keys--external-nasa-eic-integration)

---

## 1. Audio Assets Configuration

### 1.1 Overview & Architecture
The Earth Jukebox uses a hybrid sound synthesis model inspired by the Chandra X-ray Observatory sonification methodology:
- **Continuous Diffuse Layer:** Synthesized algorithmically in real time via `scipy.signal` (additive/subtractive harmonic oscillators and warm analog pads).
- **Point Source Layer:** Triggered via pre-recorded, physically motivated acoustic samples loaded through `pydub` from `assets/samples/`.

The synthesis engine ([`backend/synthesizer.py`](file:///root/NasaSpaceApps/backend/synthesizer.py)) dynamically shifts sample playback rates to match target musical pitches while preserving acoustic resonance and transient characteristics.

### 1.2 Exact Sample Files Required in `assets/samples/`

The directory `assets/samples/` should contain standard 16-bit PCM Linear WAV files. The system automatically provides procedural fallbacks via `generate_default_samples()`, but replacing them with curated studio recordings significantly elevates acoustic fidelity:

| Filename | Phenomenon / Physical Mapping | Default Frequency ($f_0$) | Typical Duration | Recommended Timbral Characteristics |
| :--- | :--- | :--- | :--- | :--- |
| `crackle.wav` | Ice fractures, cryosphere cracks, thermal sparks | 440.0 Hz (A4) | 0.3s – 0.6s | High-frequency Poisson impulse transients with resonant bandpass filtering. |
| `ice_crackle.wav` | Glacial calving, sea ice stress, polar anomalies | 440.0 Hz (A4) | 0.4s – 0.8s | Granular micro-fractures with crystalline resonance (`ice_crackle_foley.wav`). |
| `whoosh.wav` | Atmospheric gust, wind shear, cyclonic vorticity | 440.0 Hz (A4) | 0.6s – 1.0s | Swept bandpass filtered pink/brownian noise with smooth parabolic envelope. |
| `wind_whoosh.wav` | Hurricane eye-wall convection, jet stream sweeps | 440.0 Hz (A4) | 0.7s – 1.2s | Deep resonant turbulent wind with dynamic stereo displacement. |
| `pluck.wav` | Localized hotspot, wildfire spike, stellar point source | 440.0 Hz (A4) | 0.4s – 0.8s | Multi-harmonic exponential decay pluck (acoustic harp, pizzicato cello, or koto). |
| `ping.wav` | Optical beacon, satellite telemetry point, albedo spike | 880.0 Hz (A5) | 0.3s – 0.5s | Inharmonic metallic bell partials or glockenspiel tone. |

### 1.3 Recommended Curated Foley Replacements
For production deployments, sound designers can drop high-resolution Foley assets directly into `assets/samples/`:

- `glockenspiel_c4.wav`: Clean crystalline mallet strike on high-carbon steel chime. Fundamental: 261.63 Hz (C4).
- `bowed_strings_pad.wav`: Sustained expressive cello/viola section with slow vibrato. Fundamental: 220.0 Hz (A3) or 440.0 Hz (A4).
- `ice_crackle_foley.wav`: High-sample-rate (96 kHz / 24-bit downsampled to 44.1 kHz / 16-bit) contact-microphone recording of fracturing lake ice or dry ice sublimation.

### 1.4 Sample Specification Checklist
When creating or importing new `.wav` files:
1. **Container & Codec:** Uncompressed WAV (`audio/wav`), PCM 16-bit signed integer (`subtype='PCM_16'`).
2. **Sampling Rate:** `44,100 Hz` (recommended standard) or `48,000 Hz`.
3. **Channels:** Stereo (2-channel) or Mono (1-channel). The synthesizer handles auto-duplication to stereo.
4. **Peak Headroom:** Normalize audio files to `-1.0 dBFS` true peak to prevent inter-sample digital clipping during pitch shifting and panning.
5. **Pitch Registration in Code:** If adding a sample with a fundamental pitch other than 440 Hz (such as `glockenspiel_c4.wav` at 261.63 Hz), register its root frequency and aliases in `backend/synthesizer.py`:

```python
# backend/synthesizer.py

SAMPLE_ALIASES.update({
    "glockenspiel": "glockenspiel_c4.wav",
    "glockenspiel_c4": "glockenspiel_c4.wav",
    "ice_foley": "ice_crackle_foley.wav",
})

SAMPLE_BASE_FREQUENCIES.update({
    "glockenspiel_c4.wav": 261.63,   # Middle C (C4)
    "ice_crackle_foley.wav": 440.0,
})
```

---

## 2. Colorbar Detection & Hex/HSV/LAB Threshold Calibration

### 2.1 The Automated Detection Mechanism
In [`backend/pipeline.py`](file:///root/NasaSpaceApps/backend/pipeline.py), `detect_colorbar_bounding_box()` attempts to isolate visual legends from the scientific data frame using two perceptual color space thresholds:

1. **Primary HSV Threshold:**
   - Filters pixels by saturation ($S \ge 25$) and brightness ($V \ge 25$).
   - `hsv_lower = np.array([0, 25, 25], dtype=np.uint8)`
   - `hsv_upper = np.array([180, 255, 255], dtype=np.uint8)`
2. **Fallback LAB Chroma Threshold:**
   - Evaluates chroma channels ($a^*, b^*$) to catch smooth perceptual colormaps (e.g., `viridis`, `cividis`, `plasma`) whose dark end has low HSV saturation.
   - `lab_lower = np.array([10, 100, 100], dtype=np.uint8)`
   - `lab_upper = np.array([245, 255, 255], dtype=np.uint8)`
3. **Contour Geometry Filters:**
   - `min_aspect_ratio`: 2.5 (elongated bar)
   - `min_length`: 25 px
   - `min_thickness`: 3 px
   - `max_area_ratio`: 0.50 (cannot exceed half the image)
   - `extent`: $\ge 0.45$ (rectangular solidity)
   - `color_std`: $\ge 5.0$ (gradient variance check along major axis to reject monochrome borders)

### 2.2 When Automated Detection Fails
Automated detection can fail under the following common conditions:
- **Low Saturation Scientific Palettes:** Grayscale, monochrome infrared (IR), ocean bathymetry, or subdued terrain maps.
- **Embedded Legend Annotations:** Text labels, numerical ticks, or tick marks that intersect and break the bounding contour.
- **Embedded Visual Framing:** Images surrounded by high-contrast border frames or nested multi-panel plots.

### 2.3 Guide: Converting Hex Color Anchors to OpenCV HSV & LAB
If a specific NASA visualization palette has known minimum and maximum hex colors, compute the exact OpenCV thresholds using this utility snippet:

```python
import cv2
import numpy as np

def hex_to_opencv_hsv_lab(hex_str: str) -> dict:
    """Convert a hex color string (e.g., '#3B049A') to OpenCV HSV and LAB values."""
    hex_clean = hex_str.lstrip("#")
    rgb = np.uint8([[[int(hex_clean[i:i+2], 16) for i in (0, 2, 4)]]])
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    
    # OpenCV HSV ranges: H in [0, 179], S in [0, 255], V in [0, 255]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[0][0]
    
    # OpenCV LAB ranges: L in [0, 255], A in [0, 255], B in [0, 255]
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)[0][0]
    
    return {
        "hex": hex_str,
        "BGR": bgr[0][0].tolist(),
        "HSV": hsv.tolist(),
        "LAB": lab.tolist(),
    }

# Example: Viridis colormap extreme anchors
start_color = hex_to_opencv_hsv_lab("#440154") # Dark purple
end_color   = hex_to_opencv_hsv_lab("#FDE725") # Bright yellow
print("Start Anchor:", start_color)
print("End Anchor:  ", end_color)
```

### 2.4 How to Manually Update Ranges in `backend/pipeline.py`

#### Option A: Function Call Overrides (Zero Code Modifications)
Pass custom threshold bounds and geometry parameters directly to `extract_data()` or `extract_data_colorbar()`:

```python
from backend.pipeline import extract_data
import numpy as np

# Custom HSV range for low-saturation viridis/ocean colorbars
scalar_data = extract_data(
    image_path="data/custom_nasa_frame.png",
    hsv_lower=np.array([0, 10, 15], dtype=np.uint8),
    hsv_upper=np.array([180, 255, 255], dtype=np.uint8),
    min_aspect_ratio=2.0,      # Relax aspect ratio for stubby colorbars
    min_length=20,             # Permit smaller colorbars
)
```

#### Option B: Modify Pipeline Source Defaults
In [`backend/pipeline.py`](file:///root/NasaSpaceApps/backend/pipeline.py#L120-L142), locate lines 120–142 in `detect_colorbar_bounding_box()`:

```python
# To capture low-saturation or thermal grayscale gradients:
if hsv_lower is None:
    # Lower saturation floor from 25 down to 5 for near-monochrome gradients
    hsv_lower = np.array([0, 5, 15], dtype=np.uint8)
if hsv_upper is None:
    hsv_upper = np.array([180, 255, 255], dtype=np.uint8)

# And adjust LAB fallback bounds for perceptual lightness:
lab_lower = np.array([5, 80, 80], dtype=np.uint8)
lab_upper = np.array([250, 255, 255], dtype=np.uint8)
```

#### Option C: Manual Bounding Box Bypass or Vector Quantization Fallback
If the colorbar geometry cannot be reliably segmented:
1. **Explicit Bounding Box:** Crop or supply `bbox=(x, y, width, height)` directly to `build_colorbar_lut()` and `apply_lut_to_image()`.
2. **Fallback to Vector Quantization:** Force the fallback palette reverse-engineering pathway by passing `method="vq"` and naming the colormap:
   ```python
   scalar_data = extract_data(
       image_path="data/custom_nasa_frame.png",
       method="vq",
       colormap_name="viridis", # e.g., 'jet', 'viridis', 'plasma', 'turbo'
       num_samples=256,
   )
   ```

---

## 3. Tone.js & TuneJS Microtonal Scala (`.scl`) Tables

### 3.1 Architecture Overview
The web interface ([`frontend/index.html`](file:///root/NasaSpaceApps/frontend/index.html) and [`frontend/script.js`](file:///root/NasaSpaceApps/frontend/script.js)) integrates **Tone.js** for audio scheduling and **TuneJS** (`Tune`) for microtonal intonation.

When a JSON blueprint is loaded:
1. `initTune(scaleName, tuningSystem)` initializes the `Tune` engine.
2. For each scheduled musical event, `getTunedFrequency(midiNote)` resolves the microtonal frequency (in Hz) corresponding to the target MIDI note.
3. Tone.js oscillators and synths are modulated to that exact frequency.

### 3.2 Scala (`.scl`) File Format Explained
The Scala file format is the international standard for microtonal and non-Western scales:
```text
! slendro.scl
! Javanese Gamelan Slendro 5-tone scale
5
!
240.0
480.0
720.0
960.0
2/1
```
- Lines beginning with `!` are comments.
- Line 1: Short description.
- Line 2: Note count in scale (e.g., `5`).
- Remaining lines: Interval specifications, either:
  - **Cents:** Contains a decimal point (e.g., `240.0`, `1200.0`).
  - **Ratios:** Fractional integer string (e.g., `9/8`, `5/4`, `3/2`, `2/1`).

### 3.3 Adding Custom `.scl` Tunings to the Frontend

TuneJS contains an internal archive of common Scala tunings accessible via `TuningList`. To load a custom `.scl` file not present in the native library:

#### Step 1: Place the `.scl` File in `frontend/tunings/`
Create a directory `frontend/tunings/` and save your Scala file, e.g.:
`frontend/tunings/pelog_baran.scl`

#### Step 2: Implement Scala Parser Utility
Add the following lightweight parser to [`frontend/script.js`](file:///root/NasaSpaceApps/frontend/script.js):

```javascript
/**
 * Parse raw Scala (.scl) text into frequency ratios and cents.
 * @param {string} sclContent - Raw text from .scl file
 * @returns {Array<number>} Array of interval multipliers relative to 1.0 (tonic)
 */
function parseScalaString(sclContent) {
  const lines = sclContent.split(/\r?\n/)
    .map(line => line.trim())
    .filter(line => line.length > 0 && !line.startsWith('!'));

  if (lines.length < 2) {
    throw new Error("Invalid .scl file: missing description or pitch count.");
  }

  const description = lines[0];
  const numNotes = parseInt(lines[1], 10);
  const scaleRatios = [1.0]; // Tonic is always 1.0

  for (let i = 2; i < 2 + numNotes; i++) {
    const entry = lines[i].split(/\s+/)[0];
    if (entry.includes('.')) {
      // Cents value (e.g. 204.0 cents -> 2^(cents / 1200))
      const cents = parseFloat(entry);
      scaleRatios.push(Math.pow(2.0, cents / 1200.0));
    } else if (entry.includes('/')) {
      // Integer ratio (e.g. 9/8 -> 1.125)
      const parts = entry.split('/');
      const num = parseFloat(parts[0]);
      const den = parseFloat(parts[1]);
      scaleRatios.push(num / den);
    } else {
      // Direct whole integer ratio (e.g. 2 for octave)
      scaleRatios.push(parseFloat(entry));
    }
  }

  return scaleRatios;
}
```

#### Step 3: Register Custom Scale in TuneJS & `TUNEJS_SCALE_MAP`
In `frontend/script.js`, register your parsed scale into the active `Tune` instance:

```javascript
/**
 * Load and apply a custom .scl scale file dynamically.
 * @param {string} scaleUrl - Path to .scl file (e.g., "tunings/pelog_baran.scl")
 * @param {string} scaleKey - Identifier key (e.g., "pelog_baran")
 */
async function loadCustomScalaFile(scaleUrl, scaleKey) {
  try {
    const res = await fetch(scaleUrl);
    const sclText = await res.text();
    const ratios = parseScalaString(sclText);

    if (state.tune && state.tune.instance) {
      // Apply custom ratios directly to TuneJS scale property
      state.tune.instance.scale = ratios;
      state.tune.instance.tonicize(261.6255653); // Concert C4
      state.tune.resolvedScale = scaleKey;
      state.tune.scaleName = scaleKey;
      console.log(`[Earth Jukebox] Custom Scala tuning loaded: ${scaleKey}`);
    }

    // Register into alias lookup map
    TUNEJS_SCALE_MAP[scaleKey] = scaleKey;
  } catch (err) {
    console.error(`Failed to load Scala file: ${scaleUrl}`, err);
  }
}
```

#### Step 4: Add Entry to HTML Dropdown Menu
In [`frontend/index.html`](file:///root/NasaSpaceApps/frontend/index.html#L161-L171), add an `<option>` to `#select-tuning-palette`:

```html
<select id="select-tuning-palette" class="select-control select-small">
  <option value="auto">Auto (From Blueprint)</option>
  <option value="slendro">Javanese Gamelan (Slendro 5-tone)</option>
  <option value="pelog">Javanese Gamelan (Pelog 7-tone)</option>
  <option value="pelog_baran">Custom Pelog (Baran .scl)</option>
  <option value="malkauns">Indian Raga (Malkauns)</option>
  <option value="12-EDO">Standard 12-Tone Equal (12-EDO)</option>
</select>
```

---

## 4. Computer Vision & Watershed Performance Tuning

### 4.1 Architecture in `backend/morphology.py`
The morphology engine ([`backend/morphology.py`](file:///root/NasaSpaceApps/backend/morphology.py)) divides quantitative 2D scalar fields into two scientific layers:
1. `separate_features(scalar_array, kernel_size=(51, 51))`:
   - Applies Gaussian blur to extract smooth **diffuse emission** (clouds, atmospheric haze, temperature gradients).
   - Subtracts diffuse layer from original scalar data to obtain the high-frequency **point source residual** (wildfire hotspots, storm eye-walls, convective cores).
2. `segment_touching_objects(residual_image, dist_threshold_ratio=0.5, ...)`:
   - Uses marker-controlled **watershed segmentation** (`cv2.watershed` and Euclidean `cv2.distanceTransform`) to split dense clusters of touching point sources into discrete events with centroid coordinates and peak flux.

### 4.2 Resolution-Dependent Parameter Tuning Matrix

Because OpenCV kernel operations scale quadratically with kernel dimensions and image pixel counts, parameter choices must adjust to the image resolution:

| Resolution Category | Typical Dimensions | Gaussian `kernel_size` (`separate_features`) | Morphological `opening_kernel_size` | `dist_threshold_ratio` (`watershed`) | `bg_iterations` (Sure Background) | Min / Max Area Filter |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Low Res / Thumbnails** | $\le 512 \times 512$ | `(15, 15)` to `(25, 25)` | `(3, 3)` (1 iter) | `0.40` | 2 – 3 iterations | `min_area=1.0`, `max_area=500` |
| **Medium Res (Default)** | $\sim 1024 \times 1024$ | `(51, 51)` | `(3, 3)` (1 iter) | `0.50` | 3 iterations | `min_area=1.0`, `max_area=5000` |
| **High Res (Satellite)** | $2048 \times 2048$ | `(101, 101)` to `(151, 151)` | `(5, 5)` (2 iters) | `0.60 – 0.70` | 5 – 6 iterations | `min_area=4.0`, `max_area=20000` |
| **Ultra-HD / Global Swath** | $4096 \times 4096+$ | `(201, 201)` to `(301, 301)` | `(7, 7)` (2 iters) | `0.65 – 0.75` | 8 – 10 iterations | `min_area=16.0`, `max_area=50000` |

### 4.3 Detailed Tuning Guidelines

#### 1. Gaussian Blur Kernel Size (`kernel_size`)
- **Symptoms of kernel too small:** Low-frequency clouds and diffuse haze fail to be completely smoothed, leaving diffuse artifacts in the point source residual. The audio produces hundreds of false-positive discrete transient clicks.
- **Symptoms of kernel too large:** Localized bright features spread into the background, depressing the residual flux and eroding genuine point sources.
- **Rule of Thumb:** Set the kernel size to approximately **3% to 6% of the image's major dimension** (and always ensure kernel values are positive odd integers, e.g. 51, 101, 151).

#### 2. Distance Transform Ratio (`dist_threshold_ratio`)
- Controls what fraction of the maximum Euclidean distance from the background constitutes a "sure foreground seed" for watershed basin flooding.
- **Dense Wildfire / Urban Clusters:** Touching hotspots merge into a single contour under standard thresholding. **Increase `dist_threshold_ratio` to `0.70 – 0.80`** to isolate only the sharpest peaks as separate seed markers.
- **Faint / Diffuse Spot Sources:** High ratios can eliminate lower-contrast peaks. **Lower `dist_threshold_ratio` to `0.30 – 0.45`** to ensure faint emitters generate markers.

#### 3. Morphological Opening & Dilation Iterations
- `opening_kernel_size` and `opening_iterations`: Eliminates single-pixel camera noise and sub-pixel compression artifacts before distance transform computation. For resolutions $> 2048$, increase from `(3, 3)` to `(5, 5)` to prevent noisy pixels from generating spurious watershed markers.
- `bg_iterations`: Controls dilation iterations for sure background boundaries. High-resolution images require 5–8 iterations to ensure ambiguous transition zones (`unknown = sure_bg - sure_fg`) are wide enough for the watershed algorithm to locate true boundary contours.

### 4.4 High-Performance Downsampling Pattern for 4K / 8K Inputs
Processing 16-megapixel images through full-resolution distance transforms and watershed flooding can introduce latency in interactive workflows. The recommended optimization is to downsample for feature extraction while mapping detected coordinates back to original coordinates:

```python
import cv2
from backend.morphology import separate_features, segment_touching_objects

def process_high_res_image(scalar_img, max_dim=1024):
    """Downsample image for fast morphology, then rescale detected centroids."""
    h, w = scalar_img.shape[:2]
    if max(h, w) > max_dim:
        scale = max_dim / float(max(h, w))
        small = cv2.resize(scalar_img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    else:
        scale = 1.0
        small = scalar_img

    # Run feature separation and watershed on downsampled array
    features = separate_features(small, kernel_size=(51, 51))
    _, objects = segment_touching_objects(features["point_source_layer"], dist_threshold_ratio=0.55)

    # Rescale detected point source coordinates back to native resolution
    if scale != 1.0:
        inv_scale = 1.0 / scale
        for obj in objects:
            obj["x"] *= inv_scale
            obj["y"] *= inv_scale
            obj["radius"] *= inv_scale
            obj["area"] *= (inv_scale ** 2)

    return features, objects
```

---

## 5. API Keys & External NASA EIC Integration

### 5.1 Current Offline Capabilities
By design, **The Earth Jukebox core pipeline functions 100% offline without requiring any API keys or network requests**. It processes:
- User-uploaded imagery through the Streamlit dashboard ([`backend/app.py`](file:///root/NasaSpaceApps/backend/app.py))
- Local file inputs via the CLI orchestrator ([`backend/main.py`](file:///root/NasaSpaceApps/backend/main.py))
- Pre-packaged demo images in `data/`

### 5.2 External NASA API Integration Requirements
If developers choose to connect external live NASA data services (e.g., automatically pulling live Earth Information Center feeds, NASA Global Imagery Browse Services (GIBS), Earthdata CMR, or Astronomy Picture of the Day):

| Service | Endpoint | Key Required? | Rate Limit Without Key | Rate Limit With Free Key |
| :--- | :--- | :--- | :--- | :--- |
| **NASA Open APIs** | `https://api.nasa.gov/` | **Yes (`NASA_API_KEY`)** | 30 requests / hr, 50 / day (`DEMO_KEY`) | 1,000 requests / hour |
| **NASA Earthdata GIBS** | `https://gibs.earthdata.nasa.gov/` | Optional (Public WMS/WMTS) | Standard CDN throttling | Unrestricted for standard tiles |
| **NASA Earthdata CMR** | `https://cmr.earthdata.nasa.gov/` | **Yes (Bearer Token)** | Read-only anonymous search | Full access to granule downloads |
| **NASA EIC Portal API** | `https://earth.gov/api/v1/` | **Optional / Future** | Configured per endpoint | Registered institutional token |

### 5.3 `.env` Configuration Guide

To configure API keys for external services, create a `.env` file in the project root directory:

```bash
# =============================================================================
# The Earth Jukebox — Environment Configuration
# =============================================================================

# NASA Open API Key (obtain free at https://api.nasa.gov/)
NASA_API_KEY=your_nasa_api_key_here

# NASA Earthdata Login Bearer Token (https://urs.earthdata.nasa.gov/)
NASA_EARTHDATA_TOKEN=your_earthdata_token_here

# Optional: Custom Earth Information Center (EIC) REST endpoint
EIC_API_ENDPOINT=https://earth.gov/api/v1

# Logging & Runtime Environment
EARTH_JUKEBOX_ENV=development
LOG_LEVEL=INFO
```

### 5.4 Loading `.env` in Python Modules

To safely load and access these environment variables across backend modules, use `python-dotenv`:

```python
import os
from pathlib import Path
from dotenv import load_dotenv

# Locate and load root .env file
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

# Retrieve NASA API credentials with fallback to DEMO_KEY
NASA_API_KEY = os.getenv("NASA_API_KEY", "DEMO_KEY")
NASA_EARTHDATA_TOKEN = os.getenv("NASA_EARTHDATA_TOKEN", "")
EIC_API_ENDPOINT = os.getenv("EIC_API_ENDPOINT", "https://earth.gov/api/v1")

if NASA_API_KEY == "DEMO_KEY":
    import logging
    logging.getLogger("earth_jukebox").warning(
        "Using NASA DEMO_KEY with strict hourly rate limits (30 req/hr). "
        "Register for a free key at https://api.nasa.gov/ and set NASA_API_KEY in .env."
    )
```

### 5.5 Security & Version Control
Always verify that `.env` is listed in your project's `.gitignore` to prevent inadvertent credential leaks:

```gitignore
# Environment & secrets
.env
.env.local
.env.*.local
*.env
```

---

*Document version: 1.0.0 — The Earth Jukebox Team*
