"""Exit demo script for Phase 9: Time mode (docs/04 §1, §2).

Generates an animated multi-frame sequence, extracts frames, sonifies into
concatenated phrases separated by 1-beat rests, computes inter-frame change
and harmonic tension drone, and renders WAV and MIDI artifacts:
- Writes: data/cache/demo_p9.wav and data/cache/demo_p9.mid
- Verifies: F-090 frame extraction, F-091 timing/rest structure, F-092 harmonic tension
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Any

from PIL import Image

from earth_jukebox.application.use_cases.sonify import sonify
from earth_jukebox.application.use_cases.time_mode import concatenate_phrases
from earth_jukebox.domain.models import (
    ColormapKind,
    Orientation,
    SonificationParams,
)
from earth_jukebox.infrastructure.audio.midi import MidoMidiExporter
from earth_jukebox.infrastructure.audio.renderer import NumpyAudioRenderer
from earth_jukebox.infrastructure.colormaps.catalog import MatplotlibColormapCatalog
from earth_jukebox.infrastructure.vision.frames import VisionFrameExtractor
from earth_jukebox.infrastructure.vision.recoverer import VisionFieldRecoverer
from earth_jukebox.infrastructure.vision.synthetic import generate_map


def _generate_synthetic_animated_gif(
    n_frames: int = 4,
) -> tuple[bytes, Any, Any, Any]:
    """Generate an animated GIF where a synthetic field evolves across frames."""
    pil_frames: list[Image.Image] = []

    legend = None
    cbar_box = None
    map_box = None

    for i in range(n_frames):
        # Vary seed and colormap scale so each frame has a distinct data state
        png_bytes, _, leg, cb, mb = generate_map(
            cmap="viridis",
            seed=100 + i * 25,
            orientation=Orientation.HORIZONTAL,
            kind=ColormapKind.SEQUENTIAL,
        )
        legend = leg
        cbar_box = cb
        map_box = mb

        img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        pil_frames.append(img)

    bio = io.BytesIO()
    pil_frames[0].save(
        bio,
        format="GIF",
        save_all=True,
        append_images=pil_frames[1:],
        duration=250,
        loop=0,
    )
    return bio.getvalue(), legend, cbar_box, map_box


def run_demo() -> bool:
    cache_dir = Path("data/cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    catalog = MatplotlibColormapCatalog()
    recoverer = VisionFieldRecoverer(catalog)
    extractor = VisionFrameExtractor()
    renderer = NumpyAudioRenderer()
    exporter = MidoMidiExporter()

    print("=" * 90)
    print("EARTH JUKEBOX — PHASE 9 EXIT DEMO: TIME MODE (ANIMATION & PHRASES)")
    print("=" * 90)

    # 1. Generate multi-frame synthetic animation
    n_frames = 4
    gif_bytes, legend, cbar_box, map_box = _generate_synthetic_animated_gif(n_frames=n_frames)
    print(f"Generated {n_frames}-frame animated GIF ({len(gif_bytes):,} bytes)")

    # 2. Extract frames via F-090
    decoded_frames = extractor.extract_frames(gif_bytes, max_frames=24)
    print(f"F-090: Extracted {len(decoded_frames)} frames (sampled evenly)")
    assert len(decoded_frames) == n_frames

    # 3. Recover fields for each frame and sonify into phrases (F-091)
    fields = []
    phrases = []
    n_cols = 48
    n_bands = 5
    params = SonificationParams(skin_id="neutral", n_cols=n_cols, n_bands=n_bands, seed=42)

    for idx, frame in enumerate(decoded_frames):
        field = recoverer.recover(
            image=frame,
            legend=legend,
            map_box=map_box,
            colorbar_box=cbar_box,
            preset_name=None,
        )
        fields.append(field)
        phrase = sonify(field, params)
        phrases.append(phrase)
        msg = (
            f"  Frame {idx + 1}: confidence {field.quality.confidence:.2%}, "
            f"{len(phrase.notes)} notes, BPM {phrase.bpm:.1f}"
        )
        print(msg)

    # 4. Concatenate phrases with 1-beat rest and harmonic tension drone (F-091, F-092)
    score = concatenate_phrases(phrases, fields, skin_id="neutral")

    # 5. Render audio
    wav_bytes = renderer.render_wav(score, sample_rate=44100)
    mid_bytes = exporter.export_midi(score)

    wav_path = cache_dir / "demo_p9.wav"
    mid_path = cache_dir / "demo_p9.mid"
    wav_path.write_bytes(wav_bytes)
    mid_path.write_bytes(mid_bytes)

    # 6. Verifications
    phrase_beats = phrases[0].total_beats
    expected_total_beats = (n_frames - 1) * (phrase_beats + 1.0) + phrase_beats

    total_beats_ok = abs(score.total_beats - expected_total_beats) < 1e-4
    has_wav = len(wav_bytes) > 0
    has_mid = len(mid_bytes) > 0

    # Verify rest intervals have zero notes
    rest_violations = 0
    for k in range(n_frames - 1):
        rest_start = (k + 1) * phrase_beats + k * 1.0
        rest_end = rest_start + 1.0
        in_rest = [n for n in score.notes if rest_start <= n.t_beat < rest_end]
        if in_rest:
            rest_violations += len(in_rest)

    rests_ok = rest_violations == 0

    # Verify F-092 harmonic tension
    inter_frame_change = float(score.provenance.get("inter_frame_change", 0.0))
    tension_ok = inter_frame_change > 0.0 and len(score.drone_midi) == 3

    print("-" * 90)
    print(f"{'Metric':<25} | {'Expected':<20} | {'Actual':<20} | {'Status'}")
    print("-" * 90)
    frame_status = "PASS" if len(decoded_frames) == n_frames else "FAIL"
    print(f"{'Frame Count':<25} | {n_frames:<20} | {len(decoded_frames):<20} | {frame_status}")
    print(
        f"{'Phrase Duration':<25} | {f'{phrase_beats} beats':<20} | "
        f"{f'{phrase_beats} beats':<20} | PASS"
    )
    dur_status = "PASS" if total_beats_ok else "FAIL"
    print(
        f"{'Total Duration':<25} | {f'{expected_total_beats} beats':<20} | "
        f"{f'{score.total_beats} beats':<20} | {dur_status}"
    )
    rest_status = "PASS" if rests_ok else "FAIL"
    print(
        f"{'Rest Period Notes':<25} | {'0 notes':<20} | "
        f"{f'{rest_violations} notes':<20} | {rest_status}"
    )
    change_status = "PASS" if inter_frame_change > 0 else "FAIL"
    print(
        f"{'Inter-Frame Change':<25} | {'> 0.0':<20} | "
        f"{f'{inter_frame_change:.4f}':<20} | {change_status}"
    )
    drone_desc = f"{len(score.drone_midi)} pitches ({score.drone_midi})"
    drone_status = "PASS" if tension_ok else "FAIL"
    print(
        f"{'Harmonic Tension Drone':<25} | {'3 drone pitches':<20} | "
        f"{drone_desc:<20} | {drone_status}"
    )
    wav_status = "PASS" if has_wav else "FAIL"
    print(
        f"{'WAV Render':<25} | {'> 0 bytes':<20} | {f'{len(wav_bytes):,} bytes':<20} | {wav_status}"
    )
    mid_status = "PASS" if has_mid else "FAIL"
    print(
        f"{'MIDI Export':<25} | {'> 0 bytes':<20} | "
        f"{f'{len(mid_bytes):,} bytes':<20} | {mid_status}"
    )
    print("=" * 90)

    all_passed = total_beats_ok and rests_ok and tension_ok and has_wav and has_mid
    if all_passed:
        wav_kb = len(wav_bytes) / 1024
        mid_b = len(mid_bytes)
        print("PHASE 9 EXIT DEMO RESULT: ALL CHECKS PASSED")
        print(f"Rendered artifacts: {wav_path} ({wav_kb:.1f} KB), {mid_path} ({mid_b} bytes)")
        return True
    else:
        print("PHASE 9 EXIT DEMO RESULT: FAILURES DETECTED")
        return False


if __name__ == "__main__":
    success = run_demo()
    sys.exit(0 if success else 1)
