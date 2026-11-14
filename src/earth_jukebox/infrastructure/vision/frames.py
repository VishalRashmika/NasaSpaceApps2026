"""F-090: Frame extraction from animations (GIF, APNG, MP4, WebM).

Implements FrameExtractor port in infrastructure/vision.
Extracts up to 24 evenly sampled frames from animated formats.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from earth_jukebox.application.ports import FrameExtractor, ImageDecoder
from earth_jukebox.domain.errors import InvalidImageError
from earth_jukebox.domain.models import DecodedImage
from earth_jukebox.infrastructure.vision.decoder import PillowImageDecoder

VIDEO_MAGIC_PATTERNS = (
    b"ftyp",  # MP4 / MOV / M4V container
    b"\x1a\x45\xdf\xa3",  # WebM / Matroska EBML header
)


def _is_probable_video(data: bytes) -> bool:
    """Check if header contains MP4/WebM signatures."""
    if len(data) < 16:
        return False
    if data.startswith(b"\x1a\x45\xdf\xa3"):
        return True
    # MP4 ftyp usually occurs at byte offset 4..8
    return b"ftyp" in data[:32]


class VisionFrameExtractor(FrameExtractor):
    """Extracts up to 24 frames from animated GIF/APNG or video bytes (F-090)."""

    def __init__(
        self,
        decoder: ImageDecoder | None = None,
        max_upload_bytes: int = 20 * 1024 * 1024,
        max_image_dimension: int = 8000,
        working_max_dimension: int = 2048,
    ) -> None:
        self.decoder = decoder or PillowImageDecoder(
            max_upload_bytes=max_upload_bytes,
            max_image_dimension=max_image_dimension,
            working_max_dimension=working_max_dimension,
        )
        self.max_upload_bytes = max_upload_bytes
        self.max_image_dimension = max_image_dimension
        self.working_max_dimension = working_max_dimension

    def extract_frames(self, data: bytes, max_frames: int = 24) -> Sequence[DecodedImage]:
        """Extract up to max_frames evenly sampled frames from animated image or video bytes."""
        if len(data) == 0:
            raise InvalidImageError("empty image data")

        if len(data) > self.max_upload_bytes:
            raise InvalidImageError(f"upload exceeds maximum size of {self.max_upload_bytes} bytes")

        # 1. Try decoding as Pillow image first (GIF, APNG, PNG, JPEG, WEBP)
        try:
            pil_img: Image.Image = Image.open(io.BytesIO(data))
        except Exception as exc:
            # Check if this might be video (MP4 / WebM)
            if _is_probable_video(data):
                return self._extract_video_frames(data, max_frames)
            raise InvalidImageError(f"unrecognized format or cannot decode image: {exc}") from exc

        n_frames = getattr(pil_img, "n_frames", 1)

        # If static single frame image, delegate directly to decoder (AC2)
        if n_frames <= 1:
            decoded = self.decoder.decode(data)
            return [decoded]

        # Multi-frame animated image (GIF / APNG) (AC1)
        k_frames = min(n_frames, max_frames)
        if n_frames <= max_frames:
            sampled_indices = list(range(n_frames))
        else:
            sampled_indices = [round(float(i)) for i in np.linspace(0, n_frames - 1, k_frames)]

        base_hash = hashlib.sha256(data).hexdigest()
        decoded_frames: list[DecodedImage] = []

        for idx in sampled_indices:
            try:
                pil_img.seek(idx)
                frame_copy = pil_img.copy()
            except Exception as exc:
                raise InvalidImageError(f"failed reading animation frame {idx}: {exc}") from exc

            # Normalize frame: EXIF, alpha flattening, area downscaling
            with contextlib.suppress(Exception):
                frame_copy = ImageOps.exif_transpose(frame_copy) or frame_copy

            orig_w, orig_h = frame_copy.size
            if orig_w > self.max_image_dimension or orig_h > self.max_image_dimension:
                raise InvalidImageError(
                    f"frame dimension {max(orig_w, orig_h)} exceeds maximum of "
                    f"{self.max_image_dimension} px/side"
                )

            if frame_copy.mode in ("RGBA", "LA") or (
                frame_copy.mode == "P" and "transparency" in frame_copy.info
            ):
                rgba_img = frame_copy.convert("RGBA")
                bg = Image.new("RGBA", rgba_img.size, (255, 255, 255, 255))
                composite = Image.alpha_composite(bg, rgba_img)
                rgb_img = composite.convert("RGB")
            else:
                rgb_img = frame_copy.convert("RGB")

            rgb_array = np.asarray(rgb_img, dtype=np.uint8)

            max_dim = max(orig_w, orig_h)
            if max_dim > self.working_max_dimension:
                scale = self.working_max_dimension / float(max_dim)
                target_w = round(orig_w * scale)
                target_h = round(orig_h * scale)
                resized = cv2.resize(rgb_array, (target_w, target_h), interpolation=cv2.INTER_AREA)
                rgb_array = np.asarray(resized, dtype=np.uint8)

            frame_hash = hashlib.sha256(f"{base_hash}_{idx}".encode()).hexdigest()
            decoded_frames.append(
                DecodedImage(
                    rgb=rgb_array,
                    content_hash=frame_hash,
                    original_width=orig_w,
                    original_height=orig_h,
                )
            )

        return decoded_frames

    def _extract_video_frames(self, data: bytes, max_frames: int) -> list[DecodedImage]:
        """Extract frames from MP4 or WebM video using ffmpeg (AC3)."""
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            raise InvalidImageError(
                "ffmpeg binary not installed on host: required for MP4/WebM video frame extraction"
            )

        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            input_file = tmp_dir / "input_video.bin"
            input_file.write_bytes(data)

            output_pattern = str(tmp_dir / "frame_%05d.png")
            cmd = [
                ffmpeg_bin,
                "-v",
                "error",
                "-i",
                str(input_file),
                output_pattern,
            ]

            try:
                proc = subprocess.run(
                    cmd,
                    check=False,
                    capture_output=True,
                    timeout=30,
                )
            except subprocess.TimeoutExpired as exc:
                raise InvalidImageError("ffmpeg video extraction timed out") from exc

            if proc.returncode != 0:
                err_msg = proc.stderr.decode("utf-8", errors="replace")
                raise InvalidImageError(f"ffmpeg failed to extract video frames: {err_msg}")

            extracted_pngs = sorted(tmp_dir.glob("frame_*.png"))
            if not extracted_pngs:
                raise InvalidImageError("ffmpeg extracted zero video frames from input")

            n_extracted = len(extracted_pngs)
            k_frames = min(n_extracted, max_frames)
            if n_extracted <= max_frames:
                chosen_paths = extracted_pngs
            else:
                indices = [round(float(i)) for i in np.linspace(0, n_extracted - 1, k_frames)]
                chosen_paths = [extracted_pngs[i] for i in indices]

            decoded_frames: list[DecodedImage] = []
            for p in chosen_paths:
                frame_data = p.read_bytes()
                decoded_frames.append(self.decoder.decode(frame_data))

            return decoded_frames
