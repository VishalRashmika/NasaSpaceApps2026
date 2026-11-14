# Earth Jukebox

> **Hear the data, not the pixels.** An authentic NASA Earth & Space Information Jukebox.

We invert the **colorbar** of NASA EIC, SVS, Chandra, and Webb imagery to recover physical values (temperatures, anomalies, wind speeds, flux), then sonify that data deterministically into pitch, stereo panorama, rhythmic density, and cultural musical systems with microtonal accuracy and full screen-reader accessibility.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com)
[![Architecture](https://img.shields.io/badge/architecture-Clean%20%2F%20Hexagonal-555555.svg)](docs/01-ARCHITECTURE.md)
[![Accessibility](https://img.shields.io/badge/accessibility-WCAG%202.1%20AA-success.svg)](docs/SUBMISSION/07-ACCESSIBILITY-STATEMENT.md)

## Quick Start

```bash
python3.11 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
make install        # Editable install + development tools
make check          # Lint, strict types, architecture contracts, and full test suite
make run            # Launch web studio at http://127.0.0.1:8000 (API at /docs)
```

Requires Python 3.11+ and Node 20+ (for `make web-test` only). Pure vanilla ES modules—no frontend build step or bundler.

## Key Capabilities

- **Physical Data Recovery:** CIE L\*a\*b\* k-d tree color matching and luminance fallback with non-data masking and outer padding suppression.
- **Deterministic Sonification:** Longitude → time, latitude → voice/pan, spatial gradient → rhythm density, variance → tempo, rests for masked areas.
- **Cultural Musical Skins:** Western Neutral, North Indian Classical (Hindustani ragas), and Traditional Sri Lankan (*Ravana* / *Vannam*) with strict mathematical information invariance.
- **Sensory Accessibility (WCAG 2.1 AA/AAA):** 2D tactile Explore mode, Web Speech coordinate readouts, Web Haptics intensity pulses, and screen-reader polite announcements.
- **Multi-Format Export:** Studio-grade WAV (44.1 kHz 16-bit PCM), Type-1 Standard MIDI with pitch bends, and Score JSON.

## Documentation & NASA Space Apps Submission Pack

All official submission materials are cataloged under **[`docs/SUBMISSION/`](docs/SUBMISSION/)**:
1. [`01-PROJECT-SUMMARY.md`](docs/SUBMISSION/01-PROJECT-SUMMARY.md) — Executive summary, vision, and core innovations.
2. [`02-METHODOLOGY.md`](docs/SUBMISSION/02-METHODOLOGY.md) — Complete mathematical inversion and sonification methodology.
3. [`03-AI-TOOL-DISCLOSURE.md`](docs/SUBMISSION/03-AI-TOOL-DISCLOSURE.md) — Transparent disclosure of development tools.
4. [`04-DATA-CREDITS.md`](docs/SUBMISSION/04-DATA-CREDITS.md) — NASA dataset sources, credits, and citations.
5. [`05-DEMO-SCRIPT.md`](docs/SUBMISSION/05-DEMO-SCRIPT.md) · [`06-SCREENSHOTS-AND-ASSETS.md`](docs/SUBMISSION/06-SCREENSHOTS-AND-ASSETS.md) · [`07-ACCESSIBILITY-STATEMENT.md`](docs/SUBMISSION/07-ACCESSIBILITY-STATEMENT.md)
6. Technical Specs: [`docs/01-ARCHITECTURE.md`](docs/01-ARCHITECTURE.md) · [`docs/02-DOMAIN-MODEL.md`](docs/02-DOMAIN-MODEL.md) · [`docs/03-FEATURE-CATALOG.md`](docs/03-FEATURE-CATALOG.md) · [`docs/EVAL-REPORT.md`](docs/EVAL-REPORT.md)

## Credits & Attribution

Scientific imagery courtesy of NASA Earth Information Center (EIC), Scientific Visualization Studio (SVS), and Chandra/STScI. Detailed credits in [`docs/SUBMISSION/04-DATA-CREDITS.md`](docs/SUBMISSION/04-DATA-CREDITS.md).
