# Earth Jukebox — AI Tool Usage & Governance Disclosure

> NASA Space Apps Challenge 2026  
> **Prepared for:** Space Apps Evaluation Committee & Open Science Audit  
> **Guidelines Reference:** NASA Space Apps AI Usage Policy & Project Checklist H-9

---

## 1. Disclosure Statement

Earth Jukebox was engineered through human-AI pair programming utilizing **Google DeepMind's Antigravity AI coding assistant powered by Gemini models**. Every line of code, specification, and test was developed under strict human-architected constraints, continuous mechanical verification, and domain review.

---

## 2. Methodology & Architectural Guardrails

To prevent hallucination, architectural drift, or unverified outputs, the engineering process followed an automated governance framework:

1. **Clean Architecture Enforcement:**
   - Layer boundaries (`presentation`, `infrastructure`, `application`, `domain`) are mechanically enforced by `import-linter` via `make arch`.
   - Domain logic and mathematical transformations are isolated from web frameworks, graphics libraries, or external dependencies.

2. **Test-Driven Development (TDD):**
   - For every feature ID (`F-001` through `F-106`), test cases were derived strictly from the specification's acceptance criteria before implementation.
   - Over 185 unit and integration tests, alongside 40 frontend headless browser tests (`node --test`), gate all merges.

3. **Deterministic Verification:**
   - Absolute determinism is enforced across the entire data recovery and audio pipeline.
   - Given identical input bytes, the system produces byte-identical Score JSON representations and WAV audio across repeated runs.

4. **Continuous Synchronization:**
   - Automated tests (`test_docs_in_sync.py`) verify that the executable code in `models.py` and `ports.py` remains bit-for-bit identical to the specification in `docs/02-DOMAIN-MODEL.md`.

---

## 3. Division of Responsibilities

| Responsibility Area | Human Role | AI Coding Assistant Role |
|---|---|---|
| **Problem Definition** | Conceptualized colorbar inversion vs. raw pixel sonification; defined challenge goals. | Suggested architectural decomposition and pipeline structure. |
| **Scientific Calibration** | Selected color space (CIE $L^*a^*b^*$), error metrics (RMSE % of range, $\Delta E$), and verification thresholds. | Implemented k-d tree spatial indexing and color difference algorithms. |
| **Musicology & Cultural Design** | Sourced musical scales, raga structures, and traditional Sri Lankan rhythmic motifs. | Translated scale tables into cent arrays, microtonal tuning, and MIDI generator routines. |
| **Accessibility Specification** | Formulated WCAG 2.1 AA requirements, keyboard interaction maps, and screen-reader copy. | Built ARIA live regions, focus management, and DOM landmark structures. |
| **Quality Assurance & Audit** | Inspected audio recordings, audited code diffs, performed acoustic listening tests, and verified NASA media rights. | Authored unit tests, automated CI workflows, and refactored code for strict type compliance (`mypy --strict`). |

---

## 4. Software & AI Tool Inventory

- **Coding Assistant:** Google DeepMind Antigravity CLI / Gemini 3.8 Flash & Pro.
- **Languages:** Python 3.11+, Vanilla JavaScript (ES2022).
- **Libraries:** NumPy, SciPy, OpenCV (headless), Pillow, Matplotlib, Mido, FastAPI, Tone.js.
- **Verification Gates:** Ruff, Mypy (`--strict`), Import-Linter, Pytest, Node Test Runner.
- **External Network Access:** None during runtime or testing. Zero API key requirements.
