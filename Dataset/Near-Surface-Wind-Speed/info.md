# NASA Dataset: GEOS-FP Near-Surface Wind Speed

## 1. Data Context and Definition
**Source:** NASA Goddard Earth Observing System Forward Processing (GEOS-FP) system.
**Visualized Product:** Near-Surface Wind Speed.
**Measurement:** Wind speed calculated by sampling 3-D atmospheric fields at 10 meters (about 30 feet) above Earth's surface. 
**Scientific Significance:** 
This dataset represents a global best estimate of atmospheric wind conditions by integrating millions of observations from ground stations, aircraft, balloons, and satellites. Wind speed is generally higher over oceans due to lower surface friction compared to landmasses. The organized swirling patterns in the data reflect weather fronts, global circulation, and severe storm systems (like hurricanes and cyclones). This data is critical for tracking storm severity, air pollution transport, and planning renewable wind energy resources.

---

## 2. Legend & Color Mapping Definition (For AI / Computer Vision Parsing)
To allow an AI model to accurately extract scalar values from the visualization (such as `MC02_stage3_GMAO_near_surface_wind_2048x1024_en.00001_print.jpg`), the colorbar (`legend.png`) must be inverted using a perceptual color space (like CIELAB). 

**Variable:** Wind Speed
**Units:** meters per second (m/s)
**Range:** 0 m/s to 40 m/s

**Strict Color-to-Value Mapping:**
*   **0 to ~4 m/s (Calm):** Solid Gray block.
*   **~4 to 10 m/s (Light/Gentle):** Transitioning from Light Purple/Lavender -> Deep Indigo -> Solid Blue.
*   **10 to 15 m/s (Moderate):** Transitioning from Light Blue/Cyan -> Bright Green -> Yellow-Green.
*   **15 to 20 m/s (Strong):** Transitioning from Yellow -> Orange -> Bright Red (The 20 m/s mark is visually indicated as "strong" in pure red).
*   **20 to 30 m/s (Storm):** Transitioning from Bright Red -> Deep Crimson -> Dark Brown/Black.
*   **30 to 40 m/s (Hurricane Force):** Black fading into a dark grey/desaturated gradient at the extreme high end.

*AI Extraction Note:* The initial gray block (0-4 m/s) is categorical/flat, whereas 4-40 m/s acts as a continuous gradient. When building the KD-Tree for color inversion, sample the gradient strip starting *after* the initial gray block for precise scalar interpolation.

---

## 3. Sonification Concept: "The Ukusa Flow"
Instead of mapping color to basic musical pitch (which fails for continuous noise-like data like wind), we can map the wind data to a dynamic, filtered noise synthesizer, heavily inspired by the Sri Lankan **Ukusa Vannama** (which mimics the swift, gliding, and swirling currents of a hawk in the wind).

### Data-to-Audio Mapping Rules:
1.  **Scalar Wind Speed (Color Value) $\rightarrow$ Filter Cutoff & Volume (Pink Noise):** 
    *   Calm/Gray areas (0-4 m/s) produce a low, sub-bass rumble (cutoff ~100 Hz).
    *   Strong/Red areas (15-20 m/s) open the low-pass filter to release high-frequency "rushing" wind sounds (cutoff ~3000 Hz) and increase the gain.
2.  **Optical Flow Vorticity (Swirls) $\rightarrow$ Rhythmic Tremolo (Geta Bera syncopation):**
    *   Calculate the curl/vorticity of the movement between video frames. High vorticity (like the blue/yellow hurricane spirals in the southern ocean) triggers a rapid amplitude modulation (tremolo), mimicking the accelerating, fluttering drum cadences of traditional folk rhythms as a storm organizes.
3.  **Latitude $\rightarrow$ Stereo / 3D Panning:**
    *   Winds in the Northern Hemisphere are panned slightly right/high, and the massive Southern Ocean wind bands are panned left/low.

---

## 4. Suggested Processing Pipeline (Hybrid Architecture)

**Phase 1: Offline Python Telemetry Extraction**
1.  **Color Inversion:** Write a Python script using `scikit-image` to sample the `legend.png` gradient. Convert the RGB values to the CIELAB color space.
2.  **Frame Processing:** Read the main video or image (`MC02_stage3_GMAO_near_surface_wind...jpg`). For each pixel, find the nearest CIELAB color in the legend to determine the exact wind speed in m/s.
3.  **Physics Extraction:** Downsample the frame to a 128x72 grid. Use `cv2.calcOpticalFlowFarneback` to calculate the directional velocity vectors of the wind fronts.
4.  **Export:** Save this matrix as `cartridge_telemetry.json`.

**Phase 2: Real-Time Browser Audio (TypeScript & Web Audio API)**
1.  **Noise Generation:** Create a continuous `AudioBufferSourceNode` filled with Pink Noise.
2.  **Dynamic Filtering:** Route the noise through a `BiquadFilterNode` (Lowpass). Use the JSON telemetry to modulate the `frequency.value` based on the local wind speed as the user's cursor moves over the map.
3.  **Accessibility:** Implement a "Spatial Probe" where a blind user can use Arrow Keys to move across the map. When the cursor hits a "Hurricane Force" zone (black/grey pixels > 30 m/s), trigger an auditory chime and a haptic vibration pulse via `navigator.vibrate()`.