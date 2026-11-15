"""MP4 Video exporter implementing the VideoExporter port via ffmpeg (F-109).

Combines NASA scientific imagery, animated playhead/slider line, and synthesized sonification audio
into a high-definition, universally playable MP4 video.
"""

from __future__ import annotations

import io
import logging
import os
import shutil
import subprocess
import tempfile

import cv2
import numpy as np
from PIL import Image, ImageSequence

from earth_jukebox.application.ports import VideoExporter
from earth_jukebox.domain.models import PixelBox, Score

logger = logging.getLogger(__name__)


class FfmpegVideoExporter(VideoExporter):
    """Renders video of the image with synchronized slider line and audio via ffmpeg."""

    def __init__(
        self,
        ffmpeg_bin: str = "ffmpeg",
        default_fps: int = 30,
        max_dimension: int = 1280,
    ) -> None:
        self._ffmpeg_bin = ffmpeg_bin
        self._default_fps = default_fps
        self._max_dimension = max_dimension

    def is_available(self) -> bool:
        """Check if ffmpeg binary is executable on system PATH."""
        return shutil.which(self._ffmpeg_bin) is not None

    def export_video(
        self,
        image_bytes: bytes,
        wav_bytes: bytes,
        score: Score,
        map_box: PixelBox | None = None,
        fps: int = 30,
    ) -> bytes:
        """Render MP4 video with image, moving slider/playhead, and synchronized audio.

        Raises:
            RuntimeError: If ffmpeg is missing or video generation fails.
        """
        if not self.is_available():
            raise RuntimeError(f"ffmpeg binary '{self._ffmpeg_bin}' not found on system PATH.")

        if fps <= 0:
            fps = self._default_fps

        # Decode image (supporting animated GIF/APNG or static image)
        try:
            pil_img = Image.open(io.BytesIO(image_bytes))
        except Exception as exc:
            raise RuntimeError(f"failed to decode image for video: {exc}") from exc

        orig_w, orig_h = pil_img.size

        # Determine target dimensions (clamped to max_dimension and even numbers for H.264)
        scale = 1.0
        if max(orig_w, orig_h) > self._max_dimension:
            scale = self._max_dimension / float(max(orig_w, orig_h))

        nw = max(16, round(orig_w * scale))
        nh = max(16, round(orig_h * scale))
        nw -= nw % 2
        nh -= nh % 2

        # Extract frames as BGR numpy arrays
        frames_bgr: list[np.ndarray] = []
        is_animated = bool(getattr(pil_img, "is_animated", False))
        n_frames = getattr(pil_img, "n_frames", 1)

        if is_animated and n_frames > 1:
            for frame in ImageSequence.Iterator(pil_img):
                f_rgb = frame.convert("RGB")
                if f_rgb.size != (nw, nh):
                    f_rgb = f_rgb.resize((nw, nh), Image.Resampling.BILINEAR)
                frames_bgr.append(cv2.cvtColor(np.array(f_rgb), cv2.COLOR_RGB2BGR))
        else:
            base_rgb = pil_img.convert("RGB")
            if base_rgb.size != (nw, nh):
                base_rgb = base_rgb.resize((nw, nh), Image.Resampling.BILINEAR)
            frames_bgr.append(cv2.cvtColor(np.array(base_rgb), cv2.COLOR_RGB2BGR))

        if not frames_bgr:
            raise RuntimeError("no valid image frames available for video rendering")

        # Map bounds for slider sweep
        if map_box is not None:
            scale_x = float(nw) / float(orig_w)
            x_start = max(0, min(nw - 1, round(map_box.x * scale_x)))
            x_end = max(x_start + 1, min(nw, round((map_box.x + map_box.w) * scale_x)))
        else:
            x_start = 0
            x_end = nw

        # Total video duration and frames
        bpm = max(1.0, score.bpm)
        duration_sec = score.total_beats * (60.0 / bpm)
        total_video_frames = max(1, round(duration_sec * fps))

        # Time mode provenance inspection
        is_time_mode = score.provenance.get("time_mode") == "true"
        frame_beats = float(score.provenance.get("frame_beats", "48.0"))
        rest_beats = float(score.provenance.get("rest_beats", "1.0"))
        n_source_frames = len(frames_bgr)

        # Temporary files for audio input and video output
        with (
            tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_file,
            tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as mp4_file,
        ):
            wav_path = wav_file.name
            mp4_path = mp4_file.name
            wav_file.write(wav_bytes)

        try:
            cmd = [
                self._ffmpeg_bin,
                "-y",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "bgr24",
                "-s",
                f"{nw}x{nh}",
                "-r",
                str(fps),
                "-i",
                "pipe:0",
                "-i",
                wav_path,
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "22",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                "-movflags",
                "+faststart",
                mp4_path,
            ]

            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            for f_idx in range(total_video_frames):
                t_sec = f_idx / float(fps)
                t_beat = t_sec * bpm / 60.0

                # Select active image frame and calculate sweep ratio
                if is_time_mode and n_source_frames > 1:
                    cycle = frame_beats + rest_beats
                    f_num = min(n_source_frames - 1, int(t_beat // cycle))
                    intra_beat = t_beat - f_num * cycle
                    ratio = min(1.0, max(0.0, intra_beat / max(1e-6, frame_beats)))
                    base_frame = frames_bgr[f_num]
                else:
                    ratio = min(1.0, max(0.0, t_beat / max(1e-6, score.total_beats)))
                    base_frame = frames_bgr[0]

                slider_x = round(x_start + ratio * (x_end - x_start))
                slider_x = max(0, min(nw - 1, slider_x))

                # Render slider overlay
                draw_frame = base_frame.copy()

                # Vertical slider line with dark outline for contrast against any background
                cv2.line(draw_frame, (slider_x, 0), (slider_x, nh), (15, 15, 15), 4, cv2.LINE_AA)
                cv2.line(
                    draw_frame,
                    (slider_x, 0),
                    (slider_x, nh),
                    (248, 189, 56),  # Sky blue / cyan in BGR
                    2,
                    cv2.LINE_AA,
                )

                # Slider head / marker dots
                if nh > 30:
                    # Top marker
                    cv2.circle(draw_frame, (slider_x, 10), 8, (15, 15, 15), -1, cv2.LINE_AA)
                    cv2.circle(draw_frame, (slider_x, 10), 5, (248, 189, 56), -1, cv2.LINE_AA)
                    # Bottom marker
                    cv2.circle(draw_frame, (slider_x, nh - 10), 8, (15, 15, 15), -1, cv2.LINE_AA)
                    cv2.circle(draw_frame, (slider_x, nh - 10), 5, (248, 189, 56), -1, cv2.LINE_AA)

                # Bottom slider progress bar track
                if nh > 60 and (x_end - x_start) > 20:
                    track_h = 4
                    track_y = nh - 8
                    cv2.rectangle(
                        draw_frame,
                        (x_start, track_y),
                        (x_end, track_y + track_h),
                        (25, 25, 25),
                        -1,
                    )
                    if slider_x > x_start:
                        cv2.rectangle(
                            draw_frame,
                            (x_start, track_y),
                            (slider_x, track_y + track_h),
                            (248, 189, 56),
                            -1,
                        )
                    cv2.circle(
                        draw_frame,
                        (slider_x, track_y + track_h // 2),
                        5,
                        (15, 15, 15),
                        -1,
                        cv2.LINE_AA,
                    )
                    cv2.circle(
                        draw_frame,
                        (slider_x, track_y + track_h // 2),
                        4,
                        (248, 189, 56),
                        -1,
                        cv2.LINE_AA,
                    )

                assert proc.stdin is not None
                proc.stdin.write(draw_frame.tobytes())

            assert proc.stdin is not None
            proc.stdin.close()
            stderr_bytes = proc.stderr.read() if proc.stderr else b""
            ret_code = proc.wait()

            if ret_code != 0:
                err_msg = stderr_bytes.decode(errors="replace")
                logger.error("ffmpeg video export error: %s", err_msg)
                raise RuntimeError(f"ffmpeg video conversion failed: {err_msg}")

            with open(mp4_path, "rb") as out_f:
                return out_f.read()

        finally:
            if os.path.exists(wav_path):
                os.unlink(wav_path)
            if os.path.exists(mp4_path):
                os.unlink(mp4_path)
