import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  formatMarkdownToHtml,
  formatObservationDisplayTitle,
  getMissionLabel,
  formatCategoryFilterLabel,
} from "../js/ui/category-selection.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const htmlPath = path.resolve(__dirname, "../index.html");
const cssPath = path.resolve(__dirname, "../css/app.css");

const html = fs.readFileSync(htmlPath, "utf-8");
const css = fs.readFileSync(cssPath, "utf-8");

test("F-107 AC: Category selection page structure and accessibility landmarks", () => {
  // Category selection view landmark and heading
  assert.match(
    html,
    /id=["']view-categories["'][^>]*class=["'][^"']*category-selection-view[^"']*["']/i,
    "Category selection view must exist with .category-selection-view class"
  );

  // Workflow progress navigation
  assert.match(html, /class=["'][^"']*workflow-nav[^"']*["']/i, "Must have workflow navigation");
  assert.match(html, /id=["']btn-goto-categories["']/i, "Must have button to return to categories");
  assert.match(html, /id=["']btn-goto-processing["']/i, "Must have button for processing step");

  // Category cards container exists
  assert.match(
    html,
    /<div[^>]+id=["']category-cards-grid["'][^>]*class=["']category-cards-grid/i,
    "Category cards grid must exist with category-cards-grid class"
  );

  // Gallery mode tab is active by default to display preloaded gallery on opening screen
  assert.match(
    html,
    /<button[^>]*class=["'][^"']*active[^"']*["'][^>]*id=["']tab-mode-gallery["']|<button[^>]*id=["']tab-mode-gallery["'][^>]*class=["'][^"']*active[^"']*["']/i,
    "Gallery mode tab should be active by default on opening screen"
  );

  // Selection question
  assert.match(
    html,
    /class=["']category-selection-title["'][^>]*>What kind of image would you like to sonify\?<\/h2>/i,
    "Must have clear category selection question"
  );
});

test("F-107 AC: Category detail, legend handling, and preloaded gallery structure", () => {
  // Category detail panel
  assert.match(html, /id=["']category-detail-panel["']/i, "Must have category detail panel");
  assert.match(html, /id=["']btn-back-to-categories["']/i, "Must have back to categories button");

  // Legend display container and elements
  assert.match(html, /id=["']cat-legend-container["']/i, "Must have legend container");
  assert.match(html, /id=["']cat-legend-image-wrap["']/i, "Must have legend image wrap");
  assert.match(html, /<img[^>]+id=["']cat-legend-img["'][^>]*>/i, "Must have legend image element");
  assert.match(html, /id=["']cat-no-legend-notice["']/i, "Must have notice container for categories without legend");

  // Preloaded examples gallery with radiogroup semantics
  assert.match(
    html,
    /id=["']cat-examples-gallery["'][^>]*role=["']radiogroup["']/i,
    "Preloaded example gallery must have role='radiogroup'"
  );

  // Action buttons
  assert.match(html, /id=["']btn-sonify-selected-example["']/i, "Must have sonify selected example button");
  assert.match(html, /id=["']btn-upload-for-category["']/i, "Must have upload for category button");
  assert.match(html, /id=["']btn-quick-custom-upload["']/i, "Must have quick custom upload button");

  // Processing stage return button
  assert.match(html, /id=["']btn-back-from-stage["']/i, "Processing stage must have button to change category");
});

test("F-107 AC: CSS styles for category selection, legend badges, and gallery cards", () => {
  assert.match(css, /\.category-selection-view\b/, "CSS must define .category-selection-view");
  assert.match(css, /\.category-cards-grid\b/, "CSS must define .category-cards-grid");
  assert.match(css, /\.category-card\b/, "CSS must define .category-card");
  assert.match(css, /\.badge-legend-yes\b/, "CSS must define .badge-legend-yes for legend indicator");
  assert.match(css, /\.badge-legend-no\b/, "CSS must define .badge-legend-no for non-legend indicator");
  assert.match(css, /\.cat-examples-gallery\b/, "CSS must define .cat-examples-gallery");
  assert.match(css, /\.example-gallery-card\b/, "CSS must define .example-gallery-card");
  assert.match(css, /\.example-gallery-card\.selected\b/, "CSS must define selected state for example cards");
});

test("F-108 AC3, AC4: Data-to-sound mapping elements and sonification technique in category detail", () => {
  // Technique badge
  assert.match(
    html,
    /id=["']cat-sonification-technique-badge["']/i,
    "Category detail must have technique badge"
  );

  // Predefined configuration badges container
  assert.match(
    html,
    /id=["']cat-predefined-badges["']/i,
    "Category detail must have predefined badges container"
  );

  // Data-to-sound mappings container
  assert.match(
    html,
    /id=["']cat-sound-mappings-container["']/i,
    "Category detail must have sound mappings container"
  );
});

test("F-108 AC1, AC2: Upload panel has auto-supplied configuration card and collapsible advanced settings", () => {
  // Upload category config card
  assert.match(
    html,
    /id=["']upload-category-config-card["']/i,
    "Upload panel must have auto-supplied configuration card"
  );
  assert.match(
    html,
    /id=["']upload-config-category-title["']/i,
    "Must display active category title in upload config card"
  );
  assert.match(
    html,
    /id=["']upload-config-label["']/i,
    "Must display predefined label in upload config card"
  );
  assert.match(
    html,
    /id=["']upload-config-range["']/i,
    "Must display predefined range in upload config card"
  );
  assert.match(
    html,
    /id=["']upload-config-instrument["']/i,
    "Must display predefined instrument in upload config card"
  );
  assert.match(
    html,
    /id=["']upload-config-technique["']/i,
    "Must display sonification technique in upload config card"
  );

  // Advanced settings collapsible accordion
  assert.match(
    html,
    /<details[^>]+id=["']advanced-settings-toggle["']/i,
    "Manual parameters must be wrapped in collapsible <details id='advanced-settings-toggle'>"
  );

  // Active category section in How to Listen
  assert.match(
    html,
    /id=["']active-category-listen-info["']/i,
    "How to listen panel must have active category section"
  );

  // Upload panel mapping and legend accordion
  assert.match(
    html,
    /id=["']upload-category-mapping-details["']/i,
    "Upload panel must have mapping and legend details accordion"
  );
  assert.match(
    html,
    /id=["']upload-config-mappings-table["']/i,
    "Upload panel must have sound mappings table container"
  );
});

test("F-108 AC4: CSS styles for data-to-sound mapping table and category config cards", () => {
  assert.match(css, /\.badge-technique\b/, "CSS must define .badge-technique");
  assert.match(css, /\.cat-predefined-badges\b/, "CSS must define .cat-predefined-badges");
  assert.match(css, /\.predefined-chip\b/, "CSS must define .predefined-chip");
  assert.match(css, /\.sound-mapping-table\b/, "CSS must define .sound-mapping-table");
  assert.match(css, /\.badge-sound\b/, "CSS must define .badge-sound");
  assert.match(css, /\.category-config-summary-card\b/, "CSS must define .category-config-summary-card");
  assert.match(css, /\.advanced-settings-accordion\b/, "CSS must define .advanced-settings-accordion");
  assert.match(css, /\.category-listen-card\b/, "CSS must define .category-listen-card");
});

test("Opening screen preloaded example gallery structure and accessibility", () => {
  // Mode switcher tabs
  assert.match(html, /id=["']opening-view-controls["']/i, "Must have opening view controls");
  assert.match(html, /id=["']tab-mode-gallery["']/i, "Must have gallery mode tab");
  assert.match(html, /id=["']tab-mode-categories["']/i, "Must have category mode tab");
  assert.match(html, /id=["']total-examples-count["']/i, "Must display total examples count pill");
  assert.match(html, /id=["']total-categories-count["']/i, "Must display total categories count pill");

  // Category filter bar & chips & search input
  assert.match(html, /id=["']category-filter-bar["']/i, "Must have category filter bar");
  assert.match(html, /id=["']filter-chips-list["']/i, "Must have filter chips list with radiogroup semantics");
  assert.match(html, /id=["']gallery-search-input["']/i, "Must have gallery search input");
  assert.match(html, /id=["']btn-clear-search["']/i, "Must have clear search button");

  // Opening gallery section & container
  assert.match(html, /id=["']opening-gallery-section["']/i, "Must have opening gallery section");
  assert.match(
    html,
    /id=["']opening-examples-gallery["'][^>]*role=["']radiogroup["']/i,
    "Opening examples gallery must have role='radiogroup'"
  );
  assert.match(html, /id=["']gallery-visible-count["']/i, "Must have visible count readout");

  // Lightbox modal
  assert.match(html, /id=["']observation-preview-modal["']/i, "Must have observation preview modal");
  assert.match(html, /id=["']modal-obs-img["']/i, "Modal must have full image element");
  assert.match(html, /id=["']btn-modal-sonify-now["']/i, "Modal must have 1-click sonify button");

  // CSS for opening gallery
  assert.match(css, /\.opening-view-controls\b/, "CSS must define .opening-view-controls");
  assert.match(css, /\.view-mode-tabs\b/, "CSS must define .view-mode-tabs");
  assert.match(css, /\.filter-chip\b/, "CSS must define .filter-chip");
  assert.match(css, /\.filter-chip\.active\b/, "CSS must define .filter-chip.active");
  assert.match(css, /\.gallery-search-input\b/, "CSS must define .gallery-search-input");
  assert.match(css, /\.opening-gallery-section\b/, "CSS must define .opening-gallery-section");
  assert.match(css, /\.opening-examples-gallery\b/, "CSS must define .opening-examples-gallery");
  assert.match(css, /\.opening-example-card\b/, "CSS must define .opening-example-card");
  assert.match(css, /\.opening-thumb-wrap\b/, "CSS must define .opening-thumb-wrap");
  assert.match(css, /\.btn-quick-inspect\b/, "CSS must define .btn-quick-inspect");
  assert.match(css, /\.opening-mission-tag\b/, "CSS must define .opening-mission-tag");
  assert.match(css, /\.opening-card-title\b/, "CSS must define .opening-card-title");
  assert.match(css, /\.btn-sonify-card\b/, "CSS must define .btn-sonify-card");
  assert.match(css, /\.btn-detail-card\b/, "CSS must define .btn-detail-card");
  assert.match(css, /\.modal-backdrop\b/, "CSS must define .modal-backdrop");
  assert.match(css, /\.modal-gallery-preview\b/, "CSS must define .modal-gallery-preview");
  assert.match(css, /\.category-card-cover-wrap\b/, "CSS must define .category-card-cover-wrap");
  assert.match(css, /\.category-card-inner\b/, "CSS must define .category-card-inner");
  assert.match(css, /\.featured-single-card\b/, "CSS must define .featured-single-card");
});

test("formatObservationDisplayTitle and getMissionLabel curate titles and missions authentically", () => {
  // Curated titles
  assert.equal(
    formatObservationDisplayTitle("", "03_nasas-james-webb-space-telescope-captures-eerie-cats-head.png"),
    "NASA's James Webb: Eerie Cat's Eye Nebula"
  );
  assert.equal(
    formatObservationDisplayTitle("", "MC01_stage3_GMAO_near_surface_temperature_2048x1024_en.00001_print.jpg"),
    "NASA GEOS Near-Surface Temperature (T2M)"
  );
  assert.equal(
    formatObservationDisplayTitle("", "iss_lightning_preview.jpg"),
    "ISS Lightning Imaging Sensor (Global Preview)"
  );

  // Mission badges
  assert.match(getMissionLabel("03_webb_cats.png", "space"), /James Webb/);
  assert.match(getMissionLabel("01_hubble.jpg", "space"), /Hubble/);
  assert.match(getMissionLabel("chandra_ixpe.jpg", "space"), /Chandra & IXPE/);
  assert.match(getMissionLabel("lightning.jpg", "lightningEvents"), /ISS Lightning/);
  assert.match(getMissionLabel("temp.jpg", "Near-Surface-Temperature"), /GEOS-FP/);
});

test("F-107 AC2: formatMarkdownToHtml parses headers, lists, tables, and bold tags safely", () => {
  const md = `# Overview

This is **temperature** data.

* First observation
* Second observation

| Variable | Range |
|---|---|
| Temperature | -40 to +40 |`;

  const htmlOut = formatMarkdownToHtml(md);
  assert.match(htmlOut, /<h2>Overview<\/h2>/, "Should convert # to <h2>");
  assert.match(htmlOut, /<strong>temperature<\/strong>/, "Should convert **bold** to <strong>");
  assert.match(htmlOut, /<ul class=["']md-list["']>/, "Should wrap items in list");
  assert.match(htmlOut, /<li>First observation<\/li>/, "Should convert * to <li>");
  assert.match(htmlOut, /<table class=["']md-table["']>/, "Should parse table");
  assert.match(htmlOut, /Temperature/, "Table must contain row data");
});

test("formatCategoryFilterLabel formats clean and concise filter card labels", () => {
  // Test raw dataset headings and directory ids
  assert.equal(
    formatCategoryFilterLabel({ id: "GIOS Aerols", title: "Dataset Information: NASA GEOS Aerosols (2025)" }),
    "Aerosols"
  );
  assert.equal(
    formatCategoryFilterLabel({ id: "Geos-fp-precipitation-and-clouds", title: "NASA Dataset: GEOS-FP Precipitation and Clouds" }),
    "Precipitation & Clouds"
  );
  assert.equal(
    formatCategoryFilterLabel({ id: "Hubble+IOTD", title: "NASA Dataset Context: Deep Space Imagery & Sonification" }),
    "Deep Space"
  );
  assert.equal(
    formatCategoryFilterLabel({ id: "Near-Surface-Temperature", title: "NASA GEOS-FP: Near-Surface Temperature (T2M)" }),
    "Temperature"
  );
  assert.equal(
    formatCategoryFilterLabel({ id: "Near-Surface-Wind-Speed", title: "NASA Dataset: GEOS-FP Near-Surface Wind Speed" }),
    "Wind Speed"
  );
  assert.equal(
    formatCategoryFilterLabel({ id: "lightningEvents", title: "Dataset Overview: Lightning Events Detected from the ISS (2017-2023)" }),
    "ISS Lightning"
  );
});

test("Reduced size and compact layout for filter cards and toolbar in CSS", () => {
  // Compact filter chips sizing
  assert.match(css, /\.filter-chip\s*\{[^}]*min-height:\s*30px/i, "Filter chip must have compact height");
  assert.match(css, /\.filter-chip\s*\{[^}]*white-space:\s*nowrap/i, "Filter chip text must not wrap awkwardly");
  assert.match(css, /\.filter-chip\s*\.chip-text\b/, "CSS must define .chip-text styling");
  assert.match(css, /\.chip-count\b/, "CSS must define .chip-count pill");
  assert.match(css, /\.category-filter-bar\b/, "CSS must define .category-filter-bar");
});

test("Sidebar tabs in ShellUI are isolated to .sidebar-pane to prevent hiding the gallery", () => {
  const shellJs = fs.readFileSync(path.resolve(__dirname, "../js/ui/shell.js"), "utf-8");
  assert.match(
    shellJs,
    /querySelectorAll\(["']\.sidebar-pane\s+\.tab-btn["']\)/,
    "ShellUI tab buttons must be scoped to .sidebar-pane"
  );
  assert.match(
    shellJs,
    /querySelectorAll\(["']\.sidebar-pane\s+\.tab-panel["']\)/,
    "ShellUI tab panels must be scoped to .sidebar-pane"
  );
});
