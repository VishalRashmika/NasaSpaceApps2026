# Earth Jukebox — Data Credits & Third-Party Licensing

> NASA Space Apps Challenge 2026: *The Earth Information Jukebox*

---

## 1. NASA Data & Imagery Attribution

Earth Jukebox utilizes public domain imagery and scientific visualizations provided by NASA and affiliated research centers:

- **NASA Earth Information Center (EIC):** Flat-map visualizations of global temperature anomalies, biosphere carbon fluxes, and atmospheric aerosol optical depth.
- **NASA Scientific Visualization Studio (SVS):** Sea surface temperature (SST) maps, polar ice extent records, and hurricane precipitation profiles.
- **NASA Earth Observatory / GIBS (Global Imagery Browse Services):** Moderate Resolution Imaging Spectroradiometer (MODIS) and Visible Infrared Imaging Radiometer Suite (VIIRS) global daily surface reflectance maps.

*Attribution Policy:* Every sample in Earth Jukebox includes verbatim source credit strings, original URLs, and licensing statements stored in its `meta.json` catalog record. In accordance with NASA Media Usage Guidelines, all NASA visual data is in the public domain and free to adapt for educational and scientific purposes.

---

## 2. Open-Source Software Dependencies

Earth Jukebox relies on the following open-source libraries:

| Library | License | Usage in Earth Jukebox |
|---|---|---|
| **Tone.js** | MIT License | In-browser Web Audio synthesis engine (`web/vendor/Tone.js`). |
| **NumPy** | BSD 3-Clause | Core array mathematics, audio waveform generation, DSP filtering. |
| **SciPy** | BSD 3-Clause | Spatial indexing (`cKDTree`) for CIE $L^*a^*b^*$ color lookup and signal processing. |
| **OpenCV (headless)** | Apache 2.0 | Image matrix manipulation and colorbar contour detection. |
| **Pillow (PIL)** | Historical Permission Notice and Disclaimer (HPND) | Image decoding, format validation, and animated GIF frame extraction. |
| **Matplotlib** | PSF / BSD Compatible | Colormap preset definitions and RGB lookup tables. |
| **Mido** | MIT License | Standard Type-1 MIDI file generation and microtonal pitch-bend encoding. |
| **FastAPI** | MIT License | High-performance Python backend HTTP API and OpenAPI documentation. |
| **Uvicorn** | BSD 3-Clause | ASGI web server implementation. |
| **FFmpeg** | LGPL / GPL | Optional subprocess conversion of PCM WAV audio to MP3 format. |

---

## 3. Audio & Musical Attribution

- **Synthesizer Algorithms:** All default audio voices (pad, pluck, bell, flute, strings, sub, texture, percussion) are synthesized algorithmically via custom NumPy DSP math and Tone.js oscillators. Zero external copyrighted audio samples are required.
- **Cultural Audio Assets:** Any supplemental acoustic recordings (e.g. traditional Sri Lankan percussion instruments) adhere to `data/audio/LICENSES.md` under CC0 (Public Domain) or original team recordings released for open competition use.
- **Tone.js Notice:** The complete MIT license notice for Tone.js is preserved in `web/vendor/Tone.js` and `web/vendor/VERSION`.
