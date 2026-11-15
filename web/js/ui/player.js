/**
 * Player UI component with synced playhead (F-073, F-074).
 */

import { playheadX, beatAtSeconds } from "../core/playhead.js";
import { frameAtBeat, beatForFrame } from "../core/time-mode.js";
import { formatTime, formatValue } from "../core/format.js";
import { getSkins } from "../api/client.js";

export class PlayerUI {
  /**
   * @param {object} options
   * @param {import("../audio/engine.js").AudioEngine} options.audioEngine
   * @param {import("./box-editor.js").BoxEditorUI} options.boxEditor
   * @param {import("./time-mode.js").TimeModeUI} [options.timeModeUI]
   * @param {(skinId: string) => void} options.onSkinChange
   */
  constructor({ audioEngine, boxEditor, timeModeUI = null, onSkinChange }) {
    this.audio = audioEngine;
    this.boxEditor = boxEditor;
    this.timeModeUI = timeModeUI;
    this.onSkinChange = onSkinChange;

    this.playBtn = document.getElementById("btn-play");
    this.stopBtn = document.getElementById("btn-stop");
    this.scrubber = document.getElementById("player-scrub");
    this.timeDisplay = document.getElementById("player-time");
    this.skinSelect = document.getElementById("skin-select");

    this.score = null;
    this.grid = null;
    this.legend = null;
    this.animFrameId = null;

    this._initControls();
    this._initSkins();
    this._startAnimLoop();
  }

  _initControls() {
    if (this.playBtn) {
      this.playBtn.addEventListener("click", () => this.togglePlay());
    }

    if (this.stopBtn) {
      this.stopBtn.addEventListener("click", () => this.stop());
    }

    if (this.scrubber) {
      this.scrubber.addEventListener("input", (e) => {
        const pct = Number(e.target.value) / 100.0;
        const dur = this.audio.getDuration();
        if (dur > 0) {
          this.audio.seek(pct * dur);
        }
      });
    }

    if (this.skinSelect) {
      this.skinSelect.addEventListener("change", (e) => {
        if (this.onSkinChange) {
          this.onSkinChange(e.target.value);
        }
      });
    }

    // Space key toggle shortcut (Smoke test S-05/S-06)
    window.addEventListener("keydown", (e) => {
      const tag = e.target?.tagName?.toLowerCase();
      if (tag === "input" || tag === "select" || tag === "textarea") {
        return;
      }
      if (e.key === " " || e.code === "Space") {
        e.preventDefault();
        this.togglePlay();
      }
    });

    this.audio.onEnded = () => {
      this.updatePlayBtn(false);
      this.boxEditor.hidePlayhead();
    };
  }

  async _initSkins() {
    if (!this.skinSelect) return;
    try {
      const skins = await getSkins();
      this.skinSelect.innerHTML = "";
      skins.forEach((s) => {
        const opt = document.createElement("option");
        opt.value = s.id;
        const prov = s.provisional ? " (provisional)" : "";
        opt.textContent = `${s.name}${prov}`;
        this.skinSelect.appendChild(opt);
      });
    } catch {
      // ignore
    }
  }

  setScore(score, grid, legend) {
    this.score = score;
    this.grid = grid;
    this.legend = legend;
    this.audio.loadScore(score);
    this.updateTimeDisplay(0, this.audio.getDuration());
    if (this.scrubber) this.scrubber.value = "0";
  }

  async togglePlay() {
    if (!this.score) return;
    const state = this.audio.getState();
    if (state === "started") {
      this.audio.pause();
      this.updatePlayBtn(false);
    } else {
      await this.audio.play();
      this.updatePlayBtn(true);
    }
  }

  stop() {
    this.audio.stop();
    this.updatePlayBtn(false);
    this.boxEditor.hidePlayhead();
    if (this.scrubber) this.scrubber.value = "0";
    this.updateTimeDisplay(0, this.audio.getDuration());
    this.boxEditor.setReadout("—");
  }

  updatePlayBtn(isPlaying) {
    if (!this.playBtn) return;
    if (isPlaying) {
      this.playBtn.innerHTML = `<span class="btn-icon-symbol"></span> Pause`;
      this.playBtn.setAttribute("aria-label", "Pause audio");
    } else {
      this.playBtn.innerHTML = `<span class="btn-icon-symbol"></span> Play`;
      this.playBtn.setAttribute("aria-label", "Play audio");
    }
  }

  updateTimeDisplay(current, duration) {
    if (this.timeDisplay) {
      this.timeDisplay.textContent = `${formatTime(current)} / ${formatTime(duration)}`;
    }
  }

  seekToFrame(frameIndex) {
    if (!this.score) return;
    const bpm = this.score?.bpm || 96.0;
    const frameBeats = Number(this.score?.provenance?.frame_beats || 48);
    const restBeats = Number(this.score?.provenance?.rest_beats || 1);
    const startBeat = beatForFrame(frameIndex, frameBeats, restBeats);
    const targetSeconds = (startBeat * 60) / bpm;
    this.audio.seek(targetSeconds);
  }

  _startAnimLoop() {
    const loop = () => {
      const state = this.audio.getState();
      const current = this.audio.getCurrentTime();
      const duration = this.audio.getDuration();

      if (state === "started" && duration > 0) {
        this.updateTimeDisplay(current, duration);

        if (this.scrubber) {
          this.scrubber.value = String(((current / duration) * 100).toFixed(1));
        }

        const bpm = this.score?.bpm || 96.0;
        const totalBeats = this.score?.total_beats || 48.0;
        const tBeat = beatAtSeconds(current, bpm);
        const bounds = this.boxEditor.getMapBounds();

        const isTimeMode = this.score?.provenance?.time_mode === "true";
        if (isTimeMode && this.timeModeUI) {
          const nFrames = Number(this.score?.provenance?.n_frames || 1);
          const frameBeats = Number(this.score?.provenance?.frame_beats || 48);
          const restBeats = Number(this.score?.provenance?.rest_beats || 1);
          const info = frameAtBeat(tBeat, frameBeats, restBeats, nFrames);
          this.timeModeUI.setActiveFrame(info.frameIndex, info.isRest);

          const px = playheadX(info.phraseBeat, frameBeats, bounds.left, bounds.width);
          this.boxEditor.setPlayheadPosition(px);

          const nCols = this.score?.n_cols || 48;
          const col = Math.min(nCols - 1, Math.max(0, Math.floor(info.phraseBeat)));
          const restLabel = info.isRest ? " [Rest]" : "";
          this.boxEditor.setReadout(
            `Frame ${info.frameIndex + 1}/${nFrames} • Beat ${info.phraseBeat.toFixed(1)} (Col ${col + 1}/${nCols})${restLabel}`
          );
        } else {
          const px = playheadX(tBeat, totalBeats, bounds.left, bounds.width);
          this.boxEditor.setPlayheadPosition(px);

          // Update value readout under current beat / column
          const nCols = this.score?.n_cols || 48;
          const col = Math.min(nCols - 1, Math.max(0, Math.floor(tBeat)));
          this.boxEditor.setReadout(`Beat ${tBeat.toFixed(1)} (Col ${col + 1}/${nCols})`);
        }
      }

      this.animFrameId = requestAnimationFrame(loop);
    };

    this.animFrameId = requestAnimationFrame(loop);
  }
}
