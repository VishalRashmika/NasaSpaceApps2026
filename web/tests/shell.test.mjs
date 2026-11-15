import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const HTML_PATH = path.resolve(__dirname, "../index.html");

test("F-070 AC2: HTML shell has lang, one h1, and required landmarks", () => {
  const html = fs.readFileSync(HTML_PATH, "utf-8");

  // lang attribute on <html>
  assert.match(html, /<html[^>]+lang=["'][a-z]{2}(-[A-Z]{2})?["']/i, "html element must have lang attribute");

  // Exactly one <h1>
  const h1Matches = html.match(/<h1\b[^>]*>/gi);
  assert.ok(h1Matches, "Must have an h1 tag");
  assert.equal(h1Matches.length, 1, "Must have exactly one h1 tag");

  // Landmarks: header, main
  assert.match(html, /<header\b[^>]*>/i, "Must have header landmark");
  assert.match(html, /<main\b[^>]*id=["']main["'][^>]*>/i, "Must have main landmark with id='main'");

  // Skip link
  assert.match(html, /<a\b[^>]*class=["'][^"']*skip[^"']*["'][^>]*href=["']#main["']/i, "Must have skip link to #main");

  // Responsive viewport
  assert.match(html, /<meta[^>]+name=["']viewport["'][^>]+content=["'][^"']*width=device-width[^"']*["']/i, "Must have responsive viewport");
});

test("Top bar: simplified, clean header layout without verbose backend versions", () => {
  const html = fs.readFileSync(HTML_PATH, "utf-8");
  const css = fs.readFileSync(path.resolve(__dirname, "../css/app.css"), "utf-8");
  const mainJs = fs.readFileSync(path.resolve(__dirname, "../js/main.js"), "utf-8");

  // 1. Simplified brand header contains NASA badge, Earth Jukebox, and Earth Information Center
  assert.match(html, /class=["']nasa-brand-badge["']/i, "Header must have clean NASA badge");
  assert.match(html, /<h1[^>]*>Earth Jukebox<\/h1>/i, "Header must have clean Earth Jukebox h1");
  assert.match(html, /class=["']tagline["']>Earth Information Center<\/p>/i, "Header must have clean tagline");

  // 2. No verbose backend version text in the top bar HTML
  assert.doesNotMatch(html, /Backend v\d/i, "Header must not display Backend v0.0.0");
  assert.doesNotMatch(html, /Mapping \d/i, "Header must not display Mapping 1.0.0");
  assert.doesNotMatch(html, /Backend checking/i, "Header must not display Backend checking");

  // 3. Status element retains accessibility live region without visual clutter
  assert.match(html, /id=["']status["'][^>]*class=["'][^"']*sr-only[^"']*["'][^>]*role=["']status["'][^>]*aria-live=["']polite["']/i,
    "Status element must be accessible and sr-only to keep top bar simple"
  );

  // 4. In main.js, checkHealth sets clean 'Ready' status instead of verbose version strings
  assert.doesNotMatch(mainJs, /statusEl\.textContent\s*=\s*`Backend v/, "main.js must not output Backend v... to statusEl textContent");
  assert.match(mainJs, /statusEl\.textContent\s*=\s*["']Ready["']/, "main.js sets clean Ready status on health check success");

  // 5. CSS defines modern, clean styles for header, status-badge, and theme-toggle
  assert.match(css, /\.app-header\s*\{[^}]*backdrop-filter:\s*blur/i, "CSS header has sleek frosted backdrop");
  assert.match(css, /\.theme-toggle-btn\s*\{[^}]*min-height:\s*44px/i, "Theme toggle satisfies 44px min-height target");
  assert.match(css, /\.status-badge\.status-offline\b/, "CSS defines clean offline alert state");
});
