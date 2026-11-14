/**
 * Category Selection Page & Preloaded Gallery UI (F-107, F-108).
 * Discovers real categories from dataset/, displays authentic NASA preloaded gallery,
 * category overview cards, optional legends, and connects to the sonification engine.
 */

import { getCategories, fetchCategoryImageBlob } from "../api/client.js";

const CATEGORY_ICONS = {
  temperature: "🌡️",
  wind: "💨",
  precipitation: "🌧️",
  aerosol: "🌫️",
  deep_space: "🌌",
  lightning: "⚡",
  default: "🛰️",
};

function getCategoryIcon(catId) {
  const lower = (catId || "").toLowerCase();
  if (lower.includes("temp")) return CATEGORY_ICONS.temperature;
  if (lower.includes("wind")) return CATEGORY_ICONS.wind;
  if (lower.includes("precip") || lower.includes("cloud")) return CATEGORY_ICONS.precipitation;
  if (lower.includes("aerosol") || lower.includes("aerols")) return CATEGORY_ICONS.aerosol;
  if (lower.includes("hubble") || lower.includes("deep") || lower.includes("space")) return CATEGORY_ICONS.deep_space;
  if (lower.includes("lightning")) return CATEGORY_ICONS.lightning;
  return CATEGORY_ICONS.default;
}

export function formatMarkdownToHtml(markdown) {
  if (!markdown) return "";
  const lines = markdown.split("\n");
  const html = [];
  let inList = false;
  let inTable = false;

  const escapeHtml = (str) =>
    str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

  const formatInline = (text) => {
    let t = escapeHtml(text);
    t = t.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    t = t.replace(/\*(.+?)\*/g, "<em>$1</em>");
    t = t.replace(/`(.+?)`/g, "<code>$1</code>");
    return t;
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    if (line.startsWith("|") && line.endsWith("|")) {
      if (line.includes("---")) {
        continue;
      }
      if (!inTable) {
        if (inList) {
          html.push("</ul>");
          inList = false;
        }
        inTable = true;
        html.push('<div class="md-table-wrap"><table class="md-table">');
      }
      const cells = line
        .slice(1, -1)
        .split("|")
        .map((c) => c.trim());
      const tag = i === 0 || html.length <= 1 ? "th" : "td";
      html.push(`<tr>${cells.map((c) => `<${tag}>${formatInline(c)}</${tag}>`).join("")}</tr>`);
      continue;
    } else if (inTable) {
      html.push("</table></div>");
      inTable = false;
    }

    if (line.startsWith("* ") || line.startsWith("- ")) {
      if (!inList) {
        inList = true;
        html.push('<ul class="md-list">');
      }
      html.push(`<li>${formatInline(line.slice(2))}</li>`);
      continue;
    } else if (inList) {
      html.push("</ul>");
      inList = false;
    }

    if (line.startsWith("### ")) {
      html.push(`<h4>${formatInline(line.slice(4))}</h4>`);
    } else if (line.startsWith("## ")) {
      html.push(`<h3>${formatInline(line.slice(3))}</h3>`);
    } else if (line.startsWith("# ")) {
      html.push(`<h2>${formatInline(line.slice(2))}</h2>`);
    } else if (line.length === 0) {
      continue;
    } else {
      html.push(`<p>${formatInline(line)}</p>`);
    }
  }

  if (inList) html.push("</ul>");
  if (inTable) html.push("</table></div>");

  return html.join("\n");
}

export function formatObservationDisplayTitle(rawTitle, filename) {
  const map = {
    "Aerosols_2025-08-19T20_00_00_1500x1179_72dpi.png": "NASA GEOS Aerosol Optical Depth (Synoptic)",
    "Aerosols_2025-08-19T20_00_00_1920x1080.png": "NASA GEOS Global Aerosol Optical Depth (1080p)",
    "MC03_stage3_GMAO_precipitation_2048x1024_en.00001_print.jpg": "NASA GEOS Precipitation & Cloud Dynamics",
    "01_m30s-sparkling-stars.jpg": "Hubble: Sparkling Stars in Cluster M30",
    "02_hubble-reveals-cosmic-mystery.png": "Hubble: Star Formation & Cosmic Filament",
    "03_nasas-james-webb-space-telescope-captures-eerie-cats-head.png": "NASA's James Webb: Eerie Cat's Eye Nebula",
    "04_nasas-hubble-marks-way-for-roman-space-telescope.jpg": "Hubble: Wayfinding for Nancy Grace Roman Telescope",
    "05_webb-sees-turbulent-star-nursery.jpg": "JWST: Turbulent Stellar Nursery NGC 346",
    "06_spirals-edge.jpg": "Hubble: Edge-On Spiral Galaxy NGC 4565",
    "07_webb-captures-stellar-jets.png": "JWST: Supersonic Stellar Jets in Herbig-Haro",
    "08_chandra-finds-possible-origin-of-treble-clef-waves.jpg": "NASA Chandra: Acoustic Sound Waves in Galaxy Cluster",
    "09_cosmic-house-of-mirrors.jpg": "Hubble: Gravitational Lens 'Cosmic Mirrors'",
    "10_hubble-spots-chaotic-secret-in-galaxy.jpg": "Hubble: Starburst Core Dynamics in NGC 1569",
    "11_nasas-hubble-telescope-reaches-milestone-looks-for-elusive-supernova.jpg": "Hubble: Deep Supernova Progenitor Search",
    "12_nasas-chandra-finds-unusual-objects-in-pinwheel-galaxy.jpg": "NASA Chandra: Ultraluminous X-Ray Sources in M101",
    "13_nasas-chandra-spots-galactic-gem.jpg": "NASA Chandra: Galactic Core X-Ray Emission",
    "14_dust-and-water-in-sagittarius-a.png": "NASA: Molecular Gas & Water in Sagittarius A*",
    "15_superbubble-in-the-large-magellanic-cloud.jpg": "Hubble: Superbubble Cavity in LMC (N44)",
    "16_webb-opens-treasure-chest.jpg": "JWST: Dense Infrared Star Cluster NIRCam",
    "17_colorful-collage-of-tarantula-nebula.jpg": "Hubble & Webb: Multiwavelength Tarantula Nebula",
    "18_lion-nebula-roars-in-webbs-sights.png": "JWST: Starburst Lion Nebula in Infrared",
    "19_starburst-galaxy-centaurus-a.png": "Hubble & Chandra: Active Radio Galaxy Centaurus A",
    "20_a-new-look-and-sound-for-messier-94.jpg": "NASA Chandra: Acoustic Resonance in Messier 94",
    "21_nasas-chandra-and-ixpe-study-pulsar-in-lighthouse-nebula.jpg": "NASA Chandra & IXPE: Pulsar in Lighthouse Nebula",
    "22_young-galaxy-cluster.jpg": "Hubble: Massive Gravitationally Bound Young Cluster",
    "23_hubble-sees-crimson-cloud-and-stars.jpg": "Hubble: Crimson Ionized Hydrogen in Emission Nebula",
    "24_hubble-captures-star-studded-cluster.jpg": "Hubble: High-Density Globular Cluster NGC 6355",
    "25_starry-chandelier-cluster.jpg": "Hubble: Luminous Stellar Chandelier Cluster",
    "26_millions-of-stars-in-cigar-galaxy.jpg": "Hubble: Starburst Galaxy Messier 82 (Cigar)",
    "27_nasas-chandra-finds-possible-supernova-remnant.jpg": "NASA Chandra: Compact Supernova Remnant G352.7-0.1",
    "28_black-eye-galaxy.jpg": "Hubble: Black Eye Galaxy (Messier 64)",
    "MC01_stage3_GMAO_near_surface_temperature_2048x1024_en.00001_print.jpg": "NASA GEOS Near-Surface Temperature (T2M)",
    "MC02_stage3_GMAO_near_surface_wind_2048x1024_en.00001_print.jpg": "NASA GEOS Near-Surface Wind Speed & Circulation",
    "iss_lightning_SOS_thumb.jpg": "ISS Lightning Science On a Sphere (SOS)",
    "iss_lightning_preview.jpg": "ISS Lightning Imaging Sensor (Global Preview)",
    "iss_lightning_sos_yearly_debug_2023_sos_2048p60.00420_print.jpg": "ISS LIS Annual Lightning Flash Distribution",
  };

  if (filename && map[filename]) return map[filename];

  let t = (rawTitle || filename || "").trim();
  t = t.replace(/\bNasas\b/gi, "NASA's");
  t = t.replace(/\bNasa\b/gi, "NASA");
  t = t.replace(/\bIss\b/gi, "ISS");
  t = t.replace(/\bSos\b/gi, "SOS");
  t = t.replace(/\bJwst\b/gi, "JWST");
  t = t.replace(/\bGeos\b/gi, "GEOS");
  t = t.replace(/\bGmao\b/gi, "GMAO");
  t = t.replace(/\bIxpe\b/gi, "IXPE");
  t = t.replace(/\bWebbs\b/gi, "Webb's");
  t = t.replace(/\b2048X1024\b/gi, "");
  t = t.replace(/\b1920X1080\b/gi, "1080p");
  t = t.replace(/\b1500X1179\b/gi, "Synoptic");
  t = t.replace(/\s+/g, " ").trim();
  return t;
}

export function getMissionLabel(filename, catId) {
  const f = (filename || "").toLowerCase();
  const c = (catId || "").toLowerCase();

  if (f.includes("webb") || f.includes("jwst")) return "🔭 NASA James Webb Space Telescope";
  if (f.includes("chandra") && f.includes("ixpe")) return "🛰️ NASA Chandra & IXPE";
  if (f.includes("chandra")) return "🛰️ NASA Chandra X-Ray Observatory";
  if (f.includes("hubble")) return "🔭 NASA Hubble Space Telescope";
  if (f.includes("roman")) return "🔭 NASA Nancy Grace Roman Space Telescope";
  if (c.includes("space") || c.includes("hubble")) return "🌌 NASA Great Observatories";
  if (c.includes("lightning") || f.includes("lightning")) return "🛰️ ISS Lightning Imaging Sensor (LIS)";
  if (c.includes("aerosol")) return "🛰️ NASA GEOS-FP Aerosols (GMAO)";
  if (c.includes("precip")) return "🛰️ NASA GEOS-FP Precipitation & Clouds";
  if (c.includes("temp")) return "🛰️ NASA GEOS-FP Near-Surface Temperature";
  if (c.includes("wind")) return "🛰️ NASA GEOS-FP Near-Surface Wind";
  return "🛰️ NASA Earth Information Center";
}

export class CategorySelectionUI {
  /**
   * @param {object} options
   * @param {(payload: { category: object, image: object, imageBlob: Blob }) => void} options.onSelectExample
   * @param {(payload: { category: object }) => void} options.onSelectCustomUpload
   * @param {() => void} options.onDirectCustomUpload
   * @param {(msg: string) => void} options.onError
   */
  constructor({ onSelectExample, onSelectCustomUpload, onDirectCustomUpload, onError }) {
    this.onSelectExample = onSelectExample;
    this.onSelectCustomUpload = onSelectCustomUpload;
    this.onDirectCustomUpload = onDirectCustomUpload;
    this.onError = onError;

    this.categories = [];
    this.allImages = [];
    this.activeCategory = null;
    this.selectedImage = null;
    this.currentViewMode = "gallery"; // "gallery" (default) or "categories"
    this.currentCategoryFilter = "all";
    this.searchQuery = "";
    this.isProceeding = false;

    // View containers
    this.viewContainer = document.getElementById("view-categories");
    this.introCard = document.getElementById("category-intro-panel");
    this.cardsGrid = document.getElementById("category-cards-grid");
    this.detailPanel = document.getElementById("category-detail-panel");

    // Opening Gallery elements
    this.openingGalleryControls = document.getElementById("opening-view-controls");
    this.openingGallerySection = document.getElementById("opening-gallery-section");
    this.openingExamplesGallery = document.getElementById("opening-examples-gallery");
    this.tabModeGallery = document.getElementById("tab-mode-gallery");
    this.tabModeCategories = document.getElementById("tab-mode-categories");
    this.totalExamplesCount = document.getElementById("total-examples-count");
    this.totalCategoriesCount = document.getElementById("total-categories-count");
    this.categoryFilterBar = document.getElementById("category-filter-bar");
    this.filterChipsList = document.getElementById("filter-chips-list");
    this.galleryVisibleCount = document.getElementById("gallery-visible-count");
    this.gallerySearchInput = document.getElementById("gallery-search-input");
    this.btnClearSearch = document.getElementById("btn-clear-search");

    // Observation Lightbox Preview Modal elements
    this.obsPreviewModal = document.getElementById("observation-preview-modal");
    this.modalObsImg = document.getElementById("modal-obs-img");
    this.modalObsTitle = document.getElementById("modal-obs-title");
    this.modalObsMission = document.getElementById("modal-obs-mission");
    this.modalObsDesc = document.getElementById("modal-obs-desc");
    this.modalObsVoice = document.getElementById("modal-obs-voice");
    this.modalObsVariable = document.getElementById("modal-obs-variable");
    this.modalObsTechnique = document.getElementById("modal-obs-technique");
    this.modalLegendSection = document.getElementById("modal-legend-section");
    this.modalLegendImg = document.getElementById("modal-legend-img");
    this.modalLegendNotes = document.getElementById("modal-legend-notes");
    this.btnModalSonifyNow = document.getElementById("btn-modal-sonify-now");
    this.btnCloseObsModal = document.getElementById("btn-close-obs-modal");
    this.previewActiveCategory = null;
    this.previewActiveItem = null;

    // Detail panel elements
    this.btnBackToCategories = document.getElementById("btn-back-to-categories");
    this.detailTitle = document.getElementById("cat-detail-title");
    this.legendBadge = document.getElementById("cat-legend-badge");
    this.detailDesc = document.getElementById("cat-detail-desc");
    this.btnToggleMarkdown = document.getElementById("btn-toggle-info-md");
    this.fullMarkdown = document.getElementById("cat-full-markdown");

    // Legend elements
    this.legendImageWrap = document.getElementById("cat-legend-image-wrap");
    this.legendImg = document.getElementById("cat-legend-img");
    this.legendNotes = document.getElementById("cat-legend-notes");
    this.noLegendNotice = document.getElementById("cat-no-legend-notice");

    // Sonification concept elements
    this.sonificationDesc = document.getElementById("cat-sonification-desc");
    this.sonificationTechniqueBadge = document.getElementById("cat-sonification-technique-badge");
    this.predefinedBadgesContainer = document.getElementById("cat-predefined-badges");
    this.soundMappingsContainer = document.getElementById("cat-sound-mappings-container");

    // Detail Gallery elements
    this.exampleCount = document.getElementById("cat-example-count");
    this.examplesGallery = document.getElementById("cat-examples-gallery");
    this.btnSonifyExample = document.getElementById("btn-sonify-selected-example");
    this.btnUploadForCategory = document.getElementById("btn-upload-for-category");
    this.btnQuickUpload = document.getElementById("btn-quick-custom-upload");

    this._initEvents();
  }

  _initEvents() {
    if (this.btnBackToCategories) {
      this.btnBackToCategories.addEventListener("click", () => this.showCategoryList());
    }

    if (this.tabModeGallery) {
      this.tabModeGallery.addEventListener("click", () => this.setViewMode("gallery"));
    }

    if (this.tabModeCategories) {
      this.tabModeCategories.addEventListener("click", () => this.setViewMode("categories"));
    }

    if (this.gallerySearchInput) {
      this.gallerySearchInput.addEventListener("input", (e) => {
        this.searchQuery = e.target.value.trim();
        if (this.btnClearSearch) {
          this.btnClearSearch.classList.toggle("hidden", this.searchQuery.length === 0);
        }
        this.renderOpeningGallery();
      });
    }

    if (this.btnClearSearch) {
      this.btnClearSearch.addEventListener("click", () => {
        this.searchQuery = "";
        if (this.gallerySearchInput) {
          this.gallerySearchInput.value = "";
          this.gallerySearchInput.focus();
        }
        this.btnClearSearch.classList.add("hidden");
        this.renderOpeningGallery();
      });
    }

    if (this.btnCloseObsModal) {
      this.btnCloseObsModal.addEventListener("click", () => this.closePreviewModal());
    }

    if (this.obsPreviewModal) {
      this.obsPreviewModal.addEventListener("click", (e) => {
        if (e.target === this.obsPreviewModal) {
          this.closePreviewModal();
        }
      });
    }

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.obsPreviewModal && !this.obsPreviewModal.classList.contains("hidden")) {
        this.closePreviewModal();
      }
    });

    if (this.btnModalSonifyNow) {
      this.btnModalSonifyNow.addEventListener("click", () => {
        if (this.previewActiveCategory && this.previewActiveItem) {
          const cat = this.previewActiveCategory;
          const item = this.previewActiveItem;
          this.closePreviewModal();
          this.proceedWithImage(cat, item, null);
        }
      });
    }

    if (this.btnQuickUpload) {
      this.btnQuickUpload.addEventListener("click", () => {
        if (this.onDirectCustomUpload) this.onDirectCustomUpload();
      });
    }

    if (this.btnUploadForCategory) {
      this.btnUploadForCategory.addEventListener("click", () => {
        if (this.activeCategory && this.onSelectCustomUpload) {
          this.onSelectCustomUpload({ category: this.activeCategory });
        }
      });
    }

    if (this.btnSonifyExample) {
      this.btnSonifyExample.addEventListener("click", () => this.handleProceedWithSelected());
    }

    if (this.btnToggleMarkdown) {
      this.btnToggleMarkdown.addEventListener("click", () => {
        const isExpanded = this.btnToggleMarkdown.getAttribute("aria-expanded") === "true";
        this.btnToggleMarkdown.setAttribute("aria-expanded", String(!isExpanded));
        if (this.fullMarkdown) {
          this.fullMarkdown.classList.toggle("hidden", isExpanded);
          this.fullMarkdown.setAttribute("aria-hidden", String(isExpanded));
        }
        this.btnToggleMarkdown.textContent = isExpanded
          ? "View Full Scientific Notes ▾"
          : "Hide Full Scientific Notes ▴";
      });
    }
  }

  async load() {
    try {
      const data = await getCategories();
      this.categories = Array.isArray(data) ? data : [];

      // Collate all preloaded images across categories
      this.allImages = [];
      this.categories.forEach((cat) => {
        if (Array.isArray(cat.images)) {
          cat.images.forEach((img) => {
            this.allImages.push({
              ...img,
              category: cat,
            });
          });
        }
      });

      // Update counts
      if (this.totalExamplesCount) {
        this.totalExamplesCount.textContent = String(this.allImages.length);
      }
      if (this.totalCategoriesCount) {
        this.totalCategoriesCount.textContent = String(this.categories.length);
      }

      this.renderFilterChips();
      this.renderOpeningGallery();
      this.renderCategoryCards();
      this.setViewMode(this.currentViewMode);
    } catch (err) {
      if (this.cardsGrid) {
        this.cardsGrid.innerHTML = `
          <div class="empty-state error-state">
            <p>Failed to load dataset categories from backend: ${err.message}</p>
          </div>
        `;
      }
      if (this.openingExamplesGallery) {
        this.openingExamplesGallery.innerHTML = `
          <div class="empty-state error-state">
            <p>Failed to load preloaded images: ${err.message}</p>
          </div>
        `;
      }
      if (this.onError) {
        this.onError("Could not discover dataset categories.");
      }
    }
  }

  setViewMode(mode) {
    this.currentViewMode = mode;
    const isGallery = mode === "gallery";

    if (this.tabModeGallery) {
      this.tabModeGallery.classList.toggle("active", isGallery);
      this.tabModeGallery.setAttribute("aria-selected", String(isGallery));
    }
    if (this.tabModeCategories) {
      this.tabModeCategories.classList.toggle("active", !isGallery);
      this.tabModeCategories.setAttribute("aria-selected", String(!isGallery));
    }

    if (this.openingGallerySection) {
      this.openingGallerySection.classList.toggle("hidden", !isGallery);
    }
    if (this.cardsGrid) {
      this.cardsGrid.classList.toggle("hidden", isGallery);
    }
    if (this.categoryFilterBar) {
      this.categoryFilterBar.classList.toggle("hidden", !isGallery);
    }
  }

  renderFilterChips() {
    if (!this.filterChipsList) return;
    this.filterChipsList.innerHTML = "";

    // "All" chip
    const allChip = document.createElement("button");
    allChip.type = "button";
    allChip.className = `filter-chip ${this.currentCategoryFilter === "all" ? "active" : ""}`;
    allChip.setAttribute("role", "radio");
    allChip.setAttribute("aria-checked", String(this.currentCategoryFilter === "all"));
    allChip.innerHTML = `All Imagery <span class="chip-count">${this.allImages.length}</span>`;
    allChip.addEventListener("click", () => {
      this.currentCategoryFilter = "all";
      this.renderFilterChips();
      this.renderOpeningGallery();
      if (this.currentViewMode !== "gallery") this.setViewMode("gallery");
    });
    this.filterChipsList.appendChild(allChip);

    // Per-category chips
    this.categories.forEach((cat) => {
      const imgCount = Array.isArray(cat.images) ? cat.images.length : 0;
      if (imgCount === 0) return;

      const icon = getCategoryIcon(cat.id);
      const isSelected = this.currentCategoryFilter === cat.id;

      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = `filter-chip ${isSelected ? "active" : ""}`;
      chip.setAttribute("role", "radio");
      chip.setAttribute("aria-checked", String(isSelected));
      chip.innerHTML = `<span aria-hidden="true">${icon}</span> ${cat.title} <span class="chip-count">${imgCount}</span>`;

      chip.addEventListener("click", () => {
        this.currentCategoryFilter = cat.id;
        this.renderFilterChips();
        this.renderOpeningGallery();
        if (this.currentViewMode !== "gallery") this.setViewMode("gallery");
      });

      this.filterChipsList.appendChild(chip);
    });
  }

  renderOpeningGallery() {
    if (!this.openingExamplesGallery) return;
    this.openingExamplesGallery.innerHTML = "";

    const search = (this.searchQuery || "").toLowerCase();
    const filtered = this.allImages.filter((item) => {
      const cat = item.category;
      if (this.currentCategoryFilter !== "all" && cat && cat.id !== this.currentCategoryFilter) {
        return false;
      }
      if (!search) return true;
      const displayTitle = formatObservationDisplayTitle(item.title, item.filename).toLowerCase();
      const mission = getMissionLabel(item.filename, cat?.id || "").toLowerCase();
      const catTitle = (cat?.title || "").toLowerCase();
      const fname = (item.filename || "").toLowerCase();
      return (
        displayTitle.includes(search) ||
        mission.includes(search) ||
        catTitle.includes(search) ||
        fname.includes(search)
      );
    });

    if (this.galleryVisibleCount) {
      this.galleryVisibleCount.textContent = String(filtered.length);
    }

    if (filtered.length === 0) {
      this.openingExamplesGallery.innerHTML = `
        <div class="empty-state">
          <p>No preloaded observations match "${this.searchQuery || this.currentCategoryFilter}".</p>
          <button type="button" class="btn btn-sm btn-secondary" id="btn-reset-gallery-search">
            Reset Filters &amp; Search
          </button>
        </div>
      `;
      const btnReset = document.getElementById("btn-reset-gallery-search");
      if (btnReset) {
        btnReset.addEventListener("click", () => {
          this.searchQuery = "";
          this.currentCategoryFilter = "all";
          if (this.gallerySearchInput) this.gallerySearchInput.value = "";
          if (this.btnClearSearch) this.btnClearSearch.classList.add("hidden");
          this.renderFilterChips();
          this.renderOpeningGallery();
        });
      }
      return;
    }

    filtered.forEach((item) => {
      const cat = item.category;
      const card = document.createElement("article");
      card.className = "opening-example-card";
      card.tabIndex = 0;
      card.setAttribute("role", "radio");
      card.setAttribute("aria-checked", "false");
      const displayTitle = formatObservationDisplayTitle(item.title, item.filename);
      const mission = getMissionLabel(item.filename, cat.id);
      card.setAttribute("aria-label", `NASA observation: ${displayTitle} (${cat.title})`);

      const icon = getCategoryIcon(cat.id);
      const legendBadgeClass = cat.has_legend ? "badge-legend-yes" : "badge-legend-no";
      const legendBadgeText = cat.has_legend ? "✓ Colorbar Legend" : "⚡ Spatial / Direct";

      // Parameter summary
      let paramSummary = cat.title;
      let voiceSummary = (cat.predefined_config?.instrument_family || "pad").toUpperCase() + " Synth";
      if (cat.predefined_config) {
        paramSummary = `${cat.predefined_config.label} (${cat.predefined_config.vmin} to ${cat.predefined_config.vmax} ${cat.predefined_config.units})`;
      }

      card.innerHTML = `
        <div class="opening-thumb-wrap">
          <img src="${item.thumb_url}" alt="${displayTitle}" class="opening-thumb-img" loading="lazy">
          <div class="opening-card-overlay-badges">
            <span class="badge badge-cat-chip">${icon} ${cat.title}</span>
            <span class="badge ${legendBadgeClass}">${legendBadgeText}</span>
          </div>
          <button type="button" class="btn-quick-inspect" aria-label="Inspect high-res preview of ${displayTitle}">
            🔍 Inspect
          </button>
        </div>
        <div class="opening-card-content">
          <span class="opening-mission-tag" title="${mission}">${mission}</span>
          <h4 class="opening-card-title" title="${displayTitle}">${displayTitle}</h4>
          <div class="opening-card-meta">
            <span class="meta-tag meta-var" title="${paramSummary}">${paramSummary}</span>
            <span class="meta-tag meta-sound">🎵 ${voiceSummary}</span>
          </div>
        </div>
        <div class="opening-card-actions">
          <button type="button" class="btn btn-primary btn-sm btn-sonify-card" aria-label="Sonify ${displayTitle} now">
            <span class="btn-icon-symbol">▶</span> Sonify Now
          </button>
          <button type="button" class="btn btn-secondary btn-sm btn-detail-card" aria-label="View preview and details for ${displayTitle}">
            <span class="btn-icon-symbol">🔍</span> Science &amp; Details
          </button>
        </div>
      `;

      const btnSonify = card.querySelector(".btn-sonify-card");
      const btnDetail = card.querySelector(".btn-detail-card");
      const btnQuickInspect = card.querySelector(".btn-quick-inspect");

      const triggerSonify = () => {
        this.proceedWithImage(cat, item, btnSonify);
      };

      if (btnSonify) {
        btnSonify.addEventListener("click", (e) => {
          e.stopPropagation();
          triggerSonify();
        });
      }

      if (btnDetail) {
        btnDetail.addEventListener("click", (e) => {
          e.stopPropagation();
          this.openPreviewModal(cat, item);
        });
      }

      if (btnQuickInspect) {
        btnQuickInspect.addEventListener("click", (e) => {
          e.stopPropagation();
          this.openPreviewModal(cat, item);
        });
      }

      // Card selection & keyboard triggers
      card.addEventListener("click", () => {
        this.openingExamplesGallery.querySelectorAll(".opening-example-card").forEach((c) => {
          c.classList.remove("selected");
          c.setAttribute("aria-checked", "false");
        });
        card.classList.add("selected");
        card.setAttribute("aria-checked", "true");
      });

      card.addEventListener("dblclick", () => {
        triggerSonify();
      });

      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          triggerSonify();
        }
      });

      this.openingExamplesGallery.appendChild(card);
    });
  }

  openPreviewModal(category, item) {
    if (!this.obsPreviewModal) return;
    this.previewActiveCategory = category;
    this.previewActiveItem = item;

    const displayTitle = formatObservationDisplayTitle(item.title, item.filename);
    const mission = getMissionLabel(item.filename, category.id);

    if (this.modalObsTitle) this.modalObsTitle.textContent = displayTitle;
    if (this.modalObsMission) this.modalObsMission.textContent = mission;
    if (this.modalObsDesc) this.modalObsDesc.textContent = category.description || "Authentic NASA observation.";
    if (this.modalObsImg) {
      this.modalObsImg.src = item.thumb_url;
      this.modalObsImg.alt = displayTitle;
    }

    // Acoustic parameters
    const p = category.predefined_config;
    if (this.modalObsVoice) {
      this.modalObsVoice.textContent = (p?.instrument_family || "Pad").toUpperCase() + " Synthesizer";
    }
    if (this.modalObsVariable) {
      this.modalObsVariable.textContent = p ? `${p.label} (${p.vmin} to ${p.vmax} ${p.units})` : category.title;
    }
    if (this.modalObsTechnique) {
      this.modalObsTechnique.textContent = category.sonification_technique || "Spatial Grid & Luminance Mapping";
    }

    // Legend
    if (this.modalLegendSection) {
      if (category.has_legend) {
        this.modalLegendSection.classList.remove("hidden");
        if (this.modalLegendImg) {
          const encodedId = encodeURIComponent(category.id);
          this.modalLegendImg.src = `/api/categories/${encodedId}/legend`;
          this.modalLegendImg.alt = `Colorbar legend for ${category.title}`;
        }
        if (this.modalLegendNotes) {
          this.modalLegendNotes.textContent = category.legend_info || "True data colorbar for value inversion.";
        }
      } else {
        this.modalLegendSection.classList.add("hidden");
      }
    }

    this.obsPreviewModal.classList.remove("hidden");
    this.obsPreviewModal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
    if (this.btnCloseObsModal) this.btnCloseObsModal.focus();
  }

  closePreviewModal() {
    if (!this.obsPreviewModal) return;
    this.obsPreviewModal.classList.add("hidden");
    this.obsPreviewModal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
  }

  async proceedWithImage(category, image, buttonEl) {
    if (this.isProceeding) return;
    this.isProceeding = true;

    let originalText = "";
    if (buttonEl) {
      originalText = buttonEl.textContent;
      buttonEl.disabled = true;
      buttonEl.textContent = "Loading…";
    }

    try {
      const blob = await fetchCategoryImageBlob(category.id, image.filename);
      if (this.onSelectExample) {
        this.onSelectExample({
          category,
          image,
          imageBlob: blob,
        });
      }
    } catch (err) {
      if (this.onError) {
        this.onError(`Failed to load selected image: ${err.message}`);
      }
    } finally {
      this.isProceeding = false;
      if (buttonEl) {
        buttonEl.disabled = false;
        buttonEl.textContent = originalText;
      }
    }
  }

  renderCategoryCards() {
    if (!this.cardsGrid) return;
    this.cardsGrid.innerHTML = "";

    if (this.categories.length === 0) {
      this.cardsGrid.innerHTML = `
        <div class="empty-state">
          <p>No dataset categories found in dataset/ folder.</p>
        </div>
      `;
      return;
    }

    this.categories.forEach((cat) => {
      const card = document.createElement("article");
      card.className = "category-card";
      card.tabIndex = 0;
      card.setAttribute("role", "button");
      card.setAttribute("aria-label", `Select category ${cat.title}`);

      const icon = getCategoryIcon(cat.id);
      const legendBadgeClass = cat.has_legend ? "badge-legend-yes" : "badge-legend-no";
      const legendBadgeText = cat.has_legend ? "✓ Colorbar Legend" : "⚡ Direct / Spatial";

      const firstImage = cat.images && cat.images.length > 0 ? cat.images[0] : null;
      const coverHtml = firstImage
        ? `<div class="category-card-cover-wrap">
             <img src="${firstImage.thumb_url}" alt="Preview for ${cat.title}" class="category-cover-img" loading="lazy">
             <span class="cover-gradient-overlay" aria-hidden="true"></span>
           </div>`
        : "";

      card.innerHTML = `
        ${coverHtml}
        <div class="category-card-inner">
          <div class="category-card-header">
            <span class="category-icon" aria-hidden="true">${icon}</span>
            <span class="badge ${legendBadgeClass}">${legendBadgeText}</span>
          </div>
          <h3 class="category-card-title">${cat.title}</h3>
          <p class="category-card-desc">${cat.description || "Scientific data from NASA observations."}</p>
          ${
            cat.predefined_config
              ? `<div class="category-card-config-pill">
                   <span>${cat.predefined_config.label}</span> •
                   <strong>${cat.predefined_config.vmin} to ${cat.predefined_config.vmax} ${cat.predefined_config.units}</strong>
                 </div>`
              : ""
          }
          <div class="category-card-footer">
            <span class="category-card-count">🖼️ ${cat.image_count} preloaded example${cat.image_count === 1 ? "" : "s"}</span>
            <span class="category-card-action">Select Category &amp; Explore →</span>
          </div>
        </div>
      `;

      const selectAction = () => this.selectCategory(cat);
      card.addEventListener("click", selectAction);
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          selectAction();
        }
      });

      this.cardsGrid.appendChild(card);
    });
  }

  selectCategory(category, preselectedImage = null) {
    this.activeCategory = category;
    this.selectedImage = preselectedImage;

    if (this.btnSonifyExample) {
      if (preselectedImage) {
        this.btnSonifyExample.removeAttribute("aria-disabled");
        this.btnSonifyExample.classList.remove("disabled");
      } else {
        this.btnSonifyExample.setAttribute("aria-disabled", "true");
        this.btnSonifyExample.classList.add("disabled");
      }
    }

    // Switch view sections
    if (this.introCard) this.introCard.classList.add("hidden");
    if (this.openingGalleryControls) this.openingGalleryControls.classList.add("hidden");
    if (this.openingGallerySection) this.openingGallerySection.classList.add("hidden");
    if (this.cardsGrid) this.cardsGrid.classList.add("hidden");
    if (this.detailPanel) this.detailPanel.classList.remove("hidden");

    // Populate Category Details
    if (this.detailTitle) this.detailTitle.textContent = category.title;
    if (this.detailDesc) this.detailDesc.textContent = category.description || "Scientific dataset visualization.";

    // Legend badge
    if (this.legendBadge) {
      this.legendBadge.textContent = category.has_legend ? "Colorbar Legend Included" : "Direct / Spatial Sonification";
      this.legendBadge.className = category.has_legend ? "badge badge-legend-yes" : "badge badge-legend-no";
    }

    // Markdown notes expander
    if (this.fullMarkdown) {
      this.fullMarkdown.innerHTML = formatMarkdownToHtml(category.info_markdown || "");
      this.fullMarkdown.classList.add("hidden");
      this.fullMarkdown.setAttribute("aria-hidden", "true");
    }
    if (this.btnToggleMarkdown) {
      this.btnToggleMarkdown.setAttribute("aria-expanded", "false");
      this.btnToggleMarkdown.textContent = "View Full Scientific Notes ▾";
    }

    // Optional Legend Display
    if (category.has_legend && category.legend_url) {
      if (this.legendImageWrap) this.legendImageWrap.classList.remove("hidden");
      if (this.legendImg) {
        this.legendImg.src = category.legend_url;
        this.legendImg.alt = `Colorbar legend for ${category.title}`;
      }
      if (this.legendNotes) {
        this.legendNotes.textContent = category.legend_info || "Maps scientific data values to colors according to the colorbar above.";
      }
      if (this.noLegendNotice) this.noLegendNotice.classList.add("hidden");
    } else {
      if (this.legendImageWrap) this.legendImageWrap.classList.add("hidden");
      if (this.legendImg) {
        this.legendImg.src = "";
        this.legendImg.alt = "";
      }
      if (this.noLegendNotice) this.noLegendNotice.classList.remove("hidden");
    }

    // Sonification Concept & Technique
    if (this.sonificationTechniqueBadge) {
      this.sonificationTechniqueBadge.textContent = category.sonification_technique || "Scientific Sonification";
    }
    if (this.sonificationDesc) {
      this.sonificationDesc.textContent =
        category.sonification_description ||
        category.sonification_concept ||
        "Data values are mapped to pitch, timbre, and stereo panning using Earth Jukebox's rigorous sonification engine.";
    }

    // Predefined configuration badges
    if (this.predefinedBadgesContainer) {
      this.predefinedBadgesContainer.innerHTML = "";
      const p = category.predefined_config;
      if (p) {
        const items = [
          { label: "Variable", val: p.label },
          {
            label: "Range",
            val: `${p.vmin} to ${p.vmax} ${p.units}` + (p.center !== null && p.center !== undefined ? ` (Center: ${p.center})` : ""),
          },
          { label: "Voice", val: (p.instrument_family || "pad").toUpperCase() },
          { label: "Colormap", val: p.kind },
        ];
        items.forEach((item) => {
          const chip = document.createElement("div");
          chip.className = "predefined-chip";
          chip.innerHTML = `<span class="chip-label">${item.label}:</span> <strong class="chip-val">${item.val}</strong>`;
          this.predefinedBadgesContainer.appendChild(chip);
        });
      }
    }

    // Data-to-sound mappings table
    if (this.soundMappingsContainer) {
      this.soundMappingsContainer.innerHTML = "";
      const mappings = Array.isArray(category.sound_mappings) ? category.sound_mappings : [];
      if (mappings.length > 0) {
        const table = document.createElement("table");
        table.className = "sound-mapping-table";
        table.setAttribute("aria-label", `Data to sound mapping specification for ${category.title}`);
        table.innerHTML = `
          <thead>
            <tr>
              <th scope="col">Scientific Data Feature</th>
              <th scope="col">Sound Feature / Parameter</th>
              <th scope="col">Sonification Technique</th>
            </tr>
          </thead>
          <tbody>
            ${mappings
              .map(
                (m) => `
              <tr>
                <td><strong>${m.data_characteristic}</strong></td>
                <td><span class="badge-sound">${m.sound_parameter}</span></td>
                <td>
                  <div>${m.technique}</div>
                  <small class="mapping-detail">${m.detail}</small>
                </td>
              </tr>
            `
              )
              .join("")}
          </tbody>
        `;
        this.soundMappingsContainer.appendChild(table);
      }
    }

    // Render Example Gallery
    this.renderExampleGallery(category, preselectedImage);

    // Scroll to detail top
    if (this.detailPanel) {
      this.detailPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  renderExampleGallery(category, preselectedImage = null) {
    if (!this.examplesGallery) return;
    this.examplesGallery.innerHTML = "";

    const images = Array.isArray(category.images) ? category.images : [];
    if (this.exampleCount) {
      this.exampleCount.textContent = String(images.length);
    }

    if (images.length === 0) {
      this.examplesGallery.innerHTML = `
        <div class="empty-state">
          <p>No preloaded example images found in this category.</p>
        </div>
      `;
      return;
    }

    const isSingleImage = images.length === 1;

    images.forEach((img, idx) => {
      const isSelected = preselectedImage ? preselectedImage.filename === img.filename : idx === 0;
      const displayTitle = formatObservationDisplayTitle(img.title, img.filename);
      const mission = getMissionLabel(img.filename, category.id);

      const item = document.createElement("div");
      item.className = `example-gallery-card ${isSingleImage ? "featured-single-card" : ""} ${isSelected ? "selected" : ""}`;
      item.setAttribute("role", "radio");
      item.setAttribute("aria-checked", String(isSelected));
      item.setAttribute("tabindex", "0");
      item.setAttribute("aria-label", `Observation: ${displayTitle}`);

      item.innerHTML = `
        <div class="example-thumb-wrap">
          <img src="${img.thumb_url}" alt="${displayTitle}" class="example-thumb-img" loading="lazy">
        </div>
        <div class="example-info">
          <span class="example-mission-sub">${mission}</span>
          <strong class="example-title" title="${displayTitle}">${displayTitle}</strong>
          <span class="example-filename">${img.filename}</span>
          ${
            isSingleImage
              ? `<div class="featured-card-badge">✨ Featured Preloaded NASA Observation</div>`
              : ""
          }
        </div>
      `;

      const selectImg = () => {
        this.examplesGallery.querySelectorAll(".example-gallery-card").forEach((c) => {
          c.classList.remove("selected");
          c.setAttribute("aria-checked", "false");
        });

        item.classList.add("selected");
        item.setAttribute("aria-checked", "true");
        this.selectedImage = img;

        if (this.btnSonifyExample) {
          this.btnSonifyExample.removeAttribute("aria-disabled");
          this.btnSonifyExample.classList.remove("disabled");
          this.btnSonifyExample.focus();
        }
      };

      item.addEventListener("click", selectImg);
      item.addEventListener("dblclick", () => {
        selectImg();
        this.handleProceedWithSelected();
      });
      item.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          selectImg();
        }
      });

      this.examplesGallery.appendChild(item);

      if (isSelected) {
        this.selectedImage = img;
        if (this.btnSonifyExample) {
          this.btnSonifyExample.removeAttribute("aria-disabled");
          this.btnSonifyExample.classList.remove("disabled");
        }
      }
    });
  }

  async handleProceedWithSelected() {
    if (!this.activeCategory || !this.selectedImage) {
      if (this.onError) this.onError("Please select an example image to continue.");
      return;
    }

    if (this.btnSonifyExample) {
      this.btnSonifyExample.disabled = true;
      this.btnSonifyExample.textContent = "Loading image…";
    }

    try {
      const blob = await fetchCategoryImageBlob(
        this.activeCategory.id,
        this.selectedImage.filename
      );

      if (this.onSelectExample) {
        this.onSelectExample({
          category: this.activeCategory,
          image: this.selectedImage,
          imageBlob: blob,
        });
      }
    } catch (err) {
      if (this.onError) {
        this.onError(`Failed to load selected image: ${err.message}`);
      }
    } finally {
      if (this.btnSonifyExample) {
        this.btnSonifyExample.disabled = false;
        this.btnSonifyExample.textContent = "Sonify Selected Image →";
      }
    }
  }

  showCategoryList() {
    this.activeCategory = null;
    this.selectedImage = null;

    if (this.introCard) this.introCard.classList.remove("hidden");
    if (this.openingGalleryControls) this.openingGalleryControls.classList.remove("hidden");
    if (this.detailPanel) this.detailPanel.classList.add("hidden");

    this.setViewMode(this.currentViewMode || "gallery");
  }

  show() {
    if (this.viewContainer) this.viewContainer.classList.remove("hidden");
  }

  hide() {
    if (this.viewContainer) this.viewContainer.classList.add("hidden");
  }
}
