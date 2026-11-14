"""MP3 exporter implementing the Mp3Exporter port via ffmpeg (F-044).

Converts WAV audio bytes to MP3 format using ffmpeg subprocess with fixed arguments.
"""

from __future__ import annotations

import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)


class FfmpegMp3Exporter:
    """Exports WAV audio bytes to MP3 using ffmpeg if available on PATH."""

    def __init__(self, ffmpeg_bin: str = "ffmpeg", bitrate_kbps: int = 192) -> None:
        self._ffmpeg_bin = ffmpeg_bin
        self._bitrate_kbps = bitrate_kbps

    def is_available(self) -> bool:
        """Check if the ffmpeg binary is executable on system PATH."""
        return shutil.which(self._ffmpeg_bin) is not None

    def export_mp3(self, wav_bytes: bytes) -> bytes:
        """Convert WAV audio bytes to MP3 bytes.

        Raises:
            RuntimeError: If ffmpeg is missing or conversion fails.
        """
        if not self.is_available():
            raise RuntimeError(f"ffmpeg binary '{self._ffmpeg_bin}' not found on system PATH.")

        try:
            cmd = [
                self._ffmpeg_bin,
                "-y",
                "-f",
                "wav",
                "-i",
                "pipe:0",
                "-vn",
                "-b:a",
                f"{self._bitrate_kbps}k",
                "-f",
                "mp3",
                "pipe:1",
            ]
            result = subprocess.run(
                cmd,
                input=wav_bytes,
                capture_output=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as err:
            logger.error("ffmpeg MP3 export error: %s", err.stderr.decode(errors="replace"))
            raise RuntimeError(f"ffmpeg MP3 conversion failed: {err}") from err
