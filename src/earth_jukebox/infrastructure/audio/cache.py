"""F-045: Audio render cache.

Key = sha256(Score JSON + renderer version). Stored in data/cache.
Guarantees cache hit on identical requests and never serves a different mapping_version.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
from pathlib import Path

from earth_jukebox.application.ports import AudioRenderer
from earth_jukebox.domain.models import Score
from earth_jukebox.domain.sonification.score_serde import score_to_json

DEFAULT_RENDERER_VERSION = "1.0.0"


class CachedAudioRenderer:
    """Wrapper around an AudioRenderer that caches rendered WAV bytes on disk."""

    def __init__(
        self,
        inner: AudioRenderer,
        cache_dir: Path,
        renderer_version: str = DEFAULT_RENDERER_VERSION,
    ) -> None:
        self.inner = inner
        self.cache_dir = cache_dir
        self.renderer_version = renderer_version
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def render_wav(self, score: Score, sample_rate: int = 44100) -> bytes:
        """Render WAV with disk caching per F-045.

        F-045 acceptance criteria:
        - AC1: second render is a cache hit (test via spy/counter)
        - AC2: cache never serves a different mapping_version
        """
        score_json = score_to_json(score)
        key_input = f"{score_json}:{self.renderer_version}:{sample_rate}"
        key = hashlib.sha256(key_input.encode("utf-8")).hexdigest()

        wav_path = self.cache_dir / f"{key}.wav"
        meta_path = self.cache_dir / f"{key}.meta.json"

        # Check existing cache
        if wav_path.exists() and meta_path.exists():
            with contextlib.suppress(json.JSONDecodeError, OSError):
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                if meta.get("mapping_version") == score.mapping_version:
                    return wav_path.read_bytes()

        # Cache miss: render via inner renderer
        wav_bytes = self.inner.render_wav(score, sample_rate=sample_rate)

        # Write cache files atomically via temporary files
        tmp_wav = self.cache_dir / f"{key}.wav.tmp"
        tmp_meta = self.cache_dir / f"{key}.meta.json.tmp"
        with contextlib.suppress(OSError):
            tmp_wav.write_bytes(wav_bytes)
            tmp_meta.write_text(
                json.dumps(
                    {
                        "mapping_version": score.mapping_version,
                        "renderer_version": self.renderer_version,
                        "sample_rate": sample_rate,
                    }
                ),
                encoding="utf-8",
            )
            tmp_wav.replace(wav_path)
            tmp_meta.replace(meta_path)

        return wav_bytes
