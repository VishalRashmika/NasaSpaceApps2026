/**
 * Explore Mode UI component (F-077, F-081).
 *
 * Implements:
 * - Keyboard navigation across grid (Arrow keys, Shift+Arrow, Home/End, PageUp/PageDown, Enter/Space, Esc)
 * - Pointer / touch drag exploration with retriggered tone on cell change
 * - Throttled ARIA live announcements (>= 250 ms)
 * - Optional haptic pulses via navigator.vibrate (10 + 40·u ms)
 * - Visual cell cursor overlay
 */

import {
  cursorToCell,
  moveCursor,
  cellToUtterance,
  resolveCellAudio,
  hapticDuration,
} from "../core/explore.js";

export class ExploreUI {
  /**
   * @param {object} options
   * @param {import("../audio/engine.js").AudioEngine} options.audioEngine
   * @param {import("./box-editor.js").BoxEditorUI} options.boxEditor
   */
  constructor({ audioEngine, boxEditor }) {
    this.audio = audioEngine;
    this.boxEditor = boxEditor;

    this.exploreBtn = document.getElementById("btn-explore");
    this.hapticsToggle = document.getElementById("toggle-haptics");
    this.liveRegion = document.getElementById("explore-live");
    this.cursorEl = document.getElementById("explore-cursor");
    this.canvas = document.getElementById("map-canvas");
    this.container = document.getElementById("canvas-container");

    this.isActive = false;
    this.hapticsEnabled = false;

    this.grid = null;
    this.legend = null;
    this.skin = null;

    this.nCols = 48;
    this.nBands = 5;
    this.currentCell = { col: 0, band: 0 };

    this.isPointerDown = false;
    this.lastAnnouncementTime = 0;
    this.pendingAnnouncement = null;
    this.throttleTimer = null;

    this._initControls();
    this._initKeyboard();
    this._initPointer();
  }

  setData({ grid, legend, skin }) {
    this.grid = grid;
    this.legend = legend;
    this.skin = skin;

    if (grid && Array.isArray(grid)) {
      this.nBands = grid.length;
      this.nCols = grid[0] ? grid[0].length : 48;
    } else if (grid && Array.isArray(grid.data)) {
      this.nBands = grid.data.length;
      this.nCols = grid.data[0] ? grid.data[0].length : 48;
    } else if (grid && typeof grid.rows === "number" && typeof grid.cols === "number") {
      this.nBands = grid.rows;
      this.nCols = grid.cols;
    }

    if (this.exploreBtn) {
      const hasData = Boolean(this.grid);
      this.exploreBtn.removeAttribute("aria-disabled");
      this.exploreBtn.disabled = !hasData;
    }

    if (this.isActive) {
      this.updateCursorVisual();
    }
  }

  setSkin(skin) {
    this.skin = skin;
  }

  _initControls() {
    if (this.exploreBtn) {
      this.exploreBtn.addEventListener("click", () => {
        this.toggleMode();
      });
    }

    if (this.hapticsToggle) {
      this.hapticsToggle.addEventListener("change", (e) => {
        this.hapticsEnabled = Boolean(e.target.checked);
      });
    }
  }

  toggleMode(force) {
    const nextState = typeof force === "boolean" ? force : !this.isActive;
    this.isActive = nextState;

    if (this.exploreBtn) {
      this.exploreBtn.setAttribute("aria-pressed", String(this.isActive));
      this.exploreBtn.classList.toggle("active", this.isActive);
    }

    if (this.cursorEl) {
      this.cursorEl.classList.toggle("hidden", !this.isActive);
    }

    if (this.isActive) {
      // Focus container for keyboard navigation
      if (this.container) {
        this.container.focus();
      }
      this.updateCursorVisual();
      this.announceCell(this.currentCell, true);
    } else {
      if (this.boxEditor) {
        this.boxEditor.setReadout("—");
      }
    }
  }

  _initKeyboard() {
    window.addEventListener("keydown", (e) => {
      if (!this.isActive) return;

      const tag = e.target?.tagName?.toLowerCase();
      if (tag === "input" || tag === "select" || tag === "textarea") {
        return;
      }

      const keys = ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End", "PageUp", "PageDown"];
      if (keys.includes(e.key)) {
        e.preventDefault();
        const nextCell = moveCursor(this.currentCell, e.key, e.shiftKey, this.nCols, this.nBands);
        this.selectCell(nextCell);
        return;
      }

      if (e.key === "Enter" || e.key === " " || e.code === "Space") {
        e.preventDefault();
        this.playCurrentCell();
        return;
      }

      if (e.key === "Escape") {
        e.preventDefault();
        this.toggleMode(false);
      }
    });
  }

  _initPointer() {
    const target = this.container || this.canvas;
    if (!target) return;

    const handlePointer = (e) => {
      const rect = this.canvas.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return;

      const clientX = e.clientX ?? (e.touches && e.touches[0] ? e.touches[0].clientX : 0);
      const clientY = e.clientY ?? (e.touches && e.touches[0] ? e.touches[0].clientY : 0);

      const xNorm = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      const yNorm = Math.max(0, Math.min(1, (clientY - rect.top) / rect.height));

      const cell = cursorToCell(xNorm, yNorm, this.nCols, this.nBands);

      if (!this.isActive) {
        this.toggleMode(true);
      }

      if (cell.col !== this.currentCell.col || cell.band !== this.currentCell.band || !this.isPointerDown) {
        this.selectCell(cell);
      }
    };

    target.addEventListener("pointerdown", (e) => {
      this.isPointerDown = true;
      target.setPointerCapture?.(e.pointerId);
      handlePointer(e);
    });

    target.addEventListener("pointermove", (e) => {
      if (this.isPointerDown) {
        handlePointer(e);
      }
    });

    const endPointer = (e) => {
      this.isPointerDown = false;
      target.releasePointerCapture?.(e.pointerId);
    };

    target.addEventListener("pointerup", endPointer);
    target.addEventListener("pointercancel", endPointer);
  }

  selectCell(cell) {
    this.currentCell = cell;
    this.updateCursorVisual();
    this.playCurrentCell();
    this.announceCell(cell);
    this.triggerHaptic(cell);
  }

  updateCursorVisual() {
    if (!this.cursorEl || !this.canvas) return;

    const rect = this.canvas.getBoundingClientRect();
    const cellW = rect.width / this.nCols;
    const cellH = rect.height / this.nBands;

    this.cursorEl.style.left = `${this.currentCell.col * cellW}px`;
    this.cursorEl.style.top = `${this.currentCell.band * cellH}px`;
    this.cursorEl.style.width = `${Math.max(4, cellW)}px`;
    this.cursorEl.style.height = `${Math.max(4, cellH)}px`;
  }

  async playCurrentCell() {
    const audioData = resolveCellAudio(this.currentCell, this.grid, this.legend, this.skin);
    if (!audioData) return;

    // Masked cell -> silence
    if (audioData.val === null || Number.isNaN(audioData.freqHz)) {
      if (this.boxEditor) {
        this.boxEditor.setReadout(`Band ${this.currentCell.band + 1}, Col ${this.currentCell.col + 1}: No data`);
      }
      return;
    }

    if (this.boxEditor) {
      const units = this.legend?.units ? ` ${this.legend.units}` : "";
      this.boxEditor.setReadout(
        `Band ${this.currentCell.band + 1}, Col ${this.currentCell.col + 1}: ${audioData.val}${units}`
      );
    }

    try {
      await this.audio.playCellTone(audioData.freqHz, audioData.pan, audioData.instrument);
    } catch {
      // Audio autoplay block or context closed
    }
  }

  triggerHaptic(cell) {
    if (!this.hapticsEnabled) return;
    if (typeof navigator === "undefined" || typeof navigator.vibrate !== "function") return;

    const audioData = resolveCellAudio(cell, this.grid, this.legend, this.skin);
    const u = audioData?.u;
    const durMs = hapticDuration(u);
    if (durMs > 0) {
      try {
        navigator.vibrate(durMs);
      } catch {
        // Safe no-op
      }
    }
  }

  /**
   * Throttles announcements to at least 250 ms (F-078 AC, docs/09 §4).
   */
  announceCell(cell, immediate = false) {
    if (!this.liveRegion) return;

    const utterance = cellToUtterance(cell, this.grid, this.legend);
    const now = Date.now();
    const elapsed = now - this.lastAnnouncementTime;

    if (immediate || elapsed >= 250) {
      if (this.throttleTimer) {
        clearTimeout(this.throttleTimer);
        this.throttleTimer = null;
      }
      this.lastAnnouncementTime = now;
      this.liveRegion.textContent = utterance;
    } else {
      // Throttle and schedule update
      this.pendingAnnouncement = utterance;
      if (!this.throttleTimer) {
        this.throttleTimer = setTimeout(() => {
          this.lastAnnouncementTime = Date.now();
          if (this.liveRegion && this.pendingAnnouncement) {
            this.liveRegion.textContent = this.pendingAnnouncement;
          }
          this.throttleTimer = null;
        }, 250 - elapsed);
      }
    }
  }
}
