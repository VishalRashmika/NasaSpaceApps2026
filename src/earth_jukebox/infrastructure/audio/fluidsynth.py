"""FluidSynth adapter implementing the AudioRenderer port (F-046 stretch).

Provides an optional SoundFont-based synthesizer renderer behind the AudioRenderer port
when the fluidsynth CLI binary and a compatible SoundFont (.sf2) file are present.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from earth_jukebox.application.ports import AudioRenderer, MidiExporter
from earth_jukebox.domain.models import Score
from earth_jukebox.infrastructure.audio.midi import MidoMidiExporter

logger = logging.getLogger(__name__)


class FluidSynthAudioRenderer(AudioRenderer):
    """AudioRenderer adapter using the fluidsynth CLI and SoundFont files."""

    def __init__(
        self,
        soundfont_path: str | Path | None = None,
        fluidsynth_bin: str = "fluidsynth",
        midi_exporter: MidiExporter | None = None,
    ) -> None:
        self._soundfont_path = Path(soundfont_path) if soundfont_path is not None else None
        self._fluidsynth_bin = fluidsynth_bin
        self._midi_exporter = midi_exporter or MidoMidiExporter()

    def is_available(self) -> bool:
        """Check if fluidsynth binary and soundfont are present."""
        if shutil.which(self._fluidsynth_bin) is None:
            return False
        return self._soundfont_path is not None and self._soundfont_path.is_file()

    def render_wav(self, score: Score, sample_rate: int = 44100) -> bytes:
        """Render a Score to WAV bytes using FluidSynth.

        Raises:
            RuntimeError: If fluidsynth is unavailable or synthesis fails.
        """
        if not self.is_available():
            raise RuntimeError(
                f"FluidSynth audio renderer unavailable: binary '{self._fluidsynth_bin}' "
                f"or SoundFont '{self._soundfont_path}' missing."
            )

        midi_bytes = self._midi_exporter.export_midi(score)

        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            midi_file = tmp_dir / "score.mid"
            wav_file = tmp_dir / "output.wav"

            midi_file.write_bytes(midi_bytes)

            assert self._soundfont_path is not None
            cmd = [
                self._fluidsynth_bin,
                "-F",
                str(wav_file),
                "-r",
                str(sample_rate),
                str(self._soundfont_path),
                str(midi_file),
            ]

            try:
                subprocess.run(cmd, capture_output=True, check=True)
                return wav_file.read_bytes()
            except subprocess.CalledProcessError as err:
                logger.error(
                    "FluidSynth rendering failed: %s",
                    err.stderr.decode(errors="replace"),
                )
                raise RuntimeError(f"FluidSynth execution failed: {err}") from err
