# NASA GEOS-FP: Near-Surface Temperature (T2M)

## 1. Dataset Overview
This dataset visualizes **Near-Surface Temperature (T2M)** calculated by NASA’s Goddard Earth Observing System Forward Processing (GEOS-FP) system. 
* **What it represents:** The global best estimate of air temperatures at 2 meters (approx. 6 feet) above Earth's surface.
* **How it is generated:** The GEOS-FP model integrates millions of real-time weather observations from ground stations, aircraft, balloons, and Earth-observing satellites.
* **Scientific Value:** It tracks variations in daytime/nighttime temperatures, the influence of large-scale weather systems, and long-term changes in heatwave frequencies due to rising greenhouse gas concentrations.

## 2. Legend & Colorimetric Definition
To allow an AI model or computer vision script to accurately analyze the dataset images (e.g., `MC01_stage3_GMAO_near_surface_temperature_2048x1024_en.00001_print.jpg`), the color map must be inverted. The visual legend (`NearSurfaceTemperature_colorbar.png`) maps scientific scalar values (Degrees Celsius) to specific RGB profiles:

* **Value Range:** $-40^\circ\text{C}$ to $+40^\circ\text{C}$
* **Key Milestones:**
  * **Very Cold ($-40^\circ\text{C}$ to $-20^\circ\text{C}$):** Transitions from dark navy blue to pale icy white, into deep magenta. 
  * **Cold to Freezing ($-20^\circ\text{C}$ to $0^\circ\text{C}$):** Transitions from deep magenta/purple into dark blue, lightening to a pale cyan at the freezing point ($0^\circ\text{C}$).
  * **Warm ($0^\circ\text{C}$ to $+20^\circ\text{C}$):** Transitions from pale cyan into pale green, shifting into bright yellow and orange.
  * **Very Hot ($+20^\circ\text{C}$ to $+40^\circ\text{C}$):** Transitions from deep orange into intense fiery red, ultimately darkening into black/dark brown at the extreme maximum.

---

## 3. Sonification Strategy: "Earth Jukebox" Audio Mapping
To translate this visual temperature data into a multi-sensory auditory experience, we must avoid chaotic "wind-chime" noise. Instead, we map the physical properties of the data to distinct acoustic phenomena.

### Conceptual Idea: "Thermal Tension & Acoustic Beating"
Rather than mapping absolute temperature to a standard musical pitch (which lacks physical intuition), we map the **deviation from a comfortable baseline** to harmonic tension and texture.

### Audio Mapping Techniques
1. **The Baseline Drone (Spatial Foundation):**
   * Establish a consonant, calming baseline chord (e.g., a Just Intonation drone at $110\text{ Hz}$) representing a temperate baseline (e.g., $15^\circ\text{C}$).
2. **Extreme Heat (Psychoacoustic Beating):**
   * As the temperature in a sampled region rises toward $+40^\circ\text{C}$ (the dark red/black regions), introduce a secondary oscillator that detunes from the baseline by a frequency $\Delta f$. 
   * This creates a physical, throbbing "beating" effect. The hotter the temperature, the faster and more urgent the throbbing (e.g., beating at $8\text{ Hz}$ for maximum heat).
3. **Extreme Cold (Granular Synthesis):**
   * As temperatures drop toward $-40^\circ\text{C}$ (the white/magenta regions), map the scalar value to the grain density and high-pass cutoff of a granular synthesizer. This creates a brittle, crackling texture reminiscent of fracturing ice.
4. **Spatial Audio (HRTF Panning):**
   * Map the $X/Y$ coordinates of the visual map to 3D binaural space. Longitude maps to azimuth (left/right ear), and Latitude maps to elevation/pitch register. This allows blind users to "scan" the map with a cursor and hear exactly where thermal anomalies are located.

---

## 4. Suggested Data Processing Pipeline
To accurately drive the audio engine in real-time without overwhelming a browser or script, follow this processing technique:

1. **ROI Masking:** Crop out the burned-in UI elements (the NASA/GMAO logo in the top left, the timestamp in the bottom left) so they are not falsely sonified as temperature data.
2. **CIELAB Perceptual Inversion:** 
   * Do not use raw RGB values to drive audio. Instead, build a lookup table (LUT) from the `NearSurfaceTemperature_colorbar.png`.
   * Convert the video frames and the LUT into the perceptual CIELAB color space. Use a Nearest-Neighbor algorithm (like a KD-Tree) to map every pixel back to its exact scientific scalar value ($-40$ to $+40$).
3. **Downsampling for Audio:**
   * High-resolution frames ($2048 \times 1024$) will crash a real-time Web Audio API script. Downsample the active analysis grid to a $32 \times 18$ matrix using OpenCV interpolation.
4. **Hotspot Indexing:**
   * Write an algorithm to scan the downsampled matrix and identify the coordinates of the Top 3 hottest and coldest regions per frame. This data can be passed to a screen reader or used to automatically pan the audio engine to the most critical zones.