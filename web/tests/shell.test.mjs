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
