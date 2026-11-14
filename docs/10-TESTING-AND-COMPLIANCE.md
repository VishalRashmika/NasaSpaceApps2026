# 10 — Testing Strategy, Smoke Tests, Compliance

## 1. Gates

`make check` = `ruff check` + `ruff format --check` + `mypy --strict` + `lint-imports` + architecture tests + `pytest` (unit+integration) + `node --test`. **Green `make check` is part of the definition of done for every feature.** CI runs the same.

Never: weaken/skip/delete a test or guardrail to get green; add `# type: ignore`/`# noqa`/`pytest.skip` without a one-line justification **and** a Decisions-log entry; mock away the thing under test.

## 2. Strategy per layer

| Layer | Test type | Location | Rules |
|---|---|---|---|
| domain | Pure unit + `hypothesis` property tests | `tests/unit/domain/` | No I/O, no files, no network, no matplotlib. Arrays built by hand or with seeded `default_rng`. Property tests for monotonicity, bounds, determinism. |
| application | Unit tests with **fake ports** (in-memory classes implementing the Protocols) | `tests/unit/application/` | Use cases tested without OpenCV/FastAPI. Fakes live in `tests/fakes.py`. |
| infrastructure | Integration tests with real libs on **synthetic images (F-100)** and numeric tolerances from doc 05 §9 / doc 07 | `tests/integration/infrastructure/` | Deterministic seeds; temp dirs via `tmp_path`; no network; ffmpeg/tesseract tests `skipif` binary missing (with reason). |
| presentation | FastAPI `TestClient` against `build_app()` with a temp `Settings` | `tests/integration/api/` | One test per endpoint per documented status code + problem `code`. |
| web core | `node --test` | `web/tests/*.test.mjs` | Only pure `core` modules; no DOM. |
| web ui | Playwright smoke (optional marker `e2e`, `pytest.importorskip("playwright")`) | `tests/e2e/` | Drives the real app; saves screenshots to `data/cache/smoke/`; includes axe-core run (F-078). |
| architecture | pytest + import-linter | `tests/architecture/` + `pyproject.toml` | Never edit without human approval. |
| end-to-end | pipeline test: synthetic image → analyze → sonify → render → decode → check | `tests/integration/test_pipeline.py` | Asserts fidelity numbers (r ≥ 0.95; legend pitch within 20 cents). |
| golden | Score JSON for fixed input | `tests/golden/` | Regenerate only with `MAPPING_VERSION` bump (F-102). |

Conventions: test file mirrors source path (`domain/scale.py` → `tests/unit/domain/test_scale.py`); each test cites its feature in a comment `# F-022 AC1`; arrange-act-assert; ≤ 1 s per unit test; mark slow ones `@pytest.mark.slow`; use `needs_real_samples` marker for human-image tests (they skip cleanly when `data/samples` has no real samples).

Coverage guidance (not a gate): domain ≥ 90 %, application ≥ 85 %, infrastructure ≥ 75 %: `python -m pytest --cov=earth_jukebox --cov-report=term-missing`.

## 3. What "tested" means for the audio

Prove audio correctness numerically: FFT peak within 5 cents (F-040), RMS ratios for pan (F-041), peak ≤ −1 dBFS (F-041), YIN legend check (F-047), byte-identical re-render (F-042), duration (F-042). The human does the listening check.

## 4. Test data

- Synthetic: F-100 (`tests/fixtures.py` helper wrapping it; fixtures `synthetic_viridis`, `synthetic_turbo`, `synthetic_rdbu`, …).
- Real: `data/samples/*` (human). Tests that need them: `pytest.mark.needs_real_samples` + skip when `SampleRepository.list()` is empty.
- Never commit generated WAV/MP3 (gitignored). Golden JSON is committed.

## 5. Manual smoke-test checklist (human or Playwright-assisted)

Run for UI and audio verification.

| ID | Step | Expected |
|---|---|---|
| S-01 | Open `http://127.0.0.1:8000` at 1280 px and 360 px width | No horizontal scroll; header/main landmarks; skip link works (Tab → Enter) |
| S-02 | Toggle OS dark mode | UI recolours; text readable |
| S-03 | Enable OS "reduce motion" | No decorative animation; playhead still moves |
| S-04 | Gallery: arrow-key through samples, Enter selects | Selection announced; analysis starts; quality badge appears |
| S-05 | Press Play | Sound within 500 ms; playhead moves west→east in sync with audio |
| S-06 | Pause/resume/stop/scrub | Audio and playhead stay consistent; no stuck notes |
| S-07 | Audio legend | Rising sweep; readout value+units updates; diverging maps mark the centre |
| S-08 | Upload a new image; draw colorbar via numeric fields only (no mouse) | Form validates; analysis completes |
| S-09 | Switch skin during playback | Track restarts or switches cleanly; same rhythm, different pitch colour |
| S-10 | Explore mode with keyboard only | Arrow keys move; value announced; Esc exits; masked → "No data" |
| S-11 | Explore mode with touch/drag (phone) | Tone follows finger; vibration if enabled |
| S-12 | Screen reader (NVDA/VoiceOver/TalkBack) pass over main flow | All controls labelled; description readable; no announcement spam |
| S-13 | Download WAV, MIDI, JSON | Files open; WAV plays in any player |
| S-14 | Upload invalid file (.txt renamed .png) and a 30 MB image | Clear error messages, app stays usable |
| S-15 | Luminance-fallback image | Persistent "not data-faithful" banner |
| S-16 | Offline: disconnect network, reload | App still works (Tone.js vendored) |

## 6. Architecture-guardrail proof (performed in Phase 0, repeat after any config change)

Procedure: introduce each violation, run `make arch`, confirm failure, revert.

1. `domain` importing `fastapi`; 2. `application` importing `cv2`; 3. `domain` importing `earth_jukebox.infrastructure`; 4. `presentation` importing `earth_jukebox.infrastructure`; 5. `infrastructure` importing `fastapi`; 6. `web/js/core` using `fetch`; 7. a `docs/02` vs `models.py` mismatch.

Recorded results:

Performed 2026-11-10 on a clean venv (Python 3.13). Each violation was appended to the file, the check run, then reverted; the tree was re-verified clean afterwards (`make arch`: 4 contracts kept, 3 tests passed).

| # | Deliberate violation | Result |
|---|---|---|
| 1 | `domain` imports `fastapi` | CAUGHT by import-linter ("Domain and application are framework-free" BROKEN) |
| 2 | `application` imports `cv2` | CAUGHT (same contract BROKEN) |
| 3 | `domain` imports `earth_jukebox.infrastructure` | CAUGHT (layering contract BROKEN) |
| 4 | `presentation` imports `earth_jukebox.infrastructure` | CAUGHT (layering contract BROKEN; siblings are independent) |
| 5 | `infrastructure` imports `fastapi` | CAUGHT ("Infrastructure does not know the web framework" BROKEN) |
| 6 | `web/js/core` calls `fetch` | CAUGHT by `test_frontend_layers.py` ("core uses forbidden global 'fetch'") |
| 7 | `models.py` edited without updating docs/02 | CAUGHT by `test_docs_in_sync.py` |
| 8 | `presentation` imports `scipy` | CAUGHT ("Presentation does no signal/image/audio work" BROKEN) |


## 7. Submission & compliance checklist (for P10)

- [ ] Repo public/accessible as required; README explains run steps and the idea in ≤ 1 screen.
- [ ] `docs/SUBMISSION/` complete (F-105): summary, methodology, demo script, credits, AI-use disclosure.
- [ ] Every bundled image has `credit` and `source_url`; NASA credit lines copied verbatim from sources; no image without a verified usage statement.
- [ ] Any bundled audio samples listed in `data/audio/LICENSES.md`.
- [ ] Third-party licences: Tone.js (MIT) notice kept in `web/vendor/`; Python deps listed.
- [ ] A short demo video recorded by the humans (screen capture of the S-04…S-10 flow with audio).
- [ ] EVAL-REPORT.md regenerated at the final commit; numbers quoted in the summary match it.
- [ ] Accessibility statement: what is supported, known gaps.
- [ ] **[HUMAN TO VERIFY]** Space Apps 2026 submission requirements, deadlines, form fields.
- [ ] **[HUMAN TO VERIFY]** Space Apps policy on disclosing AI-tool usage; the disclosure text reflects that this project was built with AI coding agents.
- [ ] **[HUMAN TO VERIFY]** NASA media usage guidelines for the specific images.
- [ ] Fresh-clone test: new venv → `make install` → `make check` → `make run` works.
