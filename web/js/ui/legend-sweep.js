/**
 * Audio Legend Sweep player and readout (F-076).
 */

import { formatValue } from "../core/format.js";
import { midiToFreq } from "../core/schedule.js";

export class LegendSweepUI {
  /**
   * @param {object} options
   * @param {import("../audio/engine.js").AudioEngine} options.audioEngine
   * @param {import("./box-editor.js").BoxEditorUI} options.boxEditor
   */
  constructor({ audioEngine, boxEditor }) {
    this.audio = audioEngine;
    this.boxEditor = boxEditor;
    this.btn = document.getElementById("btn-audio-legend");

    this.analysisId = null;
    this.legend = null;
    this.isPlaying = false;

    if (this.btn) {
      this.btn.addEventListener("click", () => this.playSweep());
    }
  }

  setAnalysis(analysisId, legend) {
    this.analysisId = analysisId;
    this.legend = legend;

    const enabled = Boolean(analysisId && legend);
    if (this.btn) {
      this.btn.setAttribute("aria-disabled", String(!enabled));
      this.btn.title = enabled
        ? "Play ascending audio legend sweep"
        : "Disabled until an image is analyzed";
    }
  }

  async playSweep() {
    if (!this.analysisId || !this.legend || this.isPlaying) {
      return;
    }

    this.isPlaying = true;
    if (this.btn) {
      this.btn.disabled = true;
      this.btn.textContent = "Playing Legend…";
    }

    const { vmin, vmax, units, kind, center } = this.legend;
    const nSteps = 32;
    const notes = [];

    for (let i = 0; i < nSteps; i++) {
      const u = i / (nSteps - 1);
      const val = vmin + u * (vmax - vmin);
      // Map u linearly to 2 octaves C4 (60) to C6 (84)
      const midi = 60.0 + u * 24.0;
      notes.push({
        value: val,
        freqHz: midiToFreq(midi),
        step: i + 1,
        total: nSteps,
        isCenter: kind === "diverging" && Math.abs(u - 0.5) < 0.03,
      });
    }

    try {
      await this.audio.playAudioLegend(notes, (note, idx, total) => {
        const valStr = formatValue(note.value, units);
        const centerMarker = note.isCenter ? " [Center / Baseline]" : "";
        this.boxEditor.setReadout(`Legend Sweep: ${valStr}${centerMarker} (${idx + 1}/${total})`);
      });
    } finally {
      this.isPlaying = false;
      if (this.btn) {
        this.btn.disabled = false;
        this.btn.innerHTML = `<span class="btn-icon-symbol"></span> Audio Legend`;
      }
    }
  }
}
