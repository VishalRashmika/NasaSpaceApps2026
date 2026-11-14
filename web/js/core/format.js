/**
 * Pure formatting utilities (F-073, F-076).
 */

/**
 * Formats a scalar data value with appropriate precision and units.
 * Never outputs NaN or undefined.
 * @param {number|null|undefined} v Numeric value
 * @param {string|null|undefined} units Units string (e.g. "°C")
 * @returns {string} Formatted string
 */
export function formatValue(v, units) {
  if (v === null || v === undefined || typeof v !== "number" || Number.isNaN(v)) {
    return "No data";
  }

  let formatted;
  const abs = Math.abs(v);
  if (abs === 0) {
    formatted = "0";
  } else if (abs >= 100) {
    formatted = v.toFixed(1).replace(/\.0$/, "");
  } else if (abs >= 10) {
    formatted = v.toFixed(2).replace(/\.?0+$/, "");
  } else if (abs >= 0.01) {
    formatted = v.toFixed(2);
  } else {
    formatted = v.toPrecision(3);
  }

  const u = units ? units.trim() : "";
  if (!u) {
    return formatted;
  }
  return `${formatted} ${u}`;
}

/**
 * Formats time in seconds as mm:ss.
 * @param {number} seconds
 * @returns {string} Formatted time string
 */
export function formatTime(seconds) {
  if (!seconds || seconds < 0 || Number.isNaN(seconds)) {
    return "00:00";
  }
  const total = Math.floor(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
