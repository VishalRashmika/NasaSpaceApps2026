# Earth Jukebox — Project Summary

> NASA Space Apps Challenge 2026: *The Earth Information Jukebox*  
> **Repository:** [https://github.com/earth-jukebox/earth-jukebox](https://github.com/earth-jukebox/earth-jukebox)  
> **Live Demo:** [http://127.0.0.1:8000](http://127.0.0.1:8000) · API: `/docs`

---

## 1. Executive Summary & Vision

Traditional image sonifiers translate raw pixel properties (RGB brightness, hue, Cartesian coordinates) directly to audio frequencies. Because NASA Earth visualization color scales are chosen arbitrarily for visual distinction, conventional pixel sonification produces sound disconnected from physical reality.

**Earth Jukebox** introduces **colorbar inversion**: we reverse-engineer the scientific legend to recover the approximate underlying physical scalar field (temperatures in Kelvin, ozone in Dobson units, anomalies in °C). We then sonify that recovered physical field using a deterministic, versioned, and mathematically verified mapping (`MAPPING_VERSION = 1.0.0`). 

Every audible pitch corresponds directly to a physical measurement, verified by three independent fidelity benchmarks:
- **[Level 1: Mean Inversion RMSE of 0.326%](file:///root/earth-jukebox/docs/EVAL-REPORT.md#L15)** against synthetic ground truth (target: $\le 2.0\%$ sequential/diverging, $\le 3.0\%$ rainbow). Tested across 14 colormaps, including [`viridis` at 0.391%](file:///root/earth-jukebox/docs/EVAL-REPORT.md#L25), [`RdBu_r` at 0.325%](file:///root/earth-jukebox/docs/EVAL-REPORT.md#L34), and [`turbo` at 0.267%](file:///root/earth-jukebox/docs/EVAL-REPORT.md#L37).
- **[Level 2: Mean Score Round-Trip Correlation r = 0.9914](file:///root/earth-jukebox/docs/EVAL-REPORT.md#L16)** between input scalar grids and decoded score note events (target: $r \ge 0.95$).
- **[Level 3: Mean Audio Legend Pitch Correlation r = 0.9946](file:///root/earth-jukebox/docs/EVAL-REPORT.md#L17)** verified via monophonic YIN pitch-tracking with max error $\le 1.5$ cents (target: $\le 20$ cents, $r \ge 0.98$).

---

## 2. Core Innovations

1. **Hear the Legend, Not the Palette:**
   - **Audio Legend Sweep:** A 32-note ascending reference sweep spanning $u \in [0, 1]$ allows listeners to internalize the pitch scale before hearing complex visualizations.
   - **Data-Driven Sonification:** Longitude maps to time (West to East sweep), latitude bands map to spatial voice panning and timbre, local gradient maps to rhythmic density, and global variability governs tempo (72–120 BPM).

2. **Cultural "Skins" with Invariant Information Layer:**
   - Cultural music systems (Western Neutral pentatonic, Hindustani raga with descending *meend* glides, and Sri Lankan *hewisi* percussion rhythms) are swappable aesthetic layers.
   - **Principle P1 & P2 Invariance:** The physical information layer is completely preserved across all skins; pitch ranking order, note onsets, velocities, and accents are identical regardless of the chosen musical skin.

3. **Accessibility First (WCAG 2.1 AA):**
   - **Interactive Explore Mode:** Full keyboard and touch navigation across the data grid with instantaneous audio feedback, cell coordinate readouts, and physical values.
   - **Sensory Integration:** Throttled ARIA live announcements ($\ge 250$ ms) prevent screen-reader churn; tactile haptic pulses (`navigator.vibrate`) scale pulse length with data magnitude.
   - Zero reliance on color alone: High-contrast dual-modality playhead (triangle marker + line) and light/dark theme support.

4. **Temporal Flux in Time Mode:**
   - Multi-frame GIF/video animation sonification partitions frames into distinct musical phrases separated by clean 1-beat rests.
   - Inter-frame physical change dynamically injects microtonal harmonic tension into the drone bed, allowing listeners to immediately perceive climatic shifts over time.

5. **Industrial-Grade Architecture:**
   - Backend built in Python 3.11+ using Clean Architecture (presentation, infrastructure, application, domain), mechanically enforced by import-linter contracts and test suites.
   - Zero build-step vanilla ES-module frontend using vendored Tone.js. Fully operational offline without third-party cloud dependencies.
   - Comprehensive multi-format export: Studio-grade 44.1 kHz 16-bit PCM WAV, Type-1 standard MIDI with microtonal pitch bends, MP3 via ffmpeg, and Score intermediate JSON.
