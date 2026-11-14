/**
 * Server render and downloads UI (F-075).
 */

import { getRenderUrl } from "../api/client.js";

export class DownloadsUI {
  constructor() {
    this.menuBtn = document.getElementById("btn-download-menu");
    this.menu = document.getElementById("download-menu");
    this.playWavBtn = document.getElementById("btn-play-wav");
    this.downloadWavLink = document.getElementById("link-download-wav");
    this.downloadMidLink = document.getElementById("link-download-mid");
    this.downloadJsonLink = document.getElementById("link-download-json");
    this.audioEl = document.getElementById("rendered-audio");

    this.analysisId = null;
    this.skin = "neutral";
    this.nCols = 48;

    this._initMenu();
  }

  _initMenu() {
    if (this.menuBtn && this.menu) {
      this.menuBtn.addEventListener("click", () => {
        if (this.menuBtn.getAttribute("aria-disabled") === "true") return;
        const expanded = this.menuBtn.getAttribute("aria-expanded") === "true";
        this.menuBtn.setAttribute("aria-expanded", String(!expanded));
        this.menu.classList.toggle("hidden", expanded);
      });

      // Close menu on click outside
      window.addEventListener("click", (e) => {
        if (!this.menuBtn.contains(e.target) && !this.menu.contains(e.target)) {
          this.menuBtn.setAttribute("aria-expanded", "false");
          this.menu.classList.add("hidden");
        }
      });
    }

    if (this.playWavBtn && this.audioEl) {
      this.playWavBtn.addEventListener("click", () => {
        if (!this.analysisId) return;
        const url = getRenderUrl(this.analysisId, "wav", this.skin, this.nCols);
        this.audioEl.src = url;
        this.audioEl.play().catch(() => {});
        if (this.menu) this.menu.classList.add("hidden");
        if (this.menuBtn) this.menuBtn.setAttribute("aria-expanded", "false");
      });
    }
  }

  setAnalysis(analysisId, skin = "neutral", nCols = 48) {
    this.analysisId = analysisId;
    this.skin = skin;
    this.nCols = nCols;

    const hasAnalysis = Boolean(analysisId);
    if (this.menuBtn) {
      this.menuBtn.setAttribute("aria-disabled", String(!hasAnalysis));
    }

    if (hasAnalysis) {
      if (this.downloadWavLink) {
        this.downloadWavLink.href = getRenderUrl(analysisId, "wav", skin, nCols);
        this.downloadWavLink.setAttribute("download", `earth_jukebox_${analysisId}.wav`);
      }
      if (this.downloadMidLink) {
        this.downloadMidLink.href = getRenderUrl(analysisId, "mid", skin, nCols);
        this.downloadMidLink.setAttribute("download", `earth_jukebox_${analysisId}.mid`);
      }
      if (this.downloadJsonLink) {
        this.downloadJsonLink.href = getRenderUrl(analysisId, "json", skin, nCols);
        this.downloadJsonLink.setAttribute("download", `earth_jukebox_${analysisId}.score.json`);
      }
    }
  }
}
