# Dataset Overview: Lightning Events Detected from the ISS (2017-2023)

*   **NASA SVS ID:** 5011
*   **Sensor/Instrument:** Lightning Imaging Sensor (LIS) on the International Space Station (ISS).
*   **Data Type:** Point-event data (spatial and temporal coordinates of individual lightning flashes).
*   **Time Range:** January 2017 to July 2023.
*   **Visual Format:** Global maps and 3D globe representations utilizing a 10-day roving window to show seasonal lightning patterns. 

This dataset is unique compared to fluid-flow models (like winds) or scalar heatmaps (like temperature). It represents discrete, sudden physical events in the Earth's tropical and mid-latitude regions.

---

# AI Vision Legend & Color Mapping

Because this dataset visualizes discrete point-events rather than a continuous scale, there is **no traditional colorbar legend**. Instead, the visual presence of a specific color strictly indicates the occurrence of an event against a dark basemap.

For computer vision models analyzing frames (such as `iss_lightning_sos_yearly_debug_2023_sos_2048p60.00420_print.jpg`, `iss_lightning_SOS_thumb.jpg`, or `iss_lightning_preview.jpg`), use the following binary classification rules:

*   **Event Indicator (Lightning Strike):** 
    *   **Visual:** Bright yellow/gold pixels or clusters.
    *   **RGB Approximation:** High Red and Green, low Blue (e.g., `RGB(255, 255, 0)` to `RGB(255, 200, 50)`).
    *   **Meaning:** One or more lightning flashes occurred at this exact spatial coordinate within the 10-day roving window represented by the frame.
*   **Null Indicator (Background):**
    *   **Visual:** Grayscale/dark map elements (oceans, continents).
    *   **Meaning:** No lightning activity recorded at this location during the time window.

---

# Sonification Concept: Transient Point-Events

Since lightning is a discrete, instantaneous burst of energy, applying continuous synthesizers (like drones or pads) will not accurately represent the data. Instead, this dataset should use **Micro-Percussive / Granular Synthesis**. 

Taking inspiration from the traditional Sri Lankan *Geta Bera* drum cadences (which accelerate to represent storm intensities) or crisp synth-pluck models, we can map the data as follows:

### Audio Mapping Techniques
1.  **Spatial Panning (Longitude -> Azimuth):** Map the X-coordinate of a yellow pixel cluster to 3D binaural space. A lightning strike in the Americas plays in the left ear; a strike over Indonesia plays in the right ear.
2.  **Pitch/Register (Latitude -> Frequency):** Map the Y-coordinate to pitch. Strikes in the Northern mid-latitudes trigger higher-pitched percussive clicks/plucks, while strikes in the Southern mid-latitudes trigger lower, deeper thuds.
3.  **Amplitude/Timbre (Pixel Density -> Velocity):** If computer vision detects a dense cluster of yellow pixels (a massive storm system, common over Central Africa or the Amazon), increase the volume, add a slight reverb tail, and increase the distortion/harmonic grit of the percussive sound.
4.  **Temporal Density (Rhythm):** As the 10-day window slides through seasonal monsoons, the sheer number of yellow pixels will naturally create a rapidly accelerating, chaotic polyrhythm (like rain hitting a tin roof).

---

# Data Processing Pipeline Suggestions

To prepare this visual data for an audio engine, avoid heavy continuous optical flow. Instead, use a lightweight **Color Thresholding & Blob Detection** pipeline:

1.  **HSV Masking:** Convert the video frame/image to HSV color space. Create a strict mask that isolates the yellow spectrum (e.g., Hue: 20-40, Saturation > 150, Value > 150).
2.  **Contour/Blob Detection:** Run OpenCV `findContours` on the masked image to group adjacent yellow pixels into single "storm cells" (blobs).
3.  **Calculate Centroids:** For each detected blob, calculate its centroid `(x, y)` coordinate. Convert `x` to a normalized value `[0.0, 1.0]` for stereo panning, and `y` to `[0.0, 1.0]` for pitch assignment.
4.  **Calculate Area:** Count the number of pixels in each blob to determine the intensity (amplitude) of the trigger.
5.  **Event Dispatch:** Send this JSON array of `[x, y, size]` coordinates to the Web Audio API via a rapid step-sequencer to trigger the percussive samples.