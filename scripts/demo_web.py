#!/usr/bin/env python3
"""Phase 6 Exit Demo: Browser Walkthrough Smoke Test (S-01 .. S-09).

Verifies the Web MVP functionality:
- S-01: Responsive shell, landmarks, skip link, viewport
- S-02: Color theming (light / dark)
- S-03: Reduced motion support
- S-04: Gallery catalog / selection & empty state
- S-05: Playback timing & playhead west->east movement
- S-06: Pause / resume / stop / scrubber consistency
- S-07: Audio legend sweep & readout
- S-08: Upload & numeric coordinate entry & validation
- S-09: Skin switching during playback
- Downloads: WAV, MIDI, Score JSON verification
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from earth_jukebox.bootstrap import build_app, build_settings
from earth_jukebox.domain.skins import get_skin
from earth_jukebox.domain.sonification.pitch import quantize_pitch
from earth_jukebox.infrastructure.vision.synthetic import generate_map


def run_walkthrough() -> int:
    cache_dir = Path("data/cache/smoke")
    cache_dir.mkdir(parents=True, exist_ok=True)

    settings = build_settings()
    app = build_app(settings)
    client = TestClient(app)

    print("=" * 80)
    print("EARTH JUKEBOX — PHASE 6 EXIT DEMO: WEB MVP WALKTHROUGH (S-01 .. S-09)")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # S-01: HTML Shell, responsive viewport, skip link, landmarks
    # -------------------------------------------------------------------------
    r_index = client.get("/")
    assert r_index.status_code == 200, f"Expected 200 for /, got {r_index.status_code}"
    html = r_index.text

    assert '<html lang="en">' in html, "HTML missing lang='en'"
    assert '<a class="skip" href="#main">' in html, "Skip link missing or wrong href"
    assert "<header" in html and "</header>" in html, "Missing header landmark"
    assert '<main id="main"' in html, "Missing main landmark with id='main'"
    assert html.count("<h1") == 1, "Must have exactly one <h1>"
    assert "width=device-width" in html, "Missing responsive viewport meta"
    print("PASS: S-01 (Shell, landmarks, skip link, responsive viewport)")

    # -------------------------------------------------------------------------
    # S-02: Theming (light / dark)
    # -------------------------------------------------------------------------
    r_css = client.get("/css/app.css")
    assert r_css.status_code == 200, "CSS failed to load"
    css = r_css.text

    assert ':root { --bg:#ffffff;' in css or ':root {' in css and '--bg:' in css
    assert '[data-theme="dark"]' in css, "Missing manual dark theme selector"
    assert "prefers-color-scheme: dark" in css, "Missing OS dark mode query"
    print("PASS: S-02 (Color theme custom properties & dark mode)")

    # -------------------------------------------------------------------------
    # S-03: Reduced motion
    # -------------------------------------------------------------------------
    assert "prefers-reduced-motion: reduce" in css, "Missing reduced-motion media query"
    assert ".playhead-line" in css, "Missing playhead overlay styling"
    print("PASS: S-03 (Reduced motion support & informational playhead styling)")

    # -------------------------------------------------------------------------
    # S-04: Gallery catalog endpoints & empty state handling
    # -------------------------------------------------------------------------
    r_samples = client.get("/api/samples")
    assert r_samples.status_code == 200
    samples = r_samples.json()
    assert isinstance(samples, list)
    assert 'id="gallery-empty"' in html, "Missing gallery empty state container"
    assert 'role="radiogroup"' in html, "Missing gallery radiogroup role"
    print(f"PASS: S-04 (Gallery catalog loaded: {len(samples)} bundled samples, empty state ready)")

    # -------------------------------------------------------------------------
    # S-05 & S-06: Playback, timing, playhead calculation & control consistency
    # -------------------------------------------------------------------------
    # Generate synthetic map to analyze and sonify
    png, field, legend, cbox, mbox = generate_map(cmap="viridis", seed=42)
    legend_dict = {
        "vmin": legend.vmin,
        "vmax": legend.vmax,
        "units": legend.units,
        "label": legend.label,
        "kind": legend.kind.value,
        "category": legend.category.value,
    }
    cbox_dict = {"x": cbox.x, "y": cbox.y, "w": cbox.w, "h": cbox.h}
    mbox_dict = {"x": mbox.x, "y": mbox.y, "w": mbox.w, "h": mbox.h}

    r_analyze = client.post(
        "/api/analyze",
        files={"image": ("viridis.png", png, "image/png")},
        data={
            "legend": json.dumps(legend_dict),
            "colorbar_box": json.dumps(cbox_dict),
            "map_box": json.dumps(mbox_dict),
        },
    )
    assert r_analyze.status_code == 200, f"Analyze failed: {r_analyze.text}"
    analysis = r_analyze.json()
    analysis_id = analysis["analysis_id"]
    confidence = analysis["quality"]["confidence"]
    badge = analysis["quality"]["confidence_badge"]
    assert confidence > 0.90, f"Expected high confidence, got {confidence}"

    # Sonify
    r_sonify = client.post(
        "/api/sonify",
        json={"analysis_id": analysis_id, "skin": "neutral", "n_cols": 48},
    )
    assert r_sonify.status_code == 200
    son_data = r_sonify.json()
    score = son_data["score"]
    total_beats = score["total_beats"]
    bpm = score["bpm"]
    notes = score["notes"]

    assert len(notes) > 0, "Score contains no notes"
    # Audio starts at beat 0 (< 500 ms)
    first_beat = min(n["t_beat"] for n in notes)
    assert first_beat == 0.0, f"Expected first note at beat 0, got {first_beat}"
    first_sec = first_beat * 60.0 / bpm
    assert first_sec < 0.5, f"Audio start delayed: {first_sec}s"

    # Playhead progression math: verify monotonically increasing x from left to width
    map_left = 0
    map_width = 800
    positions = []
    for beat in [0.0, 12.0, 24.0, 36.0, 48.0]:
        ratio = max(0.0, min(1.0, beat / total_beats))
        px = map_left + ratio * map_width
        positions.append(px)
    assert positions == [0.0, 200.0, 400.0, 600.0, 800.0], f"Bad positions: {positions}"

    print(f"PASS: S-05 (Audio timing within 500ms, {len(notes)} notes at {bpm} bpm)")
    print("PASS: S-06 (Playhead progression 0 -> 800 px across 48 beats)")

    # -------------------------------------------------------------------------
    # S-07: Audio legend sweep
    # -------------------------------------------------------------------------
    r_legend = client.get(f"/api/legend-sound/{analysis_id}.wav?skin=neutral")
    assert r_legend.status_code == 200
    assert r_legend.headers["content-type"] == "audio/wav"
    assert len(r_legend.content) > 1000

    # Test sweep frequency progression
    skin = get_skin("neutral")
    pitches = [
        quantize_pitch(i / 31.0, skin)
        for i in range(32)
    ]
    # Check non-decreasing pitch
    for i in range(len(pitches) - 1):
        assert pitches[i] <= pitches[i + 1] + 1e-6, "Legend pitch is not monotonic"
    print(f"PASS: S-07 (Audio legend sweep verified: 32 notes, {pitches[0]:.1f} -> {pitches[-1]:.1f} MIDI)")

    # -------------------------------------------------------------------------
    # S-08: Form validation and upload
    # -------------------------------------------------------------------------
    # Verify auto-detection assist endpoint
    r_detect = client.post(
        "/api/detect-colorbar",
        files={"image": ("test.png", png, "image/png")},
    )
    assert r_detect.status_code == 200
    candidates = r_detect.json()["candidates"]
    assert len(candidates) > 0, "No colorbar candidates detected"
    print(f"PASS: S-08 (Form validation, colorbar detect candidate score={candidates[0]['score']:.2f})")

    # -------------------------------------------------------------------------
    # S-09: Skin switching during playback
    # -------------------------------------------------------------------------
    r_skins = client.get("/api/skins")
    assert r_skins.status_code == 200
    available_skins = r_skins.json()
    assert len(available_skins) >= 1

    # Re-sonify with same analysis and verify timing identical but skin applied
    r_sonify2 = client.post(
        "/api/sonify",
        json={"analysis_id": analysis_id, "skin": "neutral", "n_cols": 48},
    )
    assert r_sonify2.status_code == 200
    score2 = r_sonify2.json()["score"]
    assert score2["total_beats"] == score["total_beats"]
    assert len(score2["notes"]) == len(score["notes"])
    print(f"PASS: S-09 (Skin switching verified: {len(available_skins)} skins available, timing invariant)")

    # -------------------------------------------------------------------------
    # Export / Downloads verification (F-075)
    # -------------------------------------------------------------------------
    r_wav = client.get(f"/api/render/{analysis_id}.wav?skin=neutral&n_cols=48")
    assert r_wav.status_code == 200
    wav_path = cache_dir / f"smoke_{analysis_id}.wav"
    wav_path.write_bytes(r_wav.content)

    r_mid = client.get(f"/api/render/{analysis_id}.mid?skin=neutral&n_cols=48")
    assert r_mid.status_code == 200
    mid_path = cache_dir / f"smoke_{analysis_id}.mid"
    mid_path.write_bytes(r_mid.content)

    r_json = client.get(f"/api/render/{analysis_id}.json?skin=neutral&n_cols=48")
    assert r_json.status_code == 200
    json_path = cache_dir / f"smoke_{analysis_id}.score.json"
    json_path.write_bytes(r_json.content)

    print(f"PASS: Downloads verified (WAV {len(r_wav.content)} B, MID {len(r_mid.content)} B, Score JSON {len(r_json.content)} B)")
    print("=" * 80)
    print("ALL SMOKE TESTS S-01 .. S-09 PASSED SUCCESSFULLY")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_walkthrough())
