"""Unit tests for F-090: Frame extraction from animations and video."""

from __future__ import annotations

import io
import shutil

import pytest
from PIL import Image

from earth_jukebox.domain.errors import InvalidImageError
from earth_jukebox.infrastructure.vision.frames import VisionFrameExtractor


def _create_synthetic_gif(n_frames: int = 5, size: tuple[int, int] = (64, 64)) -> bytes:
    """Create in-memory animated GIF with distinct colored frames."""
    frames = []
    for i in range(n_frames):
        color = (int(255 * i / max(1, n_frames - 1)), 100, 150)
        img = Image.new("RGB", size, color)
        frames.append(img)

    bio = io.BytesIO()
    frames[0].save(
        bio,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0,
    )
    return bio.getvalue()


def _create_synthetic_png(size: tuple[int, int] = (64, 64)) -> bytes:
    """Create static 1-frame PNG."""
    img = Image.new("RGB", size, (50, 100, 150))
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()


def test_extract_frames_from_animated_gif_ac1() -> None:
    """F-090 AC1: Extract frames from animated GIF; sample <= 24 frames."""
    extractor = VisionFrameExtractor()
    gif_data = _create_synthetic_gif(n_frames=6)
    frames = extractor.extract_frames(gif_data, max_frames=24)

    assert len(frames) == 6
    hashes = [f.content_hash for f in frames]
    assert len(set(hashes)) == 6
    for f in frames:
        assert f.rgb.shape == (64, 64, 3)
        assert f.original_width == 64
        assert f.original_height == 64
        assert len(f.content_hash) == 64


def test_extract_frames_caps_at_max_frames_ac1() -> None:
    """F-090 AC1: When frame count > 24, sample exactly 24 frames evenly spaced."""
    extractor = VisionFrameExtractor()
    # Create 30 frames
    gif_data = _create_synthetic_gif(n_frames=30)
    frames = extractor.extract_frames(gif_data, max_frames=24)

    assert len(frames) == 24
    # Ensure all frames are valid DecodedImage
    for f in frames:
        assert f.rgb.shape == (64, 64, 3)


def test_extract_frames_single_frame_ac2() -> None:
    """F-090 AC2: Static single frame returns sequence of 1 DecodedImage."""
    extractor = VisionFrameExtractor()
    png_data = _create_synthetic_png()
    frames = extractor.extract_frames(png_data, max_frames=24)

    assert len(frames) == 1
    assert frames[0].rgb.shape == (64, 64, 3)
    assert frames[0].original_width == 64
    assert frames[0].original_height == 64


def test_extract_frames_corrupt_or_empty_ac4() -> None:
    """F-090 AC4: Corrupt or empty inputs raise InvalidImageError."""
    extractor = VisionFrameExtractor()
    with pytest.raises(InvalidImageError, match="empty image data"):
        extractor.extract_frames(b"")

    with pytest.raises(InvalidImageError):
        extractor.extract_frames(b"not_an_image_nor_video_header_random_junk")


def test_extract_frames_size_limit() -> None:
    """F-090: Enforce upload size limit."""
    extractor = VisionFrameExtractor(max_upload_bytes=100)
    data = b"x" * 200
    with pytest.raises(InvalidImageError, match="upload exceeds maximum size"):
        extractor.extract_frames(data)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed on system")
def test_extract_video_frames_with_synthetic_mp4_ac3(tmp_path: pytest.TempPathFactory) -> None:
    """F-090 AC3: Test video extraction with ffmpeg if available."""
    import subprocess

    extractor = VisionFrameExtractor()
    ffmpeg = shutil.which("ffmpeg")
    assert ffmpeg is not None

    # Generate a tiny 2-second test MP4 via ffmpeg
    video_path = tmp_path / "test.mp4"
    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=1:size=64x64:rate=10",
        "-pix_fmt",
        "yuv420p",
        str(video_path),
    ]
    res = subprocess.run(cmd, check=False, capture_output=True)
    if res.returncode != 0:
        pytest.skip("ffmpeg testsrc generation unsupported in current environment")

    video_bytes = video_path.read_bytes()
    frames = extractor.extract_frames(video_bytes, max_frames=24)
    assert len(frames) > 0
    assert len(frames) <= 24
    for f in frames:
        assert f.rgb.shape == (64, 64, 3)
