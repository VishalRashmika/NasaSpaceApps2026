/**
 * Tone.js Instrument definitions for each family (F-074, docs/07 §7).
 *
 * Families: pad, pluck, bell, flute, strings, sub, texture, percussion.
 * Touches global Tone.
 */

/* global Tone */

export function createMasterChain() {
  const limiter = new Tone.Limiter(-1).toDestination();
  return { master: limiter };
}

export function createInstrument(family, master) {
  let synth;

  switch (family) {
    case "pad": {
      const filter = new Tone.Filter(1400, "lowpass");
      synth = new Tone.PolySynth(Tone.Synth, {
        oscillator: { type: "sawtooth" },
        envelope: { attack: 0.4, decay: 0.3, sustain: 0.7, release: 0.8 },
      });
      synth.chain(filter, master);
      return synth;
    }

    case "pluck": {
      synth = new Tone.PluckSynth({
        attackNoise: 1,
        dampening: 4000,
        resonance: 0.9,
      });
      synth.connect(master);
      return synth;
    }

    case "bell": {
      synth = new Tone.FMSynth({
        harmonicity: 3.01,
        modulationIndex: 12,
        oscillator: { type: "sine" },
        envelope: { attack: 0.005, decay: 2.0, sustain: 0.0, release: 2.0 },
        modulation: { type: "sine" },
        modulationEnvelope: { attack: 0.005, decay: 1.5, sustain: 0.0, release: 1.5 },
      });
      synth.connect(master);
      return synth;
    }

    case "flute": {
      const vibrato = new Tone.Vibrato(5.5, 0.15);
      synth = new Tone.Synth({
        oscillator: { type: "sine" },
        envelope: { attack: 0.08, decay: 0.2, sustain: 0.8, release: 0.3 },
      });
      synth.chain(vibrato, master);
      return synth;
    }

    case "strings": {
      const chorus = new Tone.Chorus(2.5, 3.5, 0.6);
      synth = new Tone.PolySynth(Tone.Synth, {
        oscillator: { type: "sawtooth" },
        envelope: { attack: 0.25, decay: 0.3, sustain: 0.7, release: 0.5 },
      });
      synth.chain(chorus, master);
      return synth;
    }

    case "sub": {
      synth = new Tone.Synth({
        oscillator: { type: "sine" },
        envelope: { attack: 0.1, decay: 0.4, sustain: 0.8, release: 0.5 },
      });
      synth.connect(master);
      return synth;
    }

    case "texture": {
      synth = new Tone.NoiseSynth({
        noise: { type: "pink" },
        envelope: { attack: 0.05, decay: 0.3, sustain: 0.2, release: 0.3 },
      });
      synth.connect(master);
      return synth;
    }

    case "percussion": {
      synth = new Tone.MembraneSynth({
        pitchDecay: 0.05,
        octaves: 4,
        oscillator: { type: "sine" },
        envelope: { attack: 0.001, decay: 0.4, sustain: 0.01, release: 0.4 },
      });
      synth.connect(master);
      return synth;
    }

    default: {
      synth = new Tone.PolySynth(Tone.Synth);
      synth.connect(master);
      return synth;
    }
  }
}
