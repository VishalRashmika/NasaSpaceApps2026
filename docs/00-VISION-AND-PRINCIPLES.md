# 00 — Vision and Principles

> Stable document. Changing anything here requires a human decision (see docs/11 §5).

## 1. What this is

**Earth Jukebox** is a web app + Python backend built for the NASA Space Apps 2026 challenge *"The Earth Information Jukebox"*. A user picks (or uploads) a NASA Earth Information Center (EIC) / SVS visualization and hears a soundtrack of the **data** behind it.

The challenge asks for a tool that pairs EIC visual frames with dynamic sonification, is accessible to blind and low-vision users, and balances data fidelity with musicality.

## 2. The core idea: colorbar inversion

Most image sonifiers map **pixel properties** (brightness, hue, x/y) to sound. A rainbow palette is arbitrary, so that sound says nothing about the science.

We sonify the **recovered physical value** instead:

1. Find the image's colorbar (legend).
2. Build a lookup table: colour → physical value (min/max/units supplied or confirmed by the user).
3. Map every pixel of the map region back to a value via nearest legend colour (CIE L*a*b*, k-d tree). Result: an approximate **scalar field of real data**, with NaN where pixels are not data (land mask, labels, background).
4. Sonify that field with a **fixed, documented, versioned** mapping (doc 06).

Consequence: every sound is traceable to a number with units, regardless of which colormap the image uses.

## 3. Why this wins

| Judging lens | Our answer |
|---|---|
| Creativity | Hear the legend, not the palette. Audio legend sweep. Swappable cultural "skins" (Hindustani raga, Sri Lankan) over a fixed information layer. |
| Technical rigour | Measured fidelity: inversion error on synthetic ground truth, score round-trip correlation, audio pitch-tracking check. Deterministic output. |
| Accessibility (core theme) | Explore mode (mouse/touch/keyboard), ARIA live text, haptics, generated description, audio legend. |
| Musicality | Scale-quantised pitch, drone, rhythm from data texture; skins; mixed instrument families. |
| Real time | Browser renders the Score live (Tone.js) with a synced playhead. |

## 4. Non-negotiable principles

**P1 — Information layer is fixed; aesthetic layer is swappable.** The mapping in doc 06 never changes per skin. A skin changes scale, timbre, rhythm flavour only. Pitch rank-order of values is always preserved (testable: F-054).

**P2 — Pitch depends only on the data value.** Same value ⇒ same pitch, in any latitude band, at any time in the track. (Voices differ by timbre and pan, not by register.)

**P3 — Determinism.** Same image bytes + same params + same mapping version ⇒ byte-identical Score JSON and WAV. All randomness is seeded from the image hash. No wall-clock, no unseeded RNG.

**P4 — Honesty about data.** Masked/missing data is *silence*, never filler. Luminance fallback (no colorbar) is always labelled "approximate, not data-faithful" in API, UI, and text description. Confidence and quality are surfaced to the user, never hidden.

**P5 — Every note is traceable.** Each `NoteEvent` carries `col`, `band`, `value`. The UI can say "this note = 3.2 °C anomaly at lat band 2".

**P6 — Mapping is versioned.** `MAPPING_VERSION` (domain/mapping_version.py). Any change to what the same field sounds like bumps it.

**P7 — Accessibility is a feature, not a phase-end afterthought.** Every UI feature is keyboard operable, screen-reader labelled, respects `prefers-reduced-motion` and light/dark, works at 360 px width.

**P8 — Works offline and reproducibly.** No runtime calls to external services. Tone.js is vendored. Bundled samples live in `data/samples`. No API keys.

**P9 — Boring, testable core.** Signal/maths code is pure functions with unit tests. No ML models for the core path (a colormap lookup is explainable; a CNN is not).

**P10 — Attribution and licensing.** Every bundled image has `credit` + `source_url` in its meta. Audio samples (if any) are team-recorded or CC0, recorded in `data/audio/LICENSES.md`.

## 5. Explicitly OUT of scope

Do not build these. If a task seems to require one, stop and escalate (docs/11 §5).

- Globe / orthographic / polar-stereographic **re-projection**. We support equirectangular maps (and plain rectangular images treated as such). Other projections are flagged "unsupported projection" with the luminance fallback or a manual-extent warning.
- Machine learning / neural nets for colorbar detection or music generation.
- User accounts, databases, cloud storage, payments, analytics trackers.
- Scraping NASA sites at runtime. (Humans download images; see docs/12.)
- Real-time microphone/camera input.
- Mobile native apps.
- Speech synthesis of the soundtrack (the text description is plain text for screen readers; the soundtrack is non-speech).
- A DAW-grade editor. Users choose sample/skin/duration, not individual notes.
- Claiming scientific measurement accuracy. We say "approximate recovery from a colour legend".
- Video/animation processing **before** Phase 9.

## 6. Success definition (what a judge should experience in 3 minutes)

1. Open the app; pick a bundled EIC image from the jukebox gallery.
2. See the recovered legend and quality badge; press Play: hear the sweep with a moving playhead.
3. Press **Audio legend**: hear min→max so the scale is learned.
4. Switch **skin** to Hindustani or Sri Lankan; the information stays the same, the colour changes.
5. Use **Explore mode** with the keyboard; hear and read the local value.
6. Open the **Fidelity panel**: see the measured numbers.
7. Upload a new image, supply min/max, get a soundtrack.

## 7. Audience and language

Team of 4 professionals from Sri Lanka; judges are international and non-specialist. UI copy: plain English, short, no jargon without a tooltip. Code and docs: English.
