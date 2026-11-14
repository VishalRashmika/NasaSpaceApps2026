"""Unit tests for F-046 FluidSynth adapter (stretch)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from earth_jukebox.application.ports import AudioRenderer
from earth_jukebox.domain.models import ColormapKind, LegendSpec, NoteEvent, Score, Voice
from earth_jukebox.infrastructure.audio.fluidsynth import FluidSynthAudioRenderer


def _make_dummy_score(total_beats: float = 4.0, bpm: float = 120.0) -> Score:
    voice = Voice(
        id="band_0",
        band_index=0,
        instrument="flute",
        pan=0.0,
    )
    notes = tuple(
        NoteEvent(
            voice_id="band_0",
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
            label="Temp",
            kind=ColormapKind.SEQUENTIAL,
        ),
        provenance={"drone_brightness": "0.5"},
    )


def test_f046_fluidsynth_conforms_to_audio_renderer_protocol() -> None:
    renderer = FluidSynthAudioRenderer()
    # Check duck-typing protocol methods
    assert hasattr(renderer, "render_wav")
    assert callable(renderer.render_wav)
    # Static type check: can assign to AudioRenderer variable
    typed_renderer: AudioRenderer = renderer
    assert typed_renderer is not None


def test_f046_fluidsynth_is_available_returns_false_when_missing(tmp_path: Path) -> None:
    # No soundfont provided
    renderer1 = FluidSynthAudioRenderer(soundfont_path=None)
    assert not renderer1.is_available()

    # Nonexistent soundfont
    renderer2 = FluidSynthAudioRenderer(soundfont_path=tmp_path / "nonexistent.sf2")
    assert not renderer2.is_available()

    # Nonexistent binary
    sf_file = tmp_path / "test.sf2"
    sf_file.write_bytes(b"dummy sf2")
    renderer3 = FluidSynthAudioRenderer(
        soundfont_path=sf_file,
        fluidsynth_bin="nonexistent_fluidsynth_binary_xyz",
    )
    assert not renderer3.is_available()


def test_f046_fluidsynth_render_wav_raises_when_unavailable() -> None:
    renderer = FluidSynthAudioRenderer(soundfont_path=None)
    score = _make_dummy_score()
    with pytest.raises(RuntimeError, match="FluidSynth audio renderer unavailable"):
        renderer.render_wav(score)


def test_f046_fluidsynth_render_wav_executes_cli(tmp_path: Path) -> None:
    sf_file = tmp_path / "soundfont.sf2"
    sf_file.write_bytes(b"dummy sf2 data")

    score = _make_dummy_score()
    mock_midi_exporter = MagicMock()
    mock_midi_exporter.export_midi.return_value = b"MThd\x00\x00\x00\x06dummy midi data"

    renderer = FluidSynthAudioRenderer(
        soundfont_path=sf_file,
        fluidsynth_bin="mock_fluidsynth",
        midi_exporter=mock_midi_exporter,
    )

    dummy_wav_content = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00data"

    def fake_subprocess_run(cmd: list[str], **kwargs: object) -> MagicMock:
        # cmd: [bin, "-F", out_wav, "-r", sample_rate, sf_path, in_midi]
        out_wav_path = Path(cmd[2])
        out_wav_path.write_bytes(dummy_wav_content)
        return MagicMock(returncode=0)

    with (
        patch("shutil.which", return_value="/usr/bin/mock_fluidsynth"),
        patch("subprocess.run", side_effect=fake_subprocess_run) as mock_run,
    ):
        assert renderer.is_available()
        wav_bytes = renderer.render_wav(score, sample_rate=44100)
        assert wav_bytes == dummy_wav_content
        assert mock_run.called
        cmd_args = mock_run.call_args[0][0]
        assert cmd_args[0] == "mock_fluidsynth"
        assert cmd_args[1] == "-F"
        assert cmd_args[3] == "-r"
        assert cmd_args[4] == "44100"
        assert cmd_args[5] == str(sf_file)
