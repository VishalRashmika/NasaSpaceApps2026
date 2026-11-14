"""Unit tests for F-044 MP3 export via ffmpeg."""

from __future__ import annotations

import io
import shutil
import wave

import pytest

from earth_jukebox.infrastructure.audio.mp3 import FfmpegMp3Exporter


def _generate_test_wav_bytes(duration_sec: float = 0.5, sample_rate: int = 44100) -> bytes:
    buf = io.BytesIO()
    n_frames = int(duration_sec * sample_rate)
    with wave.open(buf, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        # 16-bit silence
        w.writeframes(b"\x00" * (n_frames * 4))
    return buf.getvalue()


def test_f044_mp3_exporter_availability() -> None:
    exporter = FfmpegMp3Exporter()
    expected = shutil.which("ffmpeg") is not None
    assert exporter.is_available() is expected


def test_f044_mp3_exporter_unavailable_raises() -> None:
    exporter = FfmpegMp3Exporter(ffmpeg_bin="definitely_nonexistent_binary_xyz123")
    assert not exporter.is_available()
    wav_bytes = _generate_test_wav_bytes()
    with pytest.raises(RuntimeError, match="not found on system PATH"):
        exporter.export_mp3(wav_bytes)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed on system")
def test_f044_mp3_exporter_converts_wav() -> None:
    exporter = FfmpegMp3Exporter()
    wav_bytes = _generate_test_wav_bytes(duration_sec=0.25)
    mp3_bytes = exporter.export_mp3(wav_bytes)

    assert len(mp3_bytes) > 0
    # MP3 files usually start with ID3 header (b'ID3') or sync word (b'\xff\xfb' / b'\xff\xf3')
    is_id3 = mp3_bytes.startswith(b"ID3")
    is_sync = mp3_bytes[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")
    assert is_id3 or is_sync


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed on system")
def test_f044_mp3_exporter_corrupt_input_raises() -> None:
    exporter = FfmpegMp3Exporter()
    with pytest.raises(RuntimeError, match="conversion failed"):
        exporter.export_mp3(b"this is not valid wav data")
