"""Unit tests for F-043 (MIDI export)."""

from __future__ import annotations

import io
import math

import mido

from earth_jukebox.domain.models import ColormapKind, LegendSpec, NoteEvent, Score, Voice
from earth_jukebox.infrastructure.audio.midi import MidoMidiExporter


def test_f043_ac1_re_reading_gives_same_note_count_and_tempo() -> None:
    # F-043 AC1: re-reading the file gives the same note count and tempo
    exporter = MidoMidiExporter()

    voice1 = Voice(id="band0", band_index=0, instrument="flute", pan=-0.5)
    voice2 = Voice(id="band1", band_index=1, instrument="strings", pan=0.5)

    notes = (
        NoteEvent(
            voice_id="band0",
            t_beat=0.0,
            dur_beat=1.0,
            pitch_midi=60.0,
            velocity=0.8,
            accent=False,
            col=0,
            band=0,
            value=1.0,
        ),
        NoteEvent(
            voice_id="band0",
            t_beat=1.0,
            dur_beat=0.5,
            pitch_midi=62.0,
            velocity=0.7,
            accent=False,
            col=1,
            band=0,
            value=2.0,
        ),
        NoteEvent(
            voice_id="band1",
            t_beat=0.5,
            dur_beat=1.5,
            pitch_midi=67.0,
            velocity=0.9,
            accent=True,
            col=0,
            band=1,
            value=3.0,
        ),
    )

    score = Score(
        mapping_version="1.0.0",
        skin_id="neutral",
        seed=123,
        bpm=110.0,
        total_beats=4.0,
        n_cols=2,
        n_bands=2,
        voices=(voice1, voice2),
        notes=notes,
        drone_midi=(),
        legend=LegendSpec(
            vmin=0.0, vmax=10.0, units="C", label="Temp", kind=ColormapKind.SEQUENTIAL
        ),
        provenance={},
    )

    midi_bytes = exporter.export_midi(score)
    assert len(midi_bytes) > 0

    mid = mido.MidiFile(file=io.BytesIO(midi_bytes))
    assert mid.type == 1
    assert mid.ticks_per_beat == 480

    # Count note_on events with velocity > 0
    note_ons = []
    found_bpm = None
    for track in mid.tracks:
        for msg in track:
            if msg.type == "note_on" and msg.velocity > 0:
                note_ons.append(msg)
            elif msg.type == "set_tempo":
                found_bpm = mido.tempo2bpm(msg.tempo)

    assert len(note_ons) == len(notes), f"Expected {len(notes)} notes, found {len(note_ons)}"
    assert found_bpm is not None
    assert math.isclose(found_bpm, score.bpm, abs_tol=1e-3)


def test_f043_ac2_microtone_pitch_bend_approx_fifty_cents() -> None:
    # F-043 AC2: a note at 60.5 produces note 60 + pitch-bend ≈ +50 cents
    exporter = MidoMidiExporter()

    voice = Voice(id="solo", band_index=0, instrument="pad", pan=0.0)
    note = NoteEvent(
        voice_id="solo",
        t_beat=0.0,
        dur_beat=1.0,
        pitch_midi=60.5,
        velocity=0.8,
        accent=False,
        col=0,
        band=0,
        value=5.0,
    )
    score = Score(
        mapping_version="1.0.0",
        skin_id="neutral",
        seed=42,
        bpm=96.0,
        total_beats=2.0,
        n_cols=1,
        n_bands=1,
        voices=(voice,),
        notes=(note,),
        drone_midi=(),
        legend=LegendSpec(
            vmin=0.0, vmax=10.0, units="%", label="Humidity", kind=ColormapKind.SEQUENTIAL
        ),
        provenance={},
    )

    midi_bytes = exporter.export_midi(score)
    mid = mido.MidiFile(file=io.BytesIO(midi_bytes))

    # Look for note_on note and pitchwheel in voice track
    found_note = None
    found_bend = None
    for track in mid.tracks:
        for msg in track:
            if msg.type == "note_on" and msg.velocity > 0:
                found_note = msg.note
            elif msg.type == "pitchwheel" and msg.pitch != 0:
                found_bend = msg.pitch

    assert found_note == 60, f"Expected base note 60, got {found_note}"
    assert found_bend is not None, "Pitchwheel message not found"
    # Pitch bend range is +-2 semitones = +-200 cents over [-8192, 8191]
    # So 50 cents corresponds to (50 / 200) * 8192 = 2048
    cents_bend = (found_bend / 8192.0) * 200.0
    assert abs(cents_bend - 50.0) < 1.0, f"Expected ~50 cents, got {cents_bend:.2f}"


def test_f043_percussion_channel_and_programs() -> None:
    # Verify percussion uses channel 9 (GM drum channel) and note 45
    exporter = MidoMidiExporter()
    voice = Voice(id="perc", band_index=0, instrument="percussion", pan=0.0)
    note = NoteEvent(
        voice_id="perc",
        t_beat=0.0,
        dur_beat=0.5,
        pitch_midi=60.0,
        velocity=0.8,
        accent=True,
        col=0,
        band=0,
        value=1.0,
    )
    score = Score(
        mapping_version="1.0.0",
        skin_id="neutral",
        seed=1,
        bpm=120.0,
        total_beats=2.0,
        n_cols=1,
        n_bands=1,
        voices=(voice,),
        notes=(note,),
        drone_midi=(),
        legend=LegendSpec(vmin=0.0, vmax=1.0, units="", label="Hit", kind=ColormapKind.SEQUENTIAL),
        provenance={},
    )
    midi_bytes = exporter.export_midi(score)
    mid = mido.MidiFile(file=io.BytesIO(midi_bytes))

    found_msg = None
    for track in mid.tracks:
        for msg in track:
            if msg.type == "note_on" and msg.velocity > 0:
                found_msg = msg
    assert found_msg is not None
    assert found_msg.channel == 9
    assert found_msg.note == 45
