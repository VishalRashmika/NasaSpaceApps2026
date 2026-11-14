/**
 * Pure score scheduler (F-074, docs/07 §7).
 *
 * Converts a Score object into a list of timed audio trigger descriptors
 * suitable for playback scheduling in Tone.js.
 */

/**
 * Converts a MIDI note number (can be microtonal float) to frequency in Hz.
 * Formula: 440 * 2^((midi - 69) / 12)
 * @param {number} midi
 * @returns {number} Frequency in Hz
 */
export function midiToFreq(midi) {
  return 440.0 * Math.pow(2.0, (midi - 69.0) / 12.0);
}

/**
 * Transforms a Score object into sorted trigger descriptors.
 *
 * @param {object} score Score JSON object
 * @returns {Array<object>} Sorted list of trigger objects
 */
export function scoreToTriggers(score) {
  if (!score || !Array.isArray(score.notes)) {
    return [];
  }

  const bpm = typeof score.bpm === "number" && score.bpm > 0 ? score.bpm : 96.0;
  const beatSec = 60.0 / bpm;

  // Build voice map for quick lookup of instrument and pan
  const voiceMap = new Map();
  if (Array.isArray(score.voices)) {
    for (const v of score.voices) {
      if (v && v.id) {
        voiceMap.set(v.id, v);
      }
    }
  }

  const triggers = [];

  for (const n of score.notes) {
    if (!n) continue;

    const tBeat = typeof n.t_beat === "number" ? n.t_beat : 0.0;
    const durBeat = typeof n.dur_beat === "number" ? n.dur_beat : 0.5;
    const timeSec = Number((tBeat * beatSec).toFixed(6));
    const durSec = Number((durBeat * beatSec).toFixed(6));

    const pitchMidi = typeof n.pitch_midi === "number" ? n.pitch_midi : 60.0;
    const freqHz = Number(midiToFreq(pitchMidi).toFixed(4));

    let glideToHz = null;
    if (typeof n.glide_to_midi === "number") {
      glideToHz = Number(midiToFreq(n.glide_to_midi).toFixed(4));
    }

    const voice = voiceMap.get(n.voice_id);
    const pan = voice && typeof voice.pan === "number" ? voice.pan : 0.0;
    const instrument = voice && voice.instrument ? voice.instrument : "strings";

    triggers.push({
      timeSec,
      durSec,
      freqHz,
      glideToHz,
      velocity: typeof n.velocity === "number" ? n.velocity : 0.7,
      pan,
      instrument,
      voiceId: n.voice_id ?? "default",
      accent: Boolean(n.accent),
      roughness: typeof n.roughness === "number" ? n.roughness : 0.0,
      kind: n.kind ?? "main",
      col: typeof n.col === "number" ? n.col : 0,
      band: typeof n.band === "number" ? n.band : 0,
      value: typeof n.value === "number" ? n.value : null,
    });
  }

  // Sort triggers by timeSec, then voiceId, then freqHz
  triggers.sort((a, b) => {
    if (a.timeSec !== b.timeSec) {
      return a.timeSec - b.timeSec;
    }
    if (a.voiceId !== b.voiceId) {
      return a.voiceId.localeCompare(b.voiceId);
    }
    return a.freqHz - b.freqHz;
  });

  return triggers;
}
