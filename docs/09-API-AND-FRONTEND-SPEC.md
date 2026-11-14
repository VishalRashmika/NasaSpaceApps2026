# 09 — HTTP API & Frontend Spec (Modules API, WEB)

## 1. API conventions

- Base path `/api`. JSON in/out except uploads (multipart) and audio/binary downloads.
- Pydantic models live only in `presentation/api/schemas.py`; routes in `presentation/api/routes_*.py`; one router per topic; all mounted in `create_app`.
- Errors: `application/problem+json`: `{"type":"about:blank","title":"…","status":422,"detail":"…","code":"invalid_legend","request_id":"…"}`.
  Mapping: `invalid_image`→422 (413 for size, 415 for type), `invalid_legend`→422, `recovery_failed`→422, `not_found`→404, unexpected→500 with generic detail (log the traceback server-side).
- Header `X-Request-Id` on every response (uuid4 generated at the edge; presentation may use uuid/time — domain may not).
- IDs: `analysis_id = sha256(image_hash + canonical(legend, boxes, preset, mapping_version))[:16]` hex.

## 2. Endpoints

| Method & path | Feature | Request | Response |
|---|---|---|---|
| `GET /api/health` | F-060 | — | `{status, version, mapping_version}` |
| `GET /api/mapping` | F-064 | — | mapping manifest (doc 06 §2) |
| `GET /api/skins` | F-067 | — | `[{id,name,provisional,scale_cents,description}]` |
| `GET /api/colormaps` | F-003 | — | `[{name,kind}]` |
| `GET /api/samples` | F-065 | — | `[{id,title,category,thumb_url,credit}]` |
| `GET /api/samples/{id}` | F-065 | — | sample meta (docs/12 §3) |
| `GET /api/samples/{id}/image` | F-065 | — | image bytes |
| `POST /api/samples/{id}/analyze` | F-065 | `{}` | same as analyze response |
| `POST /api/detect-colorbar` | F-004 | multipart `image` | `{candidates:[{box,orientation,score}]}` |
| `POST /api/analyze` | F-061 | multipart: `image`, `legend` (JSON), `colorbar_box?` (JSON), `map_box?` (JSON), `preset?` (str), `extent?` (JSON) | `{analysis_id, quality, warnings[], field_preview_png (data URL), grid:{rows,cols,min,max}, image:{width,height}}` |
| `POST /api/sonify` | F-062 | `{analysis_id, skin="neutral", n_cols=48}` | `{score, description, fidelity}` |
| `GET /api/render/{analysis_id}.wav?skin=&n_cols=` | F-063 | — | `audio/wav` |
| `GET /api/render/{analysis_id}.mid?...` | F-063/043 | — | `audio/midi` |
| `GET /api/render/{analysis_id}.json?...` | F-063 | — | Score JSON |
| `GET /api/render/{analysis_id}.mp3?...` | F-044 | — | `audio/mpeg` or 501 problem |
| `GET /api/legend-sound/{analysis_id}.wav?skin=` | F-063/034 | — | `audio/wav` |

Limits: upload ≤ 20 MB (413), images ≤ 8000 px side, `n_cols` ∈ [16, 128], band count fixed at 5 in v1.

Docs: FastAPI's automatic `/docs` must render every endpoint with schema examples.

## 3. Frontend structure (no bundler, ES modules)

```
web/index.html  css/app.css  js/main.js
js/core/     playhead.js  schedule.js  explore.js  format.js  legend.js   (PURE; node-tested)
js/audio/    engine.js (Tone.js adapter), instruments.js, legend-player.js
js/api/      client.js
js/ui/       shell.js gallery.js upload.js box-editor.js player.js explore-ui.js a11y.js panels.js
tests/       *.test.mjs  (node --test)
```
Dependency rule in docs/01 §3 (enforced by test). `Tone` global is touched **only** in `js/audio/**`. `fetch` only in `js/api/**`.

### Required pure `core` functions (signatures are a contract for tests)

```js
// playhead.js
export function playheadX(tBeat, totalBeats, mapLeft, mapWidth)         // clamps
export function beatAtSeconds(seconds, bpm)
// schedule.js
export function scoreToTriggers(score)                                  // doc 07 §7
// explore.js
export function cursorToCell(xNorm, yNorm, nCols, nBands)               // -> {col, band}
export function moveCursor(cell, key, shift, nCols, nBands)             // arrows/Home/End
export function cellToUtterance(cell, grid, legend)                     // -> string; "no data" for null
// format.js
export function formatValue(v, units)                                   // sensible digits
// legend.js
export function validateLegendForm(values)                              // -> {ok, errors:{field:msg}}
```

## 4. UI specification

**Layout (≥ 900 px):** left = map canvas (image with overlays) + player bar; right = tabs: *Listen* | *Legend* | *How to listen* | *Fidelity*. **< 900 px:** single column, same order. Nothing overflows horizontally at 360 px.

**States (each must be implemented and tested manually):** empty (no sample, no upload) → loading (analyze in progress, `aria-busy`) → ready (analysis exists) → playing → error (problem.detail shown in a `role="alert"` region with a retry action).

**Gallery:** radio-group semantics; arrow keys move, Enter/Space selects; each card has `alt` text = sample description.

**Upload & legend form:** drag-drop area is also a `<button>`/file input. After upload show the image on a canvas; boxes drawn by dragging, **also editable via four numeric fields each**; "Suggest colorbar" button (F-004). Fields: preset (select; "None – use colorbar box"), vmin, vmax, units, label, scale (linear/log), kind, category, orientation, "low value is at the start" checkbox. Inline errors via `aria-describedby`; submit disabled until valid.

**Player:** Play/Pause (Space), Stop, scrubber (`<input type=range>`), skin select, "Audio legend", "Explore mode" toggle, download menu. Time readout. `aria-live="off"` on rapidly changing readouts; polite announcements only on state changes and (throttled ≥ 250 ms) Explore moves.

**Explore mode keyboard map:** Arrow keys move one grid cell; Shift+Arrow five; Home/End = first/last column; PageUp/PageDown = band up/down; Enter/Space = play tone for current cell; Esc = leave mode. Pointer/touch drag plays continuously (tone retriggers on cell change). Announcement example: *"3.2 degrees Celsius. Band 2 of 5, column 17 of 48."* Masked: *"No data."*

**Haptics (F-081):** toggle default off; `navigator.vibrate(10 + 40·u ms)` on cell change.

**Reduced motion:** disable decorative transitions; playhead movement is informational and stays, drawn without easing.

**Theming:** CSS custom properties; light/dark via `prefers-color-scheme` plus a manual toggle persisted in `localStorage` guarded by try/catch. Contrast ≥ 4.5:1 for text, ≥ 3:1 for UI components. Focus rings ≥ 2 px. Tap targets ≥ 44 px.

**Copy:** sentence case, short. Always show units. Never show "NaN". Luminance fallback shows a persistent banner: "Approximate: no colour legend was used, so this sound is not data-faithful."

**Overlay drawing:** the recovered-field preview can be toggled over the map with an opacity slider; the playhead is a 3 px high-contrast line plus a triangle marker (shape + colour, never colour alone).

## 5. How to listen (F-080)

Rendered from `GET /api/mapping`: a short paragraph, then the table in doc 06 §2 in plain language, plus the current skin's scale. Includes a "Play audio legend" button.

## 6. Performance & robustness

Debounce analyze requests; abort in-flight requests on new selection (`AbortController`); disable controls while busy; never block the main thread > 50 ms with Score processing (the Score is ≤ ~3000 notes).
