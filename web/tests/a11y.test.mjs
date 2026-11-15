import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const htmlPath = path.resolve(__dirname, "../index.html");
const cssPath = path.resolve(__dirname, "../css/app.css");

const html = fs.readFileSync(htmlPath, "utf-8");
const css = fs.readFileSync(cssPath, "utf-8");

test("F-078 AC: Document landmarks, title, and responsive viewport", () => {
  assert.match(html, /<html\s+lang="en">/i, "HTML must declare lang='en'");
  assert.match(html, /<title>.+<\/title>/i, "Document must have a non-empty <title>");
  assert.match(html, /<meta\s+name="viewport"\s+content="[^"]*width=device-width[^"]*">/i, "Must have responsive viewport");

  // Single h1
  const h1Matches = html.match(/<h1\b[^>]*>/gi);
  assert.equal(h1Matches?.length, 1, "Must have exactly one <h1> element");

  // Required landmarks
  assert.match(html, /<header\b[^>]*>/i, "Must contain <header> landmark");
  assert.match(html, /<main\s+id="main"[^>]*>/i, "Must contain <main id='main'> landmark");
  assert.match(html, /<aside\b[^>]*>/i, "Must contain <aside> landmark");

  // Skip link
  assert.match(html, /<a\s+class="skip"\s+href="#main">Skip to main content<\/a>/i, "Must have functional skip link");
});

test("F-078 AC: Form controls and interactive buttons accessibility audit", () => {
  // Check inputs have matching labels
  const inputsWithId = [...html.matchAll(/<input\b[^>]*\bid="([^"]+)"[^>]*>/gi)];
  for (const match of inputsWithId) {
    const inputId = match[1];
    const fullTag = match[0];
    const typeMatch = fullTag.match(/type="([^"]+)"/i);
    const type = typeMatch ? typeMatch[1].toLowerCase() : "text";

    if (type === "hidden" || fullTag.includes('aria-hidden="true"')) {
      continue;
    }

    const hasAriaLabel = fullTag.includes("aria-label=") || fullTag.includes("aria-labelledby=");
    const hasLabelFor = new RegExp(`<label\\b[^>]*\\bfor="${inputId}"`, "i").test(html);
    const isWrappedInLabel = new RegExp(`<label\\b[^>]*>[^<]*<input\\b[^>]*\\bid="${inputId}"`, "i").test(html);

    assert.ok(
      hasAriaLabel || hasLabelFor || isWrappedInLabel,
      `Input #${inputId} (type=${type}) must have an associated <label> or aria-label`
    );
  }

  // Check buttons have accessible text or aria-label
  const buttons = [...html.matchAll(/<button\b([^>]*)>(.*?)<\/button>/gis)];
  for (const match of buttons) {
    const attrs = match[1];
    const innerText = match[2].replace(/<[^>]+>/g, "").trim();
    const hasAriaLabel = attrs.includes("aria-label=");
    const hasVisibleText = innerText.length > 0;

    assert.ok(
      hasAriaLabel || hasVisibleText,
      `Button with attributes ${attrs} must have accessible text or aria-label`
    );
  }
});

test("F-078 AC: ARIA live regions and polite announcements", () => {
  // Error alert: role="alert", aria-live="assertive"
  assert.match(html, /id="error-alert"[^>]*role="alert"[^>]*aria-live="assertive"/i);

  // Status badge: role="status", aria-live="polite"
  assert.match(html, /id="status"[^>]*role="status"[^>]*aria-live="polite"/i);

  // Explore live region: role="status", aria-live="polite", aria-atomic="true"
  assert.match(html, /id="explore-live"[^>]*role="status"[^>]*aria-live="polite"[^>]*aria-atomic="true"/i);

  // Rapidly changing playhead readout is muted to prevent screen-reader floods
  assert.match(html, /id="active-readout"[^>]*aria-live="off"/i);
  assert.match(html, /id="player-time"[^>]*aria-live="off"/i);
});

test("F-078 AC: Design system contrast, tap targets, focus rings, and reduced motion", () => {
  // Focus ring styling
  assert.match(css, /:focus-visible\s*\{[^}]*outline:\s*2px solid/i, "Must have visible >= 2px focus ring");
  assert.match(css, /outline-offset:\s*2px/i, "Focus ring must have outline-offset");

  // Minimum tap target size (44px)
  assert.match(css, /min-height:\s*44px/i, "Interactive buttons must satisfy 44px min-height target");
  assert.match(css, /min-width:\s*44px/i, "Interactive buttons must satisfy 44px min-width target");

  // prefers-reduced-motion media query
  assert.match(css, /@media\s*\(\s*prefers-reduced-motion:\s*reduce\s*\)/i, "Must support prefers-reduced-motion");

  // Contrast & dark theme
  assert.match(css, /\[data-theme="dark"\]/i, "Must have dark theme selector");
  assert.match(css, /@media\s*\(\s*prefers-color-scheme:\s*dark\s*\)/i, "Must support prefers-color-scheme: dark");
});

test("Issue #5 AC: Explore mode button, haptics toggle, and skin selector removed, fidelity elements retained", () => {
  // Unneeded options removed per Issue #5
  assert.ok(!html.includes('id="btn-explore"'), "Explore mode button must be removed from DOM");
  assert.ok(!html.includes('id="toggle-haptics"'), "Haptics toggle must be removed from DOM");
  assert.ok(!html.includes('id="skin-select"'), "Skin selector must be removed from DOM");

  // Explore visual cursor
  assert.match(html, /id="explore-cursor"[^>]*class="[^"]*box-explore[^"]*"/i, "Explore visual cursor must exist");

  // Canvas container keyboard focusable
  assert.match(html, /id="canvas-container"[^>]*tabindex="0"/i, "Canvas container must be keyboard focusable");

  // Fidelity panel readouts
  assert.match(html, /id="fid-confidence"/i);
  assert.match(html, /id="fid-badge"/i);
  assert.match(html, /id="fid-r"/i);
  assert.match(html, /id="fid-legend-r"/i);
  assert.match(html, /id="fid-version"/i);
  assert.match(html, /id="fid-grid"/i);
});
