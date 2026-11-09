/**
 * The Earth Jukebox - NASA EIC Sonification Frontend Script
 * 
 * Provides real-time audio playback (Tone.js) synchronized with
 * interactive visualizations and geometric scanheads (p5.js).
 */

// ============================================================================
// 1. Application State & Configuration
// ============================================================================

const state = {
  // Playback state
  isPlaying: false,
  isPaused: false,
  isLoaded: false,
  isMuted: false,

  // Timing
  currentTime: 0.0,
  durationSeconds: 5.0,

  // Blueprint Metadata
  blueprint: null,
  events: [],
  scanGeometry: "horizontal_sweep", // 'horizontal_sweep' | 'vertical_sweep' | 'radar_sweep' | 'radial_expansion'
  scaleName: "c_major_pentatonic",
  tuningSystem: "12-EDO",

  // Visuals
  activePulses: [],
  eicImage: null,
  imageLoaded: false,
  showScanHead: true,
  showPulses: true,
  showGrid: true,

  // Tone.js scheduling
  scheduledPart: null,
  activeVoicesCount: 0,

  // 3D Spatial Audio Exploration Cursor (Task 15)
  spatialCursor: {
    enabled: true,
    isHovering: false,
    canvasX: 0,
    canvasY: 0,
    normX: 0.0,
    normY: 0.0,
    scalarValue: 0.0,
    pos3D: { x: 0.0, y: 0.0, z: -1.5 },
    throttleMs: 60, // Hover earcon throttle interval
    lastTriggerTime: 0,
    lastCoord: { x: -1, y: -1, col: -1, row: -1 },
    scalarData: null, // Secondary raw scalar dataset
    scalarUrl: null,
    activeEarconPings: [], // Visual reticle ripples
  },
};

// ============================================================================
// 2. Audio Engine Setup & Synth Routing (Tone.js)
// ============================================================================

let masterVolume;
let masterLimiter;
let spaceReverb;
let diffuseSynth;
let pointSynth;
let pluckSynth;
let diffusePanner;
let pointPanner;
let spatialCursorPanner = null;
let spatialCursorSynth = null;
let audioInitialized = false;
let synthMap = {};

/**
 * Initialize instrument mapping registry connecting instrumentIds to Tone.js synths.
 */
function initInstrumentMap() {
  synthMap = {
    // Diffuse emission layers -> Tone.PolySynth
    "diffuse_pad": diffuseSynth,
    "diffuse": diffuseSynth,
    "diffuse_synth": diffuseSynth,
    "pad": diffuseSynth,
    "ambient_pad": diffuseSynth,
    "ambient": diffuseSynth,

    // Point source transients -> Tone.PluckSynth
    "point_source_pluck": pluckSynth,
    "pluck": pluckSynth,
    "point_source": pluckSynth,
    "point": pluckSynth,
    "hotspot": pluckSynth,
    "ping": pluckSynth,
    "bell": pluckSynth,
    "chime": pluckSynth,
    "crackle": pluckSynth,
    "whoosh": pluckSynth,
  };
}

/**
 * Map an instrumentId and layer type to a specific Tone.js synth.
 * 
 * @param {string} instrumentId - Identifier from JSON event (e.g. "diffuse_pad", "point_source_pluck")
 * @param {string} [layer] - Event layer ("diffuse" | "point_source")
 * @returns {Tone.Instrument} Tone.js synth instance
 */
function getSynthForInstrument(instrumentId, layer) {
  if (instrumentId && synthMap[instrumentId]) {
    return synthMap[instrumentId];
  }
  const idStr = String(instrumentId || "").toLowerCase();
  const layerStr = String(layer || "").toLowerCase();

  if (
    idStr.includes("pluck") ||
    idStr.includes("point") ||
    idStr.includes("ping") ||
    idStr.includes("bell") ||
    idStr.includes("chime") ||
    idStr.includes("hotspot") ||
    idStr.includes("crackle") ||
    layerStr === "point_source"
  ) {
    return pluckSynth || pointSynth;
  }

  // Default to diffuse polyphonic synth
  return diffuseSynth;
}

/**
 * Initialize Tone.js audio graph and routing.
 */
function initAudioEngine() {
  if (audioInitialized) return;

  try {
    // 1. Master Output Chain: Volume -> Limiter -> Destination
    masterVolume = new Tone.Volume(0);
    masterLimiter = new Tone.Limiter(-1);
    
    // 2. Space Reverb (Chandra Cosmic Ambience)
    spaceReverb = new Tone.Reverb({
      decay: 3.0,
      preDelay: 0.04,
      wet: 0.25,
    });

    masterVolume.chain(spaceReverb, masterLimiter, Tone.Destination);

    // 3. Stereo Panners for spatial staging
    diffusePanner = new Tone.Panner(0).connect(masterVolume);
    pointPanner = new Tone.Panner(0).connect(masterVolume);

    // 4. Diffuse Emission Layer Synth (Tone.PolySynth warm analog pad)
    diffuseSynth = new Tone.PolySynth(Tone.Synth, {
      oscillator: {
        type: "sawtooth6",
      },
      envelope: {
        attack: 0.12,
        decay: 0.35,
        sustain: 0.65,
        release: 0.75,
      },
    });
    diffuseSynth.volume.value = -3;
    diffuseSynth.connect(diffusePanner);

    // 5. Point Source Layer Synth (Tone.PluckSynth - Karplus-Strong physical modeling pluck)
    pluckSynth = new Tone.PluckSynth({
      attackNoise: 1.0,
      dampening: 4000,
      resonance: 0.92,
      release: 0.4,
    });
    pluckSynth.volume.value = 0;
    pluckSynth.connect(pointPanner);

    // 6. Point Source Polyphonic Synth (Transient triangle/sine voice)
    pointSynth = new Tone.PolySynth(Tone.Synth, {
      oscillator: {
        type: "triangle",
      },
      envelope: {
        attack: 0.005,
        decay: 0.18,
        sustain: 0.08,
        release: 0.25,
      },
    });
    pointSynth.volume.value = 0;
    pointSynth.connect(pointPanner);

    // 7. Register instrument map connecting JSON instrumentIds to synths
    initInstrumentMap();

    // 8. Transport configuration
    Tone.Transport.loop = false;
    Tone.Transport.bpm.value = 120;

    // 9. Initialize 3D Spatial Audio Exploration Cursor (Task 15)
    initSpatialCursorAudio();

    audioInitialized = true;
    updateAudioStatusUI();
    console.log("[Earth Jukebox] Tone.js audio engine & synths initialized.");
  } catch (err) {
    console.error("[Earth Jukebox] Error initializing audio engine:", err);
  }
}

/**
 * Initialize 3D Spatial Audio Panner (Tone.Panner3D or Web Audio PannerNode)
 * and the dedicated earcon synthesizer for hover exploration.
 */
function initSpatialCursorAudio() {
  if (spatialCursorPanner && spatialCursorSynth) {
    return { panner: spatialCursorPanner, synth: spatialCursorSynth };
  }

  // 1. Initialize 3D Spatial Panner (Tone.Panner3D or Web Audio PannerNode)
  if (!spatialCursorPanner) {
    try {
      // Option A: Tone.Panner3D
      if (typeof Tone !== "undefined" && typeof Tone.Panner3D === "function") {
        spatialCursorPanner = new Tone.Panner3D({
          panningModel: "HRTF",
          distanceModel: "inverse",
          positionX: 0,
          positionY: 0,
          positionZ: -1.5,
          refDistance: 1,
          maxDistance: 1000,
          rolloffFactor: 1,
        });
        if (masterVolume && typeof spatialCursorPanner.connect === "function") {
          spatialCursorPanner.connect(masterVolume);
        } else if (Tone.Destination && typeof spatialCursorPanner.connect === "function") {
          spatialCursorPanner.connect(Tone.Destination);
        }
        console.log("[Earth Jukebox] Initialized Tone.Panner3D for spatial audio cursor.");
      }
      // Option B: Native Web Audio PannerNode via Tone.context or AudioContext
      else if (typeof Tone !== "undefined" && Tone.context) {
        const rawCtx = Tone.context.rawContext || Tone.context;
        if (rawCtx && typeof rawCtx.createPanner === "function") {
          spatialCursorPanner = rawCtx.createPanner();
          spatialCursorPanner.panningModel = "HRTF";
          spatialCursorPanner.distanceModel = "inverse";
          spatialCursorPanner.refDistance = 1;
          spatialCursorPanner.maxDistance = 1000;
          spatialCursorPanner.rolloffFactor = 1;

          if (spatialCursorPanner.positionZ && typeof spatialCursorPanner.positionZ.value !== "undefined") {
            spatialCursorPanner.positionX.value = 0;
            spatialCursorPanner.positionY.value = 0;
            spatialCursorPanner.positionZ.value = -1.5;
          } else if (typeof spatialCursorPanner.setPosition === "function") {
            spatialCursorPanner.setPosition(0, 0, -1.5);
          }

          const dest = (masterVolume && masterVolume.input)
            ? masterVolume.input
            : (masterVolume || (Tone.Destination ? (Tone.Destination.input || Tone.Destination) : null));
          if (dest && typeof spatialCursorPanner.connect === "function") {
            spatialCursorPanner.connect(dest);
          }
          console.log("[Earth Jukebox] Initialized native Web Audio PannerNode for spatial audio cursor.");
        }
      }
    } catch (err) {
      console.warn("[Earth Jukebox] 3D Panner initialization failed, falling back to stereo Panner:", err);
    }

    // Option C: Fallback to stereo Tone.Panner if 3D panners are unsupported
    if (!spatialCursorPanner && typeof Tone !== "undefined" && typeof Tone.Panner === "function") {
      spatialCursorPanner = new Tone.Panner(0);
      if (masterVolume && typeof spatialCursorPanner.connect === "function") {
        spatialCursorPanner.connect(masterVolume);
      }
    }
  }

  // 2. Initialize Earcon Synthesizer
  if (!spatialCursorSynth) {
    try {
      const synthConfig = {
        oscillator: {
          type: "sine",
        },
        envelope: {
          attack: 0.003,
          decay: 0.07,
          sustain: 0.0,
          release: 0.07,
        },
      };

      if (typeof Tone !== "undefined" && typeof Tone.PolySynth === "function") {
        spatialCursorSynth = new Tone.PolySynth(Tone.Synth, synthConfig);
      } else if (typeof Tone !== "undefined" && typeof Tone.Synth === "function") {
        spatialCursorSynth = new Tone.Synth(synthConfig);
      }

      if (spatialCursorSynth) {
        if (spatialCursorSynth.volume) {
          spatialCursorSynth.volume.value = -6;
        }
        if (spatialCursorPanner && typeof spatialCursorSynth.connect === "function") {
          spatialCursorSynth.connect(spatialCursorPanner);
        }
      }
    } catch (err) {
      console.warn("[Earth Jukebox] Earcon synth initialization failed:", err);
    }
  }

  return { panner: spatialCursorPanner, synth: spatialCursorSynth };
}

/**
 * Apply 3D coordinates to Tone.Panner3D or native Web Audio PannerNode across standard APIs.
 */
function setPannerCoordinates(panner, x, y, z) {
  if (!panner) return;

  const audioTime = (Tone && Tone.now) ? Tone.now() : 0;

  // 1. AudioParam interface (Standard Web Audio PannerNode & Tone.Panner3D)
  if (panner.positionX && typeof panner.positionX.setValueAtTime === "function") {
    try {
      panner.positionX.setValueAtTime(x, audioTime);
      panner.positionY.setValueAtTime(y, audioTime);
      panner.positionZ.setValueAtTime(z, audioTime);
      return;
    } catch (_) {}
  }

  if (panner.positionX && typeof panner.positionX.value !== "undefined") {
    panner.positionX.value = x;
    panner.positionY.value = y;
    panner.positionZ.value = z;
    return;
  }

  // 2. Tone.Panner3D set() helper
  if (typeof panner.set === "function") {
    try {
      panner.set({ positionX: x, positionY: y, positionZ: z });
      return;
    } catch (_) {}
  }

  // 3. Web Audio legacy setPosition method
  if (typeof panner.setPosition === "function") {
    try {
      panner.setPosition(x, y, z);
      return;
    } catch (_) {}
  }

  // 4. Stereo fallback (Tone.Panner)
  if (panner.pan) {
    const panVal = Math.max(-1.0, Math.min(1.0, x / 3.5));
    if (typeof panner.pan.setValueAtTime === "function") {
      panner.pan.setValueAtTime(panVal, audioTime);
    } else if (typeof panner.pan.value !== "undefined") {
      panner.pan.value = panVal;
    }
  }
}

/**
 * Update 3D spatial acoustic position of the probe cursor based on mouse coordinates.
 * Maps canvas (normX, normY) into 3D Cartesian coordinates (posX, posY, posZ).
 * 
 * @param {number} normX - Normalized horizontal coordinate [0.0 .. 1.0] (0 = left, 1 = right)
 * @param {number} normY - Normalized vertical coordinate [0.0 .. 1.0] (0 = top, 1 = bottom)
 * @param {number} [scalar=0.5] - Probed scalar energy value [0.0 .. 1.0]
 * @returns {Object} 3D coordinates { x, y, z }
 */
function updateSpatialAudioPosition(normX, normY, scalar = 0.5) {
  // Map normalized horizontal coordinate [0..1] to acoustic azimuth [-3.5m .. +3.5m]
  const clampedX = Math.max(0.0, Math.min(1.0, normX));
  const posX = (clampedX * 2.0 - 1.0) * 3.5;

  // Map normalized vertical coordinate [0..1] to acoustic elevation [+2.5m .. -2.5m]
  // In Web Audio 3D coordinates: +Y is UP, -Y is DOWN
  const clampedY = Math.max(0.0, Math.min(1.0, normY));
  const posY = (1.0 - clampedY * 2.0) * 2.5;

  // Map depth (Z): sound plane in front of listener (-1.5m), with subtle scalar relief
  const clampedScalar = Math.max(0.0, Math.min(1.0, scalar));
  const posZ = -1.5 + (clampedScalar - 0.5) * 0.4;

  const pos3D = { x: posX, y: posY, z: posZ };
  state.spatialCursor.pos3D = pos3D;

  const audioObjs = initSpatialCursorAudio();
  if (audioObjs && audioObjs.panner) {
    setPannerCoordinates(audioObjs.panner, posX, posY, posZ);
  }

  return pos3D;
}

/**
 * Create and trigger a short "earcon" sound when hovering over the data map.
 * The earcon's pitch, timbre, and amplitude reflect the probed scalar intensity,
 * spatialized in 3D audio space.
 * 
 * @param {number} scalar - Probed scalar value [0.0 .. 1.0]
 * @param {number} normX - Normalized horizontal coordinate [0.0 .. 1.0]
 * @param {number} normY - Normalized vertical coordinate [0.0 .. 1.0]
 * @returns {boolean} True if earcon triggered, false if throttled
 */
function triggerHoverEarcon(scalar, normX, normY) {
  if (!state.spatialCursor.enabled) return false;

  const now = (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now();
  if (now - state.spatialCursor.lastTriggerTime < state.spatialCursor.throttleMs) {
    return false; // Throttled to prevent audio buffer saturation
  }
  state.spatialCursor.lastTriggerTime = now;

  // 1. Update 3D spatial position in acoustic space
  updateSpatialAudioPosition(normX, normY, scalar);

  // 2. Map scalar intensity to pitch:
  // Base frequency range: 220 Hz (A3) to 1760 Hz (A6) with logarithmic musical scaling
  const minFreq = 220.0;
  const maxFreq = 1760.0;
  const clampedScalar = Math.max(0.0, Math.min(1.0, scalar));
  const freq = minFreq * Math.pow(maxFreq / minFreq, clampedScalar);

  // Velocity scaled to scalar intensity with accessible floor
  const vel = Math.max(0.2, Math.min(0.9, 0.25 + clampedScalar * 0.65));
  const earconDuration = 0.07; // 70ms short acoustic earcon cue

  // 3. Trigger synthesizer voice if audio engine is active
  const isAudioRunning = Tone && Tone.context && Tone.context.state === "running";
  if (isAudioRunning) {
    const audioObjs = initSpatialCursorAudio();
    const synth = audioObjs ? audioObjs.synth : null;
    if (synth) {
      try {
        if (typeof synth.triggerAttackRelease === "function") {
          synth.triggerAttackRelease(freq, earconDuration, undefined, vel);
        } else if (typeof synth.triggerAttack === "function") {
          synth.triggerAttack(freq, undefined, vel);
        }
      } catch (err) {
        console.warn("[Earth Jukebox] Hover earcon trigger error:", err);
      }
    }
  }

  // 4. Register visual acoustic reticle pulse on canvas
  spawnCursorPing(state.spatialCursor.canvasX, state.spatialCursor.canvasY, clampedScalar);
  return true;
}

/**
 * Register visual reticle ping ripple on the canvas.
 */
function spawnCursorPing(x, y, scalar) {
  if (!state.spatialCursor || !Array.isArray(state.spatialCursor.activeEarconPings)) return;
  state.spatialCursor.activeEarconPings.push({
    x: x,
    y: y,
    radius: 4,
    alpha: 240,
    scalar: scalar,
  });
  if (state.spatialCursor.activeEarconPings.length > 10) {
    state.spatialCursor.activeEarconPings.shift();
  }
}


/**
 * Ensure AudioContext is unlocked following browser autoplay policy.
 */
async function ensureAudioContext() {
  if (!audioInitialized) {
    initAudioEngine();
  }
  if (Tone.context.state !== "running") {
    await Tone.start();
    console.log("[Earth Jukebox] AudioContext resumed successfully.");
  }
  updateAudioStatusUI();
}

/**
 * Trigger an audio event scheduled in the blueprint timeline.
 * Maps instrumentId to designated Tone.js synths with spatial panning and velocity.
 * 
 * @param {number} time - Audio context scheduling time in seconds
 * @param {Object} ev - Blueprint event payload
 */
function triggerAudioEvent(time, ev) {
  try {
    const synth = getSynthForInstrument(ev.instrumentId, ev.layer);
    const isPointSource =
      synth === pluckSynth ||
      synth === pointSynth ||
      (ev.layer === "point_source") ||
      (ev.instrumentId && (
        ev.instrumentId.includes("point") ||
        ev.instrumentId.includes("pluck") ||
        ev.instrumentId.includes("ping") ||
        ev.instrumentId.includes("hotspot")
      ));

    // Resolve pitch / frequency
    let pitch = ev.frequency || ev.pitch;
    if (!pitch) {
      if (typeof ev.midiNote === "number") {
        pitch = (Tone.Frequency ? Tone.Frequency(ev.midiNote, "midi").toFrequency() : 440);
      } else if (typeof ev.midi_note === "number") {
        pitch = (Tone.Frequency ? Tone.Frequency(ev.midi_note, "midi").toFrequency() : 440);
      } else {
        pitch = 440;
      }
    }

    // Resolve duration in seconds
    const durSec = ev.durationSeconds ||
      ev.duration_seconds ||
      (typeof ev.duration_ms === "number" ? ev.duration_ms / 1000.0 : null) ||
      (typeof ev.duration === "number" ? (ev.duration > 20 ? ev.duration / 1000.0 : ev.duration) : 0.2);

    // Resolve velocity / amplitude
    const vel = typeof ev.velocity === "number"
      ? Math.max(0.05, Math.min(1.0, ev.velocity))
      : (typeof ev.amplitude === "number" ? Math.max(0.05, Math.min(1.0, ev.amplitude)) : 0.7);

    // Resolve stereo pan [-1.0 .. 1.0]
    const pan = typeof ev.pan === "number" ? Math.max(-1.0, Math.min(1.0, ev.pan)) : 0.0;

    // Apply stereo panner values aligned with audio timestamp
    if (isPointSource) {
      if (pointPanner && pointPanner.pan && typeof pointPanner.pan.setValueAtTime === "function") {
        pointPanner.pan.setValueAtTime(pan, time);
      }
    } else {
      if (diffusePanner && diffusePanner.pan && typeof diffusePanner.pan.setValueAtTime === "function") {
        diffusePanner.pan.setValueAtTime(pan, time);
      }
    }

    // Trigger synthesis on the mapped synth with sub-millisecond precision
    if (synth) {
      if (typeof synth.triggerAttackRelease === "function") {
        synth.triggerAttackRelease(pitch, durSec, time, vel);
      } else if (typeof synth.triggerAttack === "function") {
        synth.triggerAttack(pitch, time, vel);
      }
    }

    flashVoiceIndicator(isPointSource ? "point" : "diffuse");

    // Schedule visual acoustic ripple pulse on the p5 canvas synchronized with audio clock
    if (state.showPulses && Tone.Draw && typeof Tone.Draw.schedule === "function") {
      Tone.Draw.schedule(() => {
        spawnEventPulse(ev);
      }, time);
    }
  } catch (e) {
    console.warn("[Earth Jukebox] Event trigger error:", e);
  }
}

/**
 * Flash active LED voice indicator in the UI.
 */
function flashVoiceIndicator(type) {
  const el = document.getElementById(type === "point" ? "point-indicator" : "diffuse-indicator");
  if (el) {
    el.classList.add("active");
    setTimeout(() => {
      el.classList.remove("active");
    }, 180);
  }
}

/**
 * Schedule blueprint timeline events onto Tone.Transport using Tone.Part.
 * 
 * @param {Object} blueprint - JSON blueprint object containing metadata and events array
 * @returns {Tone.Part} The scheduled Tone.Part instance
 */
function scheduleTimeline(blueprint) {
  initAudioEngine();

  // Clear previous schedule
  if (state.scheduledPart) {
    try {
      state.scheduledPart.dispose();
    } catch (_) {}
    state.scheduledPart = null;
  }
  Tone.Transport.cancel();

  state.blueprint = blueprint;
  const meta = blueprint.metadata || {};
  state.events = Array.isArray(blueprint.events) ? blueprint.events : [];
  state.durationSeconds =
    meta.durationSeconds ||
    meta.duration_seconds ||
    (meta.durationMs ? meta.durationMs / 1000.0 : null) ||
    (meta.duration_ms ? meta.duration_ms / 1000.0 : null) ||
    5.0;
  state.scanGeometry = meta.scanGeometry || meta.scan_geometry || meta.geometry_type || "horizontal_sweep";
  state.scaleName = meta.scaleName || meta.scale_name || "c_major_pentatonic";
  state.tuningSystem = meta.tuningSystem || meta.tuning_system || "12-EDO";

  Tone.Transport.loop = false;
  Tone.Transport.loopEnd = state.durationSeconds;

  // Format events for Tone.Part: array of [timeInSeconds, eventObject]
  const partEvents = state.events.map((ev) => {
    let tSec = 0;
    if (typeof ev.timeSeconds === "number") {
      tSec = ev.timeSeconds;
    } else if (typeof ev.time_seconds === "number") {
      tSec = ev.time_seconds;
    } else if (typeof ev.time_ms === "number") {
      tSec = ev.time_ms / 1000.0;
    } else if (typeof ev.time === "number") {
      // Milliseconds vs seconds detection: if time exceeds duration or > 100, normalize ms
      if (ev.time > (state.durationSeconds || 30) && ev.time > 100) {
        tSec = ev.time / 1000.0;
      } else {
        tSec = ev.time;
      }
    }
    return [Math.max(0, tSec), ev];
  });

  // Use Tone.Part to schedule events with sub-millisecond precision
  state.scheduledPart = new Tone.Part((time, ev) => {
    triggerAudioEvent(time, ev);
  }, partEvents);

  state.scheduledPart.start(0);
  state.scheduledPart.loop = false;

  // Schedule auto-stop when duration finishes
  Tone.Transport.schedule((time) => {
    if (Tone.Draw && typeof Tone.Draw.schedule === "function") {
      Tone.Draw.schedule(() => {
        stopPlayback();
      }, time);
    } else {
      stopPlayback();
    }
  }, state.durationSeconds);

  state.isLoaded = true;
  updateMetadataUI();
  updatePlaybackUI();
  console.log(`[Earth Jukebox] Scheduled ${state.events.length} events for ${state.durationSeconds}s playback.`);
  return state.scheduledPart;
}

// Backwards-compatible alias
const scheduleBlueprint = scheduleTimeline;

/**
 * Fetch and parse a timeline JSON from a URL or object, then schedule it for audio-visual playback.
 * 
 * @param {string|Object} jsonUrl - Remote/local URL string, or parsed blueprint object
 * @returns {Promise<Object>} Resolves with the parsed timeline blueprint
 */
async function loadTimeline(jsonUrl) {
  let blueprint;

  if (typeof jsonUrl === "string") {
    const response = await fetch(jsonUrl);
    if (!response.ok) {
      throw new Error(`Failed to load timeline from "${jsonUrl}": HTTP ${response.status} ${response.statusText}`);
    }
    blueprint = await response.json();
  } else if (typeof jsonUrl === "object" && jsonUrl !== null) {
    blueprint = jsonUrl;
  } else {
    throw new TypeError(`loadTimeline expected a URL string or object, but got ${typeof jsonUrl}`);
  }

  if (!blueprint || !Array.isArray(blueprint.events)) {
    throw new Error("Invalid timeline format: missing 'events' array in JSON blueprint.");
  }

  // Stop any active playback before scheduling new timeline
  stopPlayback();

  // Schedule onto Tone.Transport and Tone.Part
  scheduleTimeline(blueprint);

  state.timelineUrl = typeof jsonUrl === "string" ? jsonUrl : null;
  console.log(`[Earth Jukebox] Successfully loaded timeline with ${blueprint.events.length} events.`);
  return blueprint;
}

// ============================================================================
// 3. Transport Controls: Play, Pause, Stop, Seek
// ============================================================================

async function playPlayback() {
  await ensureAudioContext();

  if (!state.isLoaded) {
    await loadDefaultDemoBlueprint();
  }

  // If at the end, rewind
  if (Tone.Transport.seconds >= state.durationSeconds) {
    Tone.Transport.seconds = 0;
  }

  Tone.Transport.start();
  state.isPlaying = true;
  state.isPaused = false;
  updatePlaybackUI();
}

function pausePlayback() {
  if (!state.isPlaying) return;
  Tone.Transport.pause();
  state.isPlaying = false;
  state.isPaused = true;
  silenceActiveVoices();
  updatePlaybackUI();
}

function stopPlayback() {
  Tone.Transport.stop();
  Tone.Transport.seconds = 0;
  state.currentTime = 0;
  state.isPlaying = false;
  state.isPaused = false;
  state.activePulses = [];
  silenceActiveVoices();
  updatePlaybackUI();
}

function seekPlayback(targetSeconds) {
  const clamped = Math.max(0, Math.min(state.durationSeconds, targetSeconds));
  Tone.Transport.seconds = clamped;
  state.currentTime = clamped;
  updateTimelineScrubber(clamped / state.durationSeconds);
}

function silenceActiveVoices() {
  if (diffuseSynth && typeof diffuseSynth.releaseAll === "function") {
    try { diffuseSynth.releaseAll(); } catch (_) {}
  }
  if (pointSynth && typeof pointSynth.releaseAll === "function") {
    try { pointSynth.releaseAll(); } catch (_) {}
  }
  if (pluckSynth) {
    try {
      if (typeof pluckSynth.releaseAll === "function") {
        pluckSynth.releaseAll();
      } else if (typeof pluckSynth.triggerRelease === "function") {
        pluckSynth.triggerRelease();
      }
    } catch (_) {}
  }
}

// ============================================================================
// 4. Visual Engine & Scanhead Renderer (p5.js)
// ============================================================================

let p5CanvasInstance = null;

// Built-in synthetic fallback palette for scientific EIC rendering
const PLASMA_PALETTE = [
  [13, 8, 135],
  [84, 2, 163],
  [156, 23, 158],
  [204, 71, 120],
  [237, 121, 83],
  [253, 180, 47],
  [240, 249, 33],
];

function samplePalette(normVal) {
  const v = Math.max(0, Math.min(0.999, normVal));
  const idx = v * (PLASMA_PALETTE.length - 1);
  const i0 = Math.floor(idx);
  const i1 = Math.min(PLASMA_PALETTE.length - 1, i0 + 1);
  const frac = idx - i0;
  const c0 = PLASMA_PALETTE[i0];
  const c1 = PLASMA_PALETTE[i1];
  return [
    Math.round(c0[0] + frac * (c1[0] - c0[0])),
    Math.round(c0[1] + frac * (c1[1] - c0[1])),
    Math.round(c0[2] + frac * (c1[2] - c0[2])),
  ];
}

/**
 * Main p5.js Sketch Definition.
 */
const sketch = (p) => {
  let syntheticBackground = null;

  p.preload = () => {
    // Attempt to preload sample NASA EIC image
    p.loadImage(
      "sample_image.png",
      (img) => {
        state.eicImage = img;
        state.imageLoaded = true;
        console.log("[Earth Jukebox] Sample EIC image loaded successfully.");
      },
      () => {
        console.log("[Earth Jukebox] No local sample_image.png; using procedural NASA EIC canvas.");
        state.imageLoaded = false;
      }
    );
  };

  p.setup = () => {
    const container = document.getElementById("canvas-container");
    const containerWidth = container ? container.clientWidth : 800;
    const canvasWidth = Math.max(480, Math.min(900, containerWidth));
    const canvasHeight = Math.round(canvasWidth * (5 / 8)); // 16:10 ratio

    const cnv = p.createCanvas(canvasWidth, canvasHeight);
    cnv.parent("canvas-container");

    // Track mousemove, mouseenter, mouseleave and click over p5 canvas (Task 15)
    if (cnv && cnv.elt) {
      cnv.elt.addEventListener("mousemove", (e) => handleCanvasMouseMove(e, p, cnv.elt));
      cnv.elt.addEventListener("mouseenter", () => handleCanvasMouseEnter());
      cnv.elt.addEventListener("mouseleave", () => handleCanvasMouseLeave());
      cnv.elt.addEventListener("click", async (e) => {
        await ensureAudioContext();
        handleCanvasMouseMove(e, p, cnv.elt);
        if (state.spatialCursor && state.spatialCursor.enabled) {
          triggerHoverEarcon(state.spatialCursor.scalarValue, state.spatialCursor.normX, state.spatialCursor.normY);
        }
      });
    }

    // Remove placeholder
    const placeholder = document.getElementById("canvas-placeholder");
    if (placeholder) placeholder.style.display = "none";

    // Generate procedural fallback image
    generateProceduralEIC(p, canvasWidth, canvasHeight);

    p.frameRate(60);
  };

  p.windowResized = () => {
    const container = document.getElementById("canvas-container");
    if (!container) return;
    const containerWidth = container.clientWidth;
    const canvasWidth = Math.max(480, Math.min(900, containerWidth));
    const canvasHeight = Math.round(canvasWidth * (5 / 8));
    p.resizeCanvas(canvasWidth, canvasHeight);
    generateProceduralEIC(p, canvasWidth, canvasHeight);
  };

  p.draw = () => {
    p.background(7, 10, 18);

    // 1. Render Background Image / Data Array
    if (state.imageLoaded && state.eicImage) {
      p.image(state.eicImage, 0, 0, p.width, p.height);
    } else if (syntheticBackground) {
      p.image(syntheticBackground, 0, 0);
    }

    // 2. Render subtle coordinate grid overlay
    if (state.showGrid) {
      drawGridOverlay(p);
    }

    // 3. Compute Playhead Position & Time directly synchronized with Tone.Transport clock
    if (audioInitialized && (state.isPlaying || state.isPaused)) {
      state.currentTime = Tone.Transport.seconds;
      if (state.currentTime >= state.durationSeconds && state.isPlaying) {
        stopPlayback();
      }
    }
    const normProgress = state.durationSeconds > 0
      ? Math.max(0, Math.min(1.0, state.currentTime / state.durationSeconds))
      : 0;
    updateTimelineScrubber(normProgress);

    // 4. Render Active Event Ripples / Acoustic Pulses
    if (state.showPulses) {
      drawAcousticPulses(p);
    }

    // 5. Render Moving Geometric Scan Head
    if (state.showScanHead) {
      drawScanHead(p, normProgress);
    }

    // 6. Render Spatial Audio Exploration Reticle & Earcon Ripples (Task 15)
    if (state.spatialCursor && state.spatialCursor.enabled) {
      drawSpatialAudioCursor(p);
    }

    // 7. Update HUD overlays
    updateHUD(p);
  };

  /**
   * Procedural NASA EIC visualization generator.
   */
  function generateProceduralEIC(p, w, h) {
    syntheticBackground = p.createGraphics(w, h);
    syntheticBackground.pixelDensity(1);
    syntheticBackground.loadPixels();

    const dataWidth = w - 45;
    const cy = h / 2;
    const cx = dataWidth / 2;

    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        let r, g, b;

        if (x >= w - 30 && x <= w - 15 && y >= 30 && y <= h - 30) {
          // Colorbar gradient on the right
          const cbNorm = 1.0 - (y - 30) / (h - 60);
          [r, g, b] = samplePalette(cbNorm);
        } else if (x < dataWidth) {
          // Dual-layer atmospheric wave + localized hotspot
          const nx = x / dataWidth;
          const ny = y / h;
          const dist = Math.hypot(x - cx, y - cy);
          const angle = Math.atan2(y - cy, x - cx);

          // Broad diffuse wave (atmospheric gradient)
          const diffuse = 0.5 + 0.3 * Math.sin(nx * 4.0 + Math.cos(ny * 3.0)) + 0.15 * Math.sin(angle * 2.0 + dist / 25.0);
          
          // Point source hotspot (e.g. convective storm or thermal beacon)
          const spotDist = Math.hypot(x - dataWidth * 0.72, y - h * 0.35);
          const hotspot = Math.exp(-(spotDist * spotDist) / 450.0);

          const scalar = Math.max(0.0, Math.min(1.0, diffuse * 0.75 + hotspot * 0.7));
          [r, g, b] = samplePalette(scalar);
        } else {
          // Dark gutter
          r = 10; g = 14; b = 25;
        }

        const idx = (y * w + x) * 4;
        syntheticBackground.pixels[idx] = r;
        syntheticBackground.pixels[idx + 1] = g;
        syntheticBackground.pixels[idx + 2] = b;
        syntheticBackground.pixels[idx + 3] = 255;
      }
    }
    syntheticBackground.updatePixels();
  }

  /**
   * Draw Cartesian / Polar grid markings.
   */
  function drawGridOverlay(p) {
    p.push();
    p.stroke(148, 163, 184, 25);
    p.strokeWeight(1);

    if (state.scanGeometry === "radar_sweep" || state.scanGeometry === "radial_expansion") {
      // Polar grid
      const cx = (p.width - 45) / 2;
      const cy = p.height / 2;
      const maxR = Math.hypot(cx, cy);
      p.noFill();
      for (let r = 40; r < maxR; r += 40) {
        p.ellipse(cx, cy, r * 2, r * 2);
      }
      p.line(cx - maxR, cy, cx + maxR, cy);
      p.line(cx, cy - maxR, cx, cy + maxR);
    } else {
      // Cartesian grid
      for (let x = 40; x < p.width - 45; x += 40) {
        p.line(x, 0, x, p.height);
      }
      for (let y = 40; y < p.height; y += 40) {
        p.line(0, y, p.width - 45, y);
      }
    }
    p.pop();
  }

  /**
   * Render geometric scan head based on active geometry.
   */
  function drawScanHead(p, progress) {
    p.push();
    const dataW = p.width - 45;

    switch (state.scanGeometry) {
      case "vertical_sweep": {
        // Top-to-bottom horizontal beam
        const curY = progress * p.height;

        // Trailing glow
        p.noStroke();
        p.fill(0, 240, 255, 30);
        p.rect(0, curY - 12, dataW, 12);

        // Core laser beam
        p.stroke(0, 240, 255, 230);
        p.strokeWeight(2.5);
        p.line(0, curY, dataW, curY);

        // Leading indicator dot
        p.fill(255);
        p.noStroke();
        p.ellipse(dataW - 2, curY, 6, 6);
        break;
      }

      case "radar_sweep": {
        // Clockwise polar sweep
        const cx = dataW / 2;
        const cy = p.height / 2;
        const maxR = Math.hypot(cx, cy);
        const curAngle = progress * p.TWO_PI - p.HALF_PI; // Start at 12 o'clock

        // Radar beam sweep line
        const endX = cx + Math.cos(curAngle) * maxR;
        const endY = cy + Math.sin(curAngle) * maxR;

        // Phosphor sweep trail
        p.noStroke();
        p.fill(0, 240, 255, 35);
        p.arc(cx, cy, maxR * 2, maxR * 2, curAngle - 0.25, curAngle);

        // Scan line
        p.stroke(0, 240, 255, 240);
        p.strokeWeight(2.5);
        p.line(cx, cy, endX, endY);

        // Center beacon
        p.fill(0, 240, 255);
        p.noStroke();
        p.ellipse(cx, cy, 7, 7);
        break;
      }

      case "radial_expansion": {
        // Expanding concentric wavefront
        const cx = dataW / 2;
        const cy = p.height / 2;
        const maxR = Math.hypot(cx, cy);
        const curR = progress * maxR;

        // Trailing ripple wave
        p.noFill();
        p.stroke(0, 240, 255, 60);
        p.strokeWeight(6);
        p.ellipse(cx, cy, curR * 2, curR * 2);

        // Leading wave crest
        p.stroke(0, 240, 255, 255);
        p.strokeWeight(2.5);
        p.ellipse(cx, cy, curR * 2, curR * 2);
        break;
      }

      case "horizontal_sweep":
      default: {
        // Left-to-right vertical laser beam
        const curX = progress * dataW;

        // Trailing glow
        p.noStroke();
        p.fill(0, 240, 255, 30);
        p.rect(curX - 14, 0, 14, p.height);

        // Core laser beam
        p.stroke(0, 240, 255, 240);
        p.strokeWeight(2.5);
        p.line(curX, 0, curX, p.height);

        // Leading indicator dot
        p.fill(255);
        p.noStroke();
        p.ellipse(curX, p.height / 2, 7, 7);
        break;
      }
    }

    p.pop();
  }

  /**
   * Draw active acoustic pulses / ripples triggered by notes.
   */
  function drawAcousticPulses(p) {
    p.push();
    for (let i = state.activePulses.length - 1; i >= 0; i--) {
      const pulse = state.activePulses[i];
      pulse.radius += 1.8;
      pulse.alpha -= 4.5;

      if (pulse.alpha <= 0) {
        state.activePulses.splice(i, 1);
        continue;
      }

      p.noFill();
      p.stroke(pulse.r, pulse.g, pulse.b, pulse.alpha);
      p.strokeWeight(2);
      p.ellipse(pulse.x, pulse.y, pulse.radius * 2, pulse.radius * 2);
    }
    p.pop();
  }

  /**
   * Render 3D spatial audio cursor reticle, probing beacon and expanding earcon ripples.
   */
  function drawSpatialAudioCursor(p) {
    const cursor = state.spatialCursor;
    if (!cursor || !cursor.isHovering) return;

    const cx = cursor.canvasX;
    const cy = cursor.canvasY;
    const scalar = Math.max(0.0, Math.min(1.0, cursor.scalarValue));
    const [r, g, b] = samplePalette(scalar);

    p.push();

    // 1. Draw expanding acoustic earcon ripples
    for (let i = cursor.activeEarconPings.length - 1; i >= 0; i--) {
      const ping = cursor.activeEarconPings[i];
      ping.radius += 2.0;
      ping.alpha -= 5.5;

      if (ping.alpha <= 0) {
        cursor.activeEarconPings.splice(i, 1);
        continue;
      }

      p.noFill();
      p.stroke(r, g, b, ping.alpha);
      p.strokeWeight(1.8);
      p.ellipse(ping.x, ping.y, ping.radius * 2, ping.radius * 2);
    }

    // 2. Cursor crosshairs
    p.stroke(r, g, b, 175);
    p.strokeWeight(1.2);
    p.line(cx - 14, cy, cx - 4, cy);
    p.line(cx + 4, cy, cx + 14, cy);
    p.line(cx, cy - 14, cx, cy - 4);
    p.line(cx, cy + 4, cx, cy + 14);

    // 3. Probing targeting ring
    p.noFill();
    p.stroke(r, g, b, 235);
    p.strokeWeight(1.5);
    const probeRadius = 7 + scalar * 6;
    p.ellipse(cx, cy, probeRadius * 2, probeRadius * 2);

    // 4. Center indicator pip
    p.fill(255);
    p.noStroke();
    p.ellipse(cx, cy, 3, 3);

    // 5. Floating HUD tooltip next to cursor
    const tagX = cx + 12;
    const tagY = cy - 12;
    const tagText = `Val: ${scalar.toFixed(3)}`;
    p.textSize(10);
    const textW = p.textWidth(tagText) + 8;
    p.fill(15, 23, 42, 215);
    p.stroke(r, g, b, 180);
    p.strokeWeight(1);
    p.rect(tagX, tagY - 12, textW, 16, 3);
    p.noStroke();
    p.fill(255);
    p.text(tagText, tagX + 4, tagY);

    p.pop();
  }

  /**
   * Live HUD telemetry readout.
   */
  function updateHUD(p) {
    const dataW = p.width - 45;
    const hudCoords = document.getElementById("hud-coordinates");
    if (hudCoords) {
      if (state.spatialCursor && state.spatialCursor.isHovering) {
        hudCoords.textContent = `X: ${Math.round(state.spatialCursor.canvasX)} | Y: ${Math.round(state.spatialCursor.canvasY)} | Scalar: ${state.spatialCursor.scalarValue.toFixed(3)}`;
      } else if (p.mouseX >= 0 && p.mouseX <= dataW && p.mouseY >= 0 && p.mouseY <= p.height) {
        hudCoords.textContent = `X: ${Math.round(p.mouseX)} | Y: ${Math.round(p.mouseY)}`;
      } else {
        hudCoords.textContent = `X: -- | Y: --`;
      }
    }

    const hudVoices = document.getElementById("hud-active-voices");
    if (hudVoices) {
      hudVoices.textContent = `Events: ${state.events.length}`;
    }
  }
};

/**
 * Register a visual event pulse on note trigger.
 */
function spawnEventPulse(ev) {
  if (!p5CanvasInstance) return;

  const dataW = p5CanvasInstance.width - 45;
  const h = p5CanvasInstance.height;

  let px = dataW / 2;
  let py = h / 2;

  if (ev.spatialPosition && typeof ev.spatialPosition.x === "number") {
    // If normalized coordinates [0, 1]
    if (ev.spatialPosition.x <= 1.0 && ev.spatialPosition.y <= 1.0) {
      px = ev.spatialPosition.x * dataW;
      py = ev.spatialPosition.y * h;
    } else {
      // Pixel coordinates
      px = (ev.spatialPosition.x / 400.0) * dataW;
      py = (ev.spatialPosition.y / 300.0) * h;
    }
  } else {
    // Fallback: place along the scanhead at current progress
    const progress = Math.max(0, Math.min(1.0, state.currentTime / state.durationSeconds));
    if (state.scanGeometry === "horizontal_sweep") {
      px = progress * dataW;
      // Map pitch to vertical coordinate
      py = h - (Math.min(1000, Math.max(100, ev.pitch || 440)) - 100) / 900 * h;
    } else if (state.scanGeometry === "vertical_sweep") {
      py = progress * h;
      px = dataW / 2 + (ev.pan || 0) * (dataW / 2.2);
    }
  }

  const isPoint =
    ev.instrumentId &&
    (ev.instrumentId.includes("point") ||
     ev.instrumentId.includes("pluck") ||
     ev.instrumentId.includes("ping") ||
     ev.layer === "point_source");

  state.activePulses.push({
    x: px,
    y: py,
    radius: 4,
    alpha: 220,
    r: isPoint ? 245 : 0,
    g: isPoint ? 158 : 240,
    b: isPoint ? 11 : 255,
  });
}

// ============================================================================
// 5. UI Interactions, File Loading & State Synchronization
// ============================================================================

/**
 * Update UI text and button disabled states.
 */
function updatePlaybackUI() {
  const btnPlay = document.getElementById("btn-play");
  const btnPause = document.getElementById("btn-pause");
  const btnStop = document.getElementById("btn-stop");
  const statusVal = document.getElementById("transport-status-value");

  if (state.isPlaying) {
    if (btnPlay) btnPlay.disabled = true;
    if (btnPause) btnPause.disabled = false;
    if (btnStop) btnStop.disabled = false;
    if (statusVal) statusVal.textContent = "PLAYING";
  } else if (state.isPaused) {
    if (btnPlay) btnPlay.disabled = false;
    if (btnPause) btnPause.disabled = true;
    if (btnStop) btnStop.disabled = false;
    if (statusVal) statusVal.textContent = "PAUSED";
  } else {
    if (btnPlay) btnPlay.disabled = false;
    if (btnPause) btnPause.disabled = true;
    if (btnStop) btnStop.disabled = true;
    if (statusVal) statusVal.textContent = "STOPPED";
  }
}

/**
 * Update Audio Context badge in the top navigation.
 */
function updateAudioStatusUI() {
  const badgeDot = document.getElementById("audio-status-dot");
  const badgeText = document.getElementById("audio-status-text");

  if (!badgeDot || !badgeText) return;

  if (Tone.context && Tone.context.state === "running") {
    badgeDot.className = "status-dot running";
    badgeText.textContent = "Audio: Active";
  } else {
    badgeDot.className = "status-dot suspended";
    badgeText.textContent = "Audio: Suspended (Click Play)";
  }
}

/**
 * Format and update timecode & progress bar.
 */
function updateTimelineScrubber(normProgress) {
  const fill = document.getElementById("timeline-fill");
  const playhead = document.getElementById("timeline-playhead");
  const timeDisplay = document.getElementById("time-display");
  const pctDisplay = document.getElementById("time-percentage");

  const pct = Math.max(0, Math.min(100, normProgress * 100));

  if (fill) fill.style.width = `${pct}%`;
  if (playhead) playhead.style.left = `${pct}%`;

  if (timeDisplay) {
    const curFormatted = formatTimecode(state.currentTime);
    const durFormatted = formatTimecode(state.durationSeconds);
    timeDisplay.textContent = `${curFormatted} / ${durFormatted}`;
  }

  if (pctDisplay) {
    pctDisplay.textContent = `${pct.toFixed(1)}%`;
  }
}

function formatTimecode(totalSec) {
  const mins = Math.floor(totalSec / 60);
  const secs = Math.floor(totalSec % 60);
  const ms = Math.floor((totalSec % 1) * 100);
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}.${ms.toString().padStart(2, "0")}`;
}

/**
 * Populate metadata panel values.
 */
function updateMetadataUI() {
  const metaGeo = document.getElementById("meta-geometry");
  const metaScale = document.getElementById("meta-scale");
  const metaTuning = document.getElementById("meta-tuning");
  const metaDuration = document.getElementById("meta-duration");
  const metaEvents = document.getElementById("meta-events");
  const metaSplit = document.getElementById("meta-layer-split");
  const scanBadgeText = document.getElementById("scan-mode-text");

  if (metaGeo) metaGeo.textContent = state.scanGeometry;
  if (metaScale) metaScale.textContent = state.scaleName;
  if (metaTuning) metaTuning.textContent = state.tuningSystem;
  if (metaDuration) metaDuration.textContent = `${state.durationSeconds.toFixed(2)}s`;
  if (metaEvents) metaEvents.textContent = state.events.length;

  if (scanBadgeText) {
    scanBadgeText.textContent = state.scanGeometry.replace(/_/g, " ").toUpperCase();
  }

  if (metaSplit) {
    let diffCount = 0;
    let ptCount = 0;
    for (const ev of state.events) {
      if (ev.layer === "point_source" || (ev.instrumentId && ev.instrumentId.includes("point"))) {
        ptCount++;
      } else {
        diffCount++;
      }
    }
    metaSplit.textContent = `${diffCount} / ${ptCount}`;
  }
}

/**
 * Load and parse a JSON blueprint file.
 */
function handleJsonFileUpload(file) {
  const reader = new FileReader();
  reader.onload = async (e) => {
    try {
      const parsed = JSON.parse(e.target.result);
      if (!parsed.events || !Array.isArray(parsed.events)) {
        throw new Error("Invalid blueprint format: missing 'events' array.");
      }
      await loadTimeline(parsed);
      console.log(`[Earth Jukebox] Successfully loaded JSON: ${file.name}`);
    } catch (err) {
      alert(`Failed to parse blueprint JSON: ${err.message}`);
      console.error(err);
    }
  };
  reader.readAsText(file);
}

/**
 * Fetch and load sample NASA EIC blueprint.
 */
async function loadDefaultDemoBlueprint() {
  try {
    return await loadTimeline("sample_blueprint.json");
  } catch (err) {
    console.warn("[Earth Jukebox] Could not fetch sample_blueprint.json; generating algorithmic blueprint:", err);
    // Fallback: Generate demo blueprint algorithmically
    generateAlgorithmicDemoBlueprint();
  }
}

/**
 * Fallback algorithmic blueprint if network fetch is unavailable.
 */
function generateAlgorithmicDemoBlueprint() {
  const demoEvents = [];
  const duration = 5.0;
  const numSteps = 60;
  const pentatonicFrequencies = [130.81, 146.83, 164.81, 196.0, 220.0, 261.63, 293.66, 329.63, 392.0, 440.0, 523.25];

  for (let i = 0; i < numSteps; i++) {
    const t = (i / numSteps) * duration;
    const freq = pentatonicFrequencies[i % pentatonicFrequencies.length];
    const pan = (i / numSteps) * 2.0 - 1.0;

    demoEvents.push({
      timeSeconds: t,
      durationSeconds: 0.12,
      pitch: freq,
      velocity: 0.65,
      pan: pan,
      instrumentId: "diffuse_pad",
      layer: "diffuse",
      spatialPosition: { x: (i / numSteps) * 400, y: 150 },
    });
  }

  // Add distinct point source events
  demoEvents.push({
    timeSeconds: 1.8,
    durationSeconds: 0.35,
    pitch: 587.33, // D5
    velocity: 0.9,
    pan: 0.3,
    instrumentId: "point_source_pluck",
    layer: "point_source",
    spatialPosition: { x: 280, y: 90 },
  });

  demoEvents.push({
    timeSeconds: 3.4,
    durationSeconds: 0.4,
    pitch: 659.25, // E5
    velocity: 0.95,
    pan: 0.6,
    instrumentId: "point_source_pluck",
    layer: "point_source",
    spatialPosition: { x: 330, y: 110 },
  });

  const demoBlueprint = {
    metadata: {
      scaleName: "c_major_pentatonic",
      tuningSystem: "12-EDO",
      scanGeometry: "horizontal_sweep",
      durationSeconds: duration,
      totalEvents: demoEvents.length,
    },
    events: demoEvents,
  };

  scheduleBlueprint(demoBlueprint);
}

// ============================================================================
// 5.5. Accessibility: Spatial Audio Cursor & Scalar Data Loading Engine (Task 15)
// ============================================================================

/**
 * Load and parse secondary JSON containing raw quantitative scalar data.
 * Enables accessible probing of the true scientific data underlying legacy RGB pixels.
 * 
 * @param {string|Object} jsonUrlOrData - URL string or parsed JSON object/array
 * @returns {Promise<Object>} Resolves with parsed scalar dataset
 */
async function loadScalarData(jsonUrlOrData) {
  let rawData = null;

  if (typeof jsonUrlOrData === "string") {
    try {
      const response = await fetch(jsonUrlOrData);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status} ${response.statusText}`);
      }
      rawData = await response.json();
      state.spatialCursor.scalarUrl = jsonUrlOrData;
    } catch (err) {
      console.warn(`[Earth Jukebox] Failed to fetch secondary scalar JSON from "${jsonUrlOrData}", using procedural fallback:`, err.message);
      state.spatialCursor.scalarData = generateProceduralScalarData();
      updateScalarTelemetryUI();
      return state.spatialCursor.scalarData;
    }
  } else if (typeof jsonUrlOrData === "object" && jsonUrlOrData !== null) {
    rawData = jsonUrlOrData;
  } else {
    state.spatialCursor.scalarData = generateProceduralScalarData();
    updateScalarTelemetryUI();
    return state.spatialCursor.scalarData;
  }

  state.spatialCursor.scalarData = parseScalarDataset(rawData);
  console.log(
    `[Earth Jukebox] Secondary scalar dataset loaded: ${state.spatialCursor.scalarData.width}x${state.spatialCursor.scalarData.height} (Range: [${state.spatialCursor.scalarData.min.toFixed(4)}, ${state.spatialCursor.scalarData.max.toFixed(4)}])`
  );
  updateScalarTelemetryUI();
  return state.spatialCursor.scalarData;
}

/**
 * Parse and normalize arbitrary JSON scalar dataset formats into a uniform matrix.
 * Supports 2D matrices, flat arrays with shape/width/height, and wrapped objects.
 */
function parseScalarDataset(rawData) {
  if (!rawData) {
    return generateProceduralScalarData();
  }

  // Case 1: Direct 2D matrix [[0.1, 0.2], ...]
  if (Array.isArray(rawData) && Array.isArray(rawData[0])) {
    const h = rawData.length;
    const w = rawData[0].length;
    let min = Infinity, max = -Infinity;
    for (let r = 0; r < h; r++) {
      for (let c = 0; c < w; c++) {
        const val = Number(rawData[r][c]) || 0;
        if (val < min) min = val;
        if (val > max) max = val;
      }
    }
    return {
      width: w,
      height: h,
      matrix: rawData,
      min: min === Infinity ? 0 : min,
      max: max === -Infinity ? 1 : max,
      metadata: {},
    };
  }

  // Case 2: Wrapped object { width, height, data: ... } or { scalar_array: ... } or { matrix: ... }
  if (typeof rawData === "object") {
    const meta = rawData.metadata || {};
    const innerData = rawData.data || rawData.scalar_array || rawData.matrix || rawData.values || rawData.grid;

    if (Array.isArray(innerData)) {
      // 2D nested array inside object
      if (Array.isArray(innerData[0])) {
        const h = innerData.length;
        const w = innerData[0].length;
        let min = Infinity, max = -Infinity;
        for (let r = 0; r < h; r++) {
          for (let c = 0; c < w; c++) {
            const val = Number(innerData[r][c]) || 0;
            if (val < min) min = val;
            if (val > max) max = val;
          }
        }
        return {
          width: w,
          height: h,
          matrix: innerData,
          min: typeof meta.minValue === "number" ? meta.minValue : (min === Infinity ? 0 : min),
          max: typeof meta.maxValue === "number" ? meta.maxValue : (max === -Infinity ? 1 : max),
          metadata: meta,
        };
      }

      // Flat 1D array inside object
      const w = rawData.width || (meta.width) || (rawData.shape ? rawData.shape[1] : 80);
      const h = rawData.height || (meta.height) || (rawData.shape ? rawData.shape[0] : Math.ceil(innerData.length / w));
      const matrix = [];
      let min = Infinity, max = -Infinity;

      for (let r = 0; r < h; r++) {
        const row = [];
        for (let c = 0; c < w; c++) {
          const idx = r * w + c;
          const val = idx < innerData.length ? (Number(innerData[idx]) || 0) : 0;
          row.push(val);
          if (val < min) min = val;
          if (val > max) max = val;
        }
        matrix.push(row);
      }

      return {
        width: w,
        height: h,
        matrix: matrix,
        min: typeof meta.minValue === "number" ? meta.minValue : (min === Infinity ? 0 : min),
        max: typeof meta.maxValue === "number" ? meta.maxValue : (max === -Infinity ? 1 : max),
        metadata: meta,
      };
    }
  }

  return generateProceduralScalarData();
}

/**
 * Procedural fallback scalar field matching the synthetic EIC visualization.
 */
function generateProceduralScalarData(w = 80, h = 50) {
  const matrix = [];
  const cx = w / 2;
  const cy = h / 2;
  let minVal = Infinity;
  let maxVal = -Infinity;

  for (let y = 0; y < h; y++) {
    const row = [];
    const ny = y / h;
    for (let x = 0; x < w; x++) {
      const nx = x / w;
      const dist = Math.hypot(x - cx, y - cy);
      const angle = Math.atan2(y - cy, x - cx);
      const diffuse = 0.5 + 0.3 * Math.sin(nx * 4.0 + Math.cos(ny * 3.0)) + 0.15 * Math.sin(angle * 2.0 + dist / 8.0);
      const spotDist = Math.hypot(x - w * 0.72, y - h * 0.35);
      const hotspot = Math.exp(-(spotDist * spotDist) / 50.0);
      const val = Math.max(0.0, Math.min(1.0, diffuse * 0.75 + hotspot * 0.7));
      row.push(val);
      if (val < minVal) minVal = val;
      if (val > maxVal) maxVal = val;
    }
    matrix.push(row);
  }

  return {
    width: w,
    height: h,
    matrix: matrix,
    min: minVal === Infinity ? 0 : minVal,
    max: maxVal === -Infinity ? 1 : maxVal,
    metadata: { description: "Procedural fallback NASA EIC scalar field" },
  };
}

/**
 * Map canvas (x, y) coordinates to the underlying quantitative scalar data array.
 * 
 * @param {number} canvasX - Mouse X in canvas pixel space
 * @param {number} canvasY - Mouse Y in canvas pixel space
 * @returns {Object} Probed scalar value, grid indices, and normalized coordinates
 */
function getScalarAt(canvasX, canvasY) {
  if (!state.spatialCursor.scalarData) {
    state.spatialCursor.scalarData = generateProceduralScalarData();
  }

  const dataset = state.spatialCursor.scalarData;
  const canvasW = p5CanvasInstance ? p5CanvasInstance.width : 800;
  const canvasH = p5CanvasInstance ? p5CanvasInstance.height : 500;
  const dataW = Math.max(1, canvasW - 45); // Left data area, excluding colorbar

  let normX = canvasX / dataW;
  let normY = canvasY / canvasH;

  // Probe colorbar if mouse is in the right colorbar strip
  if (canvasX > dataW && canvasX <= canvasW) {
    const cbScalar = Math.max(0.0, Math.min(1.0, 1.0 - (canvasY - 30) / Math.max(1, canvasH - 60)));
    return {
      scalar: cbScalar,
      col: dataset.width - 1,
      row: Math.min(dataset.height - 1, Math.max(0, Math.floor(normY * dataset.height))),
      normX: Math.max(0.0, Math.min(1.0, normX)),
      normY: Math.max(0.0, Math.min(1.0, normY)),
      isColorbar: true,
    };
  }

  normX = Math.max(0.0, Math.min(1.0, normX));
  normY = Math.max(0.0, Math.min(1.0, normY));

  const col = Math.min(dataset.width - 1, Math.max(0, Math.floor(normX * dataset.width)));
  const row = Math.min(dataset.height - 1, Math.max(0, Math.floor(normY * dataset.height)));

  let val = 0;
  if (Array.isArray(dataset.matrix) && Array.isArray(dataset.matrix[row])) {
    val = dataset.matrix[row][col];
  }

  return {
    scalar: typeof val === "number" ? val : 0,
    col: col,
    row: row,
    normX: normX,
    normY: normY,
    isColorbar: false,
  };
}

/**
 * Handle mousemove event over the p5.js canvas to drive the spatial audio cursor.
 */
function handleCanvasMouseMove(e, p, canvasElt) {
  if (!state.spatialCursor.enabled) return;

  const target = canvasElt || (p5CanvasInstance ? p5CanvasInstance.canvas : null);
  if (!target) return;

  const rect = target.getBoundingClientRect();
  const scaleX = target.width / (rect.width || 1);
  const scaleY = target.height / (rect.height || 1);

  const canvasX = Math.max(0, Math.min(target.width, (e.clientX - rect.left) * scaleX));
  const canvasY = Math.max(0, Math.min(target.height, (e.clientY - rect.top) * scaleY));

  state.spatialCursor.canvasX = canvasX;
  state.spatialCursor.canvasY = canvasY;
  state.spatialCursor.isHovering = true;

  // Map mouse (x, y) to the underlying scalar data
  const probe = getScalarAt(canvasX, canvasY);
  state.spatialCursor.scalarValue = probe.scalar;
  state.spatialCursor.normX = probe.normX;
  state.spatialCursor.normY = probe.normY;

  // Update 3D spatial audio position
  updateSpatialAudioPosition(probe.normX, probe.normY, probe.scalar);

  // Trigger earcon when hover moves between cells or beyond pixel threshold
  const dist = Math.hypot(
    canvasX - state.spatialCursor.lastCoord.x,
    canvasY - state.spatialCursor.lastCoord.y
  );

  if (
    dist >= 4 ||
    probe.col !== state.spatialCursor.lastCoord.col ||
    probe.row !== state.spatialCursor.lastCoord.row
  ) {
    state.spatialCursor.lastCoord.x = canvasX;
    state.spatialCursor.lastCoord.y = canvasY;
    state.spatialCursor.lastCoord.col = probe.col;
    state.spatialCursor.lastCoord.row = probe.row;

    triggerHoverEarcon(probe.scalar, probe.normX, probe.normY);
  }

  updateSpatialCursorTelemetryUI(probe);
}

/**
 * Handle cursor entering the canvas.
 */
function handleCanvasMouseEnter() {
  if (!state.spatialCursor.enabled) return;
  state.spatialCursor.isHovering = true;
}

/**
 * Handle cursor leaving the canvas.
 */
function handleCanvasMouseLeave() {
  state.spatialCursor.isHovering = false;
  state.spatialCursor.lastCoord = { x: -1, y: -1, col: -1, row: -1 };
  const hudCoords = document.getElementById("hud-coordinates");
  if (hudCoords) {
    hudCoords.textContent = "X: -- | Y: --";
  }
}

/**
 * Toggle spatial audio cursor enabled state.
 */
function setSpatialCursorEnabled(enabled) {
  state.spatialCursor.enabled = Boolean(enabled);
  if (!state.spatialCursor.enabled) {
    state.spatialCursor.isHovering = false;
  }
  const chk = document.getElementById("chk-spatial-cursor");
  if (chk) chk.checked = state.spatialCursor.enabled;
}

/**
 * Update UI telemetry indicators with live scalar probe data.
 */
function updateSpatialCursorTelemetryUI(probe) {
  const hudCoords = document.getElementById("hud-coordinates");
  if (hudCoords && state.spatialCursor.isHovering) {
    hudCoords.textContent = `X: ${Math.round(state.spatialCursor.canvasX)} | Y: ${Math.round(state.spatialCursor.canvasY)} | Scalar: ${probe.scalar.toFixed(3)}`;
  }

  const telScalar = document.getElementById("telemetry-scalar");
  if (telScalar) {
    telScalar.textContent = probe.scalar.toFixed(4);
  }

  const tel3D = document.getElementById("telemetry-3d-pos");
  if (tel3D && state.spatialCursor.pos3D) {
    const p = state.spatialCursor.pos3D;
    tel3D.textContent = `[${p.x.toFixed(2)}, ${p.y.toFixed(2)}, ${p.z.toFixed(2)}]m`;
  }
}

/**
 * Update scalar grid size readout in the UI.
 */
function updateScalarTelemetryUI() {
  const gridEl = document.getElementById("telemetry-grid-size");
  if (gridEl && state.spatialCursor.scalarData) {
    gridEl.textContent = `${state.spatialCursor.scalarData.width} × ${state.spatialCursor.scalarData.height}`;
  }
}

/**
 * Handle secondary scalar JSON file upload via FileReader.
 */
function handleScalarFileUpload(file) {
  const reader = new FileReader();
  reader.onload = async (e) => {
    try {
      const parsed = JSON.parse(e.target.result);
      await loadScalarData(parsed);
      console.log(`[Earth Jukebox] Successfully loaded secondary scalar JSON: ${file.name}`);
    } catch (err) {
      alert(`Failed to parse scalar data JSON: ${err.message}`);
      console.error(err);
    }
  };
  reader.readAsText(file);
}

// ============================================================================
// 6. DOM Event Listeners & Bootstrapping
// ============================================================================

function setupEventListeners() {
  // Load JSON Button & File Input
  const btnLoadJson = document.getElementById("btn-load-json");
  const fileInput = document.getElementById("json-file-input");

  if (btnLoadJson && fileInput) {
    btnLoadJson.addEventListener("click", () => {
      fileInput.click();
    });
    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleJsonFileUpload(e.target.files[0]);
      }
    });
  }

  // Quick Demo Button
  const btnDemo = document.getElementById("btn-load-demo");
  if (btnDemo) {
    btnDemo.addEventListener("click", () => {
      loadDefaultDemoBlueprint();
    });
  }

  // Play Button
  const btnPlay = document.getElementById("btn-play");
  if (btnPlay) {
    btnPlay.addEventListener("click", () => {
      playPlayback();
    });
  }

  // Pause Button
  const btnPause = document.getElementById("btn-pause");
  if (btnPause) {
    btnPause.addEventListener("click", () => {
      pausePlayback();
    });
  }

  // Stop Button
  const btnStop = document.getElementById("btn-stop");
  if (btnStop) {
    btnStop.addEventListener("click", () => {
      stopPlayback();
    });
  }

  // Timeline Scrubber Click/Seek
  const scrubber = document.getElementById("timeline-scrubber");
  if (scrubber) {
    scrubber.addEventListener("click", (e) => {
      const rect = scrubber.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const normProgress = Math.max(0, Math.min(1.0, clickX / rect.width));
      seekPlayback(normProgress * state.durationSeconds);
    });
  }

  // Master Volume Slider & Mute
  const volumeSlider = document.getElementById("volume-slider");
  const volumeReadout = document.getElementById("volume-readout");
  const btnMute = document.getElementById("btn-mute");

  if (volumeSlider) {
    volumeSlider.addEventListener("input", (e) => {
      const val = parseFloat(e.target.value);
      if (masterVolume) {
        masterVolume.volume.value = val;
      }
      if (volumeReadout) {
        volumeReadout.textContent = `${val >= 0 ? "+" : ""}${val} dB`;
      }
    });
  }

  if (btnMute) {
    btnMute.addEventListener("click", () => {
      state.isMuted = !state.isMuted;
      if (masterVolume) {
        masterVolume.mute = state.isMuted;
      }
      btnMute.textContent = state.isMuted ? "🔈" : "🔇";
      btnMute.title = state.isMuted ? "Unmute" : "Mute";
    });
  }

  // Space Reverb Wet Slider
  const reverbSlider = document.getElementById("reverb-slider");
  const reverbReadout = document.getElementById("reverb-readout");
  if (reverbSlider) {
    reverbSlider.addEventListener("input", (e) => {
      const wet = parseInt(e.target.value, 10) / 100.0;
      if (spaceReverb) {
        spaceReverb.wet.value = wet;
      }
      if (reverbReadout) {
        reverbReadout.textContent = `${e.target.value}%`;
      }
    });
  }

  // Visualization Checkbox Toggles
  const chkScanHead = document.getElementById("chk-show-scanhead");
  if (chkScanHead) {
    chkScanHead.addEventListener("change", (e) => {
      state.showScanHead = e.target.checked;
    });
  }

  const chkPulses = document.getElementById("chk-show-pulses");
  if (chkPulses) {
    chkPulses.addEventListener("change", (e) => {
      state.showPulses = e.target.checked;
    });
  }

  const chkGrid = document.getElementById("chk-show-grid");
  if (chkGrid) {
    chkGrid.addEventListener("change", (e) => {
      state.showGrid = e.target.checked;
    });
  }

  // Spatial Audio Cursor Checkbox Toggle (Task 15)
  const chkCursor = document.getElementById("chk-spatial-cursor");
  if (chkCursor) {
    chkCursor.addEventListener("change", (e) => {
      setSpatialCursorEnabled(e.target.checked);
    });
  }

  // Load Scalar Data Button & File Input (Task 15)
  const btnLoadScalar = document.getElementById("btn-load-scalar");
  const scalarFileInput = document.getElementById("scalar-file-input");
  if (btnLoadScalar && scalarFileInput) {
    btnLoadScalar.addEventListener("click", () => {
      scalarFileInput.click();
    });
    scalarFileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleScalarFileUpload(e.target.files[0]);
      }
    });
  }

  // Sample Scalar Data Button (Task 15)
  const btnSampleScalar = document.getElementById("btn-load-sample-scalar");
  if (btnSampleScalar) {
    btnSampleScalar.addEventListener("click", () => {
      loadScalarData("sample_scalar_data.json");
    });
  }

  // Keyboard Shortcuts: Space = Play/Pause, Esc = Stop
  window.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT") return;
    if (e.code === "Space") {
      e.preventDefault();
      if (state.isPlaying) {
        pausePlayback();
      } else {
        playPlayback();
      }
    } else if (e.code === "Escape") {
      e.preventDefault();
      stopPlayback();
    }
  });
}

// ============================================================================
// 7. Initialization Lifecycle
// ============================================================================

window.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  updatePlaybackUI();
  updateAudioStatusUI();

  // Instantiate p5 instance in the container
  p5CanvasInstance = new p5(sketch);

  // Auto-load default demo blueprint
  loadDefaultDemoBlueprint();

  // Auto-load secondary sample scalar dataset for spatial audio probe (Task 15)
  loadScalarData("sample_scalar_data.json");
});

// ============================================================================
// 8. Global Module & Window Exports
// ============================================================================

if (typeof window !== "undefined") {
  window.loadTimeline = loadTimeline;
  window.scheduleTimeline = scheduleTimeline;
  window.scheduleBlueprint = scheduleBlueprint;
  window.getSynthForInstrument = getSynthForInstrument;
  window.playPlayback = playPlayback;
  window.pausePlayback = pausePlayback;
  window.stopPlayback = stopPlayback;
  window.seekPlayback = seekPlayback;
  window.state = state;

  // Spatial Audio Cursor API exports (Task 15)
  window.loadScalarData = loadScalarData;
  window.getScalarAt = getScalarAt;
  window.triggerHoverEarcon = triggerHoverEarcon;
  window.updateSpatialAudioPosition = updateSpatialAudioPosition;
  window.initSpatialCursorAudio = initSpatialCursorAudio;
  window.setSpatialCursorEnabled = setSpatialCursorEnabled;
  window.handleCanvasMouseMove = handleCanvasMouseMove;
  window.handleCanvasMouseEnter = handleCanvasMouseEnter;
  window.handleCanvasMouseLeave = handleCanvasMouseLeave;
  window.generateProceduralScalarData = generateProceduralScalarData;
  window.parseScalarDataset = parseScalarDataset;
  window.spatialCursorState = state.spatialCursor;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    loadTimeline,
    scheduleTimeline,
    scheduleBlueprint,
    getSynthForInstrument,
    playPlayback,
    pausePlayback,
    stopPlayback,
    seekPlayback,
    state,

    // Spatial Audio Cursor API exports (Task 15)
    loadScalarData,
    getScalarAt,
    triggerHoverEarcon,
    updateSpatialAudioPosition,
    initSpatialCursorAudio,
    setSpatialCursorEnabled,
    handleCanvasMouseMove,
    handleCanvasMouseEnter,
    handleCanvasMouseLeave,
    generateProceduralScalarData,
    parseScalarDataset,
    spatialCursorState: state.spatialCursor,
  };
}
