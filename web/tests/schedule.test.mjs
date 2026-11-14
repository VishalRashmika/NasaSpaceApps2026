import { test } from "node:test";
import assert from "node:assert/strict";
import { scoreToTriggers, midiToFreq } from "../js/core/schedule.js";

test("midiToFreq computes equal-temperament frequency", () => {
  // A4 = 440 Hz
  assert.ok(Math.abs(midiToFreq(69) - 440.0) < 1e-4);
  // C4 = ~261.6256 Hz
  assert.ok(Math.abs(midiToFreq(60) - 261.6256) < 0.01);
  // A5 = 880 Hz
  assert.ok(Math.abs(midiToFreq(81) - 880.0) < 1e-4);
});

test("scoreToTriggers produces sorted triggers with valid properties", () => {
  const sampleScore = {
    schema: "earth-jukebox.score/1",
    mapping_version: "1.0.0",
    skin_id: "neutral",
    bpm: 120.0, // 1 beat = 0.5s
    total_beats: 4.0,
    voices: [
      { id: "band0", band_index: 0, instrument: "strings", pan: -0.5 },
      { id: "band1", band_index: 1, instrument: "bell", pan: 0.5 },
    ],
    notes: [
      {
        voice_id: "band1",
        t_beat: 2.0,
        dur_beat: 1.0,
        pitch_midi: 69.0,
        velocity: 0.8,
        accent: true,
        col: 2,
        band: 1,
        value: 15.0,
        glide_to_midi: null,
      },
      {
        voice_id: "band0",
        t_beat: 0.0,
        dur_beat: 0.5,
        pitch_midi: 60.0,
        velocity: 0.7,
        accent: false,
        col: 0,
        band: 0,
        value: 5.0,
        glide_to_midi: 62.0,
      },
    ],
  };

  const triggers = scoreToTriggers(sampleScore);
  assert.equal(triggers.length, 2);

  // First trigger should be at timeSec = 0.0
  const t0 = triggers[0];
  assert.equal(t0.timeSec, 0.0);
  assert.equal(t0.durSec, 0.25); // 0.5 beat * 0.5s/beat
  assert.ok(Math.abs(t0.freqHz - 261.6256) < 0.1);
  assert.ok(t0.glideToHz !== null && Math.abs(t0.glideToHz - 293.6648) < 0.1);
  assert.equal(t0.pan, -0.5);
  assert.equal(t0.instrument, "strings");
  assert.equal(t0.voiceId, "band0");
  assert.equal(t0.accent, false);
  assert.equal(t0.col, 0);
  assert.equal(t0.band, 0);

  // Second trigger should be at timeSec = 1.0 (2.0 beat * 0.5s/beat)
  const t1 = triggers[1];
  assert.equal(t1.timeSec, 1.0);
  assert.equal(t1.durSec, 0.5);
  assert.ok(Math.abs(t1.freqHz - 440.0) < 0.1);
  assert.equal(t1.glideToHz, null);
  assert.equal(t1.pan, 0.5);
  assert.equal(t1.instrument, "bell");
  assert.equal(t1.voiceId, "band1");
  assert.equal(t1.accent, true);
  assert.equal(t1.col, 2);
  assert.equal(t1.band, 1);
});

test("scoreToTriggers handles empty or malformed score safely", () => {
  assert.deepEqual(scoreToTriggers(null), []);
  assert.deepEqual(scoreToTriggers({}), []);
  assert.deepEqual(scoreToTriggers({ notes: [] }), []);
});
