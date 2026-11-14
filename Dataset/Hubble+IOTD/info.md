# NASA Dataset Context: Deep Space Imagery & Sonification

## 1. Data Definition
This dataset consists of deep-space astronomical imagery captured by space telescopes (such as the Hubble Space Telescope and Chandra X-ray Observatory). The data captures massive, distant structures, primarily:
*   **Globular Clusters:** Spherical, gravitationally bound groups of stars with highly concentrated centers (e.g., Caldwell 73 / NGC 1851).
*   **Galaxies & Galaxy Clusters:** Massive gravitational groupings of stars, gas, and dark matter (e.g., as seen in `28_black-eye-galaxy.jpg` and `22_young-galaxy-cluster.jpg`).
*   **Nebulae & Interstellar Gas:** Diffuse clouds of dust and ionized gases (e.g., `03_nasas-james-webb-space-telescope-captures-eerie-cats-head.jpg`).
*   **Multi-Wavelength Anomalies:** High-energy phenomena captured in X-ray or infrared (e.g., `13_nasas-chandra-spots-galactic-gem.jpg`).

The data contains two primary visual components: **Point Sources** (distinct, bright stars) and **Diffuse Backgrounds** (gas, dust, and cosmic background light).

## 2. The "Legend" (AI-Parseable Visual-to-Audio Rules)
Unlike Earth science datasets that use a gradient colorbar, this astronomical dataset utilizes a **Rule-Based Mapping Legend** based on physical and spatial characteristics. 

An analyzing AI should map the image pixels using the following strict logic:

| Visual Feature (Input) | Scientific Interpretation | Audio Element (Output) | Parameter Mapping |
| :--- | :--- | :--- | :--- |
| **Point Source: Orange/Red Pixel Cluster** | Cooler, often older stars (Red Giants). | **Marimba** (Percussive, warm wood resonance) | Triggered upon playhead intersection. |
| **Point Source: Blue Pixel Cluster** | Hotter, often younger stars. | **Glockenspiel** (Bright, metallic chime) | Triggered upon playhead intersection. |
| **Diffuse / Background Pixels** | Ambient galactic gas, unresolved distant stars. | **Choir / Synth Pad** (Continuous harmonic drone) | Volume/Intensity scales with pixel luminosity. |
| **Spatial Radius ($r$)** | Distance from the gravitational center of the cluster. | **Pitch / Frequency** | $Pitch \propto r$ (Stars farther from the center generate higher-pitched notes). |
| **Spatial Angle ($\theta$)** | Angular position in a 360-degree sweep. | **Time / Playback Trigger** | A radar playhead sweeps circularly. When playhead angle = $\theta$, the sound is triggered. |

## 3. Conceptual Sonification Idea: "Gravitational Orbital Sequencing"
For images like `28_black-eye-galaxy.jpg` or `22_young-galaxy-cluster.jpg`, a standard left-to-right or radar scan can sometimes feel arbitrary. 

**The Idea:** Treat the brightest central point of the image (the galactic core or cluster center) as a gravitational well. Instead of a sweeping radar line, sonify the image as a set of concentric orbital rings.
*   **The Rhythm (Drawing from traditional Sri Lankan patterns):** Map the dense, massive center to the slow, heavy, and majestic rhythms of the *Gajaga Vannama* (elephant rhythm) using deep bass or drone elements. Map the sparse, fast-moving outer edges to the swift, high-pitched *Ukusa Vannama* (eagle/flight rhythm) using the blue-star glockenspiels. 
*   **Acoustic Mass:** The brighter the point source (star), the heavier the "attack" or velocity of the synthesized note. 
*   **Multi-Wavelength Layers:** If analyzing `13_nasas-chandra-spots-galactic-gem.jpg`, use stereo separation: optical light (Hubble) plays in the center channel, while high-energy X-ray spots (Chandra) trigger microtonal, high-frequency pings panned hard left and right.

## 4. Suggested Data Processing Pipeline
To process this type of data into an audio engine, a computer vision (CV) pipeline must isolate point sources from the background. 

1.  **Coordinate Transformation (Cartesian to Polar):**
    *   Locate the image's center of mass (the brightest concentration of pixels).
    *   Map every pixel's $(x, y)$ coordinate to a polar coordinate $(r, \theta)$, where $r$ is the radius and $\theta$ is the angle. This makes it mathematically trivial to map radius to pitch and angle to time.
2.  **Background Subtraction & Segmentation:**
    *   Apply a Gaussian Blur and background subtraction to separate the diffuse gas (which will drive the continuous "Choir" drone) from the sharp stars.
3.  **Blob Detection & Color Masking (HSV):**
    *   Convert the image to HSV (Hue, Saturation, Value) color space. 
    *   Create two masks: One isolating the Hue range for Blue (e.g., $100^{\circ}-140^{\circ}$) and one for Orange/Red (e.g., $0^{\circ}-20^{\circ}$ and $340^{\circ}-360^{\circ}$).
    *   Run OpenCV `SimpleBlobDetector` on both masks to extract the exact $(r, \theta)$ coordinates and size (luminosity) of every star.
4.  **JSON Telemetry Export:**
    *   Export the blob coordinates into a lightweight JSON file. The web-audio synthesizer will read this JSON (e.g., `{"starType": "blue", "radius_normalized": 0.85, "angle_deg": 120}`) and trigger the correct instrument and pitch without needing to process image pixels in real-time.