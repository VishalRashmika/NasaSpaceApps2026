/**
 * Audio Engine: Tone.js adapter (F-074, F-076).
 *
 * Exclusively manages Web Audio / Tone.js playback, synths, and scheduling.
 */

/* global Tone */

import { scoreToTriggers, midiToFreq } from "../core/schedule.js";
import { createMasterChain, createInstrument } from "./instruments.js";

const FAMILIES = ["pad", "pluck", "bell", "flute", "strings", "sub", "texture", "percussion"];

export class AudioEngine {
  constructor() {
    this.initialized = false;
    this.score = null;
    this.triggers = [];
    this.scheduledEvents = [];
    this.durationSec = 0;
    this.bpm = 96.0;

    this.master = null;
    this.instruments = new Map();
    this.panners = new Map();
    this.droneSynth = null;
    this.previewSynth = null;

    this.onNote = null;
    this.onEnded = null;
  }

  async ensureStarted() {
    if (typeof Tone === "undefined") {
      throw new Error("Tone.js library not loaded");
    }
    if (Tone.context.state !== "running") {
      await Tone.start();
    }
    if (!this.initialized) {
      this._initNodes();
      this.initialized = true;
    }
  }

  _initNodes() {
    const { master } = createMasterChain();
    this.master = master;

    for (const fam of FAMILIES) {
      const panner = new Tone.Panner(0).connect(this.master);
      const inst = createInstrument(fam, panner);
      this.instruments.set(fam, inst);
      this.panners.set(fam, panner);
    }

    this.droneSynth = new Tone.PolySynth(Tone.Synth, {
      oscillator: { type: "triangle" },
      envelope: { attack: 1.0, decay: 0.5, sustain: 0.9, release: 1.5 },
      volume: -14,
    }).connect(this.master);

    this.previewSynth = new Tone.Synth({
      oscillator: { type: "sine" },
      envelope: { attack: 0.01, decay: 0.15, sustain: 0.1, release: 0.15 },
      volume: -6,
    }).connect(this.master);

    Tone.Transport.on("stop", () => {
      this._releaseAll();
      if (this.onEnded) this.onEnded();
    });
  }

  _releaseAll() {
    for (const inst of this.instruments.values()) {
      if (inst.releaseAll) {
        inst.releaseAll();
      }
    }
    if (this.droneSynth && this.droneSynth.releaseAll) {
      this.droneSynth.releaseAll();
    }
  }

  loadScore(score) {
    this.stop();
    this._clearSchedule();

    this.score = score;
    if (!score) {
      this.triggers = [];
      this.durationSec = 0;
      return;
    }

    this.bpm = score.bpm && score.bpm > 0 ? score.bpm : 96.0;
    const totalBeats = score.total_beats && score.total_beats > 0 ? score.total_beats : 48.0;
    this.durationSec = (totalBeats * 60.0) / this.bpm;

    Tone.Transport.bpm.value = this.bpm;

    this.triggers = scoreToTriggers(score);

    // Schedule note triggers on Tone.Transport
    for (const tr of this.triggers) {
      const eventId = Tone.Transport.schedule((time) => {
        const inst = this.instruments.get(tr.instrument) || this.instruments.get("strings");
        const panner = this.panners.get(tr.instrument) || this.panners.get("strings");

        if (panner && typeof tr.pan === "number") {
          panner.pan.setValueAtTime(tr.pan, time);
        }

        if (inst) {
          const vel = tr.accent ? Math.min(1.0, tr.velocity * 1.3) : tr.velocity;
          if (inst.triggerAttackRelease) {
            inst.triggerAttackRelease(tr.freqHz, tr.durSec, time, vel);
          }
        }

        if (this.onNote) {
          this.onNote(tr);
        }
      }, tr.timeSec);

      this.scheduledEvents.push(eventId);
    }

    // Schedule drone bed if present
    if (score.drone_midi && Array.isArray(score.drone_midi) && score.drone_midi.length > 0) {
      const freqs = score.drone_midi.map((m) => midiToFreq(m));
      const droneId = Tone.Transport.schedule((time) => {
        if (this.droneSynth) {
          this.droneSynth.triggerAttackRelease(freqs, this.durationSec, time);
        }
      }, 0.0);
      this.scheduledEvents.push(droneId);
    }

    // Schedule stop event at the end of track
    const endId = Tone.Transport.schedule(() => {
      this.stop();
    }, this.durationSec);
    this.scheduledEvents.push(endId);
  }

  _clearSchedule() {
    for (const id of this.scheduledEvents) {
      Tone.Transport.clear(id);
    }
    this.scheduledEvents = [];
  }

  async play() {
    await this.ensureStarted();
    if (Tone.Transport.state !== "started") {
      Tone.Transport.start();
    }
  }

  pause() {
    if (typeof Tone !== "undefined" && Tone.Transport.state === "started") {
      Tone.Transport.pause();
      this._releaseAll();
    }
  }

  stop() {
    if (typeof Tone !== "undefined") {
      Tone.Transport.stop();
      Tone.Transport.seconds = 0;
      this._releaseAll();
    }
  }

  seek(seconds) {
    if (typeof Tone !== "undefined") {
      const clamped = Math.max(0, Math.min(this.durationSec, seconds));
      Tone.Transport.seconds = clamped;
    }
  }

  getState() {
    if (typeof Tone === "undefined") return "stopped";
    return Tone.Transport.state;
  }

  getCurrentTime() {
    if (typeof Tone === "undefined") return 0;
    return Tone.Transport.seconds;
  }

  getDuration() {
    return this.durationSec;
  }

  /**
   * Plays a single cell tone for Explore Mode (F-077).
   * Maps timbre by instrument family and pan by column x.
   */
  async playCellTone(freqHz, pan = 0, instrument = "strings") {
    await this.ensureStarted();
    const inst = this.instruments.get(instrument) || this.instruments.get("strings") || this.previewSynth;
    const panner = this.panners.get(instrument) || this.panners.get("strings");
    if (panner && typeof pan === "number") {
      panner.pan.setValueAtTime(pan, Tone.now());
    }
    if (inst && inst.triggerAttackRelease) {
      inst.triggerAttackRelease(freqHz, 0.2, Tone.now());
    } else if (this.previewSynth) {
      this.previewSynth.triggerAttackRelease(freqHz, 0.2);
    }
  }

  /**
   * Plays the audio legend sweep note-by-note (F-076).
   */
  async playAudioLegend(sweepNotes, onStep) {
    await this.ensureStarted();
    this.stop();

    if (!Array.isArray(sweepNotes) || sweepNotes.length === 0) {
      return;
    }

    const noteDur = 0.22;
    const synth = this.instruments.get("flute") || this.previewSynth;

    for (let i = 0; i < sweepNotes.length; i++) {
      const note = sweepNotes[i];
      const freq = note.freqHz || midiToFreq(note.pitch_midi || 60);

      if (onStep) {
        onStep(note, i, sweepNotes.length);
      }

      if (synth && synth.triggerAttackRelease) {
        synth.triggerAttackRelease(freq, noteDur);
      }

      // Small pause between notes
      await new Promise((resolve) => setTimeout(resolve, noteDur * 1000 + 40));
    }
  }
}
