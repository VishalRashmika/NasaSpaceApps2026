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
};

// ============================================================================
// 2. Audio Engine Setup & Synth Routing (Tone.js)
// ============================================================================

let masterVolume;
let masterLimiter;
let spaceReverb;
let diffuseSynth;
let pointSynth;
let diffusePanner;
let pointPanner;
let audioInitialized = false;

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

    // 4. Diffuse Emission Layer Synth (Polyphonic warm analog pad)
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

    // 5. Point Source Layer Synth (Snappy plucked transient)
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

    // 6. Transport configuration
    Tone.Transport.loop = false;
    Tone.Transport.bpm.value = 120;

    audioInitialized = true;
    updateAudioStatusUI();
    console.log("[Earth Jukebox] Tone.js audio engine & synths initialized.");
  } catch (err) {
    console.error("[Earth Jukebox] Error initializing audio engine:", err);
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
 */
function triggerAudioEvent(time, ev) {
  try {
    const pitch = ev.frequency || ev.pitch || 440;
    const durSec = ev.durationSeconds || (ev.duration ? ev.duration / 1000 : 0.2);
    const vel = typeof ev.velocity === "number" ? Math.max(0.05, Math.min(1.0, ev.velocity)) : 0.7;
    const pan = typeof ev.pan === "number" ? Math.max(-1.0, Math.min(1.0, ev.pan)) : 0.0;

    const isPointSource =
      ev.instrumentId &&
      (ev.instrumentId.includes("point") ||
       ev.instrumentId.includes("pluck") ||
       ev.instrumentId.includes("ping") ||
       ev.instrumentId.includes("hotspot") ||
       ev.layer === "point_source");

    if (isPointSource) {
      if (pointPanner && pointPanner.pan) {
        pointPanner.pan.setValueAtTime(pan, time);
      }
      pointSynth.triggerAttackRelease(pitch, durSec, time, vel);
      flashVoiceIndicator("point");
    } else {
      if (diffusePanner && diffusePanner.pan) {
        diffusePanner.pan.setValueAtTime(pan, time);
      }
      diffuseSynth.triggerAttackRelease(pitch, durSec, time, vel);
      flashVoiceIndicator("diffuse");
    }

    // Schedule visual acoustic ripple pulse on the p5 canvas
    if (state.showPulses) {
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
 * Schedule blueprint events onto Tone.Transport using Tone.Part.
 */
function scheduleBlueprint(blueprint) {
  initAudioEngine();

  // Clear previous schedule
  if (state.scheduledPart) {
    state.scheduledPart.dispose();
    state.scheduledPart = null;
  }
  Tone.Transport.cancel();

  state.blueprint = blueprint;
  const meta = blueprint.metadata || {};
  state.events = blueprint.events || [];
  state.durationSeconds = meta.durationSeconds || meta.duration_seconds || 5.0;
  state.scanGeometry = meta.scanGeometry || meta.scan_geometry || "horizontal_sweep";
  state.scaleName = meta.scaleName || meta.scale_name || "c_major_pentatonic";
  state.tuningSystem = meta.tuningSystem || meta.tuning_system || "12-EDO";

  // Format events for Tone.Part
  const partEvents = state.events.map((ev) => {
    let tSec = 0;
    if (typeof ev.timeSeconds === "number") {
      tSec = ev.timeSeconds;
    } else if (typeof ev.time === "number") {
      tSec = ev.time / 1000.0;
    }
    return [tSec, ev];
  });

  state.scheduledPart = new Tone.Part((time, ev) => {
    triggerAudioEvent(time, ev);
  }, partEvents);

  state.scheduledPart.start(0);
  state.scheduledPart.loop = false;

  // Schedule auto-stop when duration finishes
  Tone.Transport.schedule((time) => {
    Tone.Draw.schedule(() => {
      stopPlayback();
    }, time);
  }, state.durationSeconds);

  state.isLoaded = true;
  updateMetadataUI();
  updatePlaybackUI();
  console.log(`[Earth Jukebox] Scheduled ${state.events.length} events for ${state.durationSeconds}s playback.`);
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
  if (diffuseSynth) {
    try { diffuseSynth.releaseAll(); } catch (_) {}
  }
  if (pointSynth) {
    try { pointSynth.releaseAll(); } catch (_) {}
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

    // 3. Compute Playhead Position & Time
    if (audioInitialized && (state.isPlaying || state.isPaused)) {
      state.currentTime = Tone.Transport.seconds;
    }
    const normProgress = Math.max(0, Math.min(1.0, state.currentTime / state.durationSeconds));
    updateTimelineScrubber(normProgress);

    // 4. Render Active Event Ripples / Acoustic Pulses
    if (state.showPulses) {
      drawAcousticPulses(p);
    }

    // 5. Render Moving Geometric Scan Head
    if (state.showScanHead) {
      drawScanHead(p, normProgress);
    }

    // 6. Update HUD overlays
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
   * Live HUD telemetry readout.
   */
  function updateHUD(p) {
    const dataW = p.width - 45;
    const hudCoords = document.getElementById("hud-coordinates");
    if (hudCoords) {
      if (p.mouseX >= 0 && p.mouseX <= dataW && p.mouseY >= 0 && p.mouseY <= p.height) {
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
  reader.onload = (e) => {
    try {
      const parsed = JSON.parse(e.target.result);
      if (!parsed.events || !Array.isArray(parsed.events)) {
        throw new Error("Invalid blueprint format: missing 'events' array.");
      }
      stopPlayback();
      scheduleBlueprint(parsed);
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
    const res = await fetch("sample_blueprint.json");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    scheduleBlueprint(data);
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
});
