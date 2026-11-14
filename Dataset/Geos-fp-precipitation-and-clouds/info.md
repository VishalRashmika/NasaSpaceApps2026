# NASA Dataset: GEOS-FP Precipitation and Clouds

## 1. Scientific Context
*   **Source:** NASA Global Modeling and Assimilation Office (GMAO) / Scientific Visualization Studio (SVS ID: 5149).
*   **Model:** Goddard Earth Observing System Forward Processing (GEOS-FP).
*   **Variables:** 
    *   **Precipitation:** Total estimated precipitation (including both rain and snowfall) in millimeters (mm).
    *   **Clouds:** Simulated cloud fields shaded by optical thickness.
*   **Significance:** Tracks the formation of clouds and estimates rainfall, highlighting atmospheric rivers, storm severity, and shifting precipitation patterns driven by climate change.

## 2. AI Computer Vision Legend Mapping
This visualization contains two distinct visual layers: a grayscale cloud layer and a colored precipitation layer. To allow an AI or computer vision script to extract accurate data, the layers must be interpreted as follows:

### Layer A: Clouds (Background/Context)
*   **Visual Representation:** White to dark gray/black shading.
*   **Meaning:** Cloud optical thickness. High luminance (white) indicates thick, dense clouds; low luminance (dark gray/transparent) indicates thin or no clouds.
*   **AI Extraction Rule:** Pixels with very low Saturation (in HSV space) should be classified as the cloud/basemap layer.

### Layer B: Precipitation (Data Overlay)
*   **Visual Representation:** High-saturation colors mapped along a continuous gradient.
*   **Unit:** Millimeters (mm).
*   **Range:** 0 mm to 20 mm.
*   **Color-to-Scalar Map (Strict extraction guidelines for `legend.png`):**
    *   **0.0 - 1.5 mm:** Dark Green to Light Green
    *   **1.5 - 4.0 mm ("light"):** Dark Blue transitioning to Cyan
    *   **4.0 - 7.0 mm:** Cyan transitioning into Light Purple
    *   **7.0 - 9.0 mm:** Light Purple transitioning to Dark Magenta
    *   **9.0 - 11.0 mm ("moderate"):** Dark Magenta transitioning to Dark Red
    *   **11.0 - 15.0 mm:** Dark Red transitioning to Orange
    *   **15.0 - 20.0 mm ("very heavy"):** Orange transitioning to bright Yellow
*   **AI Extraction Rule:** Pixels with high Saturation (HSV) belong to this layer. Map the RGB values against the CIELAB nearest-neighbor lookup table based on the gradient above to extract the exact precipitation in mm.

## 3. Sonification Strategy: "Atmospheric Rivers & The Uraga Vannama"
To sonify both the gentle formation of clouds and the violent downpours of atmospheric rivers, we can map the two visual layers to distinct audio engines, drawing inspiration from Sri Lankan rhythmic structures:

*   **Stem 1: Cloud Optical Thickness (The Airy Pad)**
    *   **Concept:** Clouds represent potential energy and atmospheric weight.
    *   **Mapping:** Map grayscale luminance to the cutoff frequency and amplitude of a broadband noise generator or a slow-attack airy synthesizer pad. Bright white clouds open the filter (creating a rushing wind sound), while dark/clear areas close it.
*   **Stem 2: Precipitation (Granular & Percussive Flow)**
    *   **Concept:** Rain is particulate and rhythmic. 
    *   **Mapping:** Use Granular Synthesis. The extracted mm value (0-20) controls the *grain density* (number of droplets). 
    *   **Cultural Element (Optional):** Tie the density mapping to the accelerating tempo of traditional *Geta Bera* rhythms or the fluid, sinuous pacing of the *Uraga Vannama* (which mimics wave-like flow). As precipitation hits "very heavy" (Yellow/15-20mm), the granular droplets lock into an intense, driving percussive rhythm, symbolizing flash flood risks.

## 4. Suggested Data Processing Pipeline
To implement this in the Earth Jukebox architecture, use the following processing pipeline:

1.  **HSV Masking for Layer Separation:** In your Web Worker / Python script, convert the video frames from RGB to HSV. 
    *   Create a mask isolating pixels with `Saturation > 0.2` and `Value > 0.2` (These are your Precipitation pixels).
    *   The remaining pixels are your Cloud/Basemap pixels.
2.  **Colorbar Inversion (CIELAB LUT):** Create a 256-point lookup table matching the `legend.png` gradient exactly (Green -> Blue -> Cyan -> Purple -> Red -> Orange -> Yellow). Use a KD-Tree in CIELAB color space to match the masked precipitation pixels to their exact millimeter value (0-20).
3.  **Audio Parameter Extraction:**
    *   Calculate `mean_cloud_thickness` from the luminance of the non-masked pixels.
    *   Calculate `peak_precipitation` and `total_precipitation_volume` from the masked colored pixels.
4.  **Audio Engine Routing:** Pass the `mean_cloud_thickness` to the filter of your drone/pad stem, and pass the `peak_precipitation` to the grain density and amplitude of your granular rain synthesizer.