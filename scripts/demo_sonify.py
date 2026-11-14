"""Exit demo script for Phase 3: Sonification engine -> Score (docs/04 §2).

Runs sonification on 3 synthetic fields (viridis, turbo, RdBu_r):
- Prints: bpm, #notes, accents, silence share, description text, round-trip r
- Writes: data/cache/*.score.json
- Verifies: round-trip r >= 0.95 on all fields
"""

from __future__ import annotations

import sys
from pathlib import Path

from earth_jukebox.application.use_cases.description import generate_description
from earth_jukebox.application.use_cases.round_trip import fidelity_round_trip
from earth_jukebox.application.use_cases.sonify import sonify
from earth_jukebox.domain.models import ColormapKind, Orientation, SonificationParams
from earth_jukebox.domain.sonification.score_serde import score_to_json
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

    print("=" * 80)
    print("EARTH JUKEBOX — PHASE 3 EXIT DEMO: SONIFICATION ENGINE -> SCORE")
    print("=" * 80)
    print(
        f"{'Field':<10} | {'BPM':<6} | {'Notes':<6} | {'Accents':<7} | {'Silence':<8} | {'RoundTrip r':<11} | {'Status'}"
    )
    print("-" * 80)

    all_passed = True

    for cmap, kind in DEMO_CONFIGS:
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

        score = sonify(field, SonificationParams(n_bands=5, n_cols=48))
        r = fidelity_round_trip(field, score)
        desc = generate_description(field)

        main_accents = sum(1 for n in score.notes if n.accent and n.kind == "main")
        silence_share = f"{field.quality.masked_fraction * 100:.1f}%"
        status = "PASS" if r >= 0.95 else "FAIL"
        if r < 0.95:
            all_passed = False

        print(
            f"{cmap:<10} | {score.bpm:<6.1f} | {len(score.notes):<6} | {main_accents:<7} | "
            f"{silence_share:<8} | {r:<11.4f} | {status}"
        )
        print(f'  Description: "{desc}"')
        print()

        # Write score JSON
        score_file = cache_dir / f"{cmap}.score.json"
        score_file.write_text(score_to_json(score), encoding="utf-8")

    print("-" * 80)
    if all_passed:
        print("PHASE 3 EXIT DEMO RESULT: ALL PASS (r >= 0.95)")
    else:
        print("PHASE 3 EXIT DEMO RESULT: FAIL")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    success = run_demo()
    sys.exit(0 if success else 1)
