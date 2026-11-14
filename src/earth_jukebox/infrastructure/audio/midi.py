"""F-043: MIDI export.

Implements MidiExporter port with mido:
- Type 1 MIDI file, 480 ticks/beat
- Tempo meta from bpm
- One track per voice (+ drone track)
- Channel = voice index (skip 9 unless percussion which uses channel 9)
- Fractional pitch: base note round(pitch) + pitch-bend (±2 semitones range)
- RPN 0 = 2 at track start; pitch bend resets after each note
- GM programs: pad 89, pluck 46, bell 14, flute 73, strings 49, sub 38, texture 95
- percussion -> channel 9 note 45
"""

from __future__ import annotations

import io
from typing import Any

import mido

from earth_jukebox.domain.models import NoteEvent, Score

GM_PROGRAMS: dict[str, int] = {
    "pad": 89,
    "pluck": 46,
    "bell": 14,
    "flute": 73,
    "strings": 49,
    "sub": 38,
    "texture": 95,
}

TICKS_PER_BEAT = 480


class MidoMidiExporter:
    """MIDI exporter implementing the MidiExporter application port."""

    def export_midi(self, score: Score) -> bytes:
        """Export Score to Type 1 MIDI file bytes.

        F-043 acceptance criteria:
        - AC1: re-reading gives the same note count and tempo
        - AC2: note at 60.5 produces note 60 + pitch-bend ≈ +50 cents
        """
        mid = mido.MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)

        # Track 0: Tempo and conductor track
        tempo_track = mido.MidiTrack()
        mid.tracks.append(tempo_track)
        tempo = mido.bpm2tempo(max(1.0, score.bpm))
        tempo_track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))
        tempo_track.append(mido.MetaMessage("end_of_track", time=0))

        # Track assignment per voice
        for i, voice in enumerate(score.voices):
            track = mido.MidiTrack()
            mid.tracks.append(track)
            track.append(
                mido.MetaMessage("track_name", name=f"{voice.id}_{voice.instrument}", time=0)
            )

            is_perc = voice.instrument == "percussion"
            channel = 9 if is_perc else ((i if i < 9 else i + 1) % 16)

            # Program change (skip for percussion)
            if not is_perc:
                prog = GM_PROGRAMS.get(voice.instrument, 89)
                track.append(mido.Message("program_change", program=prog, channel=channel, time=0))

            # RPN 0 = 2 for pitch bend range ±2 semitones (doc 07 §5)
            # CC 101: 0, CC 100: 0, CC 6: 2, CC 38: 0, then reset CC 101/100 to 127
            for ctrl, val in ((101, 0), (100, 0), (6, 2), (38, 0), (101, 127), (100, 127)):
                track.append(
                    mido.Message("control_change", control=ctrl, value=val, channel=channel, time=0)
                )

            # Collect voice notes
            voice_notes = [n for n in score.notes if n.voice_id == voice.id]
            self._schedule_notes(track, voice_notes, channel, is_perc)

        # Drone track if drone_midi present
        if score.drone_midi:
            drone_track = mido.MidiTrack()
            mid.tracks.append(drone_track)
            drone_track.append(mido.MetaMessage("track_name", name="drone", time=0))
            drone_channel = 15  # Use high channel for drone
            drone_track.append(
                mido.Message("program_change", program=89, channel=drone_channel, time=0)
            )

            drone_dur_ticks = max(1, round(score.total_beats * TICKS_PER_BEAT))
            events: list[tuple[int, int, Any]] = []
            for midi_pitch in score.drone_midi:
                note_num = max(0, min(127, round(midi_pitch)))
                events.append(
                    (
                        0,
                        1,
                        mido.Message("note_on", note=note_num, velocity=50, channel=drone_channel),
                    )
                )
                events.append(
                    (
                        drone_dur_ticks,
                        0,
                        mido.Message("note_off", note=note_num, velocity=0, channel=drone_channel),
                    )
                )

            self._emit_events_to_track(drone_track, events)

        buf = io.BytesIO()
        mid.save(file=buf)
        return buf.getvalue()

    def _schedule_notes(
        self,
        track: mido.MidiTrack,
        notes: list[NoteEvent],
        channel: int,
        is_perc: bool,
    ) -> None:
        """Schedule notes on a MIDI track with pitch bend and delta timing."""
        events: list[tuple[int, int, Any]] = []

        for note in notes:
            start_tick = round(note.t_beat * TICKS_PER_BEAT)
            dur_tick = max(1, round(note.dur_beat * TICKS_PER_BEAT))
            end_tick = start_tick + dur_tick

            vel = max(1, min(127, round(note.velocity * 127.0)))

            if is_perc:
                base_note = 45  # GM Low Tom
                events.append(
                    (
                        start_tick,
                        3,
                        mido.Message("note_on", note=base_note, velocity=vel, channel=channel),
                    )
                )
                events.append(
                    (
                        end_tick,
                        1,
                        mido.Message("note_off", note=base_note, velocity=0, channel=channel),
                    )
                )
            else:
                base_note = max(0, min(127, round(note.pitch_midi)))
                rem = note.pitch_midi - base_note
                bend = round((rem / 2.0) * 8192.0)
                bend = max(-8192, min(8191, bend))

                # Pitchwheel before note_on if microtonal
                if bend != 0:
                    events.append(
                        (start_tick, 2, mido.Message("pitchwheel", pitch=bend, channel=channel))
                    )
                events.append(
                    (
                        start_tick,
                        3,
                        mido.Message("note_on", note=base_note, velocity=vel, channel=channel),
                    )
                )
                # Note off
                events.append(
                    (
                        end_tick,
                        1,
                        mido.Message("note_off", note=base_note, velocity=0, channel=channel),
                    )
                )
                # Reset pitch bend after note off
                if bend != 0:
                    events.append(
                        (end_tick, 2, mido.Message("pitchwheel", pitch=0, channel=channel))
                    )

        self._emit_events_to_track(track, events)

    def _emit_events_to_track(
        self,
        track: mido.MidiTrack,
        events: list[tuple[int, int, Any]],
    ) -> None:
        """Sort timed events and convert to delta times on track."""
        events.sort(key=lambda item: (item[0], item[1]))

        last_tick = 0
        for tick, _, msg in events:
            dt = max(0, tick - last_tick)
            msg.time = dt
            track.append(msg)
            last_tick = tick

        track.append(mido.MetaMessage("end_of_track", time=0))
