/**
 * Pure playhead math (F-073).
 *
 * Rules:
 * - playheadX = mapLeft + clamp(tBeat / totalBeats, 0, 1) * mapWidth
 * - beatAtSeconds = seconds * bpm / 60
 */

/**
 * Calculates pixel X position for the playhead.
 * @param {number} tBeat Current beat
 * @param {number} totalBeats Total beats in score
 * @param {number} mapLeft Pixel left offset of the map
 * @param {number} mapWidth Pixel width of the map
 * @returns {number} Clamped pixel X coordinate
 */
export function playheadX(tBeat, totalBeats, mapLeft, mapWidth) {
  if (totalBeats <= 0 || mapWidth <= 0) {
    return mapLeft;
  }
  const ratio = Math.max(0, Math.min(1, tBeat / totalBeats));
  return mapLeft + ratio * mapWidth;
}

/**
 * Converts elapsed seconds to beats.
 * @param {number} seconds Elapsed audio seconds
 * @param {number} bpm Beats per minute
 * @returns {number} Beat position
 */
export function beatAtSeconds(seconds, bpm) {
  if (bpm <= 0 || seconds <= 0) {
    return 0;
  }
  return (seconds * bpm) / 60;
}
