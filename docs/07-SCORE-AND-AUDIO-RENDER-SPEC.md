# 07 — Score Protocol & Audio Rendering Spec (Module AUD)

## 1. Roles

`Score` is the only thing the renderers see (D-04). Server renderer = deterministic NumPy synth → WAV. Browser renderer = Tone.js from the same JSON. MIDI export is a convenience view of the Score.

## 2. Score JSON wire schema (v1)

Serialisation rules: UTF-8, `separators=(",",":")`, key order exactly as below, floats rounded to **6 decimals** (`round(x, 6)`), no NaN/Infinity anywhere (use `null`), enums as strings, notes sorted by `(t_beat, voice_id, pitch_midi)`.

```json
{
  "schema": "earth-jukebox.score/1",
  "mapping_version": "1.0.0",
  "skin_id": "neutral",
  "seed": 123456789,
  "bpm": 96.0,
  "total_beats": 48.0,
  "n_cols": 48,
  "n_bands": 5,
  "legend": {
    "vmin": -4.0, "vmax": 4.0, "units": "°C", "label": "Temperature anomaly",
    "kind": "diverging", "category": "temperature", "center": 0.0,
    "orientation": "horizontal", "low_at_start": true, "scale": "linear"
  },
  "voices": [
    {"id": "band0", "band_index": 0, "instrument": "strings", "pan": -0.6}
  ],
  "drone_midi": [48.0, 55.0],
  "notes": [
    {"voice_id": "band0", "t_beat": 0.0, "dur_beat": 0.9, "pitch_midi": 60.0,
     "velocity": 0.7, "accent": false, "col": 0, "band": 0, "value": 0.12,
     "glide_to_midi": null, "roughness": 0.1, "kind": "main"}
  ],
  "provenance": {
    "recovery_mode": "colorbar", "confidence": "0.94", "warnings": "",
    "band_brightness": "0.6,0.85,1.15,0.85,0.6", "drone_brightness": "0.512"
  }
}
```
The same schema serves the legend sweep (voice id `legend`, `n_bands = 1`). Required: JSON Schema file `docs/schemas/score.schema.json` (created in P3) and a test that validates every produced Score against it (use `jsonschema`-free hand validation in tests or add `jsonschema` as a dev dependency — log it).

## 3. Instrument families (closed set)

`pad`, `pluck`, `bell`, `flute`, `strings`, `sub`, `texture`, `percussion`. New families require a Decision.

Server NumPy synth recipes (all at 44.1 kHz, float64 internally; band brightness `b` multiplies the filter cutoff / harmonic rolloff):

| Family | Recipe |
|---|---|
| `pad` | 3 detuned saws (±7 cents), low-pass 1.2 kHz·b, ADSR (0.4 / 0.3 / 0.7 / 0.8 s) |
| `pluck` | Karplus-Strong string (deterministic seeded noise burst), damping by `b`; decay ≈ `dur` |
| `bell` | additive partials at ratios 1, 2.76, 5.4, 8.93, exp. decay (2 s), velocity scales brightness |
| `flute` | sine + 2nd/3rd harmonic (0.3/0.1) + breath noise (−30 dB), 5.5 Hz vibrato depth 8 cents after 0.15 s |
| `strings` | 4 detuned saws, band-limited, slow attack 0.25 s, low-pass 2.5 kHz·b, ensemble chorus (2 delayed copies) |
| `sub` | sine + 2nd harmonic, mono, slow attack |
| `texture` | band-passed noise centred at note frequency; `roughness` widens the band |
| `percussion` | Skin pattern hits: membrane = decaying sine pitch-dropping 180→90 Hz + noise burst; accent hits brighter |

`roughness` r (0..1): adds detune spread `+r·12` cents and shifts cutoff ×`(1 + r)`.
All DSP filters are implemented with `scipy.signal` (infrastructure only) **or** pure NumPy; no real-time randomness — noise comes from a `numpy.random.default_rng(seed_for_note)` where `seed_for_note = score.seed ^ hash_of(col, band, index)` using a fixed integer hash (not Python's `hash()`).

## 4. Rendering rules (F-040…F-042)

1. seconds = `t_beat × 60 / bpm`. Note frequency `f = 440·2^((pitch_midi − 69)/12)` (fractional MIDI allowed).
2. Glide: if `glide_to_midi` is set, pitch moves linearly **in cents** from `pitch_midi` to `glide_to_midi` between 30 % and 100 % of the note.
3. Velocity → gain: `gain = velocity^1.5 × 0.25`.
4. Equal-power pan: `L = g·cos((pan+1)·π/4)`, `R = g·sin((pan+1)·π/4)`.
5. Drone: sine+triangle pair at `drone_midi`, gain 0.05, brightness hint scales a low-pass 400–1200 Hz; fades with the track.
6. Mix: sum all voices in float64; fade-in 50 ms, fade-out 500 ms; soft limiter `tanh(x/0.89)·0.89`; reserve a **tail** of 1.5 s after the last note end for decays.
7. Output: stereo, 44.1 kHz, 16-bit PCM via stdlib `wave`; quantise with `np.round(x*32767)`, clip to int16.
8. **Determinism:** single-threaded, no unseeded RNG, no time, no float32/float64 mixing differences across platforms beyond NumPy's own ops. Tests compare SHA-256 of WAV bytes between two runs in the same process/platform.

## 5. MIDI export (F-043)

`mido`: type 1 file, 480 ticks/beat, tempo meta from `bpm`. One track per voice (+ drone track). Channel = voice index (skip 9 unless the voice is `percussion`, which uses channel 9). Fractional pitch: base note `round(pitch)` + pitch-bend for the remainder, assuming bend range ±2 semitones (send RPN 0 = 2 at track start); bend resets after each note. Program numbers (General MIDI): pad 89, pluck 46, bell 14, flute 73, strings 49, sub 38, texture 95, percussion → channel 9 note 45.

## 6. Audio-level fidelity check (F-047)

Render the legend sweep (monophonic voice) with the `flute` or `sine`-based test renderer; YIN pitch detection (frame 2048, hop 512, fmin 80, fmax 2000, threshold 0.1) per note (median over the stable middle 50 % of each note); compare to expected `pitch_midi`: pass if ≤ 20 cents error; `audio_legend_r` = Pearson r between detected pitch and `value`.

## 7. Browser rendering (F-073, F-074)

**Pure core `scoreToTriggers(score)`** (web/js/core/schedule.js) → array of:
```js
{ timeSec, durSec, freqHz, glideToHz /*|null*/, velocity, pan, instrument, voiceId, accent, roughness, kind, col, band, value }
```
Rules identical to §4.1–§4.4 (frequency formula, glide semantics, gain curve is applied by the audio layer). Sorted by `timeSec`. Node-tested.

**Audio layer** (web/js/audio/): one Tone.js instrument per `instrument` family, mapped approximately: `pad`→`PolySynth(Synth,sawtooth)`+lowpass, `pluck`→`PluckSynth`, `bell`→`FMSynth` (harmonicity 3.01), `flute`→`Synth(sine)` + vibrato, `strings`→`PolySynth(sawtooth)` + chorus, `sub`→`Synth(sine)`, `texture`→`NoiseSynth`+bandpass, `percussion`→`MembraneSynth`. Each voice routes through `Tone.Panner(pan)` → master `Limiter`. Notes are scheduled by absolute `Tone.Transport` time. Audio starts only after a user gesture (`await Tone.start()`).

**Playhead:** `playheadX = mapLeft + clamp(t_beat/total_beats, 0, 1) × mapWidth` where `t_beat = elapsedSec × bpm / 60`, elapsedSec taken from `Tone.Transport.seconds` (the audio clock), drawn via `requestAnimationFrame`. Pure function `playheadX` in `core/playhead.js`.

**Parity contract:** the browser and server renderers agree on: which notes sound when, at which pitch, relative velocity, pan, instrument *family*, glides. They do **not** need identical waveforms.

## 6a. Optional sample-based voices (Sri Lankan skin, P8)

If `data/audio/<skin_id>/<instrument>.wav` exists with `data/audio/<skin_id>/<instrument>.json` `{ "root_midi": 60, "license": "CC0|own-recording" }`, the server renderer may resample (linear interpolation) it for that instrument; absent → fall back to the synth recipe. Never required; never downloaded at runtime.
