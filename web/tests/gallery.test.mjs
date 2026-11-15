import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const HTML_PATH = path.resolve(__dirname, "../index.html");

test("F-071 AC: HTML has gallery container with radiogroup semantics and empty state", () => {
  const html = fs.readFileSync(HTML_PATH, "utf-8");

  // Gallery container with radiogroup semantics
  assert.match(
    html,
    /id=["']gallery-container["'][^>]*role=["']radiogroup["']/i,
    "Gallery container must have role='radiogroup'"
  );

  // Empty state container present
  assert.match(
    html,
    /id=["']gallery-empty["']/i,
    "Gallery must contain an empty state element"
  );
});

test("F-072 AC: Form has numeric fields for boxes, preset select, and aria-describedby errors", () => {
  const html = fs.readFileSync(HTML_PATH, "utf-8");

  // Four numeric inputs for colorbar box
  assert.match(html, /<input[^>]+id=["']cbox-x["'][^>]*>/i);
  assert.match(html, /<input[^>]+id=["']cbox-y["'][^>]*>/i);
  assert.match(html, /<input[^>]+id=["']cbox-w["'][^>]*>/i);
  assert.match(html, /<input[^>]+id=["']cbox-h["'][^>]*>/i);

  // Preset dropdown
  assert.match(html, /id=["']legend-preset["']/i);

  // Suggest colorbar button
  assert.match(html, /id=["']btn-suggest-cbox["']/i);

  // Inline errors linked via aria-describedby
  assert.match(html, /id=["']legend-label["'][^>]*aria-describedby=["']err-label["']/i);
  assert.match(html, /id=["']legend-units["'][^>]*aria-describedby=["']err-units["']/i);
  assert.match(html, /id=["']legend-vmin["'][^>]*aria-describedby=["']err-vmin["']/i);
  assert.match(html, /id=["']legend-vmax["'][^>]*aria-describedby=["']err-vmax["']/i);
});

test("F-075 & F-076 AC: Player has audio legend, export buttons, and scrubber", () => {
  const html = fs.readFileSync(HTML_PATH, "utf-8");

  // F-076: Audio legend button disabled initially
  assert.match(
    html,
    /id=["']btn-audio-legend["'][^>]*aria-disabled=["']true["']/i,
    "Audio legend button must be initially aria-disabled='true'"
  );

  // F-075 & F-109: Export buttons
  assert.match(html, /id=["']btn-play-wav["']/i, "Must have Play Rendered WAV button");
  assert.match(html, /link-download-wav/i, "Must have Download WAV link");
  assert.match(html, /link-download-mp4/i, "Must have Download Video (MP4) link");
  assert.match(html, /link-download-mid/i, "Must have Download MIDI link");
  assert.match(html, /link-download-json/i, "Must have Download Score JSON link");

  // Scrubber & play controls
  assert.match(html, /id=["']btn-play["']/i);
  assert.match(html, /id=["']btn-stop["']/i);
  assert.match(html, /<input[^>]+id=["']player-scrub["'][^>]*>/i);
  assert.match(html, /id=["']player-time["']/i);
});
