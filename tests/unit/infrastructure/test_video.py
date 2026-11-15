"""Unit tests for F-109: FfmpegVideoExporter."""

from __future__ import annotations

import io
import shutil
import wave

import numpy as np
import pytest
from PIL import Image

from earth_jukebox.domain.models import ColormapKind, LegendSpec, NoteEvent, PixelBox, Score, Voice
from earth_jukebox.infrastructure.video.mp4 import FfmpegVideoExporter


def _make_test_score(bpm: float = 96.0, total_beats: float = 4.0) -> Score:
    voice = Voice(id="band0", band_index=0, instrument="pad", pan=0.0)
    notes = tuple(
        NoteEvent(
            voice_id="band0",
            t_beat=float(i),
            dur_beat=0.8,
            pitch_midi=60.0 + i,
            velocity=0.7,
            accent=(i == 0),
            col=i,
            band=0,
            value=float(i),
        )
        for i in range(int(total_beats))
    )
    return Score(
        mapping_version="1.0.0",
        skin_id="neutral",
        seed=42,
        bpm=bpm,
        total_beats=total_beats,
        n_cols=int(total_beats),
        n_bands=1,
        voices=(voice,),
        notes=notes,
        drone_midi=(48.0,),
        legend=LegendSpec(
            vmin=0.0,
            vmax=10.0,
            units="K",
            label="Test Variable",
            kind=ColormapKind.SEQUENTIAL,
        ),
    )


def _make_test_wav(duration_sec: float = 1.0) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        n_samples = int(duration_sec * 44100)
        t = np.linspace(0, duration_sec, n_samples, endpoint=False)
        sig = (np.sin(2 * np.pi * 440 * t) * 8000).astype(np.int16)
        stereo = np.column_stack([sig, sig]).tobytes()
        wf.writeframes(stereo)
    return buf.getvalue()


def _make_test_image_png(width: int = 120, height: int = 80) -> bytes:
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    arr[:, :] = [30, 45, 60]
    img = Image.fromarray(arr, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_video_exporter_availability() -> None:
    exporter = FfmpegVideoExporter(ffmpeg_bin="ffmpeg")
    assert exporter.is_available() == (shutil.which("ffmpeg") is not None)

    missing = FfmpegVideoExporter(ffmpeg_bin="non_existent_binary_12345")
    assert not missing.is_available()
    with pytest.raises(RuntimeError, match="not found on system PATH"):
        missing.export_video(
            image_bytes=b"dummy",
            wav_bytes=b"dummy",
            score=_make_test_score(),
        )


def test_video_exporter_renders_valid_mp4() -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed on system")

    exporter = FfmpegVideoExporter()
    img_bytes = _make_test_image_png(160, 100)
    wav_bytes = _make_test_wav(1.0)
    score = _make_test_score(bpm=120.0, total_beats=2.0)

    mp4_bytes = exporter.export_video(
        image_bytes=img_bytes,
        wav_bytes=wav_bytes,
        score=score,
        fps=15,
    )

    assert len(mp4_bytes) > 0
    # MP4 file structure: 'ftyp' box
    assert b"ftyp" in mp4_bytes[:32]


def test_video_exporter_with_map_box() -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed on system")

    exporter = FfmpegVideoExporter()
    img_bytes = _make_test_image_png(200, 120)
    wav_bytes = _make_test_wav(0.5)
    score = _make_test_score(bpm=120.0, total_beats=1.0)
    map_box = PixelBox(x=20, y=10, w=160, h=100)

    mp4_bytes = exporter.export_video(
        image_bytes=img_bytes,
        wav_bytes=wav_bytes,
        score=score,
        map_box=map_box,
        fps=15,
    )

    assert len(mp4_bytes) > 0
    assert b"ftyp" in mp4_bytes[:32]
