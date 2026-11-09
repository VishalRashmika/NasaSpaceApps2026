"""
Unit tests for frontend files: index.html, style.css, script.js, and sample blueprints.
Verifies CDN inclusions, canvas container setup, UI panel buttons, and audio/canvas bindings.
"""

import json
from pathlib import Path
import re
import subprocess
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


class TestFrontendStructure(unittest.TestCase):
    """Test suite ensuring all frontend files meet the sonification specifications."""

    def setUp(self):
        self.index_html_path = FRONTEND_DIR / "index.html"
        self.style_css_path = FRONTEND_DIR / "style.css"
        self.script_js_path = FRONTEND_DIR / "script.js"
        self.sample_blueprint_path = FRONTEND_DIR / "sample_blueprint.json"

    def test_frontend_files_exist(self):
        """Verify index.html, style.css, and script.js exist in frontend/."""
        self.assertTrue(self.index_html_path.exists(), "frontend/index.html is missing")
        self.assertTrue(self.style_css_path.exists(), "frontend/style.css is missing")
        self.assertTrue(self.script_js_path.exists(), "frontend/script.js is missing")

    def test_index_html_cdn_links(self):
        """Task 1: index.html must include CDN links for p5.js and Tone.js."""
        content = self.index_html_path.read_text(encoding="utf-8")

        # p5.js CDN check
        self.assertTrue(
            re.search(r'<script[^>]*src=["\'][^"\']*p5(\.min)?\.js[^"\']*["\']', content),
            "p5.js CDN script tag missing in index.html",
        )

        # Tone.js CDN check
        self.assertTrue(
            re.search(r'<script[^>]*src=["\'][^"\']*tone[^"\']*(\.min)?\.js[^"\']*["\']', content, re.IGNORECASE),
            "Tone.js CDN script tag missing in index.html",
        )

        # Style & Script linking
        self.assertIn('href="style.css"', content)
        self.assertIn('src="script.js"', content)

    def test_index_html_canvas_container(self):
        """Task 2: index.html must have a canvas container for p5.js to render EIC image and moving scan head."""
        content = self.index_html_path.read_text(encoding="utf-8")
        self.assertTrue(
            re.search(r'id=["\']canvas-container["\']', content),
            "Canvas container with id='canvas-container' missing in index.html",
        )

    def test_index_html_ui_panel_buttons(self):
        """Task 3: Create a UI panel with buttons to 'Load JSON', 'Play', 'Pause', and 'Stop'."""
        content = self.index_html_path.read_text(encoding="utf-8")

        # Check for UI panel / control panel
        self.assertTrue(
            re.search(r'class=["\'][^"\']*(ui-panel|control-panel)[^"\']*["\']', content),
            "UI panel / control panel missing in index.html",
        )

        # Button: Load JSON
        self.assertTrue(
            re.search(r'id=["\']btn-load-json["\']|Load JSON', content, re.IGNORECASE),
            "Button to 'Load JSON' missing in index.html",
        )

        # Button: Play
        self.assertTrue(
            re.search(r'id=["\']btn-play["\']|>Play<', content),
            "Button to 'Play' missing in index.html",
        )

        # Button: Pause
        self.assertTrue(
            re.search(r'id=["\']btn-pause["\']|>Pause<', content),
            "Button to 'Pause' missing in index.html",
        )

        # Button: Stop
        self.assertTrue(
            re.search(r'id=["\']btn-stop["\']|>Stop<', content),
            "Button to 'Stop' missing in index.html",
        )

    def test_style_css_styling(self):
        """Verify style.css includes rules for canvas container, panel, buttons, and animations."""
        css = self.style_css_path.read_text(encoding="utf-8")
        self.assertIn("canvas-container", css)
        self.assertIn(".btn", css)
        self.assertTrue(
            re.search(r'btn-play|\.btn', css),
            "Button styling missing in style.css",
        )

    def test_script_js_syntax_and_initializations(self):
        """Task 4: script.js initializes p5.js canvas and sets up basic Tone.js transport and synth routing."""
        js = self.script_js_path.read_text(encoding="utf-8")

        # Syntax check via Node.js
        res = subprocess.run(
            ["node", "-c", str(self.script_js_path)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"script.js syntax error: {res.stderr}")

        # p5.js canvas initialization
        self.assertIn("createCanvas", js, "p5 createCanvas call missing in script.js")
        self.assertIn("canvas-container", js, "parent canvas-container binding missing in script.js")

        # Tone.js transport and routing setup
        self.assertIn("Tone.Transport", js, "Tone.Transport missing in script.js")
        self.assertTrue(
            "Tone.PolySynth" in js or "Tone.Synth" in js,
            "Tone synth routing missing in script.js",
        )
        self.assertTrue(
            "Tone.Destination" in js or "toDestination" in js,
            "Tone.Destination routing missing in script.js",
        )

        # Transport playback methods
        self.assertIn("Tone.Transport.start", js)
        self.assertIn("Tone.Transport.pause", js)
        self.assertIn("Tone.Transport.stop", js)

        # Scanhead rendering
        self.assertIn("drawScanHead", js)
        self.assertIn("horizontal_sweep", js)

    def test_load_timeline_function(self):
        """Task 14.1: Write loadTimeline(jsonUrl) to fetch and parse the JSON timeline."""
        js = self.script_js_path.read_text(encoding="utf-8")
        self.assertTrue(
            re.search(r"async\s+function\s+loadTimeline\s*\(\s*jsonUrl\s*\)", js) or
            re.search(r"function\s+loadTimeline\s*\(\s*jsonUrl\s*\)", js),
            "loadTimeline(jsonUrl) function missing in script.js",
        )
        self.assertIn("fetch(jsonUrl)", js)
        self.assertIn(".json()", js)

    def test_tone_part_scheduling(self):
        """Task 14.2: Use Tone.js Part or Sequence to schedule the events with precise timing."""
        js = self.script_js_path.read_text(encoding="utf-8")
        self.assertTrue(
            "new Tone.Part" in js or "new Tone.Sequence" in js,
            "Tone.Part or Tone.Sequence scheduling missing in script.js",
        )
        self.assertIn("partEvents", js)
        self.assertIn("triggerAudioEvent", js)

    def test_instrument_id_synth_mapping(self):
        """Task 14.3: Map instrumentId from JSON to Tone.js synths (Tone.PolySynth for diffuse, Tone.PluckSynth for point sources)."""
        js = self.script_js_path.read_text(encoding="utf-8")
        self.assertIn("Tone.PolySynth", js, "Tone.PolySynth missing in script.js")
        self.assertIn("Tone.PluckSynth", js, "Tone.PluckSynth missing in script.js")
        self.assertIn("getSynthForInstrument", js, "getSynthForInstrument mapping function missing in script.js")
        self.assertIn("diffuse_pad", js, "diffuse_pad mapping missing in script.js")
        self.assertIn("point_source_pluck", js, "point_source_pluck mapping missing in script.js")

    def test_scanhead_sync_with_transport_clock(self):
        """Task 14.4: Ensure p5.js canvas visualizes scan head moving in exact sync with Tone.Transport clock."""
        js = self.script_js_path.read_text(encoding="utf-8")
        self.assertIn("Tone.Transport.seconds", js, "Tone.Transport.seconds sync missing in script.js")
        self.assertIn("drawScanHead", js, "drawScanHead function missing in script.js")
        self.assertIn("normProgress", js, "normProgress computation missing in script.js")

    def test_node_load_timeline_execution(self):
        """Task 14 integration: Evaluate script.js in Node.js with Tone and p5 mocks to verify end-to-end loadTimeline behavior."""
        node_script = """
const fs = require('fs');
const vm = require('vm');

let scheduledPartEvents = null;
let partStarted = false;

const sandbox = {
  window: {},
  document: {
    getElementById: () => ({
      addEventListener: () => {},
      classList: { add: () => {}, remove: () => {} },
      style: {},
      textContent: ''
    }),
    querySelectorAll: () => []
  },
  console: console,
  setTimeout: setTimeout,
  clearTimeout: clearTimeout,
  fetch: async (url) => {
    if (url === 'frontend/sample_blueprint.json' || url === 'sample_blueprint.json') {
      const data = JSON.parse(fs.readFileSync('frontend/sample_blueprint.json', 'utf8'));
      return { ok: true, status: 200, json: async () => data };
    }
    throw new Error('404: ' + url);
  },
  Tone: {
    Volume: function() { this.chain = () => {}; this.connect = () => this; this.volume = { value: 0 }; },
    Limiter: function() {},
    Reverb: function() { this.wet = { value: 0 }; },
    Panner: function() { this.connect = () => this; this.pan = { setValueAtTime: () => {} }; },
    PolySynth: function() {
      this.connect = () => this;
      this.volume = { value: 0 };
      this.triggerAttackRelease = () => {};
      this.releaseAll = () => {};
    },
    PluckSynth: function() {
      this.connect = () => this;
      this.volume = { value: 0 };
      this.triggerAttackRelease = () => {};
      this.triggerAttack = () => {};
      this.triggerRelease = () => {};
    },
    Synth: function() {},
    Destination: {},
    Frequency: () => ({ toFrequency: () => 440 }),
    Transport: {
      bpm: { value: 120 },
      seconds: 0,
      start: () => {},
      pause: () => {},
      stop: () => {},
      cancel: () => {},
      schedule: () => {}
    },
    Part: function(cb, events) {
      this.events = events;
      scheduledPartEvents = events;
      this.start = () => { partStarted = true; };
      this.dispose = () => {};
    },
    Draw: { schedule: (fn) => fn() },
    context: { state: 'running' }
  },
  p5: function() {}
};
sandbox.window.addEventListener = () => {};

const script = fs.readFileSync('frontend/script.js', 'utf8');
vm.createContext(sandbox);
vm.runInContext(script, sandbox);

sandbox.window.loadTimeline('frontend/sample_blueprint.json').then((bp) => {
  if (!bp || !Array.isArray(bp.events)) process.exit(1);
  if (!scheduledPartEvents || scheduledPartEvents.length !== bp.events.length) process.exit(2);
  if (!partStarted) process.exit(3);

  const diffSynth = sandbox.window.getSynthForInstrument('diffuse_pad', 'diffuse');
  const pluckSynth = sandbox.window.getSynthForInstrument('point_source_pluck', 'point_source');
  if (!diffSynth || !pluckSynth) process.exit(4);
  if (diffSynth === pluckSynth) process.exit(5);

  process.exit(0);
}).catch((err) => {
  console.error(err);
  process.exit(10);
});
"""
        res = subprocess.run(
            ["node", "-e", node_script],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Node execution error: {res.stderr}\n{res.stdout}")

    def test_sample_blueprint_validity(self):
        """Verify sample blueprint JSON contains expected NASA EIC sonification schema."""
        self.assertTrue(self.sample_blueprint_path.exists())
        with open(self.sample_blueprint_path, "r", encoding="utf-8") as f:
            blueprint = json.load(f)

        self.assertIn("metadata", blueprint)
        self.assertIn("events", blueprint)
        self.assertGreater(len(blueprint["events"]), 0)
        self.assertIn("scanGeometry", blueprint["metadata"])

    def test_sample_scalar_data_validity(self):
        """Verify sample secondary scalar dataset JSON exists and matches 2D quantitative schema."""
        sample_scalar_path = FRONTEND_DIR / "sample_scalar_data.json"
        self.assertTrue(sample_scalar_path.exists(), "frontend/sample_scalar_data.json is missing")
        with open(sample_scalar_path, "r", encoding="utf-8") as f:
            scalar_data = json.load(f)

        self.assertIn("metadata", scalar_data)
        self.assertIn("width", scalar_data)
        self.assertIn("height", scalar_data)
        self.assertIn("data", scalar_data)
        self.assertEqual(len(scalar_data["data"]), scalar_data["height"])
        self.assertEqual(len(scalar_data["data"][0]), scalar_data["width"])
        self.assertGreaterEqual(scalar_data["metadata"]["minValue"], 0.0)
        self.assertLessEqual(scalar_data["metadata"]["maxValue"], 1.0)

    def test_spatial_audio_cursor_static_definitions(self):
        """Task 15: Verify script.js and index.html implement the 4 core spatial cursor tasks."""
        html = self.index_html_path.read_text(encoding="utf-8")
        js = self.script_js_path.read_text(encoding="utf-8")

        # 1. Track mousemove events over canvas
        self.assertIn("mousemove", js, "mousemove event tracking missing in script.js")
        self.assertIn("handleCanvasMouseMove", js, "handleCanvasMouseMove missing in script.js")
        self.assertIn("chk-spatial-cursor", html, "Spatial cursor checkbox missing in index.html")

        # 2. Map mouse (x, y) to underlying data array (secondary JSON load)
        self.assertIn("loadScalarData", js, "loadScalarData function missing in script.js")
        self.assertIn("getScalarAt", js, "getScalarAt function missing in script.js")
        self.assertIn("btn-load-scalar", html, "Load scalar button missing in index.html")

        # 3. Create short earcon sound that triggers on hover
        self.assertIn("triggerHoverEarcon", js, "triggerHoverEarcon function missing in script.js")
        self.assertIn("activeEarconPings", js, "activeEarconPings reticle visual missing in script.js")

        # 4. Use Tone.js Panner3D or native Web Audio PannerNode for 3D positioning
        self.assertIn("Tone.Panner3D", js, "Tone.Panner3D integration missing in script.js")
        self.assertIn("createPanner", js, "Native Web Audio createPanner integration missing in script.js")
        self.assertIn("updateSpatialAudioPosition", js, "updateSpatialAudioPosition missing in script.js")

    def test_node_spatial_audio_cursor_with_tone_panner3d(self):
        """Task 15 Node integration: Verify Tone.Panner3D 3D positioning, scalar mapping, and hover earcon."""
        node_test = """
const fs = require('fs');
const vm = require('vm');

let pannerPositions = [];
let earconAttacks = [];

const mockAudioParam = (initVal = 0) => {
  let v = initVal;
  return {
    value: v,
    setValueAtTime: (newV, time) => {
      v = newV;
      pannerPositions.push({ val: newV, time: time });
    }
  };
};

const sandbox = {
  window: {},
  document: {
    getElementById: () => ({
      addEventListener: () => {},
      classList: { add: () => {}, remove: () => {} },
      style: {},
      textContent: ''
    }),
    querySelectorAll: () => []
  },
  console: console,
  setTimeout: setTimeout,
  clearTimeout: clearTimeout,
  performance: { now: () => Date.now() },
  fetch: async (url) => {
    if (url === 'frontend/sample_scalar_data.json' || url === 'sample_scalar_data.json') {
      const data = JSON.parse(fs.readFileSync('frontend/sample_scalar_data.json', 'utf8'));
      return { ok: true, status: 200, json: async () => data };
    }
    throw new Error('404: ' + url);
  },
  Tone: {
    Volume: function() { this.chain = () => {}; this.connect = () => this; this.volume = { value: 0 }; },
    Limiter: function() {},
    Reverb: function() { this.wet = { value: 0 }; },
    Panner: function() { this.connect = () => this; this.pan = { setValueAtTime: () => {} }; },
    Panner3D: function(opts = {}) {
      this.panningModel = opts.panningModel || 'HRTF';
      this.distanceModel = opts.distanceModel || 'inverse';
      this.positionX = mockAudioParam(opts.positionX || 0);
      this.positionY = mockAudioParam(opts.positionY || 0);
      this.positionZ = mockAudioParam(opts.positionZ || -1.5);
      this.connect = () => this;
    },
    PolySynth: function() {
      this.connect = () => this;
      this.volume = { value: 0 };
      this.triggerAttackRelease = (freq, dur, time, vel) => {
        earconAttacks.push({ freq, dur, time, vel });
      };
      this.releaseAll = () => {};
    },
    PluckSynth: function() {
      this.connect = () => this;
      this.volume = { value: 0 };
      this.triggerAttackRelease = () => {};
      this.releaseAll = () => {};
    },
    Synth: function() {
      this.connect = () => this;
      this.triggerAttackRelease = (freq, dur, time, vel) => {
        earconAttacks.push({ freq, dur, time, vel });
      };
    },
    Destination: {},
    Frequency: () => ({ toFrequency: () => 440 }),
    Transport: {
      bpm: { value: 120 },
      seconds: 0,
      start: () => {},
      pause: () => {},
      stop: () => {},
      cancel: () => {},
      schedule: () => {}
    },
    Part: function(cb, events) {
      this.start = () => {};
      this.dispose = () => {};
    },
    Draw: { schedule: (fn) => fn() },
    now: () => 1.25,
    context: { state: 'running' }
  },
  p5: function() {}
};
sandbox.window.addEventListener = () => {};

const script = fs.readFileSync('frontend/script.js', 'utf8');
vm.createContext(sandbox);
vm.runInContext(script, sandbox);

// Test 1: Load secondary scalar data
const customData = {
  width: 4,
  height: 3,
  data: [
    [0.1, 0.2, 0.3, 0.4],
    [0.5, 0.6, 0.7, 0.8],
    [0.9, 0.95, 0.98, 1.0]
  ]
};

sandbox.window.loadScalarData(customData).then((ds) => {
  if (!ds || ds.width !== 4 || ds.height !== 3) process.exit(1);

  // Test 2: Map canvas (x, y) to underlying data
  // Middle of data area
  const probe = sandbox.window.getScalarAt(200, 150);
  if (typeof probe.scalar !== 'number' || probe.scalar < 0 || probe.scalar > 1) process.exit(2);

  // Test 3: 3D spatial acoustic positioning
  // normX = 0 (far left), normY = 0 (top)
  const posLeftTop = sandbox.window.updateSpatialAudioPosition(0.0, 0.0, 0.5);
  if (posLeftTop.x >= 0) process.exit(3); // Left must be negative X
  if (posLeftTop.y <= 0) process.exit(4); // Top must be positive Y
  if (posLeftTop.z >= 0) process.exit(5); // In front of listener: negative Z

  // normX = 1.0 (far right), normY = 1.0 (bottom)
  const posRightBottom = sandbox.window.updateSpatialAudioPosition(1.0, 1.0, 0.5);
  if (posRightBottom.x <= 0) process.exit(6); // Right must be positive X
  if (posRightBottom.y >= 0) process.exit(7); // Bottom must be negative Y

  // Test 4: Trigger hover earcon
  earconAttacks = [];
  const triggered = sandbox.window.triggerHoverEarcon(0.85, 0.75, 0.25);
  if (!triggered) process.exit(8);
  if (earconAttacks.length === 0) process.exit(9);
  const earcon = earconAttacks[0];
  if (typeof earcon.freq !== 'number' || earcon.freq < 200) process.exit(10);
  if (earcon.vel <= 0) process.exit(11);

  // Test 5: Canvas mousemove tracking
  const mockCanvas = {
    width: 800,
    height: 500,
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 800, height: 500 })
  };
  const mouseEvent = { clientX: 400, clientY: 250 };
  sandbox.window.handleCanvasMouseMove(mouseEvent, null, mockCanvas);
  const state = sandbox.window.spatialCursorState;
  if (!state.isHovering || state.canvasX !== 400 || state.canvasY !== 250) process.exit(12);

  process.exit(0);
}).catch((err) => {
  console.error(err);
  process.exit(20);
});
"""
        res = subprocess.run(
            ["node", "-e", node_test],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Node Tone.Panner3D test error: {res.stderr}\n{res.stdout}")

    def test_node_spatial_audio_cursor_with_native_web_audio_panner(self):
        """Task 15 Node integration: Verify fallback to native Web Audio PannerNode."""
        node_test = """
const fs = require('fs');
const vm = require('vm');

let nativePannerCreated = false;
let nativePositions = [];

const mockAudioParam = (initVal = 0) => {
  let v = initVal;
  return {
    value: v,
    setValueAtTime: (newV, time) => {
      v = newV;
      nativePositions.push({ val: newV, time: time });
    }
  };
};

const sandbox = {
  window: {},
  document: {
    getElementById: () => ({
      addEventListener: () => {},
      classList: { add: () => {}, remove: () => {} },
      style: {},
      textContent: ''
    }),
    querySelectorAll: () => []
  },
  console: console,
  setTimeout: setTimeout,
  clearTimeout: clearTimeout,
  performance: { now: () => Date.now() },
  fetch: async () => ({
    ok: true,
    json: async () => ({ width: 2, height: 2, data: [[0.2, 0.4], [0.6, 0.8]] })
  }),
  Tone: {
    Volume: function() { this.chain = () => {}; this.connect = () => this; this.volume = { value: 0 }; },
    Limiter: function() {},
    Reverb: function() { this.wet = { value: 0 }; },
    Panner: function() { this.connect = () => this; this.pan = { setValueAtTime: () => {} }; },
    PolySynth: function() {
      this.connect = () => this;
      this.volume = { value: 0 };
      this.triggerAttackRelease = () => {};
      this.releaseAll = () => {};
    },
    PluckSynth: function() {
      this.connect = () => this;
      this.volume = { value: 0 };
      this.triggerAttackRelease = () => {};
      this.releaseAll = () => {};
    },
    Synth: function() { this.connect = () => this; this.triggerAttackRelease = () => {}; },
    Destination: {},
    Frequency: () => ({ toFrequency: () => 440 }),
    Transport: {
      bpm: { value: 120 },
      seconds: 0,
      start: () => {},
      pause: () => {},
      stop: () => {},
      cancel: () => {},
      schedule: () => {}
    },
    Part: function() { this.start = () => {}; this.dispose = () => {}; },
    Draw: { schedule: (fn) => fn() },
    now: () => 2.0,
    context: {
      state: 'running',
      createPanner: () => {
        nativePannerCreated = true;
        return {
          panningModel: 'HRTF',
          distanceModel: 'inverse',
          positionX: mockAudioParam(0),
          positionY: mockAudioParam(0),
          positionZ: mockAudioParam(-1.5),
          connect: () => {}
        };
      }
    }
  },
  p5: function() {}
};
sandbox.window.addEventListener = () => {};

const script = fs.readFileSync('frontend/script.js', 'utf8');
vm.createContext(sandbox);
vm.runInContext(script, sandbox);

const audioObjs = sandbox.window.initSpatialCursorAudio();
if (!audioObjs || !audioObjs.panner) process.exit(1);
if (!nativePannerCreated) process.exit(2);

sandbox.window.updateSpatialAudioPosition(0.8, 0.2, 0.7);
if (nativePositions.length === 0) process.exit(3);

process.exit(0);
"""
        res = subprocess.run(
            ["node", "-e", node_test],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Node native PannerNode test error: {res.stderr}\n{res.stdout}")



if __name__ == "__main__":
    unittest.main()
