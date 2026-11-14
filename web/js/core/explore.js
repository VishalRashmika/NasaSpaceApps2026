/**
 * Pure explore mode cursor math and utterances (F-077, F-081, docs/09 §3).
 */

import { formatValue } from "./format.js";
import { midiToFreq } from "./schedule.js";

/**
 * Maps normalized coordinates (0..1) to grid cell indices.
 *
 * @param {number} xNorm Normalized X coordinate [0, 1]
 * @param {number} yNorm Normalized Y coordinate [0, 1]
 * @param {number} nCols Number of grid columns
 * @param {number} nBands Number of grid latitude bands
 * @returns {{ col: number, band: number }}
 */
export function cursorToCell(xNorm, yNorm, nCols, nBands) {
  if (nCols <= 0 || nBands <= 0) {
    return { col: 0, band: 0 };
  }
  const col = Math.min(nCols - 1, Math.max(0, Math.floor(xNorm * nCols)));
  const band = Math.min(nBands - 1, Math.max(0, Math.floor(yNorm * nBands)));
  return { col, band };
}

/**
 * Moves cursor according to keyboard input.
 *
 * @param {{ col: number, band: number }} cell Current cell
 * @param {string} key Keyboard key name (ArrowLeft, ArrowRight, ArrowUp, ArrowDown, Home, End, PageUp, PageDown)
 * @param {boolean} shift Whether shift key was held (moves 5 cells)
 * @param {number} nCols Total columns
 * @param {number} nBands Total bands
 * @returns {{ col: number, band: number }} New clamped cell
 */
export function moveCursor(cell, key, shift, nCols, nBands) {
  const step = shift ? 5 : 1;
  let col = cell ? cell.col : 0;
  let band = cell ? cell.band : 0;

  switch (key) {
    case "ArrowLeft":
      col -= step;
      break;
    case "ArrowRight":
      col += step;
      break;
    case "ArrowUp":
      band -= step;
      break;
    case "ArrowDown":
      band += step;
      break;
    case "Home":
      col = 0;
      break;
    case "End":
      col = nCols - 1;
      break;
    case "PageUp":
      band -= 1;
      break;
    case "PageDown":
      band += 1;
      break;
  }

  col = Math.min(Math.max(0, col), Math.max(0, nCols - 1));
  band = Math.min(Math.max(0, band), Math.max(0, nBands - 1));

  return { col, band };
}

function _expandUnits(units) {
  if (!units) return "";
  const trimmed = units.trim();
  if (trimmed === "°C") return "degrees Celsius";
  if (trimmed === "K") return "Kelvin";
  if (trimmed === "%") return "percent";
  return trimmed;
}

/**
 * Builds an accessible spoken utterance for the cell's current data.
 *
 * @param {{ col: number, band: number }} cell
 * @param {Array<Array<number|null>>|object} grid 2D array or object with data/rows
 * @param {object} legend Legend metadata (units, label, etc.)
 * @returns {string} Spoken announcement
 */
export function cellToUtterance(cell, grid, legend) {
  if (!cell) {
    return "No data.";
  }

  let matrix = null;
  let nBands = 5;
  let nCols = 48;

  if (Array.isArray(grid)) {
    matrix = grid;
    nBands = grid.length;
    nCols = grid[0] ? grid[0].length : 0;
  } else if (grid && Array.isArray(grid.data)) {
    matrix = grid.data;
    nBands = grid.data.length;
    nCols = grid.data[0] ? grid.data[0].length : 0;
  } else if (grid && typeof grid.rows === "number" && typeof grid.cols === "number") {
    nBands = grid.rows;
    nCols = grid.cols;
  }

  const { col, band } = cell;

  let val = null;
  if (matrix && matrix[band] && matrix[band][col] !== undefined) {
    val = matrix[band][col];
  }

  if (val === null || val === undefined || Number.isNaN(val)) {
    return "No data.";
  }

  const rawUnits = legend && legend.units ? legend.units : "";
  const spokenUnits = _expandUnits(rawUnits);
  const formattedVal = formatValue(val, spokenUnits);

  return `${formattedVal}. Band ${band + 1} of ${nBands}, column ${col + 1} of ${nCols}.`;
}

/**
 * Maps a science category to an instrument family id (doc 06 §6).
 *
 * @param {string} category
 * @returns {string} Instrument family
 */
export function categoryToFamily(category) {
  const map = {
    temperature: "strings",
    precipitation: "pluck",
    vegetation: "flute",
    chlorophyll: "flute",
    ice: "bell",
    aerosol: "texture",
    aerosol_optical_depth: "texture",
    ocean: "pad",
    sea_surface_height: "pad",
    wind_speed: "pad",
    carbon_dioxide: "texture",
    generic: "pad",
  };
  return (category && map[category.toLowerCase()]) || "pad";
}

/**
 * Computes stereo panning [-1, +1] for a grid column index.
 *
 * @param {number} col Column index 0..nCols-1
 * @param {number} nCols Total columns
 * @returns {number} Pan between -1.0 (west) and +1.0 (east)
 */
export function cellPan(col, nCols) {
  if (!nCols || nCols <= 1) return 0.0;
  const clamped = Math.min(nCols - 1, Math.max(0, col));
  return Number(((clamped / (nCols - 1)) * 2 - 1).toFixed(3));
}

/**
 * Normalises a scalar physical value into u in [0, 1] per docs/06 §3.
 *
 * @param {number|null} v Physical value
 * @param {object} legend Legend specification
 * @returns {number} u in [0, 1], or NaN if invalid/masked
 */
export function normalizeValue(v, legend) {
  if (v === null || v === undefined || Number.isNaN(v)) return NaN;
  if (!legend) return 0.5;

  const vmin = typeof legend.vmin === "number" ? legend.vmin : 0;
  const vmax = typeof legend.vmax === "number" ? legend.vmax : 100;
  if (vmax <= vmin) return 0.0;

  const val = Number(v);

  if (legend.scale === "log") {
    const effV = val <= 0 ? vmin : val;
    const logV = Math.log10(effV);
    const logMin = Math.log10(vmin > 0 ? vmin : 1e-6);
    const logMax = Math.log10(vmax > 0 ? vmax : 1);
    if (logMax <= logMin) return 0.0;
    const u = (logV - logMin) / (logMax - logMin);
    return Math.min(1.0, Math.max(0.0, u));
  }

  if (legend.kind === "diverging") {
    const center = typeof legend.center === "number" ? legend.center : (vmin + vmax) / 2.0;
    let u;
    if (val < center) {
      u = center === vmin ? 0.5 : 0.5 * (val - vmin) / (center - vmin);
    } else {
      u = vmax === center ? 0.5 : 0.5 + 0.5 * (val - center) / (vmax - center);
    }
    return Math.min(1.0, Math.max(0.0, u));
  }

  const u = (val - vmin) / (vmax - vmin);
  return Math.min(1.0, Math.max(0.0, u));
}

/**
 * Quantises normalized u in [0, 1] to MIDI pitch according to skin (docs/06 §4).
 *
 * @param {number} u Normalized value [0, 1]
 * @param {object} skin Skin object with tonic_midi, scale_cents, n_octaves
 * @returns {number} MIDI pitch (float), or NaN
 */
export function quantizePitch(u, skin) {
  if (u === null || u === undefined || Number.isNaN(u)) return NaN;
  const tonic = skin && typeof skin.tonic_midi === "number" ? skin.tonic_midi : 48.0;
  const scaleCents = skin && Array.isArray(skin.scale_cents)
    ? skin.scale_cents
    : [0, 200, 400, 700, 900];
  const nOctaves = skin && typeof skin.n_octaves === "number" ? skin.n_octaves : 2;

  const pitches = [];
  for (let o = 0; o < nOctaves; o++) {
    for (const c of scaleCents) {
      pitches.push(tonic + 12.0 * o + c / 100.0);
    }
  }
  pitches.push(tonic + 12.0 * nOctaves);

  const clampedU = Math.min(1.0, Math.max(0.0, u));
  const idx = Math.floor(clampedU * (pitches.length - 1) + 0.5);
  const clampedIdx = Math.min(pitches.length - 1, Math.max(0, idx));
  return pitches[clampedIdx];
}

/**
 * Resolves full audio parameters for a single cell in Explore mode (F-077).
 *
 * @param {{ col: number, band: number }} cell
 * @param {Array<Array<number|null>>|object} grid
 * @param {object} legend
 * @param {object} skin
 * @returns {{ val: number|null, u: number, pitchMidi: number, freqHz: number, pan: number, instrument: string } | null}
 */
export function resolveCellAudio(cell, grid, legend, skin) {
  if (!cell) return null;

  let matrix = null;
  let nBands = 5;
  let nCols = 48;

  if (Array.isArray(grid)) {
    matrix = grid;
    nBands = grid.length;
    nCols = grid[0] ? grid[0].length : 0;
  } else if (grid && Array.isArray(grid.data)) {
    matrix = grid.data;
    nBands = grid.data.length;
    nCols = grid.data[0] ? grid.data[0].length : 0;
  }

  const { col, band } = cell;
  let val = null;
  if (matrix && matrix[band] && matrix[band][col] !== undefined) {
    val = matrix[band][col];
  }

  if (val === null || val === undefined || Number.isNaN(val)) {
    return { val: null, u: NaN, pitchMidi: NaN, freqHz: NaN, pan: cellPan(col, nCols), instrument: "pad" };
  }

  const u = normalizeValue(val, legend);
  const pitchMidi = quantizePitch(u, skin);
  const freqHz = Number(midiToFreq(pitchMidi).toFixed(2));
  const pan = cellPan(col, nCols);
  const category = legend?.category || "generic";
  const instrument = categoryToFamily(category);

  return { val, u, pitchMidi, freqHz, pan, instrument };
}

/**
 * Computes haptic pulse duration in ms for normalized value u (F-081, docs/09 §4).
 * Formula: 10 + 40·u ms. Returns 0 if u is null/NaN.
 *
 * @param {number|null} u Normalized value [0, 1]
 * @returns {number} Pulse duration in milliseconds
 */
export function hapticDuration(u) {
  if (u === null || u === undefined || Number.isNaN(u)) return 0;
  const clamped = Math.min(1.0, Math.max(0.0, u));
  return Math.round(10.0 + 40.0 * clamped);
}
