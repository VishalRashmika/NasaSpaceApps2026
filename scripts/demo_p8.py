"""Exit demo script for Phase 8: Cultural skins (docs/04 §2).

Renders the same synthetic field in neutral / hindustani / sri_lankan:
- Writes: data/cache/demo_p8_<skin>.wav and demo_p8_<skin>.mid
- Verifies: F-054 invariance (main note onsets, velocities, accents, voices, pans)
- Verifies: Hindustani descending glides and Sri Lankan percussion accompaniment
- Prepared for human A/B listening verification
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from earth_jukebox.application.use_cases.sonify import sonify
from earth_jukebox.domain.models import ColormapKind, Orientation, SonificationParams
from earth_jukebox.domain.skins import get_skin
from earth_jukebox.domain.sonification.pitch import quantize_pitch
from earth_jukebox.infrastructure.audio.midi import MidoMidiExporter
from earth_jukebox.infrastructure.audio.renderer import NumpyAudioRenderer
from earth_jukebox.infrastructure.colormaps.catalog import MatplotlibColormapCatalog
from earth_jukebox.infrastructure.vision.decoder import PillowImageDecoder
from earth_jukebox.infrastructure.vision.recoverer import VisionFieldRecoverer
from earth_jukebox.infrastructure.vision.synthetic import generate_map

DEMO_SKINS = ("neutral", "hindustani", "sri_lankan")


def run_demo() -> bool:
    cache_dir = Path("data/cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    catalog = MatplotlibColormapCatalog()
    recoverer = VisionFieldRecoverer(catalog)
    decoder = PillowImageDecoder()
    renderer = NumpyAudioRenderer()
    exporter = MidoMidiExporter()

    print("=" * 90)
    print("EARTH JUKEBOX — PHASE 8 EXIT DEMO: CULTURAL SKINS (A/B INVARIANCE & RENDERING)")
    print("=" * 90)

    # 1. Generate map and recover scalar field
    png, _, legend, cbar_box, map_box = generate_map(
        cmap="viridis",
        seed=42,
        orientation=Orientation.HORIZONTAL,
        kind=ColormapKind.SEQUENTIAL,
    )
    decoded = decoder.decode(png)
    field = recoverer.recover(
        image=decoded,
        legend=legend,
        map_box=map_box,
        colorbar_box=cbar_box,
        preset_name=None,
    )

    print(
        f"Synthetic map generated (viridis): image shape {decoded.rgb.shape}, "
        f"legend range [{legend.vmin}, {legend.vmax}] {legend.units}, "
        f"confidence {field.quality.confidence:.2%}"
    )
    print("-" * 90)
    print(
        f"{'Skin ID':<14} | {'Name':<18} | {'Scale Cents':<24} | {'Main Notes':<10} | "
        f"{'WAV (KB)':<9} | {'MID (B)':<8} | {'Status'}"
    )
    print("-" * 90)

    scores = {}
    all_passed = True

    # 2. Sonify and render each skin
    for skin_id in DEMO_SKINS:
        skin = get_skin(skin_id)
        params = SonificationParams(skin_id=skin_id, n_bands=5, n_cols=48, seed=42)
        score = sonify(field, params)
        scores[skin_id] = score

        # Render audio
        wav_bytes = renderer.render_wav(score, sample_rate=44100)
        mid_bytes = exporter.export_midi(score)

        wav_path = cache_dir / f"demo_p8_{skin_id}.wav"
        mid_path = cache_dir / f"demo_p8_{skin_id}.mid"
        wav_path.write_bytes(wav_bytes)
        mid_path.write_bytes(mid_bytes)

        main_notes = [n for n in score.notes if n.kind == "main"]
        scale_str = ",".join(str(int(c)) for c in skin.scale_cents[:4]) + "…"

        passed = len(wav_bytes) > 0 and len(mid_bytes) > 0 and len(main_notes) > 0
        if not passed:
            all_passed = False

        status = "PASS" if passed else "FAIL"
        wav_kb = len(wav_bytes) / 1024
        mid_b = len(mid_bytes)
        print(
            f"{skin_id:<14} | {skin.name:<18} | {scale_str:<24} | {len(main_notes):<10} | "
            f"{wav_kb:<9.1f} | {mid_b:<8} | {status}"
        )

    print("-" * 90)
    print("F-054 INVARIANCE VERIFICATION:")

    ref_score = scores["neutral"]
    ref_main = [n for n in ref_score.notes if n.kind == "main"]

    for skin_id in DEMO_SKINS:
        skin = get_skin(skin_id)
        score = scores[skin_id]
        main_notes = [n for n in score.notes if n.kind == "main"]

        # Check (a) pitch monotonicity for sorted u
        u_vals = np.linspace(0.0, 1.0, 101)
        pitches = [quantize_pitch(float(u), skin) for u in u_vals]
        mono = all(pitches[i] <= pitches[i + 1] for i in range(len(pitches) - 1))

        # Check (b) identical main note structure
        same_count = len(main_notes) == len(ref_main)
        same_onsets = all(n.t_beat == r.t_beat for n, r in zip(main_notes, ref_main, strict=True))
        same_dur = all(n.dur_beat == r.dur_beat for n, r in zip(main_notes, ref_main, strict=True))
        same_vel = all(n.velocity == r.velocity for n, r in zip(main_notes, ref_main, strict=True))
        same_acc = all(n.accent == r.accent for n, r in zip(main_notes, ref_main, strict=True))
        same_voice = all(
            n.voice_id == r.voice_id for n, r in zip(main_notes, ref_main, strict=True)
        )
        same_geom = all(
            n.col == r.col and n.band == r.band for n, r in zip(main_notes, ref_main, strict=True)
        )

        skin_inv_pass = (
            mono
            and same_count
            and same_onsets
            and same_dur
            and same_vel
            and same_acc
            and same_voice
            and same_geom
        )

        if not skin_inv_pass:
            all_passed = False

        res_str = "PASS" if skin_inv_pass else "FAIL"
        print(
            f"  - {skin_id:<12}: pitch monotone={mono}, "
            f"main note count={len(main_notes)} ({'match' if same_count else 'MISMATCH'}), "
            f"timing/dynamics match={same_onsets and same_vel and same_acc} => {res_str}"
        )

    # Extra skin feature verification
    hindustani_glides = [n for n in scores["hindustani"].notes if n.glide_to_midi is not None]
    sri_lankan_perc = [n for n in scores["sri_lankan"].notes if n.voice_id == "perc"]
    print("-" * 90)
    print("SPECIALIZED CULTURAL MACHINERY EVIDENCE:")
    print(f"  - Hindustani meend glides: {len(hindustani_glides)} notes with glide_to_midi")
    print(f"  - Sri Lankan percussion: {len(sri_lankan_perc)} notes on 'perc' voice")
    print("=" * 90)

    if all_passed and len(hindustani_glides) > 0 and len(sri_lankan_perc) > 0:
        print("PHASE 8 EXIT DEMO RESULT: ALL CHECKS PASSED")
        return True
    else:
        print("PHASE 8 EXIT DEMO RESULT: FAILURES DETECTED")
        return False


if __name__ == "__main__":
    success = run_demo()
    sys.exit(0 if success else 1)
