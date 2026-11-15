/**
 * Frontend Composition Root (web/js/main.js).
 * Wires together API client, AudioEngine, and UI components.
 */

import {
  getHealth,
  getSample,
  getSampleImageUrl,
  analyzeSample,
  analyzeImage,
  sonify,
  fetchCategoryImageBlob,
} from "./api/client.js";
import { AudioEngine } from "./audio/engine.js";
import { ShellUI } from "./ui/shell.js";
import { BoxEditorUI } from "./ui/box-editor.js";
import { GalleryUI } from "./ui/gallery.js";
import { UploadUI } from "./ui/upload.js";
import { PlayerUI } from "./ui/player.js";
import { DownloadsUI } from "./ui/downloads.js";
import { LegendSweepUI } from "./ui/legend-sweep.js";
import { ExplainerUI } from "./ui/explainer.js";
import { FidelityUI } from "./ui/fidelity.js";
import { ExploreUI } from "./ui/explore.js";
import { TimeModeUI } from "./ui/time-mode.js";
import { CategorySelectionUI } from "./ui/category-selection.js";

function getCategoryFormDefaults(category) {
  if (category && category.predefined_config) {
    const p = category.predefined_config;
    return {
      label: p.label,
      units: p.units,
      vmin: p.vmin,
      vmax: p.vmax,
      kind: p.kind,
      center: p.center,
      category: p.category,
      scale: p.scale || "linear",
      orientation: p.orientation || "horizontal",
      low_at_start: p.low_at_start !== undefined ? p.low_at_start : true,
      instrument_family: p.instrument_family || "pad",
    };
  }
  const lower = (category.id || "").toLowerCase();
  if (lower.includes("temp")) {
    return {
      label: "Near-Surface Temperature (T2M)",
      units: "°C",
      vmin: -40,
      vmax: 40,
      kind: "diverging",
      center: 0,
      category: "temperature",
      scale: "linear",
      orientation: "horizontal",
    };
  }
  if (lower.includes("wind")) {
    return {
      label: "Near-Surface Wind Speed",
      units: "m/s",
      vmin: 0,
      vmax: 40,
      kind: "sequential",
      center: null,
      category: "ocean",
      scale: "linear",
      orientation: "horizontal",
    };
  }
  if (lower.includes("precip") || lower.includes("cloud")) {
    return {
      label: "Precipitation Rate",
      units: "mm",
      vmin: 0,
      vmax: 20,
      kind: "sequential",
      center: null,
      category: "precipitation",
      scale: "linear",
      orientation: "horizontal",
    };
  }
  if (lower.includes("aerosol") || lower.includes("aerols")) {
    return {
      label: "Aerosol Optical Thickness",
      units: "AOD",
      vmin: 0,
      vmax: 5,
      kind: "sequential",
      center: null,
      category: "aerosol",
      scale: "linear",
      orientation: "horizontal",
    };
  }
  if (lower.includes("lightning")) {
    return {
      label: "Lightning Flash Density",
      units: "flashes/area",
      vmin: 0,
      vmax: 1,
      kind: "sequential",
      center: null,
      category: "precipitation",
      scale: "linear",
      orientation: "horizontal",
    };
  }
  if (lower.includes("hubble") || lower.includes("deep") || lower.includes("space")) {
    return {
      label: "Astronomical Flux / Luminance",
      units: "rel. flux",
      vmin: 0,
      vmax: 100,
      kind: "sequential",
      center: null,
      category: "ice",
      scale: "linear",
      orientation: "horizontal",
    };
  }
  if (lower.includes("veg") || lower.includes("land") || lower.includes("ndvi")) {
    return {
      label: "Normalized Difference Vegetation Index (NDVI)",
      units: "NDVI",
      vmin: -0.1,
      vmax: 0.9,
      kind: "sequential",
      center: null,
      category: "vegetation",
      scale: "linear",
      orientation: "horizontal",
    };
  }
  return {
    label: category.title || "Observation",
    units: "units",
    vmin: 0,
    vmax: 100,
    kind: "sequential",
    center: null,
    category: "generic",
    scale: "linear",
    orientation: "horizontal",
  };
}

class App {
  constructor() {
    this.shell = new ShellUI();
    this.boxEditor = new BoxEditorUI();
    this.audio = new AudioEngine();
    this.explainer = new ExplainerUI();
    this.fidelity = new FidelityUI();
    this.downloads = new DownloadsUI();
    this.legendSweep = new LegendSweepUI({
      audioEngine: this.audio,
      boxEditor: this.boxEditor,
    });
    this.explore = new ExploreUI({
      audioEngine: this.audio,
      boxEditor: this.boxEditor,
    });
    this.timeMode = new TimeModeUI({
      onSelectFrame: (idx) => this.player.seekToFrame(idx),
    });

    this.currentAnalysisId = null;
    this.currentLegend = null;
    this.currentGrid = null;
    this.currentSkin = "neutral";
    this.currentScore = null;

    this.player = new PlayerUI({
      audioEngine: this.audio,
      boxEditor: this.boxEditor,
      timeModeUI: this.timeMode,
      onSkinChange: (newSkin) => this.handleSkinChange(newSkin),
    });

    this.upload = new UploadUI({
      onImageLoaded: (blob) => this.handleImageLoaded(blob),
      onAnalyze: (data) => this.handleCustomAnalyze(data),
      onSuggestColorbar: (box) => this.boxEditor.setBoxes({ colorbarBox: box }),
      onError: (msg) => this.shell.showError(msg),
    });

    const galleryContainer = document.getElementById("gallery-container");
    this.gallery = new GalleryUI(galleryContainer, (id) => this.handleSampleSelect(id));

    // Category Selection & Views Navigation (F-107)
    this.viewCategories = document.getElementById("view-categories");
    this.viewProcessing = document.getElementById("view-processing");
    this.btnGotoCategories = document.getElementById("btn-goto-categories");
    this.btnGotoProcessing = document.getElementById("btn-goto-processing");
    this.btnBackFromStage = document.getElementById("btn-back-from-stage");
    this.btnSwitchCategory = document.getElementById("btn-switch-category");
    this.stageActiveCategory = document.getElementById("stage-active-category");
    this.stageActiveImage = document.getElementById("stage-active-image");
    this.stageActiveImageSep = document.getElementById("stage-active-image-sep");
    this.activeCategoryPill = document.getElementById("active-category-pill");
    this.activeCategoryName = document.getElementById("active-category-name");

    this.categorySelection = new CategorySelectionUI({
      onSelectExample: (payload) => this.handleCategoryExampleSelect(payload),
      onSelectCustomUpload: (payload) => this.handleCategoryCustomUpload(payload),
      onDirectCustomUpload: () => this.handleDirectCustomUpload(),
      onError: (msg) => this.shell.showError(msg),
    });

    this.sessionMode = "dataset"; // "dataset" or "upload"

    if (this.btnGotoCategories) {
      this.btnGotoCategories.addEventListener("click", () => {
        this.showCategoryView();
        this.categorySelection.showCategoryList("gallery");
      });
    }
    if (this.btnGotoProcessing) {
      this.btnGotoProcessing.addEventListener("click", () => this.showProcessingView());
    }
    if (this.btnBackFromStage) {
      this.btnBackFromStage.addEventListener("click", () => {
        if (this.sessionMode === "upload") {
          this.showCategoryView();
          this.categorySelection.showCustomTypeSelection();
        } else {
          this.showCategoryView();
          this.categorySelection.showCategoryList("gallery");
        }
      });
    }
    if (this.btnSwitchCategory) {
      this.btnSwitchCategory.addEventListener("click", () => {
        this.showCategoryView();
        this.categorySelection.showCategoryList("gallery");
      });
    }
  }

  async init() {
    await this.checkHealth();
    await this.categorySelection.load();
    await this.gallery.load();
    await this.explainer.load();
    this.showCategoryView();
  }

  setSessionMode(mode) {
    this.sessionMode = mode;
    const tabGallery = document.getElementById("tab-gallery");
    const panelGallery = document.getElementById("panel-gallery");
    const tabUpload = document.getElementById("tab-upload");
    const panelUpload = document.getElementById("panel-upload");

    if (mode === "dataset") {
      // Preloaded dataset observation mode: Gallery tab active; Upload tab completely hidden!
      if (tabUpload) tabUpload.classList.add("hidden");
      if (panelUpload) panelUpload.classList.add("hidden");
      if (tabGallery) {
        tabGallery.classList.remove("hidden");
        tabGallery.click();
      }
      if (this.btnBackFromStage) {
        this.btnBackFromStage.textContent = "← Back to Preloaded Gallery";
      }
    } else if (mode === "upload") {
      // Custom image upload mode: Gallery tab hidden; Upload tab active and visible!
      if (tabGallery) tabGallery.classList.add("hidden");
      if (panelGallery) panelGallery.classList.add("hidden");
      if (tabUpload) {
        tabUpload.classList.remove("hidden");
        tabUpload.click();
      }
      if (this.btnBackFromStage) {
        this.btnBackFromStage.textContent = "← Change Image Type";
      }
    }
  }

  showCategoryView() {
    if (this.viewCategories) this.viewCategories.classList.remove("hidden");
    if (this.viewProcessing) this.viewProcessing.classList.add("hidden");
    if (this.btnGotoCategories) {
      this.btnGotoCategories.classList.add("active");
      this.btnGotoCategories.setAttribute("aria-current", "step");
    }
    if (this.btnGotoProcessing) {
      this.btnGotoProcessing.classList.remove("active");
      this.btnGotoProcessing.removeAttribute("aria-current");
    }
  }

  showProcessingView() {
    if (this.viewCategories) this.viewCategories.classList.add("hidden");
    if (this.viewProcessing) this.viewProcessing.classList.remove("hidden");
    if (this.btnGotoCategories) {
      this.btnGotoCategories.classList.remove("active");
      this.btnGotoCategories.removeAttribute("aria-current");
    }
    if (this.btnGotoProcessing) {
      this.btnGotoProcessing.classList.add("active");
      this.btnGotoProcessing.setAttribute("aria-current", "step");
    }
  }

  async checkHealth() {
    const statusEl = document.getElementById("status");
    try {
      const h = await getHealth();
      if (statusEl) {
        statusEl.textContent = `Backend v${h.version} (Mapping ${h.mapping_version})`;
      }
    } catch {
      if (statusEl) {
        statusEl.textContent = "Backend offline";
      }
    }
  }

  async handleImageLoaded(blob) {
    this.shell.hideError();
    try {
      await this.boxEditor.loadImage(blob);
    } catch (err) {
      this.shell.showError("Failed to render image on canvas");
    }
  }

  async handleCategoryExampleSelect({ category, image, imageBlob }) {
    this.shell.hideError();
    this.showProcessingView();
    this.setSessionMode("dataset");

    if (this.stageActiveCategory) this.stageActiveCategory.textContent = category.title;
    if (this.stageActiveImage) this.stageActiveImage.textContent = image.title;
    if (this.stageActiveImageSep) this.stageActiveImageSep.classList.remove("hidden");
    if (this.activeCategoryName) this.activeCategoryName.textContent = category.title;
    if (this.activeCategoryPill) this.activeCategoryPill.classList.remove("hidden");

    const defaults = getCategoryFormDefaults(category);
    this.upload.setCategory(category);
    this.upload.populateDefaults(defaults);
    this.updateHowToListenCategory(category);

    this.gallery.setCategory(
      category,
      async (img) => {
        try {
          const blob = await fetchCategoryImageBlob(category.id, img.filename);
          await this.handleCategoryExampleSelect({ category, image: img, imageBlob: blob });
        } catch (err) {
          this.shell.showError(`Failed to load scene: ${err.message}`);
        }
      },
      () => {
        this.showCategoryView();
        this.categorySelection.showCategoryList("gallery");
      }
    );

    try {
      await this.boxEditor.loadImage(imageBlob);
      this.upload.setImageBlob(imageBlob);

      const legend = {
        label: defaults.label,
        units: defaults.units,
        vmin: Number(defaults.vmin),
        vmax: Number(defaults.vmax),
        kind: defaults.kind,
        category: defaults.category,
        scale: defaults.scale || "linear",
        orientation: defaults.orientation || "horizontal",
        center: defaults.center !== null && defaults.center !== undefined ? Number(defaults.center) : null,
        low_at_start: true,
      };

      const res = await analyzeImage({
        imageBlob,
        legend,
        colorbarBox: null,
        preset: null,
        categoryId: category.id,
      });
      await this.applyAnalysisResult(res, legend, category);
    } catch (err) {
      this.shell.showError(err.message || "Failed to analyze example image");
    }
  }

  handleCategoryCustomUpload({ category, customType }) {
    this.shell.hideError();
    this.showProcessingView();
    this.setSessionMode("upload");

    const catTitle = customType ? customType.title : category.title;
    if (this.stageActiveCategory) this.stageActiveCategory.textContent = catTitle;
    if (this.stageActiveImage) this.stageActiveImage.textContent = "Custom Image Upload";
    if (this.stageActiveImageSep) this.stageActiveImageSep.classList.remove("hidden");
    if (this.activeCategoryName) this.activeCategoryName.textContent = catTitle;
    if (this.activeCategoryPill) this.activeCategoryPill.classList.remove("hidden");

    const defaults = customType
      ? {
          label: customType.title,
          units: customType.units,
          vmin: customType.vmin,
          vmax: customType.vmax,
          kind: customType.kind,
          center: customType.center,
          category: customType.categoryKey,
          scale: customType.scale,
          orientation: customType.orientation,
          low_at_start: true,
          instrument_family: customType.instrumentFamily,
        }
      : getCategoryFormDefaults(category);

    this.upload.setCategory(category);
    this.upload.populateDefaults(defaults);
    this.updateHowToListenCategory(category);

    // Update auto-supplied configuration card with legend status & logic
    const configTitle = document.getElementById("upload-config-category-title");
    const configLabel = document.getElementById("upload-config-label");
    const configRange = document.getElementById("upload-config-range");
    const configInstrument = document.getElementById("upload-config-instrument");
    const configTechnique = document.getElementById("upload-config-technique");
    const legendWrap = document.getElementById("upload-config-legend-wrap");
    const noLegendNotice = document.getElementById("upload-config-no-legend-notice");

    if (configTitle) configTitle.textContent = catTitle;
    if (configLabel) configLabel.textContent = defaults.label;
    if (configRange) configRange.textContent = `${defaults.vmin} to ${defaults.vmax} ${defaults.units}`;
    if (configInstrument) {
      configInstrument.textContent = customType
        ? customType.synthVoice
        : (defaults.instrument_family || "pad").toUpperCase() + " Synth";
    }
    if (configTechnique) {
      configTechnique.textContent =
        customType && !customType.hasLegend
          ? "Direct Spatial Luminance & Event Mapping"
          : "Colorbar Legend Inversion & Frequency Mapping";
    }

    if (customType && !customType.hasLegend) {
      if (legendWrap) legendWrap.classList.add("hidden");
      if (noLegendNotice) noLegendNotice.classList.remove("hidden");
    } else {
      if (noLegendNotice) noLegendNotice.classList.add("hidden");
    }
  }

  handleDirectCustomUpload() {
    this.categorySelection.showCustomTypeSelection();
  }

  updateHowToListenCategory(category) {
    const wrap = document.getElementById("active-category-listen-info");
    const titleEl = document.getElementById("listen-category-title");
    const badgeEl = document.getElementById("listen-category-badge");
    const techEl = document.getElementById("listen-category-technique");
    const mapWrap = document.getElementById("listen-category-mapping-wrap");

    if (!category || !wrap) return;
    wrap.classList.remove("hidden");
    if (titleEl) titleEl.textContent = `Category Sound Design: ${category.title}`;
    if (badgeEl) badgeEl.textContent = category.sonification_technique || "Sonification";
    if (techEl) techEl.textContent = category.sonification_description || category.description || "";

    if (mapWrap) {
      mapWrap.innerHTML = "";
      const mappings = Array.isArray(category.sound_mappings) ? category.sound_mappings : [];
      if (mappings.length > 0) {
        const table = document.createElement("table");
        table.className = "sound-mapping-table";
        table.setAttribute("aria-label", `Sound design mappings for ${category.title}`);
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
        mapWrap.appendChild(table);
      }
    }
  }

  async handleSampleSelect(sampleId) {
    this.shell.hideError();
    try {
      const meta = await getSample(sampleId);
      this.upload.populateFromMeta(meta);

      const imageUrl = getSampleImageUrl(sampleId);
      await this.boxEditor.loadImage(imageUrl);

      if (meta.colorbar_box) {
        this.boxEditor.setBoxes({
          colorbarBox: meta.colorbar_box,
          mapBox: meta.map_box,
        });
      }

      const res = await analyzeSample(sampleId);
      await this.applyAnalysisResult(res, meta.legend);
    } catch (err) {
      this.shell.showError(err.message || "Failed to analyze sample");
    }
  }

  async handleCustomAnalyze({ imageBlob, legend, preset, categoryId }) {
    this.shell.hideError();
    try {
      const activeCat = this.upload.currentCategory;
      const activeCatId = categoryId || (activeCat ? activeCat.id : undefined);
      const res = await analyzeImage({
        imageBlob,
        legend,
        colorbarBox: this.boxEditor.colorbarBox,
        preset,
        categoryId: activeCatId,
      });
      await this.applyAnalysisResult(res, legend, activeCat);
    } catch (err) {
      this.shell.showError(err.message || "Analysis failed");
    }
  }

  async applyAnalysisResult(analysis, legend, activeCategory = null) {
    this.currentAnalysisId = analysis.analysis_id;
    this.currentLegend = legend;
    this.currentGrid = analysis.grid;

    // Quality badge
    const quality = analysis.quality || {};
    this.shell.setQualityBadge(quality.confidence, quality.confidence_badge);

    // Legend / fallback notice
    const bannerEl = document.getElementById("fallback-banner");
    const isFallback = quality.recovery_mode === "luminance_fallback";
    if (bannerEl) {
      if (isFallback && activeCategory && activeCategory.has_legend === false) {
        bannerEl.textContent =
          "Spatial / Event Mode: This dataset uses spatial and discrete event sonification without a continuous colorbar.";
        bannerEl.classList.remove("banner-warning");
        bannerEl.classList.add("banner-info");
      } else {
        bannerEl.textContent =
          "Approximate: no colour legend was used, so this sound is not data-faithful.";
        bannerEl.classList.remove("banner-info");
        bannerEl.classList.add("banner-warning");
      }
    }
    this.shell.setFallbackBannerVisible(isFallback);

    // Time mode frame strip (F-093)
    if (analysis.is_animation && Array.isArray(analysis.frame_previews)) {
      this.timeMode.renderFrames(analysis.frame_previews, (idx) => this.player.seekToFrame(idx));
    } else {
      this.timeMode.clear();
    }

    // Sonify
    const sonResult = await sonify({
      analysisId: this.currentAnalysisId,
      skin: this.currentSkin,
      nCols: 48,
    });

    this.currentScore = sonResult.score;

    // Update player, audio legend, downloads, fidelity
    this.player.setScore(this.currentScore, this.currentGrid, this.currentLegend);
    this.legendSweep.setAnalysis(this.currentAnalysisId, this.currentLegend);
    this.downloads.setAnalysis(this.currentAnalysisId, this.currentSkin, 48);
    this.explore.setData({
      grid: this.currentGrid,
      legend: this.currentLegend,
      skin: sonResult.skin || { id: this.currentSkin },
    });

    this.fidelity.update({
      quality: analysis.quality,
      fidelity: sonResult.fidelity,
      mappingVersion: this.currentScore?.mapping_version,
      grid: analysis.grid,
      description: sonResult.description,
    });
  }

  async handleSkinChange(newSkin) {
    this.currentSkin = newSkin;
    if (!this.currentAnalysisId) return;

    try {
      const sonResult = await sonify({
        analysisId: this.currentAnalysisId,
        skin: this.currentSkin,
        nCols: 48,
      });

      this.currentScore = sonResult.score;
      this.player.setScore(this.currentScore, this.currentGrid, this.currentLegend);
      this.downloads.setAnalysis(this.currentAnalysisId, this.currentSkin, 48);
      this.explore.setSkin(sonResult.skin || { id: this.currentSkin });
    } catch (err) {
      this.shell.showError(err.message || "Failed to change skin");
    }
  }
}

// Start application on DOM ready
window.addEventListener("DOMContentLoaded", () => {
  const app = new App();
  app.init().catch(() => {});
});
