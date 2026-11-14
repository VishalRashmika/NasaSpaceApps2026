import { test } from "node:test";
import assert from "node:assert/strict";
import {
  cursorToCell,
  moveCursor,
  cellToUtterance,
  categoryToFamily,
  cellPan,
  normalizeValue,
  quantizePitch,
  resolveCellAudio,
  hapticDuration,
} from "../js/core/explore.js";

test("cursorToCell maps normalized coordinates to grid cells", () => {
  // Corners
  assert.deepEqual(cursorToCell(0.0, 0.0, 48, 5), { col: 0, band: 0 });
  assert.deepEqual(cursorToCell(0.999, 0.999, 48, 5), { col: 47, band: 4 });
  // Center
  assert.deepEqual(cursorToCell(0.5, 0.5, 48, 5), { col: 24, band: 2 });
  // Clamping
  assert.deepEqual(cursorToCell(1.5, -0.2, 48, 5), { col: 47, band: 0 });
  // Degenerate bounds
  assert.deepEqual(cursorToCell(0.5, 0.5, 0, 0), { col: 0, band: 0 });
});

test("moveCursor navigates grid with arrow keys and modifiers (F-077 AC2)", () => {
  const start = { col: 10, band: 2 };

  // Single steps
  assert.deepEqual(moveCursor(start, "ArrowRight", false, 48, 5), { col: 11, band: 2 });
  assert.deepEqual(moveCursor(start, "ArrowLeft", false, 48, 5), { col: 9, band: 2 });
  assert.deepEqual(moveCursor(start, "ArrowDown", false, 48, 5), { col: 10, band: 3 });
  assert.deepEqual(moveCursor(start, "ArrowUp", false, 48, 5), { col: 10, band: 1 });

  // Shift = 5 steps
  assert.deepEqual(moveCursor(start, "ArrowRight", true, 48, 5), { col: 15, band: 2 });
  assert.deepEqual(moveCursor(start, "ArrowLeft", true, 48, 5), { col: 5, band: 2 });

  // Home and End
  assert.deepEqual(moveCursor(start, "Home", false, 48, 5), { col: 0, band: 2 });
  assert.deepEqual(moveCursor(start, "End", false, 48, 5), { col: 47, band: 2 });

  // PageUp and PageDown
  assert.deepEqual(moveCursor(start, "PageUp", false, 48, 5), { col: 10, band: 1 });
  assert.deepEqual(moveCursor(start, "PageDown", false, 48, 5), { col: 10, band: 3 });

  // Clamping bounds
  assert.deepEqual(moveCursor({ col: 0, band: 0 }, "ArrowLeft", false, 48, 5), { col: 0, band: 0 });
  assert.deepEqual(moveCursor({ col: 47, band: 4 }, "ArrowRight", false, 48, 5), { col: 47, band: 4 });
  assert.deepEqual(moveCursor({ col: 0, band: 0 }, "ArrowUp", false, 48, 5), { col: 0, band: 0 });
  assert.deepEqual(moveCursor({ col: 47, band: 4 }, "ArrowDown", false, 48, 5), { col: 47, band: 4 });
});

test("arrow-key navigation covers the whole grid (F-077 AC2)", () => {
  const nCols = 10;
  const nBands = 5;
  const visited = new Set();

  let cur = { col: 0, band: 0 };
  visited.add(`${cur.col},${cur.band}`);

  // Walk through entire grid line-by-line using arrow keys
  for (let b = 0; b < nBands; b++) {
    for (let c = 0; c < nCols - 1; c++) {
      const dir = (b % 2 === 0) ? "ArrowRight" : "ArrowLeft";
      cur = moveCursor(cur, dir, false, nCols, nBands);
      visited.add(`${cur.col},${cur.band}`);
    }
    if (b < nBands - 1) {
      cur = moveCursor(cur, "ArrowDown", false, nCols, nBands);
      visited.add(`${cur.col},${cur.band}`);
    }
  }

  assert.equal(visited.size, nCols * nBands, "Arrow-key movement must cover every single cell in grid");
});

test("cellToUtterance creates speech announcement and handles masked cells (F-077 AC1, AC3)", () => {
  const grid = [
    [null, 1.2],
    [3.2, null],
  ];
  const legend = { units: "°C" };

  // Masked cell (F-077 AC3)
  assert.equal(cellToUtterance({ col: 0, band: 0 }, grid, legend), "No data.");
  assert.equal(cellToUtterance(null, grid, legend), "No data.");
  assert.equal(cellToUtterance({ col: 1, band: 1 }, grid, legend), "No data.");

  // Valid cell
  const utt = cellToUtterance({ col: 0, band: 1 }, grid, legend);
  assert.match(utt, /3\.2/);
  assert.match(utt, /degrees Celsius/);
  assert.match(utt, /Band 2 of 2, column 1 of 2/);
});

test("categoryToFamily maps variable categories to instrument families (F-077)", () => {
  assert.equal(categoryToFamily("temperature"), "strings");
  assert.equal(categoryToFamily("precipitation"), "pluck");
  assert.equal(categoryToFamily("vegetation"), "flute");
  assert.equal(categoryToFamily("ice"), "bell");
  assert.equal(categoryToFamily("aerosol"), "texture");
  assert.equal(categoryToFamily("ocean"), "pad");
  assert.equal(categoryToFamily("unknown_cat"), "pad");
});

test("cellPan computes stereo panning across columns (F-077)", () => {
  assert.equal(cellPan(0, 48), -1.0); // West
  assert.equal(cellPan(47, 48), 1.0); // East
  assert.equal(cellPan(0, 1), 0.0);   // Monophonic fallback
  const midPan = cellPan(24, 49);     // Exact center
  assert.equal(midPan, 0.0);
});

test("normalizeValue scales linear, diverging, and log legends (F-077)", () => {
  // Linear
  const linLeg = { vmin: 0, vmax: 100, scale: "linear", kind: "sequential" };
  assert.equal(normalizeValue(0, linLeg), 0.0);
  assert.equal(normalizeValue(50, linLeg), 0.5);
  assert.equal(normalizeValue(100, linLeg), 1.0);
  assert.ok(Number.isNaN(normalizeValue(null, linLeg)));

  // Diverging
  const divLeg = { vmin: -10, vmax: 10, center: 0, kind: "diverging" };
  assert.equal(normalizeValue(-10, divLeg), 0.0);
  assert.equal(normalizeValue(0, divLeg), 0.5);
  assert.equal(normalizeValue(10, divLeg), 1.0);

  // Log
  const logLeg = { vmin: 1, vmax: 100, scale: "log" };
  assert.equal(normalizeValue(1, logLeg), 0.0);
  assert.equal(normalizeValue(10, logLeg), 0.5);
  assert.equal(normalizeValue(100, logLeg), 1.0);
});

test("quantizePitch maps u to skin pitches (F-077, F-052, F-053)", () => {
  const neutralSkin = {
    tonic_midi: 48.0,
    scale_cents: [0, 200, 400, 700, 900],
    n_octaves: 2,
  };
  // u=0 -> tonic (48)
  assert.equal(quantizePitch(0.0, neutralSkin), 48.0);
  // u=1 -> tonic + 24 (72)
  assert.equal(quantizePitch(1.0, neutralSkin), 72.0);
  // u=0.5 -> middle tonic (60)
  assert.equal(quantizePitch(0.5, neutralSkin), 60.0);
  // masked
  assert.ok(Number.isNaN(quantizePitch(NaN, neutralSkin)));

  // Hindustani skin (F-052): 7 notes per octave
  const hindustaniSkin = {
    tonic_midi: 48.0,
    scale_cents: [0, 200, 300, 500, 700, 900, 1000],
    n_octaves: 2,
  };
  assert.equal(quantizePitch(0.0, hindustaniSkin), 48.0);
  assert.equal(quantizePitch(1.0, hindustaniSkin), 72.0);
  assert.equal(quantizePitch(0.5, hindustaniSkin), 60.0);

  // Sri Lankan skin (F-053): 5 notes per octave
  const sriLankanSkin = {
    tonic_midi: 48.0,
    scale_cents: [0, 200, 400, 700, 1000],
    n_octaves: 2,
  };
  assert.equal(quantizePitch(0.0, sriLankanSkin), 48.0);
  assert.equal(quantizePitch(1.0, sriLankanSkin), 72.0);
  assert.equal(quantizePitch(0.5, sriLankanSkin), 60.0);
});

test("resolveCellAudio extracts all playback parameters (F-077)", () => {
  const grid = [
    [10.0, null],
  ];
  const legend = { vmin: 0, vmax: 100, units: "°C", category: "temperature" };
  const skin = { tonic_midi: 48.0, scale_cents: [0, 200, 400, 700, 900], n_octaves: 2 };

  const cellData = resolveCellAudio({ col: 0, band: 0 }, grid, legend, skin);
  assert.equal(cellData.val, 10.0);
  assert.equal(cellData.instrument, "strings");
  assert.equal(cellData.pan, -1.0);
  assert.ok(cellData.freqHz > 0);

  // Masked cell
  const maskedData = resolveCellAudio({ col: 1, band: 0 }, grid, legend, skin);
  assert.equal(maskedData.val, null);
  assert.ok(Number.isNaN(maskedData.u));
  assert.ok(Number.isNaN(maskedData.freqHz));
});

test("hapticDuration computes pulse length proportional to u (F-081)", () => {
  // F-081: navigator.vibrate(10 + 40·u ms); off/silent for invalid
  assert.equal(hapticDuration(0.0), 10);
  assert.equal(hapticDuration(0.5), 30);
  assert.equal(hapticDuration(1.0), 50);

  // Clamping
  assert.equal(hapticDuration(-0.5), 10);
  assert.equal(hapticDuration(1.5), 50);

  // Masked / invalid values
  assert.equal(hapticDuration(null), 0);
  assert.equal(hapticDuration(undefined), 0);
  assert.equal(hapticDuration(NaN), 0);
});
