"""
Unit tests for backend/synthesizer.py: Backend Audio Synthesis Engine & WAV Generation.
"""

import io
import json
import math
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np
import scipy.signal
import soundfile as sf
from pydub import AudioSegment

from backend.scanner import (
    AudioEventList,
    generate_scan_path,
    map_parameters,
)
from backend.synthesizer import (
    DEFAULT_DIFFUSE_WAVEFORM,
    DEFAULT_SAMPLE_RATE,
    SampleManager,
    SampleNotFoundError,
    SynthesisResult,
    SynthesizerError,
    export_json_timeline,
    generate_default_samples,
    generate_waveform,
    get_default_sample_manager,
    mix_tracks,
    pitch_shift_segment,
    pydub_to_numpy,
    resolve_point_source_sample_name,
    synthesize_diffuse_track,
    synthesize_point_sources_track,
    synthesize_wav,
)


class TestWaveformGeneration(unittest.TestCase):
    """Test suite for continuous diffuse waveform generation via scipy.signal."""

    def setUp(self):
        self.sr = 44100
        self.freq = 440.0
        self.dur = 0.2

    def test_sine_waveform_generation(self):
        """Verify sine wave shape, frequency, and amplitude bounds."""
        wave = generate_waveform("sine", self.freq, self.dur, sample_rate=self.sr)
        expected_len = int(round(self.sr * self.dur))
        self.assertEqual(len(wave), expected_len)
        self.assertEqual(wave.dtype, np.float32)
        self.assertLessEqual(np.max(np.abs(wave)), 1.0)
        self.assertGreater(np.max(np.abs(wave)), 0.3)

    def test_sawtooth_waveform_scipy(self):
        """Verify sawtooth wave generation using scipy.signal.sawtooth."""
        wave = generate_waveform("sawtooth", self.freq, self.dur, sample_rate=self.sr)
        expected_len = int(round(self.sr * self.dur))
        self.assertEqual(len(wave), expected_len)
        self.assertEqual(wave.dtype, np.float32)
        # Check harmonic presence: sawtooth has higher harmonic content than sine
        sine = generate_waveform("sine", self.freq, self.dur, sample_rate=self.sr, apply_envelope=False)
        saw = generate_waveform("sawtooth", self.freq, self.dur, sample_rate=self.sr, apply_envelope=False)
        fft_sine = np.abs(np.fft.rfft(sine))
        fft_saw = np.abs(np.fft.rfft(saw))
        # 2nd harmonic (880 Hz) should be significantly higher in sawtooth than sine
        freqs = np.fft.rfftfreq(len(sine), 1.0 / self.sr)
        h2_idx = np.argmin(np.abs(freqs - 880.0))
        self.assertGreater(fft_saw[h2_idx], fft_sine[h2_idx] * 5.0)

    def test_triangle_and_square_waveforms(self):
        """Verify triangle and square waveform generation."""
        tri = generate_waveform("triangle", self.freq, self.dur, sample_rate=self.sr)
        sqr = generate_waveform("square", self.freq, self.dur, sample_rate=self.sr)
        self.assertEqual(len(tri), int(round(self.sr * self.dur)))
        self.assertEqual(len(sqr), int(round(self.sr * self.dur)))
        self.assertEqual(tri.dtype, np.float32)
        self.assertEqual(sqr.dtype, np.float32)

    def test_blend_waveform(self):
        """Verify hybrid warm pad waveform combining sine and sawtooth."""
        blend = generate_waveform("blend", self.freq, self.dur, sample_rate=self.sr)
        self.assertEqual(len(blend), int(round(self.sr * self.dur)))
        self.assertGreater(np.max(np.abs(blend)), 0.2)

    def test_zero_or_negative_duration(self):
        """Verify handling of zero or negative duration."""
        zero_w = generate_waveform("sine", self.freq, 0.0, sample_rate=self.sr)
        neg_w = generate_waveform("sawtooth", self.freq, -0.5, sample_rate=self.sr)
        self.assertEqual(len(zero_w), 0)
        self.assertEqual(len(neg_w), 0)

    def test_tukey_envelope_edge_attenuation(self):
        """Verify that Tukey envelope tapers slice boundaries to 0 to prevent clicks."""
        wave = generate_waveform("sine", self.freq, 0.1, sample_rate=self.sr, apply_envelope=True)
        # First and last samples should be near zero
        self.assertAlmostEqual(wave[0], 0.0, places=2)
        self.assertAlmostEqual(wave[-1], 0.0, places=2)


class TestDiffuseLayerSynthesis(unittest.TestCase):
    """Test suite for continuous diffuse emission layer synthesis."""

    def setUp(self):
        self.sr = 44100
        self.duration = 1.0

    def test_synthesize_diffuse_track_stereo_shape(self):
        """Verify diffuse track output is 2D stereo (N, 2) float32."""
        events = [
            {"time": 0.0, "duration": 0.5, "frequency": 261.63, "amplitude": 0.8, "pan": 0.0},
            {"time": 0.5, "duration": 0.5, "frequency": 329.63, "amplitude": 0.7, "pan": 0.5},
        ]
        track = synthesize_diffuse_track(events, self.duration, sample_rate=self.sr)
        self.assertEqual(track.ndim, 2)
        self.assertEqual(track.shape[1], 2)
        self.assertEqual(track.shape[0], int(self.sr * self.duration))
        self.assertEqual(track.dtype, np.float32)

    def test_diffuse_stereo_panning(self):
        """Verify that panning shifts energy between left and right channels."""
        # Full Left (pan = -1.0)
        left_event = [{"time": 0.0, "duration": 0.5, "frequency": 440.0, "amplitude": 1.0, "pan": -1.0}]
        left_track = synthesize_diffuse_track(left_event, 0.5, sample_rate=self.sr)
        left_energy = np.sum(left_track[:, 0] ** 2)
        right_energy = np.sum(left_track[:, 1] ** 2)
        self.assertGreater(left_energy, right_energy * 20.0)

        # Full Right (pan = 1.0)
        right_event = [{"time": 0.0, "duration": 0.5, "frequency": 440.0, "amplitude": 1.0, "pan": 1.0}]
        right_track = synthesize_diffuse_track(right_event, 0.5, sample_rate=self.sr)
        l_energy_r = np.sum(right_track[:, 0] ** 2)
        r_energy_r = np.sum(right_track[:, 1] ** 2)
        self.assertGreater(r_energy_r, l_energy_r * 20.0)

    def test_empty_diffuse_events(self):
        """Verify that empty diffuse events produce a silent stereo array."""
        track = synthesize_diffuse_track([], self.duration, sample_rate=self.sr)
        self.assertEqual(track.shape, (int(self.sr * self.duration), 2))
        self.assertTrue(np.all(track == 0.0))


class TestPhysicalSamplePlayback(unittest.TestCase):
    """Test suite for pydub pre-recorded sample playback, pitch shifting, and mixing."""

    @classmethod
    def setUpClass(cls):
        # Ensure default samples exist
        generate_default_samples(overwrite=False)

    def test_sample_manager_loads_default_samples(self):
        """Verify that crackle, whoosh, pluck, and ping can be loaded via pydub."""
        manager = get_default_sample_manager()
        for name in ("crackle", "whoosh", "pluck", "ping"):
            seg = manager.get_sample(name)
            self.assertIsInstance(seg, AudioSegment)
            self.assertGreater(len(seg), 50)  # > 50ms
            self.assertEqual(seg.channels, 2)
            self.assertEqual(seg.frame_rate, DEFAULT_SAMPLE_RATE)

    def test_sample_alias_resolution(self):
        """Verify that aliases like 'ice', 'wind', 'hotspot' resolve to correct samples."""
        manager = get_default_sample_manager()
        ice_seg = manager.get_sample("ice")
        wind_seg = manager.get_sample("wind")
        star_seg = manager.get_sample("star")
        self.assertIsNotNone(ice_seg)
        self.assertIsNotNone(wind_seg)
        self.assertIsNotNone(star_seg)

    def test_pitch_shift_segment_ratio(self):
        """Verify playback rate pitch shifting transposes audio and modifies duration."""
        manager = get_default_sample_manager()
        orig = manager.get_sample("pluck")
        orig_len = len(orig)

        # 1 octave up (ratio 2.0) -> duration should be approximately half
        shifted_up = pitch_shift_segment(orig, ratio=2.0)
        self.assertEqual(shifted_up.frame_rate, DEFAULT_SAMPLE_RATE)
        self.assertAlmostEqual(len(shifted_up), orig_len // 2, delta=orig_len * 0.1)

        # 1 octave down (ratio 0.5) -> duration should be approximately double
        shifted_down = pitch_shift_segment(orig, ratio=0.5)
        self.assertEqual(shifted_down.frame_rate, DEFAULT_SAMPLE_RATE)
        self.assertAlmostEqual(len(shifted_down), orig_len * 2, delta=orig_len * 0.1)

        # Identity (ratio 1.0) -> unchanged
        same = pitch_shift_segment(orig, ratio=1.0)
        self.assertEqual(len(same), orig_len)

    def test_synthesize_point_sources_track(self):
        """Verify point source track synthesis with multiple physical samples."""
        events = [
            {"time": 0.1, "duration": 0.3, "frequency": 440.0, "velocity": 0.9, "pan": -0.5, "sample": "crackle"},
            {"time": 0.5, "duration": 0.3, "frequency": 880.0, "velocity": 0.7, "pan": 0.5, "sample": "whoosh"},
        ]
        track = synthesize_point_sources_track(events, total_duration=1.2, sample_rate=DEFAULT_SAMPLE_RATE)
        self.assertEqual(track.ndim, 2)
        self.assertEqual(track.shape[1], 2)
        self.assertEqual(track.shape[0], int(DEFAULT_SAMPLE_RATE * 1.2))
        self.assertGreater(np.max(np.abs(track)), 0.1)

    def test_empty_point_source_events(self):
        """Verify empty point source events return silent stereo array."""
        track = synthesize_point_sources_track([], total_duration=1.0, sample_rate=DEFAULT_SAMPLE_RATE)
        self.assertEqual(track.shape, (int(DEFAULT_SAMPLE_RATE * 1.0), 2))
        self.assertTrue(np.all(track == 0.0))

    def test_resolve_point_source_sample_name_metadata(self):
        """Verify sample name resolution from source metadata tags."""
        ev_ice = {"source_metadata": {"tag": "ice_sheet"}}
        ev_wind = {"source_metadata": {"feature_type": "wind_gust"}}
        ev_ping = {"instrumentId": "beacon_ping"}
        self.assertEqual(resolve_point_source_sample_name(ev_ice), "crackle")
        self.assertEqual(resolve_point_source_sample_name(ev_wind), "whoosh")
        self.assertEqual(resolve_point_source_sample_name(ev_ping), "ping")


class TestMixingAndHeadroom(unittest.TestCase):
    """Test suite for combining tracks, gain staging, and master headroom."""

    def setUp(self):
        self.sr = 44100
        t = np.linspace(0, 1.0, self.sr, endpoint=False)
        sig1 = (0.5 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)
        sig2 = (0.5 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
        self.diffuse = np.column_stack([sig1, sig1])
        self.point = np.column_stack([sig2, sig2])

    def test_mix_tracks_normalization(self):
        """Verify that normalize=True scales master peak to target_peak (0.95)."""
        mixed = mix_tracks(self.diffuse, self.point, normalize=True, target_peak=0.95)
        peak = np.max(np.abs(mixed))
        self.assertAlmostEqual(peak, 0.95, places=3)

    def test_mix_tracks_gain_control(self):
        """Verify that diffuse_gain and point_source_gain affect relative amplitudes."""
        # Diffuse only
        mix_d = mix_tracks(self.diffuse, self.point, diffuse_gain=1.0, point_source_gain=0.0, normalize=False)
        self.assertAlmostEqual(np.max(np.abs(mix_d)), 0.5, places=3)

        # Point only
        mix_p = mix_tracks(self.diffuse, self.point, diffuse_gain=0.0, point_source_gain=0.8, normalize=False)
        self.assertAlmostEqual(np.max(np.abs(mix_p)), 0.4, places=3)

    def test_mix_tracks_unequal_lengths(self):
        """Verify that tracks of different lengths are zero-padded to align perfectly."""
        short_track = self.point[: self.sr // 2]
        mixed = mix_tracks(self.diffuse, short_track, normalize=False)
        self.assertEqual(mixed.shape[0], self.diffuse.shape[0])


class TestSynthesizeWavExport(unittest.TestCase):
    """Test suite for synthesize_wav API and soundfile export."""

    def setUp(self):
        self.events = [
            {
                "time": 0.0,
                "duration": 0.5,
                "frequency": 220.0,
                "amplitude": 0.7,
                "pan": -0.3,
                "layer": "diffuse",
                "instrument": "diffuse_pad",
            },
            {
                "time": 0.3,
                "duration": 0.4,
                "frequency": 440.0,
                "velocity": 0.85,
                "pan": 0.4,
                "layer": "point_source",
                "sample": "pluck",
            },
            {
                "time": 0.6,
                "duration": 0.3,
                "frequency": 660.0,
                "velocity": 0.9,
                "pan": 0.0,
                "layer": "point_source",
                "sample": "crackle",
            },
        ]

    def test_synthesize_wav_to_file(self):
        """Verify that synthesize_wav exports a valid 16-bit stereo WAV readable by soundfile."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name

        try:
            res_path = synthesize_wav(self.events, tmp_path)
            self.assertEqual(str(res_path), tmp_path)
            self.assertTrue(os.path.exists(tmp_path))

            info = sf.info(tmp_path)
            self.assertEqual(info.samplerate, DEFAULT_SAMPLE_RATE)
            self.assertEqual(info.channels, 2)
            self.assertEqual(info.subtype, "PCM_16")
            self.assertGreaterEqual(info.duration, 0.9)

            data, sr = sf.read(tmp_path)
            self.assertEqual(sr, DEFAULT_SAMPLE_RATE)
            self.assertEqual(data.ndim, 2)
            self.assertGreater(np.max(np.abs(data)), 0.5)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_synthesize_wav_return_details(self):
        """Verify return_details=True returns SynthesisResult object."""
        result = synthesize_wav(self.events, output_path=None, return_details=True)
        self.assertIsInstance(result, SynthesisResult)
        self.assertIsInstance(result.mixed_audio, np.ndarray)
        self.assertIsInstance(result.diffuse_track, np.ndarray)
        self.assertIsInstance(result.point_source_track, np.ndarray)
        self.assertGreater(result.duration_seconds, 0.5)
        self.assertEqual(result.sample_rate, DEFAULT_SAMPLE_RATE)

    def test_synthesize_wav_in_memory_bytesio(self):
        """Verify synthesizing directly into an in-memory BytesIO stream."""
        bio = io.BytesIO()
        synthesize_wav(self.events, output_path=bio)
        bio.seek(0)
        data, sr = sf.read(bio)
        self.assertEqual(sr, DEFAULT_SAMPLE_RATE)
        self.assertEqual(data.ndim, 2)
        self.assertGreater(len(data), 0)

    def test_synthesize_wav_empty_events(self):
        """Verify synthesizing empty events generates a valid silent WAV without error."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name

        try:
            synthesize_wav([], tmp_path, duration=0.5)
            self.assertTrue(os.path.exists(tmp_path))
            info = sf.info(tmp_path)
            self.assertEqual(info.channels, 2)
            self.assertAlmostEqual(info.duration, 0.5, places=2)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_synthesize_wav_custom_sample_rates(self):
        """Verify custom sample rate support (22050 Hz and 48000 Hz)."""
        for target_sr in (22050, 48000):
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_path = f.name
            try:
                synthesize_wav(self.events, tmp_path, sample_rate=target_sr, duration=0.8)
                info = sf.info(tmp_path)
                self.assertEqual(info.samplerate, target_sr)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)


class TestJsonTimelineExport(unittest.TestCase):
    """Test suite for Tone.js frontend JSON blueprint timeline export."""

    def setUp(self):
        self.events = [
            {
                "time": 0.25,
                "duration": 0.1,
                "frequency": 440.0,
                "pitch": 440.0,
                "velocity": 0.8,
                "pan": -0.5,
                "instrumentId": "diffuse_pad",
                "x": 20.0,
                "y": 30.0,
            },
            {
                "time": 0.75,
                "duration": 0.15,
                "frequency": 880.0,
                "pitch": 880.0,
                "velocity": 0.95,
                "pan": 0.5,
                "instrumentId": "point_source_pluck",
                "spatialPosition": {"x": 50.0, "y": 60.0},
            },
        ]

    def test_export_json_timeline_structure(self):
        """Verify exported JSON blueprint contains metadata and event objects with millisecond timings."""
        blueprint = export_json_timeline(
            self.events,
            metadata={"scaleName": "dorian", "tuningSystem": "12-EDO"},
            scan_geometry="radar_sweep",
        )
        self.assertIn("metadata", blueprint)
        self.assertIn("events", blueprint)

        meta = blueprint["metadata"]
        self.assertEqual(meta["scaleName"], "dorian")
        self.assertEqual(meta["tuningSystem"], "12-EDO")
        self.assertEqual(meta["scanGeometry"], "radar_sweep")
        self.assertEqual(meta["totalEvents"], 2)

        ev0 = blueprint["events"][0]
        self.assertAlmostEqual(ev0["time"], 250.0, places=1)
        self.assertAlmostEqual(ev0["duration"], 100.0, places=1)
        self.assertAlmostEqual(ev0["pitch"], 440.0, places=1)
        self.assertAlmostEqual(ev0["velocity"], 0.8, places=2)
        self.assertAlmostEqual(ev0["pan"], -0.5, places=2)
        self.assertEqual(ev0["instrumentId"], "diffuse_pad")
        self.assertIn("spatialPosition", ev0)

    def test_export_json_timeline_file_io(self):
        """Verify export_json_timeline writes valid, deserializable JSON to disk."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_json = f.name

        try:
            export_json_timeline(self.events, output_path=tmp_json)
            self.assertTrue(os.path.exists(tmp_json))

            with open(tmp_json, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            self.assertIn("metadata", loaded)
            self.assertIn("events", loaded)
            self.assertEqual(len(loaded["events"]), 2)
        finally:
            if os.path.exists(tmp_json):
                os.unlink(tmp_json)

    def test_export_json_timeline_positional_signature(self):
        """Verify export_json_timeline(audio_events, metadata, output_path) works with exact positional arguments."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_json = f.name

        try:
            meta = {
                "scaleName": "pelog",
                "tuningSystem": "just_intonation",
                "scanGeometry": "radial_expansion",
            }
            # Positional call: audio_events, metadata, output_path
            res = export_json_timeline(self.events, meta, tmp_json)

            self.assertIsInstance(res, dict)
            self.assertTrue(os.path.exists(tmp_json))

            with open(tmp_json, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.assertEqual(data["metadata"]["scaleName"], "pelog")
            self.assertEqual(data["metadata"]["tuningSystem"], "just_intonation")
            self.assertEqual(data["metadata"]["scanGeometry"], "radial_expansion")
            self.assertEqual(len(data["events"]), 2)
        finally:
            if os.path.exists(tmp_json):
                os.unlink(tmp_json)

    def test_export_json_timeline_path_as_second_positional_arg(self):
        """Verify passing output_path as 2nd positional argument works seamlessly."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_json = f.name

        try:
            export_json_timeline(self.events, tmp_json)
            self.assertTrue(os.path.exists(tmp_json))
            with open(tmp_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("metadata", data)
            self.assertIn("events", data)
        finally:
            if os.path.exists(tmp_json):
                os.unlink(tmp_json)

    def test_export_json_timeline_spatial_coordinates_and_optionality(self):
        """Verify spatialPosition is properly formatted when present and omitted when absent."""
        events_mixed = [
            # Event 1: Has explicit spatialPosition dict
            {
                "time_ms": 100.0,
                "duration_ms": 50.0,
                "pitch": 440.0,
                "velocity": 0.7,
                "pan": 0.0,
                "instrumentId": "diffuse_pad",
                "spatialPosition": {"x": 12.34, "y": 56.78, "z": 1.0},
            },
            # Event 2: Has top-level (x, y) coordinates
            {
                "time_ms": 200.0,
                "duration_ms": 60.0,
                "pitch": 550.0,
                "velocity": 0.8,
                "pan": 0.5,
                "instrumentId": "point_source_pluck",
                "x": 30.5,
                "y": 40.5,
            },
            # Event 3: Has tuple spatialPosition
            {
                "time_ms": 300.0,
                "duration_ms": 70.0,
                "pitch": 660.0,
                "velocity": 0.9,
                "pan": -0.5,
                "instrumentId": "ping",
                "spatialPosition": (75.2, 85.3),
            },
            # Event 4: Pure non-spatial audio event (e.g. background master drone)
            {
                "time_ms": 400.0,
                "duration_ms": 80.0,
                "pitch": 220.0,
                "velocity": 0.5,
                "pan": 0.0,
                "instrumentId": "sub_bass",
            },
        ]

        blueprint = export_json_timeline(events_mixed)
        evs = blueprint["events"]
        self.assertEqual(len(evs), 4)

        # Ev 1: Dict spatial coordinates
        self.assertIn("spatialPosition", evs[0])
        self.assertAlmostEqual(evs[0]["spatialPosition"]["x"], 12.34)
        self.assertAlmostEqual(evs[0]["spatialPosition"]["y"], 56.78)
        self.assertAlmostEqual(evs[0]["spatialPosition"]["z"], 1.0)

        # Ev 2: Top-level coordinates converted
        self.assertIn("spatialPosition", evs[1])
        self.assertAlmostEqual(evs[1]["spatialPosition"]["x"], 30.5)
        self.assertAlmostEqual(evs[1]["spatialPosition"]["y"], 40.5)

        # Ev 3: Tuple coordinates converted
        self.assertIn("spatialPosition", evs[2])
        self.assertAlmostEqual(evs[2]["spatialPosition"]["x"], 75.2)
        self.assertAlmostEqual(evs[2]["spatialPosition"]["y"], 85.3)

        # Ev 4: Omitted when no spatial coordinates exist
        self.assertNotIn("spatialPosition", evs[3])

        # Metadata records spatial audio capability
        self.assertTrue(blueprint["metadata"]["spatialAudio"]["supported"])
        self.assertTrue(blueprint["metadata"]["spatialAudio"]["hasSpatialPositions"])

    def test_export_json_timeline_velocity_and_pitch_normalization(self):
        """Verify velocity clipping/normalization (e.g. MIDI 0-127) and pitch formatting."""
        test_events = [
            {
                "time": 0.1,
                "duration": 0.05,
                "pitch": 69,  # MIDI A4
                "midi_note": 69,
                "frequency": 440.0,
                "velocity": 127.0,  # MIDI max velocity -> normalized to 1.0
                "pan": 1.5,  # Exceeds +1.0 -> clipped to 1.0
                "instrumentId": "lead",
            },
            {
                "time": 0.2,
                "duration": 0.05,
                "pitch": 261.63,
                "velocity": -0.5,  # Below 0.0 -> clipped to 0.0
                "pan": -2.0,  # Below -1.0 -> clipped to -1.0
                "instrumentId": "bass",
            },
        ]

        blueprint = export_json_timeline(test_events)
        ev0 = blueprint["events"][0]
        self.assertAlmostEqual(ev0["velocity"], 1.0, places=3)
        self.assertAlmostEqual(ev0["pan"], 1.0, places=3)
        self.assertEqual(ev0["pitch"], 69.0)
        self.assertEqual(ev0["midiNote"], 69)
        self.assertAlmostEqual(ev0["frequency"], 440.0)

        ev1 = blueprint["events"][1]
        self.assertAlmostEqual(ev1["velocity"], 0.0, places=3)
        self.assertAlmostEqual(ev1["pan"], -1.0, places=3)

    def test_export_json_timeline_tonejs_structure(self):
        """Verify Tone.js frontend requirements: ms timings, Tone.Part second helpers, chronologic sort."""
        unsorted_events = [
            {"time_ms": 500.0, "duration_ms": 100.0, "pitch": 600.0, "instrumentId": "inst2"},
            {"time_ms": 100.0, "duration_ms": 200.0, "pitch": 300.0, "instrumentId": "inst1"},
        ]

        blueprint = export_json_timeline(unsorted_events)
        events = blueprint["events"]

        # Chronologically sorted by time
        self.assertLess(events[0]["time"], events[1]["time"])
        self.assertEqual(events[0]["time"], 100.0)
        self.assertEqual(events[1]["time"], 500.0)

        # Tone.js seconds helpers for native Transport scheduling
        self.assertAlmostEqual(events[0]["timeSeconds"], 0.1)
        self.assertAlmostEqual(events[0]["durationSeconds"], 0.2)
        self.assertAlmostEqual(events[1]["timeSeconds"], 0.5)
        self.assertAlmostEqual(events[1]["durationSeconds"], 0.1)

    def test_export_json_timeline_audio_event_list_integration(self):
        """Verify export_json_timeline directly handles AudioEventList produced by map_parameters."""
        w, h = 40, 30
        scalar = np.ones((h, w), dtype=np.float32) * 0.7
        scan_path = generate_scan_path("horizontal_sweep", w, h, duration_seconds=1.0, num_steps=10)
        events = map_parameters(scan_path, scalar, scale_name="c_major_pentatonic")

        blueprint = export_json_timeline(events)
        self.assertIn("metadata", blueprint)
        self.assertIn("events", blueprint)
        self.assertEqual(blueprint["metadata"]["scaleName"], "c_major_pentatonic")
        self.assertEqual(blueprint["metadata"]["scanGeometry"], "horizontal_sweep")
        self.assertGreater(blueprint["metadata"]["totalEvents"], 0)
        self.assertGreater(len(blueprint["events"]), 0)

        first_event = blueprint["events"][0]
        self.assertIn("time", first_event)
        self.assertIn("duration", first_event)
        self.assertIn("pitch", first_event)
        self.assertIn("velocity", first_event)
        self.assertIn("pan", first_event)
        self.assertIn("instrumentId", first_event)

    def test_export_json_timeline_empty_input(self):
        """Verify export_json_timeline gracefully handles empty or None input."""
        res_empty = export_json_timeline([])
        self.assertEqual(res_empty["metadata"]["totalEvents"], 0)
        self.assertEqual(res_empty["events"], [])

        res_none = export_json_timeline(None)
        self.assertEqual(res_none["metadata"]["totalEvents"], 0)
        self.assertEqual(res_none["events"], [])


class TestEndToEndSonificationIntegration(unittest.TestCase):
    """End-to-end integration test connecting Scanner, Morphology, and Synthesizer."""

    def test_horizontal_sweep_full_pipeline(self):
        """Run complete sonification: scan path -> parameter mapping -> WAV synthesis."""
        w, h = 60, 40
        duration = 1.5
        image = np.zeros((h, w), dtype=np.float32)
        image[15:25, 20:40] = 0.85

        point_sources = [
            {"x": 25.0, "y": 20.0, "flux": 0.95, "radius": 4.0, "sample": "crackle"},
            {"x": 35.0, "y": 22.0, "flux": 0.80, "radius": 3.0, "sample": "whoosh"},
        ]

        scan_path = generate_scan_path("horizontal_sweep", w, h, duration, num_steps=20, samples_per_step=15)
        events = map_parameters(scan_path, image, point_sources=point_sources, scale_name="c_major_pentatonic")

        self.assertIsInstance(events, AudioEventList)
        self.assertGreater(len(events["diffuse_events"]), 0)
        self.assertEqual(len(events["point_source_events"]), 2)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_wav = f.name

        try:
            synthesize_wav(events, output_path=tmp_wav)
            self.assertTrue(os.path.exists(tmp_wav))

            info = sf.info(tmp_wav)
            self.assertEqual(info.channels, 2)
            self.assertEqual(info.samplerate, DEFAULT_SAMPLE_RATE)
            self.assertAlmostEqual(info.duration, duration, delta=0.2)

            data, _ = sf.read(tmp_wav)
            self.assertGreater(np.max(np.abs(data)), 0.5)
        finally:
            if os.path.exists(tmp_wav):
                os.unlink(tmp_wav)

    def test_radar_sweep_pipeline(self):
        """Run radar sweep playhead pipeline into WAV synthesis."""
        w, h = 50, 50
        duration = 1.0
        image = np.zeros((h, w), dtype=np.float32)
        image[20:30, 20:30] = 0.9

        scan_path = generate_scan_path("radar_sweep", w, h, duration, num_steps=15, samples_per_step=10)
        events = map_parameters(scan_path, image, scale_name="major")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_wav = f.name

        try:
            synthesize_wav(events, output_path=tmp_wav, diffuse_waveform="sawtooth")
            self.assertTrue(os.path.exists(tmp_wav))
            info = sf.info(tmp_wav)
            self.assertEqual(info.channels, 2)
        finally:
            if os.path.exists(tmp_wav):
                os.unlink(tmp_wav)


if __name__ == "__main__":
    unittest.main()
