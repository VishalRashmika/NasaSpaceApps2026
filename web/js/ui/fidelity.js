/**
 * Fidelity and Metadata display (F-079).
 */

export class FidelityUI {
  constructor() {
    this.confEl = document.getElementById("fid-confidence");
    this.badgeEl = document.getElementById("fid-badge");
    this.rEl = document.getElementById("fid-r");
    this.legendREl = document.getElementById("fid-legend-r");
    this.verEl = document.getElementById("fid-version");
    this.gridEl = document.getElementById("fid-grid");

    this.descCard = document.getElementById("description-card");
    this.descText = document.getElementById("description-text");
  }

  update({ quality, fidelity, mappingVersion, grid, description }) {
    if (quality) {
      if (this.confEl && typeof quality.confidence === "number") {
        this.confEl.textContent = `${(quality.confidence * 100).toFixed(1)}%`;
      }
      if (this.badgeEl && quality.confidence_badge) {
        this.badgeEl.textContent = quality.confidence_badge;
      }
    }

    if (fidelity) {
      if (this.rEl && typeof fidelity.round_trip_r === "number") {
        this.rEl.textContent = fidelity.round_trip_r.toFixed(4);
      }
      if (this.legendREl && typeof fidelity.legend_r === "number") {
        this.legendREl.textContent = fidelity.legend_r.toFixed(4);
      }
    }

    if (mappingVersion && this.verEl) {
      this.verEl.textContent = mappingVersion;
    }

    if (grid && this.gridEl) {
      this.gridEl.textContent = `${grid.rows} rows × ${grid.cols} cols`;
    }

    if (description && this.descCard && this.descText) {
      this.descText.textContent = description;
      this.descCard.classList.remove("hidden");
    }
  }
}
