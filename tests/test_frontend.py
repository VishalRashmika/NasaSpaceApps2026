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

    def test_sample_blueprint_validity(self):
        """Verify sample blueprint JSON contains expected NASA EIC sonification schema."""
        self.assertTrue(self.sample_blueprint_path.exists())
        with open(self.sample_blueprint_path, "r", encoding="utf-8") as f:
            blueprint = json.load(f)

        self.assertIn("metadata", blueprint)
        self.assertIn("events", blueprint)
        self.assertGreater(len(blueprint["events"]), 0)
        self.assertIn("scanGeometry", blueprint["metadata"])


if __name__ == "__main__":
    unittest.main()
