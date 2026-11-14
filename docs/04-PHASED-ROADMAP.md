# 04 — Phased Roadmap

> Architecture and development roadmap tracking milestone deliverables from scaffolding through submission.

## 1. Phase overview

| Phase | Name | Features | Exit demo | Needs human inputs? |
|---|---|---|---|---|
| **P0** | Scaffold + guardrails | F-060, F-104, F-106 | `make check` green | no — **DONE** |
| **P1** | Data recovery core (manual boxes / presets) | F-100, F-101, F-001, F-002, F-003, F-005, F-007, F-006, F-008, F-009, F-010, F-011, F-013 | `python -m scripts.demo_recover` | no (synthetic) |
| **P2** | Auto-detection & real-image hardening | F-004, F-012 | `python -m scripts.demo_detect` | **yes** — real samples (docs/12) |
| **P3** | Sonification engine → Score | F-050, F-051, F-020, F-021, F-022, F-023, F-024, F-025, F-026, F-027, F-028, F-029, F-030, F-031, F-032, F-033, F-034, F-035, F-036, F-102 | `python -m scripts.demo_sonify` | no |
| **P4** | Audio rendering & export | F-040, F-041, F-042, F-043, F-045, F-047 | `python -m scripts.demo_render` → WAV + MIDI | no |
| **P5** | HTTP API | F-061, F-062, F-063, F-064, F-065, F-066, F-067 | curl script + OpenAPI at `/docs` | optional (real samples for F-065) |
| **P6** | Web MVP | F-070, F-071, F-072, F-073, F-074, F-075, F-076, F-080 | Browser walkthrough S-01..S-09 | yes (samples for gallery) |
| **P7** | Accessibility, Explore mode, fidelity | F-077, F-078, F-079, F-081, F-103 | Blind-use walkthrough + `EVAL-REPORT.md` | yes |
| **P8** | Cultural skins | F-052, F-053, F-054, F-055 | Same image, 3 skins A/B | **yes — musician validation** (docs/08 §5) |
| **P9** | Time mode (stretch) | F-090, F-091, F-092, F-093 | Animated sample plays as phrases | yes (a GIF/MP4) |
| **P10** | Submission polish | F-105, F-044, F-046 | Final regression + submission pack | yes |

**Cut line for a minimum viable submission: P0–P7.** P8 is the biggest creativity differentiator; **the human-side musical work for P8 should start in parallel on day 1** (docs/08 §5, docs/12 §6). P9 and P10's optional features are stretch.

Phases are strictly sequential (P(N+1) never starts before P(N)'s exit demo is recorded), **except** that P4 may not begin before P3's `Score` JSON schema (docs/07 §2) is satisfied by the P3 output.

## 2. Phase detail

### P1 — Data recovery core
**Goal:** given an image + legend (+ boxes or preset), produce a `ScalarField` with a quality report. Prove it on synthetic maps with known truth.
**Deliverables beyond the features:**
- `scripts/demo_recover.py`: generates 3 synthetic maps (viridis, turbo, RdBu_r), recovers each, prints RMSE as % of range, saves side-by-side PNG (`data/cache/demo_recover_*.png`: original | recovered | error).
- `tests/unit` + `tests/integration` covering every AC.
**Exit demo:** run the script; all three RMSE values are under the doc 05 §9 thresholds; paste the table into the session log.
**Do not:** build sonification, API routes, or UI.

### P2 — Auto-detection & real-image hardening
**Prereq:** the human has put ≥ 6 real samples in `data/samples/` (docs/12). If fewer exist, the agent implements everything against synthetic data, marks real-sample checks as *pending human input* in PROJECT-STATE, and stops at the phase's end without inventing images.
**Exit demo:** `scripts/demo_detect.py` prints, per sample, detected box vs. ground-truth box IoU and the inversion RMSE (when a sample has `truth` data) or the confidence badge.
**Tuning rule:** thresholds in doc 05 may be tuned **only** inside the documented ranges; log every change in the Decisions log with the before/after numbers.

### P3 — Sonification engine → Score
**Goal:** deterministic `ScalarField → Score` per doc 06, with the neutral skin, legend sweep, round-trip fidelity and text description.
**Exit demo:** `scripts/demo_sonify.py` on 3 synthetic fields prints: bpm, #notes, accents, silence share, description text, round-trip r, and writes `data/cache/*.score.json`.
**Do not:** write audio samples/WAV; no synth code (that is P4).

### P4 — Audio rendering & export
**Goal:** Score → WAV/MIDI offline, deterministic.
**Exit demo:** `scripts/demo_render.py` writes `data/cache/demo_<name>.wav/.mid` for 3 synthetic fields plus `legend_<name>.wav`; prints the YIN legend check (all notes within 20 cents, r ≥ 0.98). The human listens (listening notes recorded by the human in PROJECT-STATE, not by the agent).

### P5 — HTTP API
**Exit demo:** `scripts/demo_api.sh` (curl) walks: health → analyze (synthetic PNG) → sonify → download WAV; FastAPI `/docs` lists all endpoints with schemas.

### P6 — Web MVP
**Exit demo:** the browser walkthrough: gallery → select → analyze → Play with moving playhead → Audio legend → upload own image with legend form → download WAV. Each step maps to a smoke-test ID in docs/10 §5. The agent runs the app and drives it with Playwright (screenshots saved under `data/cache/smoke/`) to prove S-01…S-09 pass; the human then does the listening check.

### P7 — Accessibility, Explore mode, fidelity
**Exit demo:** keyboard-only + screen-reader-label walkthrough (script in docs/10 §5); `docs/EVAL-REPORT.md` generated; axe-core 0 serious/critical.

### P8 — Cultural skins
**Prereq:** the validated scale tables in docs/08 §3–§4 are *filled in by the human musician* (cells marked `TO BE VALIDATED`). If they are not, the agent implements the machinery with the **provisional** values already in docs/08, flags the skin `provisional=True` in its name in the UI ("Hindustani (provisional)"), and logs an assumption.
**Exit demo:** the same synthetic field rendered in neutral / hindustani / sri_lankan; the invariance test F-054 passes; the human does an A/B listening.

### P9 — Time mode (stretch). **P10 — Submission polish.** As catalogued.

## 3. Engineering & Development Rules

1. Each milestone feature must satisfy its full acceptance criteria and pass the automated test suite.
2. Architecture layering is strictly enforced: `presentation` and `infrastructure` depend on `application`, which depends on `domain`.
3. New features are assigned permanent IDs in `docs/03-FEATURE-CATALOG.md`.
4. Domain model and ports are mirrored in `docs/02-DOMAIN-MODEL.md` and guarded by architecture tests.
