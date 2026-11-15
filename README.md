# Earth Jukebox

> **Hear the data, not the pixels.** An authentic NASA Earth & Space Information Jukebox.

We invert the **colorbar legend** of NASA EIC, SVS, Chandra, and Webb imagery to recover true physical values (temperatures, anomalies, wind speeds, aerosol optical depth, particle flux), then sonify that physical data deterministically into pitch, stereo panorama, rhythmic density, and cultural musical systems with microtonal accuracy and full screen-reader accessibility.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com)
[![Architecture](https://img.shields.io/badge/architecture-Clean%20%2F%20Hexagonal-555555.svg)](docs/01-ARCHITECTURE.md)
[![Accessibility](https://img.shields.io/badge/accessibility-WCAG%202.1%20AA-success.svg)](docs/SUBMISSION/07-ACCESSIBILITY-STATEMENT.md)
[![Demo Video](https://img.shields.io/badge/YouTube-Demo%20Video-red.svg?logo=youtube)](https://youtu.be/olTJtKZuKnM)

---

## Demonstration Video

▶️ **Watch the official video demonstration on YouTube:**  
👉 **[Earth Jukebox Demonstration Video (https://youtu.be/olTJtKZuKnM)](https://youtu.be/olTJtKZuKnM)**

---

## The Core Problem & Scientific Innovation

Most traditional image sonification tools map raw RGB pixel colors directly to musical pitch. For scientific imagery, this approach fails:
1. **Rainbow Colormaps Are Non-Perceptual:** Colormaps like *Jet* or *Rainbow* introduce sharp artificial color boundaries that do not correspond to actual physical transitions.
2. **Arbitrary Color Assignment:** Different NASA missions assign different false colors to the same physical phenomena. Mapping color directly to pitch produces sound that reflects visual rendering artifacts rather than the underlying physics.
3. **Loss of Quantitative Scale:** Listeners hear brightness or hue changes without knowing whether a sound represents 2°C or 40°C.

**Earth Jukebox solves this by inverting the colorbar legend before generating sound:**
```
Scientific Image + Colorbar Legend
             │
             ▼
[ CIE L*a*b* k-d Tree Inversion ]  ──► Recovers true physical field (sub-percent error)
             │
             ▼
[ Deterministic 10D Sonification ] ──► Maps physical dimensions directly to sound
             │
             ▼
[ Information-Invariant Audio ]   ──► Accurate acoustic representation across cultural skins
```

---

## Technical Architecture & Pipeline

Earth Jukebox is engineered with a strict **Clean / Hexagonal Architecture** separating mathematical domain rules from framework and I/O logic:

```
┌─────────────────────────────────────────────────────────────┐
│                     Presentation Layer                      │
│   FastAPI Async REST API  │  Vanilla ES Module Web Studio   │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
┌──────────────▼───────────────────────────────▼──────────────┐
│                     Application Layer                       │
│    Use Cases: SonifyImage, RecoverField, RenderAudio,       │
│               ExportMidi, ExportVideo, QualityMetrics       │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
┌──────────────▼───────────────────────────────▼──────────────┐
│                       Domain Layer                          │
│   Pure Domain Models, Sonification Engine, Cultural Skins,  │
│   Microtonal Pitch Tuning, Information-Invariance Theorems │
└──────────────▲───────────────────────────────▲──────────────┘
               │                               │
┌──────────────┴───────────────────────────────┴──────────────┐
│                    Infrastructure Layer                     │
│  CIE L*a*b* k-d Tree Search │ OpenCV & NumPy Signal Math    │
│  FFmpeg Video/Audio Renderers │ Mido MIDI Exporter          │
└─────────────────────────────────────────────────────────────┘
```

### 1. Physical Data Recovery (Colorbar Inversion)
- **CIE L\*a\*b\* Color Space:** Images and colorbar legends are converted into the perceptually uniform CIE L\*a\*b\* color space, where Euclidean distances closely mirror human color differentiation ($\Delta E$).
- **k-d Tree Nearest Neighbor Matching:** The algorithm indexes sampled legend points into a spatial $k\text{-d}$ tree for rapid pixel-to-value resolution with sub-step linear interpolation.
- **Non-Data & Outlier Masking:** Automatic background, coastline, and null-data detection suppress unmapped regions, preventing borders or map backgrounds from corrupting the sonification.
- **Luminance Fallback:** For monochrome imagery or uncalibrated gradients, the engine falls back to calibrated perceptual luminance matching ($L^*$).

### 2. Deterministic 10-Dimension Sonification Mapping
The sonification engine deterministically maps physical spatial dimensions to acoustic parameters:

| Dimension Key | Scientific Property | Sound Parameter | Deterministic Rule |
| :--- | :--- | :--- | :--- |
| `value->pitch` | Physical Measurement ($u \in [0, 1]$) | Musical Pitch | Monotonic quantization into selected scale/raga across 2–3 octaves |
| `longitude->time` | Longitude Coordinates | Time Sweep | Horizontal playhead moves West to East across beats |
| `latitude_band->voice_pan` | Latitude Bands | Stereo Panning & Voices | 5 independent voices binaurally separated from North (Left) to South (Right) |
| `local_variability->rhythm_density` | Spatial Gradient ($\|\nabla u\|$) | Rhythmic Density | Steep transitions trigger rapid subdivisions ($1\times, 2\times, 4\times$ pulses/beat) |
| `local_variability->roughness` | Gradient Magnitude | Acoustic Roughness | Sharp plume/front edges detune filter resonance for textural friction |
| `global_variability->tempo` | Field Variance ($\sigma^2$) | Master Tempo | Globally dynamic fields play with increased pulse rate |
| `extremes->accent` | Value Outliers ($u \ge 0.95$) | Velocity Accents & Bells | Top 5% extremes receive $+0.25$ velocity boost and bell doubling |
| `masked->silence` | Masked / Null Data | Acoustic Rest | Inactive regions emit complete silence, preserving spatial contrast |
| `category->instrument` | Physical Category | Instrument Timbre | Temperature $\rightarrow$ warm pads; Wind $\rightarrow$ flutes; Aerosols $\rightarrow$ textures; Lightning $\rightarrow$ plucks |
| `global_mean->drone_brightness` | Global Mean Value ($\bar{u}$) | Drone Harmonic Filter | Persistent baseline drone cutoff frequency reflects global planetary average |

### 3. Cultural Musical Skins with Strict Information Invariance
Scientific communication is made culturally universal through three distinct musical systems:
- **Western Neutral:** Equal-tempered reference tuning with modern synthesized instruments.
- **North Indian Classical (Hindustani):** Microtonal Ragas (*Bhairav*, *Megh*, *Todi*) with authentic *shruti* intervals, continuous *meend* (glissando), and tanpura drone accompaniment.
- **Traditional Sri Lankan (*Ravana* / *Vannam*):** Modal structures based on traditional Vannama scales paired with acoustic percussion timbres (*Getaberaya*, *Yakberaya*).

> **Information Invariance Theorem:** Switching cultural skins alters the aesthetic expression without changing the underlying scientific data. Extremes, spatial gradients, and temporal relationships sound at identical relative points across all skins.

### 4. Universal Sensory Accessibility (WCAG 2.1 AA/AAA)
Designed from the ground up for blind, low-vision, and neurodiverse users:
- **2D Tactile Explore Mode:** Arrow-key cell-by-cell navigation of physical data grids.
- **Web Speech Synthesis:** Spoken readouts announce exact coordinates and physical units (e.g., *"Latitude 12 North, 28.4 degrees Celsius"*).
- **Web Haptics API:** Physical device vibration durations scale directly with data intensity.
- **Screen Reader Announcements:** ARIA live regions provide polite, non-intrusive auditory feedback.

### 5. Multi-Format Studio Export Suite
- **Studio WAV:** 44.1 kHz, 16-bit PCM broadcast-grade stereo audio.
- **Compressed MP3:** 192 kbps high-efficiency audio.
- **Type-1 Standard MIDI:** Multi-track polyphonic MIDI with continuous pitch-bend automation.
- **Synchronized MP4 Video:** HD video rendering featuring the source NASA visualization, animated time-slider sweep, and audio soundtrack.
- **Score JSON:** Open schema-validated score specification for scientific re-synthesis.

---

## Quick Start

### Prerequisites
- **Python:** 3.11 or higher
- **FFmpeg:** Installed and available on system `PATH` (for MP3 and MP4 video generation)
- **Node.js:** v20+ (optional, only required to execute `make web-test`)

### Local Installation & Launch

```bash
# 1. Clone repository
git clone https://github.com/VishalRashmika/NasaSpaceApps2026.git
cd NasaSpaceApps2026

# 2. Create and activate Python virtual environment
python3.11 -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate

# 3. Install dependencies in editable mode
make install

# 4. Verify test suite and architectural contracts
make check

# 5. Launch the Web Studio
make run
```

Once running, navigate to:
- **Web Studio:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive OpenAPI Documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## Verification & Quality Assurance

To run the complete verification suite:
```bash
make check          # Runs linting, type checks, architecture contracts, unit/integration tests, and web tests
```

Individual test targets:
```bash
make lint           # Ruff code formatting and linting
make types          # Strict Mypy type-checking across all packages
make arch           # Import-linter architectural contracts and docs synchronization
make test           # Pytest unit and integration test suite
make web-test       # Native Node.js web component and accessibility suite
```

---

## Documentation & NASA Space Apps Submission Pack

All official submission materials are cataloged under **[`docs/SUBMISSION/`](docs/SUBMISSION/)**:
1. [`01-PROJECT-SUMMARY.md`](docs/SUBMISSION/01-PROJECT-SUMMARY.md) — Executive summary, vision, and core innovations.
2. [`02-METHODOLOGY.md`](docs/SUBMISSION/02-METHODOLOGY.md) — Mathematical inversion and sonification methodology.
3. [`03-AI-TOOL-DISCLOSURE.md`](docs/SUBMISSION/03-AI-TOOL-DISCLOSURE.md) — Transparent disclosure of development tools and AI usage.
4. [`04-DATA-CREDITS.md`](docs/SUBMISSION/04-DATA-CREDITS.md) — NASA dataset sources, citations, and credits.
5. [`05-DEMO-SCRIPT.md`](docs/SUBMISSION/05-DEMO-SCRIPT.md) — 3-minute video storyboard, narration script, and [YouTube Video Link](https://youtu.be/olTJtKZuKnM).
6. [`06-SCREENSHOTS-AND-ASSETS.md`](docs/SUBMISSION/06-SCREENSHOTS-AND-ASSETS.md) — Visual asset index and UI screenshots.
7. [`07-ACCESSIBILITY-STATEMENT.md`](docs/SUBMISSION/07-ACCESSIBILITY-STATEMENT.md) — WCAG 2.1 AA/AAA compliance audit and accessibility implementation.
8. [`docs/01-ARCHITECTURE.md`](docs/01-ARCHITECTURE.md) — Detailed Clean / Hexagonal Architecture specification.
9. [`docs/02-DOMAIN-MODEL.md`](docs/02-DOMAIN-MODEL.md) — Formal domain entities, value objects, and application ports.
10. [`docs/03-FEATURE-CATALOG.md`](docs/03-FEATURE-CATALOG.md) — Complete catalog of 108 engineering features and acceptance criteria.
11. [`docs/EVAL-REPORT.md`](docs/EVAL-REPORT.md) — Quantitative evaluation report: $L^*a^*b^*$ recovery errors, pitch correlation ($r \ge 0.99$), and latency benchmarks.

---

## Credits & Attribution

Scientific imagery and data courtesy of:
- **NASA Earth Information Center (EIC)**
- **NASA Scientific Visualization Studio (SVS)**
- **NASA Chandra X-ray Observatory / STScI**

For complete citations, dataset IDs, and sensor credits, please see [`docs/SUBMISSION/04-DATA-CREDITS.md`](docs/SUBMISSION/04-DATA-CREDITS.md).
