/**
 * Upload & Legend form UI (F-072).
 */

import { validateLegendForm } from "../core/legend.js";
import { getColormaps, detectColorbar } from "../api/client.js";

export class UploadUI {
  /**
   * @param {object} options
   * @param {(blob: Blob) => void} options.onImageLoaded
   * @param {(analysisData: object) => void} options.onAnalyze
   * @param {(box: object) => void} options.onSuggestColorbar
   * @param {(msg: string) => void} options.onError
   */
  constructor({ onImageLoaded, onAnalyze, onSuggestColorbar, onError }) {
    this.onImageLoaded = onImageLoaded;
    this.onAnalyze = onAnalyze;
    this.onSuggestColorbar = onSuggestColorbar;
    this.onError = onError;

    this.currentBlob = null;

    this.uploadZone = document.getElementById("upload-zone");
    this.fileInput = document.getElementById("file-input");
    this.legendForm = document.getElementById("legend-form");
    this.presetSelect = document.getElementById("legend-preset");
    this.suggestCBoxBtn = document.getElementById("btn-suggest-cbox");

    this.kindSelect = document.getElementById("legend-kind");
    this.groupCenter = document.getElementById("group-center");

    // Category predefined configuration elements (F-108)
    this.configCategoryTitle = document.getElementById("upload-config-category-title");
    this.configLabel = document.getElementById("upload-config-label");
    this.configRange = document.getElementById("upload-config-range");
    this.configInstrument = document.getElementById("upload-config-instrument");
    this.configTechnique = document.getElementById("upload-config-technique");
    this.currentCategory = null;

    this._initDropZone();
    this._initForm();
    this.loadPresets();
  }

  async loadPresets() {
    if (!this.presetSelect) return;
    try {
      const presets = await getColormaps();
      this.presetSelect.innerHTML = `<option value="">None — Extract from image colorbar</option>`;
      const seqGroup = document.createElement("optgroup");
      seqGroup.label = "Sequential Colormaps";
      const divGroup = document.createElement("optgroup");
      divGroup.label = "Diverging Colormaps";

      presets.forEach((p) => {
        const opt = document.createElement("option");
        opt.value = p.name;
        opt.textContent = `${p.name} (${p.kind})`;
        if (p.kind === "diverging") {
          divGroup.appendChild(opt);
        } else {
          seqGroup.appendChild(opt);
        }
      });
      if (seqGroup.children.length > 0) this.presetSelect.appendChild(seqGroup);
      if (divGroup.children.length > 0) this.presetSelect.appendChild(divGroup);
    } catch {
      // ignore
    }
  }

  _initDropZone() {
    if (!this.uploadZone) return;

    this.uploadZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      this.uploadZone.classList.add("dragover");
    });

    this.uploadZone.addEventListener("dragleave", () => {
      this.uploadZone.classList.remove("dragover");
    });

    this.uploadZone.addEventListener("drop", (e) => {
      e.preventDefault();
      this.uploadZone.classList.remove("dragover");
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
        this.handleFile(e.dataTransfer.files[0]);
      }
    });

    if (this.fileInput) {
      this.fileInput.addEventListener("change", (e) => {
        if (e.target.files && e.target.files[0]) {
          this.handleFile(e.target.files[0]);
        }
      });
    }

    if (this.suggestCBoxBtn) {
      this.suggestCBoxBtn.addEventListener("click", () => this.suggestColorbar());
    }
  }

  handleFile(file) {
    if (!file) return;

    // Check size cap 20 MB
    if (file.size > 20 * 1024 * 1024) {
      this.onError("Upload exceeds the 20 MB file size limit.");
      return;
    }

    this.currentBlob = file;
    if (this.onImageLoaded) {
      this.onImageLoaded(file);
    }
  }

  setImageBlob(blob) {
    this.currentBlob = blob;
  }

  async suggestColorbar() {
    if (!this.currentBlob) {
      this.onError("Please upload or select an image first.");
      return;
    }

    try {
      this.suggestCBoxBtn.disabled = true;
      this.suggestCBoxBtn.textContent = "Detecting…";
      const res = await detectColorbar(this.currentBlob);
      if (res && res.candidates && res.candidates.length > 0) {
        const top = res.candidates[0];
        if (this.onSuggestColorbar) {
          this.onSuggestColorbar(top.box, top.orientation);
        }
        const orientSelect = document.getElementById("legend-orientation");
        if (orientSelect && top.orientation) {
          orientSelect.value = top.orientation;
        }
      } else {
        this.onError("No colorbar automatically detected. Please enter coordinates manually.");
      }
    } catch (err) {
      this.onError(err.message || "Failed to detect colorbar");
    } finally {
      this.suggestCBoxBtn.disabled = false;
      this.suggestCBoxBtn.textContent = "Suggest Colorbar";
    }
  }

  _initForm() {
    if (this.kindSelect && this.groupCenter) {
      this.kindSelect.addEventListener("change", () => {
        const isDiverging = this.kindSelect.value === "diverging";
        this.groupCenter.style.opacity = isDiverging ? "1" : "0.5";
      });
    }

    if (this.legendForm) {
      this.legendForm.addEventListener("submit", (e) => {
        e.preventDefault();
        this.submitForm();
      });
    }
  }

  setCategory(category) {
    this.currentCategory = category;
    if (!category) return;

    if (this.configCategoryTitle) {
      this.configCategoryTitle.textContent = category.title || "Selected Category";
    }

    const p = category.predefined_config;
    if (p) {
      if (this.configLabel) this.configLabel.textContent = p.label;
      if (this.configRange) {
        this.configRange.textContent =
          `${p.vmin} to ${p.vmax} ${p.units}` +
          (p.center !== null && p.center !== undefined ? ` (Center: ${p.center})` : "");
      }
      if (this.configInstrument) {
        this.configInstrument.textContent = (p.instrument_family || "pad").toUpperCase();
      }
      if (this.configTechnique) {
        this.configTechnique.textContent = category.sonification_technique || "Scientific Sonification";
      }
      this.populateDefaults(p);
    }

    // Populate legend and mappings preview inside upload config card
    const legendWrap = document.getElementById("upload-config-legend-wrap");
    const legendImg = document.getElementById("upload-config-legend-img");
    const legendNotes = document.getElementById("upload-config-legend-notes");
    const noLegendNotice = document.getElementById("upload-config-no-legend-notice");

    if (category.has_legend && category.legend_url) {
      if (legendWrap) legendWrap.classList.remove("hidden");
      if (legendImg) {
        legendImg.src = category.legend_url;
        legendImg.alt = `Colorbar legend for ${category.title}`;
      }
      if (legendNotes) legendNotes.textContent = category.legend_info || "";
      if (noLegendNotice) noLegendNotice.classList.add("hidden");
    } else {
      if (legendWrap) legendWrap.classList.add("hidden");
      if (legendImg) {
        legendImg.src = "";
        legendImg.alt = "";
      }
      if (noLegendNotice) noLegendNotice.classList.remove("hidden");
    }

    const mappingsTableContainer = document.getElementById("upload-config-mappings-table");
    if (mappingsTableContainer) {
      mappingsTableContainer.innerHTML = "";
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
        mappingsTableContainer.appendChild(table);
      }
    }
  }

  submitForm() {
    if (!this.currentBlob) {
      this.onError("Please select or upload an image before analyzing.");
      return;
    }

    // Auto-fill any empty fields from predefined category config (F-108)
    if (this.currentCategory && this.currentCategory.predefined_config) {
      const p = this.currentCategory.predefined_config;
      const el = (id) => document.getElementById(id);
      if (el("legend-label") && !el("legend-label").value) el("legend-label").value = p.label;
      if (el("legend-units") && !el("legend-units").value) el("legend-units").value = p.units;
      if (el("legend-vmin") && !el("legend-vmin").value) el("legend-vmin").value = String(p.vmin);
      if (el("legend-vmax") && !el("legend-vmax").value) el("legend-vmax").value = String(p.vmax);
      if (el("legend-kind") && !el("legend-kind").value) el("legend-kind").value = p.kind;
      if (el("legend-category") && !el("legend-category").value) el("legend-category").value = p.category;
      if (el("legend-scale") && !el("legend-scale").value) el("legend-scale").value = p.scale || "linear";
      if (el("legend-orientation") && !el("legend-orientation").value) el("legend-orientation").value = p.orientation || "horizontal";
      if (p.center !== null && p.center !== undefined && el("legend-center") && !el("legend-center").value) {
        el("legend-center").value = String(p.center);
      }
    }

    const values = this.getFormValues();
    this.clearErrors();

    const valResult = validateLegendForm(values);
    if (!valResult.ok) {
      this.showValidationErrors(valResult.errors);
      return;
    }

    const legend = {
      label: values.label,
      units: values.units,
      vmin: Number(values.vmin),
      vmax: Number(values.vmax),
      kind: values.kind,
      category: values.category,
      scale: values.scale,
      orientation: values.orientation,
      low_at_start: Boolean(values.low_at_start),
    };

    if (values.kind === "diverging" && values.center !== "") {
      legend.center = Number(values.center);
    }

    if (this.onAnalyze) {
      this.onAnalyze({
        imageBlob: this.currentBlob,
        legend,
        preset: values.preset || undefined,
        categoryId: this.currentCategory ? this.currentCategory.id : undefined,
      });
    }
  }

  getFormValues() {
    const valOf = (id) => {
      const el = document.getElementById(id);
      return el ? el.value : "";
    };

    return {
      label: valOf("legend-label"),
      units: valOf("legend-units"),
      vmin: valOf("legend-vmin"),
      vmax: valOf("legend-vmax"),
      kind: valOf("legend-kind"),
      category: valOf("legend-category"),
      scale: valOf("legend-scale"),
      orientation: valOf("legend-orientation"),
      center: valOf("legend-center"),
      preset: valOf("legend-preset"),
      low_at_start: document.getElementById("legend-low-at-start")?.checked ?? true,
    };
  }

  clearErrors() {
    ["err-label", "err-units", "err-vmin", "err-vmax", "err-center"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.textContent = "";
    });
  }

  showValidationErrors(errors) {
    if (errors.label) {
      const el = document.getElementById("err-label");
      if (el) el.textContent = errors.label;
    }
    if (errors.units) {
      const el = document.getElementById("err-units");
      if (el) el.textContent = errors.units;
    }
    if (errors.vmin) {
      const el = document.getElementById("err-vmin");
      if (el) el.textContent = errors.vmin;
    }
    if (errors.vmax) {
      const el = document.getElementById("err-vmax");
      if (el) el.textContent = errors.vmax;
    }
    if (errors.center) {
      const el = document.getElementById("err-center");
      if (el) el.textContent = errors.center;
    }
  }

  populateFromMeta(meta) {
    if (!meta) return;
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el && val !== undefined && val !== null) el.value = String(val);
    };

    if (meta.legend) {
      setVal("legend-label", meta.legend.label);
      setVal("legend-units", meta.legend.units);
      setVal("legend-vmin", meta.legend.vmin);
      setVal("legend-vmax", meta.legend.vmax);
      setVal("legend-kind", meta.legend.kind);
      setVal("legend-category", meta.legend.category);
      setVal("legend-scale", meta.legend.scale || "linear");
      setVal("legend-orientation", meta.legend.orientation || "horizontal");
      setVal("legend-center", meta.legend.center ?? "");

      const lowEl = document.getElementById("legend-low-at-start");
      if (lowEl && meta.legend.low_at_start !== undefined) {
        lowEl.checked = Boolean(meta.legend.low_at_start);
      }
    }
  }

  populateDefaults(defaults) {
    if (!defaults) return;
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el && val !== undefined && val !== null) el.value = String(val);
    };
    if (defaults.label !== undefined) setVal("legend-label", defaults.label);
    if (defaults.units !== undefined) setVal("legend-units", defaults.units);
    if (defaults.vmin !== undefined) setVal("legend-vmin", defaults.vmin);
    if (defaults.vmax !== undefined) setVal("legend-vmax", defaults.vmax);
    if (defaults.kind !== undefined) setVal("legend-kind", defaults.kind);
    if (defaults.category !== undefined) setVal("legend-category", defaults.category);
    if (defaults.scale !== undefined) setVal("legend-scale", defaults.scale || "linear");
    if (defaults.orientation !== undefined) setVal("legend-orientation", defaults.orientation || "horizontal");
    if (defaults.center !== undefined && defaults.center !== null) {
      setVal("legend-center", defaults.center);
    } else {
      setVal("legend-center", "");
    }
  }
}
