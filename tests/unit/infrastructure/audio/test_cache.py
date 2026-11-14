"""Unit tests for F-045 (Render cache)."""

from __future__ import annotations

import json
from pathlib import Path

from earth_jukebox.domain.models import ColormapKind, LegendSpec, Score, Voice
from earth_jukebox.infrastructure.audio.cache import CachedAudioRenderer


class _SpyRenderer:
    """Mock AudioRenderer that counts render calls."""

    def __init__(self) -> None:
        self.call_count = 0

    def render_wav(self, score: Score, sample_rate: int = 44100) -> bytes:
        self.call_count += 1
        return f"WAV_DATA_FOR_{score.mapping_version}_{self.call_count}".encode()


def _make_dummy_score(mapping_version: str = "1.0.0") -> Score:
    voice = Voice(id="v0", band_index=0, instrument="flute", pan=0.0)
    return Score(
        mapping_version=mapping_version,
        skin_id="neutral",
        seed=1,
        bpm=120.0,
        total_beats=2.0,
        n_cols=1,
        n_bands=1,
        voices=(voice,),
        notes=(),
        drone_midi=(),
        legend=LegendSpec(
            vmin=0.0, vmax=1.0, units="m", label="Test", kind=ColormapKind.SEQUENTIAL
        ),
        provenance={},
    )


def test_f045_ac1_second_render_is_cache_hit(tmp_path: Path) -> None:
    # F-045 AC1: second render is a cache hit (test via spy/counter)
    spy = _SpyRenderer()
    cached_renderer = CachedAudioRenderer(inner=spy, cache_dir=tmp_path)
    score = _make_dummy_score()

    # First render: cache miss
    result1 = cached_renderer.render_wav(score)
    assert spy.call_count == 1
    assert result1 == b"WAV_DATA_FOR_1.0.0_1"

    # Second render: cache hit
    result2 = cached_renderer.render_wav(score)
    assert spy.call_count == 1, "Inner renderer should not be called on cache hit"
    assert result2 == result1


def test_f045_ac2_cache_never_serves_different_mapping_version(tmp_path: Path) -> None:
    # F-045 AC2: cache never serves a different mapping_version
    spy = _SpyRenderer()
    cached_renderer = CachedAudioRenderer(inner=spy, cache_dir=tmp_path)
    score_v1 = _make_dummy_score(mapping_version="1.0.0")

    # Render v1.0.0
    res_v1 = cached_renderer.render_wav(score_v1)
    assert spy.call_count == 1

    # Render score with different mapping version v2.0.0
    score_v2 = _make_dummy_score(mapping_version="2.0.0")
    res_v2 = cached_renderer.render_wav(score_v2)
    assert spy.call_count == 2
    assert res_v2 != res_v1

    # Deliberately modify cached metadata to simulate a stale/different mapping version
    # Find metadata files in tmp_path
    meta_files = list(tmp_path.glob("*.meta.json"))
    assert len(meta_files) >= 1
    for mf in meta_files:
        meta = json.loads(mf.read_text(encoding="utf-8"))
        meta["mapping_version"] = "0.0.1"  # Different version
        mf.write_text(json.dumps(meta), encoding="utf-8")

    # Requesting score_v1 again should NOT serve the altered mapping_version entry
    _ = cached_renderer.render_wav(score_v1)
    assert spy.call_count == 3, "Stale mapping_version in cache must trigger re-render"
