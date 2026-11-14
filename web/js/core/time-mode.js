/**
 * Pure time-mode math (F-093).
 *
 * Rules:
 * - Cycle length = frameBeats + restBeats (default 48 + 1 = 49 beats)
 * - frameAtBeat computes active frame index (0..F-1) and intra-frame phrase beat
 * - beatForFrame computes start beat of frameIndex: frameIndex * (frameBeats + restBeats)
 */

/**
 * Calculates current active frame index and intra-frame beat.
 *
 * @param {number} tBeat Current beat position in audio track
 * @param {number} [frameBeats=48] Duration of one frame phrase in beats
 * @param {number} [restBeats=1] Rest duration between phrases in beats
 * @param {number} [totalFrames=1] Total number of frames in animation
 * @returns {{ frameIndex: number, phraseBeat: number, isRest: boolean }}
 */
export function frameAtBeat(tBeat, frameBeats = 48, restBeats = 1, totalFrames = 1) {
  if (totalFrames <= 1) {
    const clampedBeat = Math.max(0, Math.min(tBeat, frameBeats));
    return {
      frameIndex: 0,
      phraseBeat: clampedBeat,
      isRest: false,
    };
  }

  const cycleLen = frameBeats + restBeats;
  if (cycleLen <= 0) {
    return { frameIndex: 0, phraseBeat: 0, isRest: false };
  }

  const safeBeat = Math.max(0, tBeat);
  const cycle = Math.floor(safeBeat / cycleLen);
  const frameIndex = Math.min(totalFrames - 1, cycle);
  const beatInCycle = safeBeat - frameIndex * cycleLen;

  if (frameIndex === totalFrames - 1) {
    // Last frame has no subsequent rest
    const phraseBeat = Math.min(frameBeats, beatInCycle);
    return {
      frameIndex,
      phraseBeat,
      isRest: false,
    };
  }

  if (beatInCycle >= frameBeats) {
    return {
      frameIndex,
      phraseBeat: frameBeats,
      isRest: true,
    };
  }

  return {
    frameIndex,
    phraseBeat: beatInCycle,
    isRest: false,
  };
}

/**
 * Calculates starting beat for a given frame index.
 *
 * @param {number} frameIndex 0-based frame index
 * @param {number} [frameBeats=48] Duration of one frame phrase in beats
 * @param {number} [restBeats=1] Rest duration between phrases in beats
 * @returns {number} Beat offset
 */
export function beatForFrame(frameIndex, frameBeats = 48, restBeats = 1) {
  const safeIdx = Math.max(0, Math.floor(frameIndex));
  return safeIdx * (frameBeats + restBeats);
}
