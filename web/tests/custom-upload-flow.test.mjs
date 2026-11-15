import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { CUSTOM_IMAGE_TYPES } from "../js/ui/category-selection.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const htmlPath = path.resolve(__dirname, "../index.html");
const cssPath = path.resolve(__dirname, "../css/app.css");

const html = fs.readFileSync(htmlPath, "utf-8");
const css = fs.readFileSync(cssPath, "utf-8");

test("No emojis anywhere across web source files (HTML, CSS, JS)", () => {
  const emojiPattern = /[\u{1F000}-\u{1FFFF}]|[\u{2600}-\u{27BF}]|[\u{2B50}-\u{2B55}]|[\u203C\u2049\u2122\u2139\u2194-\u2199\u21A9-\u21AA\u231A-\u231B\u2328\u23CF\u23E9-\u23F3\u23F8-\u23FA\u24C2\u2600-\u2604\u260E\u2611\u2614-\u2615\u2618\u261D\u2620\u2622-\u2623\u2626\u262A\u262E-\u262F\u2638-\u263A\u2640\u2642\u2648-\u2653\u2660\u2663\u2665-\u2666\u2668\u267B\u267F\u2692-\u2697\u2699\u269B-\u269C\u26A0-\u26A1\u26A7\u26AA-\u26AB\u26B0-\u26B1\u26BD-\u26BE\u26C4-\u26C5\u26C8\u26CE-\u26CF\u26D1\u26D3-\u26D4\u26E9-\u26EA\u26F0-\u26F5\u26F7-\u26FA\u26FD\u2702\u2705\u2708-\u270D\u270F\u2712\u2714\u2716\u271D\u2721\u2728\u2733-\u2734\u2744\u2747\u274C\u274E\u2753-\u2755\u2757\u2763-\u2764\u2795-\u2797\u27A1\u27B0\u27BF\u2934-\u2935\u2B05-\u2B07\u2B1B-\u2B1C\u2B50\u2B55\u3030\u303D\u3297\u3299]/u;

  function checkDir(dir) {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name === "vendor" || entry.name === "node_modules") continue;
        checkDir(fullPath);
      } else if (entry.isFile() && (entry.name.endsWith(".js") || entry.name.endsWith(".mjs") || entry.name.endsWith(".html") || entry.name.endsWith(".css"))) {
        const content = fs.readFileSync(fullPath, "utf-8");
        const match = emojiPattern.exec(content);
        assert.equal(
          match,
          null,
          `File ${fullPath} contains forbidden emoji character: ${match ? match[0] : ""}`
        );
      }
    }
  }

  checkDir(path.resolve(__dirname, ".."));
});

test("Custom upload pre-selection asks image type before upload screen", () => {
  // Screen 1B container
  assert.match(
    html,
    /id=["']view-custom-upload-type["']/i,
    "Must have dedicated image type selection screen #view-custom-upload-type"
  );

  // Clear question asking what kind of image to process
  assert.match(
    html,
    /class=["']custom-type-title["'][^>]*>What kind of image would you like to process\?<\/h2>/i,
    "Must ask 'What kind of image would you like to process?'"
  );

  // Grid for category choices
  assert.match(
    html,
    /id=["']custom-type-grid["'][^>]*role=["']radiogroup["']/i,
    "Must have custom-type-grid with radiogroup role"
  );

  // Back button to preloaded gallery
  assert.match(
    html,
    /id=["']btn-back-from-type-select["']/i,
    "Must have button to return to preloaded gallery"
  );

  // Decision & logic panel
  assert.match(
    html,
    /id=["']custom-type-decision-panel["']/i,
    "Must have panel displaying legend decision and sonification logic"
  );
  assert.match(html, /id=["']decision-legend-badge["']/i, "Must have legend decision badge");
  assert.match(html, /id=["']decision-legend-desc["']/i, "Must have legend decision description");
  assert.match(html, /id=["']decision-logic-desc["']/i, "Must have sonification logic description");
  assert.match(html, /id=["']btn-proceed-to-custom-upload["']/i, "Must have proceed to upload button");
});

test("CUSTOM_IMAGE_TYPES correctly identifies legend requirements and acoustic logic", () => {
  assert.ok(Array.isArray(CUSTOM_IMAGE_TYPES), "CUSTOM_IMAGE_TYPES must be exported as an array");
  assert.ok(CUSTOM_IMAGE_TYPES.length >= 6, "Must define at least 6 scientific image types");

  // GEOS Aerosols: Legend Required
  const aerosols = CUSTOM_IMAGE_TYPES.find((t) => t.title.toLowerCase().includes("aerosol"));
  assert.ok(aerosols, "Must include GEOS Aerosols type");
  assert.equal(aerosols.hasLegend, true, "GEOS Aerosols must require a colorbar legend");
  assert.match(aerosols.legendDecision, /legend required/i);
  assert.match(aerosols.sonificationLogic, /aerosol optical depth/i);
  assert.equal(aerosols.units, "AOD");

  // Hubble: Direct Spatial (No Legend Needed)
  const hubble = CUSTOM_IMAGE_TYPES.find((t) => t.title.toLowerCase().includes("hubble"));
  assert.ok(hubble, "Must include Hubble & Deep Space type");
  assert.equal(hubble.hasLegend, false, "Hubble must use direct spatial sonification without a legend");
  assert.match(hubble.legendDecision, /no legend required|direct/i);
  assert.match(hubble.sonificationLogic, /flux|brightness/i);

  // ISS Lightning: Direct Events (No Legend Needed)
  const lightning = CUSTOM_IMAGE_TYPES.find((t) => t.title.toLowerCase().includes("lightning"));
  assert.ok(lightning, "Must include ISS Lightning type");
  assert.equal(lightning.hasLegend, false, "ISS Lightning must use direct event sonification without a legend");
  assert.match(lightning.legendDecision, /no legend required|direct/i);
  assert.match(lightning.sonificationLogic, /flash/i);

  // Near-Surface Temperature: Legend Required
  const temp = CUSTOM_IMAGE_TYPES.find((t) => t.title.toLowerCase().includes("temperature"));
  assert.ok(temp, "Must include Temperature type");
  assert.equal(temp.hasLegend, true, "Temperature must require a colorbar legend");
  assert.equal(temp.kind, "diverging");
});

test("CSS rules for custom type selection and non-overlapping layout", () => {
  assert.match(css, /\.custom-type-view\b/, "CSS must define .custom-type-view");
  assert.match(css, /\.custom-type-grid\b/, "CSS must define .custom-type-grid");
  assert.match(css, /\.custom-type-card\b/, "CSS must define .custom-type-card");
  assert.match(css, /\.custom-type-card\.selected\b/, "CSS must define .custom-type-card.selected");
  assert.match(css, /\.custom-type-decision-panel\b/, "CSS must define .custom-type-decision-panel");
  assert.match(css, /\.decision-card\b/, "CSS must define .decision-card");
  assert.match(css, /\.decision-meta-grid\b/, "CSS must define .decision-meta-grid");
});
