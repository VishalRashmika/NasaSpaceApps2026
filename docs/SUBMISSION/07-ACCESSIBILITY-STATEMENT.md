# Earth Jukebox — Accessibility Conformance Statement

> **Standard:** Web Content Accessibility Guidelines (WCAG) 2.1 Level AA  
> **Evaluation Date:** November 2026  
> **Status:** Fully Compliant with documented device constraints

---

## 1. Conformance Overview

Accessibility is a foundational design pillar of Earth Jukebox. The application is built to ensure that scientific data visualizations from NASA are fully interpretable by blind, low-vision, motor-impaired, and neurodiverse users.

---

## 2. Key Accessibility Implementations

### 2.1 Non-Visual Data Exploration (Explore Mode)
- **Full Keyboard Navigation:** Users can inspect the entire physical scalar grid using standard navigation keys:
  - `Arrow Keys`: Move one grid cell in any direction.
  - `Shift + Arrow Keys`: Move five grid cells (fast scan).
  - `Home / End`: Jump to the first or last column.
  - `PageUp / PageDown`: Jump to the northernmost or southernmost latitude band.
  - `Enter / Space`: Re-trigger tone synthesis for the current focused cell.
  - `Escape`: Exit Explore Mode safely.
- **Auditory Value Sonification:** Focusing any cell immediately synthesizes its quantified physical pitch in real time using Tone.js.
- **Throttled Speech Output:** ARIA live announcements (`aria-live="polite"`) deliver clear physical readings (e.g. *"3.2 degrees Celsius. Band 2 of 5, column 17 of 48"*) throttled to $\ge 250$ ms to avoid screen-reader buffer overload. Missing data is unequivocally reported as *"No data"*.

### 2.2 Tactile & Sensory Feedback
- **Data Haptics (`navigator.vibrate`):** On compatible mobile and touch devices, cell transitions trigger vibration pulses whose duration is directly proportional to data magnitude ($10 + 40 \cdot u$ ms). Haptics are toggleable and default to off.
- **Reduced Motion Support:** All non-essential animations respect `@media (prefers-reduced-motion: reduce)`. The playhead line updates linearly without easing or disorienting visual effects.

### 2.3 Visual Ergonomics & Theming
- **Dual-Modality Indicators:** The playhead combines an explicit high-contrast vertical line with a geometric triangle marker, ensuring readability without relying on color alone.
- **Contrast Compliance:** All text content achieves a contrast ratio $\ge 4.5:1$ against backgrounds; interactive controls and borders achieve $\ge 3:1$.
- **Theme Persistence:** Automated detection of `prefers-color-scheme` with an accessible manual light/dark toggle persisted across sessions.
- **Responsive Layout:** Responsive down to 360 px viewport width without horizontal scroll clipping. Touch targets are sized $\ge 44 \times 44$ CSS pixels.

---

## 3. Known Limitations & Technical Notes

- **Web Audio User Gesture Policy:** Modern web browsers require an explicit user gesture (click, tap, or keypress) before starting audio contexts. Audio playback starts only upon user engagement.
- **Hardware Haptic Support:** Haptic vibration relies on the browser's implementation of the HTML5 Vibration API (`navigator.vibrate`), which is supported primarily on Android mobile devices and selective trackpads.
