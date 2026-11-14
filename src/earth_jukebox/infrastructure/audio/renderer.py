"""F-042: WAV writer.

Implements AudioRenderer port (44.1 kHz, 16-bit stereo PCM via stdlib wave).
"""

from __future__ import annotations

import io
import wave

import numpy as np

from earth_jukebox.domain.models import Score
from earth_jukebox.infrastructure.audio.mixer import mix_score


class NumpyAudioRenderer:
    """Deterministic server audio renderer using our own NumPy synth."""

    def render_wav(self, score: Score, sample_rate: int = 44100) -> bytes:
        """Render Score into 16-bit PCM stereo WAV bytes.

        F-042 acceptance criteria:
        - AC1: valid header; duration = total_beats * 60 / bpm + tail (<= 2 s) +- 50 ms
        - AC2: byte-identical across runs (F-102 determinism)
        """
        # Mix score notes and drone into (2, n_samples) float64
        stereo = mix_score(score, sample_rate=sample_rate)

        # Quantise to signed 16-bit PCM [-32768, 32767]
        left_pcm = np.clip(np.round(stereo[0] * 32767.0), -32768, 32767).astype(np.int16)
        right_pcm = np.clip(np.round(stereo[1] * 32767.0), -32768, 32767).astype(np.int16)

        # Interleave channels: [L0, R0, L1, R1, ...]
        n_samples = len(left_pcm)
        interleaved = np.empty((n_samples * 2,), dtype=np.int16)
        interleaved[0::2] = left_pcm
        interleaved[1::2] = right_pcm

        # Write WAV using stdlib wave
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)  # 16-bit PCM = 2 bytes per sample
            w.setframerate(sample_rate)
            w.writeframes(interleaved.tobytes())

        return buf.getvalue()
