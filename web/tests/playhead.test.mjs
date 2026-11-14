import { test } from "node:test";
import assert from "node:assert/strict";
import { playheadX, beatAtSeconds } from "../js/core/playhead.js";

test("playheadX computes clamped pixel position", () => {
  // Start of track
  assert.equal(playheadX(0, 48, 100, 800), 100);

  // Middle of track
  assert.equal(playheadX(24, 48, 100, 800), 500);

  // End of track
  assert.equal(playheadX(48, 48, 100, 800), 900);

  // Clamps negative beats
  assert.equal(playheadX(-5, 48, 100, 800), 100);

  // Clamps overflow beats
  assert.equal(playheadX(100, 48, 100, 800), 900);

  // Zero total beats fallback
  assert.equal(playheadX(10, 0, 100, 800), 100);
});

test("beatAtSeconds computes beats from seconds and bpm", () => {
  assert.equal(beatAtSeconds(0, 120), 0);
  assert.equal(beatAtSeconds(30, 120), 60);
  assert.equal(beatAtSeconds(15, 60), 15);
  assert.equal(beatAtSeconds(-10, 120), 0);
  assert.equal(beatAtSeconds(10, 0), 0);
});
