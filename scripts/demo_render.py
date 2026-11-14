"""Exit demo script for Phase 4: Audio rendering & export (docs/04 §2).

Renders WAV and MIDI for 3 synthetic fields (viridis, turbo, RdBu_r) plus legend sweeps:
- Writes: data/cache/demo_<name>.wav, demo_<name>.mid, legend_<name>.wav
- Verifies: YIN legend pitch check (all notes within 20 cents, r >= 0.98)
"""

from __future__ import annotations

import sys
from pathlib import Path

from earth_jukebox.application.use_cases.audio_legend import legend_score
from earth_jukebox.application.use_cases.sonify import sonify
from earth_jukebox.domain.models import ColormapKind, Orientation, SonificationParams
from earth_jukebox.domain.skins.neutral import NEUTRAL_SKIN
from earth_jukebox.infrastructure.audio.midi import MidoMidiExporter
from earth_jukebox.infrastructure.audio.renderer import NumpyAudioRenderer
from earth_jukebox.infrastructure.audio.yin import check_legend_sweep_audio
from earth_jukebox.infrastructure.colormaps.catalog import MatplotlibColormapCatalog
from earth_jukebox.infrastructure.vision.decoder import PillowImageDecoder
from earth_jukebox.infrastructure.vision.recoverer import VisionFieldRecoverer
from earth_jukebox.infrastructure.vision.synthetic import generate_map

DEMO_CONFIGS = [
    ("viridis", ColormapKind.SEQUENTIAL),
    ("turbo", ColormapKind.SEQUENTIAL),
    ("RdBu_r", ColormapKind.DIVERGING),
]


def run_demo() -> bool:
    cache_dir = Path("data/cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    catalog = MatplotlibColormapCatalog()
    recoverer = VisionFieldRecoverer(catalog)
    decoder = PillowImageDecoder()
    renderer = NumpyAudioRenderer()
    exporter = MidoMidiExporter()

    print("=" * 80)
    print("EARTH JUKEBOX — PHASE 4 EXIT DEMO: AUDIO RENDERING & EXPORT")
    print("=" * 80)
    print(
        f"{'Field':<10} | {'WAV (KB)':<9} | {'MID (B)':<8} | {'Leg WAV (KB)':<12} | "
        f"{'Max Cents':<10} | {'Legend r':<9} | {'Status'}"
    )
    print("-" * 80)

    all_passed = True

    for cmap, kind in DEMO_CONFIGS:
        # 1. Generate map and recover scalar field
        png, _, legend, cbar_box, map_box = generate_map(
            cmap=cmap,
            seed=42,
            orientation=Orientation.HORIZONTAL,
            kind=kind,
        )
        decoded = decoder.decode(png)
        field = recoverer.recover(
            image=decoded,
            legend=legend,
            map_box=map_box,
            colorbar_box=cbar_box,
            preset_name=None,
        )

        # 2. Sonify to Score
        score = sonify(field, SonificationParams(n_bands=5, n_cols=48))

        # 3. Render track WAV and MIDI
        wav_bytes = renderer.render_wav(score, sample_rate=44100)
        mid_bytes = exporter.export_midi(score)

        wav_path = cache_dir / f"demo_{cmap}.wav"
        mid_path = cache_dir / f"demo_{cmap}.mid"
        wav_path.write_bytes(wav_bytes)
        mid_path.write_bytes(mid_bytes)

        # 4. Generate & render Audio Legend sweep
        l_score = legend_score(legend, NEUTRAL_SKIN)
        l_wav_bytes = renderer.render_wav(l_score, sample_rate=44100)
        l_wav_path = cache_dir / f"legend_{cmap}.wav"
        l_wav_path.write_bytes(l_wav_bytes)

        # 5. YIN pitch detection on audio legend sweep
        yin_result = check_legend_sweep_audio(l_score, renderer=renderer, sample_rate=44100)

        passed = (
            yin_result.all_within_threshold
            and yin_result.audio_legend_r >= 0.98
            and len(wav_bytes) > 0
            and len(mid_bytes) > 0
        )
        if not passed:
            all_passed = False

        status = "PASS" if passed else "FAIL"

        wav_kb = len(wav_bytes) / 1024.0
        mid_b = len(mid_bytes)
        leg_kb = len(l_wav_bytes) / 1024.0

        print(
            f"{cmap:<10} | {wav_kb:<9.1f} | {mid_b:<8} | {leg_kb:<12.1f} | "
            f"{yin_result.max_cents_error:<10.2f} | {yin_result.audio_legend_r:<9.4f} | {status}"
        )

    print("-" * 80)
    if all_passed:
        print("PHASE 4 EXIT DEMO RESULT: ALL PASS (max cents <= 20, legend r >= 0.98)")
    else:
        print("PHASE 4 EXIT DEMO RESULT: FAIL")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    success = run_demo()
    sys.exit(0 if success else 1)
