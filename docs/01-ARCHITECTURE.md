# 01 — Architecture

> Stable document. Section 2 contains **locked technical decisions**. The human must sanity-check them BEFORE Phase 1 starts. Agents never reopen them on their own (docs/11 §5).

## 1. Stack

| Concern | Choice |
|---|---|
| Language (backend) | Python ≥ 3.11 (developed on 3.13) |
| Web framework | FastAPI + uvicorn |
| Numerics | NumPy; SciPy (`cKDTree`, filters) in infrastructure only |
| Image | OpenCV (headless) + Pillow in infrastructure only |
| Colormap presets | matplotlib (`matplotlib.colormaps`) in infrastructure only |
| Audio synthesis | Our own NumPy synth (no system dependency) |
| WAV | stdlib `wave` |
| MIDI export | `mido` |
| Optional | `ffmpeg` binary (MP3), `pytesseract` + Tesseract (OCR assist), FluidSynth (stretch) |
| Frontend | Vanilla ES modules, **no bundler, no framework**, Tone.js vendored (UMD global) |
| Tests | pytest (+hypothesis), `node --test` for pure JS |
| Quality gates | ruff (lint+format), mypy `--strict`, import-linter, custom architecture tests |

## 2. LOCKED DECISIONS — human: please sanity-check these

| ID | Decision | Why | Alternative rejected |
|---|---|---|---|
| **D-01** | **Sonify the recovered scalar field (colorbar inversion), not raw pixels.** | Gives scientific meaning + a measurable fidelity story. | Pixel/hue→pitch (what vOICe/Chandra-style mappers do). |
| **D-02** | **Three recovery modes with a strict fallback order:** (1) colorbar extracted from the image, (2) named colormap preset + user min/max, (3) luminance fallback flagged "not data-faithful". Auto-detection (F-004) is an *assist*; manual boxes and presets are always available. | Auto-detecting colorbars on arbitrary EIC art will fail sometimes; the product must never dead-end. | Auto-only detection. |
| **D-03** | **Equirectangular maps only.** Globes/polar views are out of scope; we warn and fall back. Time axis = longitude sweep W→E, voice = latitude band. | Re-projection is a research project. Many EIC/SVS flat maps are equirectangular. | Globe unwrapping. |
| **D-04** | **The `Score` is the single intermediate artifact.** Pure data (`domain.models.Score`), JSON-serialisable. Everything audible derives from it: server WAV, MIDI, browser Tone.js. | Inspectable, testable, reproducible; decouples mapping from rendering. | Rendering audio directly from the field. |
| **D-05** | **Two renderers, one contract.** Server: our NumPy synth → WAV (deterministic, downloadable, used for tests). Browser: Tone.js plays the same Score JSON live (real-time, playhead, Explore mode). Parity is at **Score semantics** (pitch/time/velocity/pan/instrument id), NOT sample-identical audio. | Real-time requirement of the challenge + deterministic offline render. | FluidSynth/SoundFonts as the primary renderer: system dependency, soundfont licensing, no microtones — kept only as a stretch adapter (F-046). |
| **D-06** | **Pitch is a pure function of value** (P2). Latitude bands change timbre/pan only. | Keeps the audio legend valid everywhere. | Register per band (muddier, breaks legend). |
| **D-07** | **Clean Architecture, 4 layers + composition root** (§3), enforced by import-linter. | Parallel work by 4 people and by agents without tangling. | Flat package. |
| **D-08** | **Rule-based music, not ML.** Ragas are implemented as scale + phrase templates + glides, validated by a musician. | Explainable, deterministic, fits the time-box. | Generative models. |
| **D-09** | **No frontend build step.** | Zero tooling risk for the agent and the demo machine. | React/Vite. |
| **D-10** | **Fidelity is measured at three levels:** inversion error on synthetic maps, Score round-trip correlation, audio pitch-track on the legend sweep. | Rigour that most teams skip; achievable without polyphonic transcription. | Transcribing arbitrary polyphonic audio. |

## 3. Layers and the dependency rule

```
presentation  ┐ (siblings: neither imports the other)
infrastructure┘
      │
      ▼
 application   (use cases + ports)
      │
      ▼
   domain      (entities + pure rules)
```

**Dependency rule (mechanically enforced by `lint-imports` in `make arch`):**

1. `domain` imports only stdlib + `numpy`. It imports nothing from `application`, `infrastructure`, `presentation`.
2. `application` imports `domain`, stdlib, `numpy`. **Never** `cv2`, `scipy`, `PIL`, `matplotlib`, `mido`, `pytesseract`, `fastapi`, `starlette`, `pydantic`.
3. `infrastructure` implements the **ports** in `application/ports.py`. May use `cv2`, `scipy`, `PIL`, `matplotlib`, `mido`. **Never** `fastapi`/`starlette`. Never imports `presentation`.
4. `presentation` (FastAPI routes, request/response schemas) calls use cases via `application.services.Services`. **Never** imports `infrastructure`, `cv2`, `scipy`, `PIL`, `mido`, `matplotlib`.
5. `earth_jukebox/bootstrap.py` is the **composition root** — the only module allowed to import all layers. It constructs adapters and injects them into use cases.
6. Where do pure algorithms live? Mapping rules, scale quantisation, resampling math → `domain` (numpy). Orchestration (decode → recover → sonify → render) → `application/use_cases`. Anything touching OpenCV/SciPy/files/synth DSP → `infrastructure`.

   *Judgement rule:* if it can be tested with plain arrays and no I/O library, it is domain. If it needs a library beyond numpy, it is infrastructure behind a port.
7. Pydantic is allowed **only** in `presentation` for request/response schemas. Domain objects are dataclasses.

### Frontend layers (enforced by `tests/architecture/test_frontend_layers.py`)

```
web/js/main.js        composition root
web/js/ui/            DOM, canvas, keyboard, ARIA      -> may import core, audio, api
web/js/audio/         Tone.js adapter (only place Tone is used) -> core
web/js/api/           fetch client (only place fetch is used)   -> core
web/js/core/          pure logic, NO DOM/network/audio globals  -> nothing
```

## 4. Folder structure

```
earth-jukebox/
  docs/                         # specifications and architecture documents
  src/earth_jukebox/
    domain/                     # models.py errors.py mapping_version.py (+ pure rules per phase)
    application/                # ports.py services.py settings.py use_cases/
    infrastructure/{vision,audio,storage,colormaps}/
    presentation/api/
    bootstrap.py __main__.py
  tests/{unit,integration,architecture}/
  web/{index.html,css/,js/{core,audio,api,ui},tests/,vendor/}
  data/samples/<id>/{image.*,meta.json}   # human-supplied (docs/12)
  data/cache/                   # render cache (gitignored)
  scripts/ tools/               # dev scripts, bbox picker for humans
```

New modules go in the layer where they belong; mirror the path in `tests/unit/...`.

## 5. Primary data flow

```
bytes ──ImageDecoder──▶ DecodedImage
   │            + LegendSpec (+ boxes | preset)
   └──FieldRecoverer──▶ ScalarField (NaN = masked) + RecoveryQuality
         └─ sonify (domain rules; skin) ──▶ Score
               ├─ AudioRenderer ──▶ WAV
               ├─ MidiExporter  ──▶ MIDI
               └─ JSON ─────────▶ browser Tone.js + playhead + Explore mode
```

## 6. Error handling

Domain raises `JukeboxError` subclasses (domain/errors.py). Presentation converts them to RFC 7807-style JSON `{type, title, status, detail, code}`. No raw tracebacks to clients. Upload limits: 20 MB, 8000 px per side; only PNG/JPEG/WebP/GIF accepted, verified by decoding, not by extension.

## 7. Performance budget (guidance, not tests)

Analyze ≤ 3 s and sonify ≤ 1 s for a 2048-px image on a laptop; WAV render of a 40 s track ≤ 5 s. Working images are downscaled to ≤ 2048 px max side (nearest/area interpolation as specified in doc 05).

## 8. Security basics

Treat uploads as hostile: size cap, decode in-process with Pillow `Image.MAX_IMAGE_PIXELS` set, no path joins from user input (sample ids validated against `^[a-z0-9][a-z0-9_-]{0,63}$`), no shell-outs with user data (ffmpeg only with fixed args on our own temp files), CORS off by default (same-origin app).
