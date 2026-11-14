import test from "node:test";
import assert from "node:assert/strict";

import { frameAtBeat, beatForFrame } from "../js/core/time-mode.js";

test("frameAtBeat handles single frame static field (F-093 AC1)", () => {
  const info0 = frameAtBeat(0, 48, 1, 1);
  assert.equal(info0.frameIndex, 0);
  assert.equal(info0.phraseBeat, 0);
  assert.equal(info0.isRest, false);

  const info24 = frameAtBeat(24, 48, 1, 1);
  assert.equal(info24.frameIndex, 0);
  assert.equal(info24.phraseBeat, 24);
  assert.equal(info24.isRest, false);

  const infoEnd = frameAtBeat(60, 48, 1, 1);
  assert.equal(infoEnd.frameIndex, 0);
  assert.equal(infoEnd.phraseBeat, 48); // clamped at frameBeats
});

test("frameAtBeat navigates multi-frame animation and rest beats (F-093 AC1)", () => {
  // 3 frames, each 48 beats, 1 beat rest. Cycle = 49 beats.
  // Frame 0: beats 0..48. Rest: 48..49.
  // Frame 1: beats 49..97. Rest: 97..98.
  // Frame 2: beats 98..146.

  // In Frame 0
  const at10 = frameAtBeat(10, 48, 1, 3);
  assert.equal(at10.frameIndex, 0);
  assert.equal(at10.phraseBeat, 10);
  assert.equal(at10.isRest, false);

  // In Rest 0 (e.g. beat 48.5)
  const at48_5 = frameAtBeat(48.5, 48, 1, 3);
  assert.equal(at48_5.frameIndex, 0);
  assert.equal(at48_5.phraseBeat, 48);
  assert.equal(at48_5.isRest, true);

  // Start of Frame 1 (beat 49)
  const at49 = frameAtBeat(49, 48, 1, 3);
  assert.equal(at49.frameIndex, 1);
  assert.equal(at49.phraseBeat, 0);
  assert.equal(at49.isRest, false);

  // In Frame 1 (beat 60 -> 60 - 49 = 11)
  const at60 = frameAtBeat(60, 48, 1, 3);
  assert.equal(at60.frameIndex, 1);
  assert.equal(at60.phraseBeat, 11);
  assert.equal(at60.isRest, false);

  // In Rest 1 (beat 97.2)
  const at97_2 = frameAtBeat(97.2, 48, 1, 3);
  assert.equal(at97_2.frameIndex, 1);
  assert.equal(at97_2.phraseBeat, 48);
  assert.equal(at97_2.isRest, true);

  // Start of Frame 2 (beat 98)
  const at98 = frameAtBeat(98, 48, 1, 3);
  assert.equal(at98.frameIndex, 2);
  assert.equal(at98.phraseBeat, 0);
  assert.equal(at98.isRest, false);

  // End of Frame 2 (beat 146)
  const at146 = frameAtBeat(146, 48, 1, 3);
  assert.equal(at146.frameIndex, 2);
  assert.equal(at146.phraseBeat, 48);
  assert.equal(at146.isRest, false);

  // Beyond end
  const at200 = frameAtBeat(200, 48, 1, 3);
  assert.equal(at200.frameIndex, 2);
  assert.equal(at200.phraseBeat, 48);
  assert.equal(at200.isRest, false);
});

test("beatForFrame computes exact start beats (F-093 AC1, AC4)", () => {
  assert.equal(beatForFrame(0, 48, 1), 0);
  assert.equal(beatForFrame(1, 48, 1), 49);
  assert.equal(beatForFrame(2, 48, 1), 98);
  assert.equal(beatForFrame(3, 48, 1), 147);
});

test("F-093 AC2: HTML shell has accessible frame strip section", async () => {
  const fs = await import("node:fs");
  const path = await import("node:path");
  const { fileURLToPath } = await import("node:url");

  const __filename = fileURLToPath(import.meta.url);
  const __dirname = path.dirname(__filename);
  const htmlPath = path.resolve(__dirname, "../index.html");
  const html = fs.readFileSync(htmlPath, "utf-8");

  assert.match(
    html,
    /id=["']time-mode-strip["'][^>]*role=["']region["']/i,
    "Time mode strip section must have role='region'"
  );
  assert.match(
    html,
    /id=["']time-mode-strip["'][^>]*aria-label=["']Time mode frame strip["']/i,
    "Time mode strip must have aria-label"
  );
});

test("F-093 AC2, AC3: CSS defines time-mode strip and active button highlights", async () => {
  const fs = await import("node:fs");
  const path = await import("node:path");
  const { fileURLToPath } = await import("node:url");

  const __filename = fileURLToPath(import.meta.url);
  const __dirname = path.dirname(__filename);
  const cssPath = path.resolve(__dirname, "../css/app.css");
  const css = fs.readFileSync(cssPath, "utf-8");

  assert.match(css, /\.time-mode-strip\b/, "CSS must define .time-mode-strip");
  assert.match(css, /\.frame-thumb-btn\b/, "CSS must define .frame-thumb-btn");
  assert.match(css, /\.frame-thumb-btn\.active\b/, "CSS must define .frame-thumb-btn.active");
});
