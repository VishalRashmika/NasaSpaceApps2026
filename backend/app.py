"""
The Earth Jukebox - NASA Earth Information Center (EIC) Sonification Web Application.

Streamlit UI exposing the fundamental duality between:
1. Scientific Integrity (Raw Data): Inharmonic timbres, continuous unquantized microtones,
   raw uncompressed dynamic range, and full unthrottled polyphony.
2. Artistic Expression (Musicality): Rich harmonic analog pads, scale-quantized notes,
   arcsinh dynamic range compression with noise-floor gating, and polyphony throttling.
"""

import io
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np
import soundfile as sf
import streamlit as st

# Configure backend imports
from backend.morphology import detect_point_sources, separate_features
from backend.pipeline import (
    ColorbarNotFoundError,
    PipelineError,
    extract_data,
    load_image,
    preprocess_image,
)
from backend.scanner import (
    MUSICAL_SCALES,
    ScanGeometry,
    generate_scan_path,
    map_parameters,
)
from backend.synthesizer import (
    DEFAULT_SAMPLE_RATE,
    export_json_timeline,
    synthesize_wav,
)

logger = logging.getLogger("earth_jukebox.app")


def setup_ui() -> None:
    """Initialize Streamlit page configuration and styling."""
    st.set_page_config(
        page_title="The Earth Jukebox | NASA EIC Sonification",
        page_icon="🌍",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Custom Styling for Dark Theme & NASA Chandra Aesthetic
    st.markdown(
        """
        <style>
        .main-title {
            font-size: 2.2rem;
            font-weight: 800;
            background: linear-gradient(90deg, #38bdf8, #818cf8, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.2rem;
        }
        .sub-title {
            color: #94a3b8;
            font-size: 1.05rem;
            margin-bottom: 1.5rem;
        }
        .hud-card {
            background: rgba(30, 41, 59, 0.7);
            border: 1px solid #334155;
            border-radius: 10px;
            padding: 1rem;
            margin-bottom: 1rem;
        }
        .metric-badge {
            display: inline-block;
            padding: 0.25rem 0.6rem;
            border-radius: 6px;
            font-weight: 600;
            font-size: 0.85rem;
        }
        .science-badge {
            background-color: #0284c7;
            color: white;
        }
        .music-badge {
            background-color: #9333ea;
            color: white;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def generate_sample_image(sample_type: str = "temperature") -> np.ndarray:
    """
    Generate synthetic NASA-style scientific visualization with colorbar
    for instant out-of-the-box demonstration.
    """
    h, w = 300, 400
    canvas = np.zeros((h, w, 3), dtype=np.uint8)

    if sample_type == "radar_cyclone":
        # Concentric swirling vortex
        cy, cx = h // 2, (w - 60) // 2
        y, x = np.ogrid[:h, : w - 60]
        r = np.hypot(x - cx, y - cy)
        theta = np.arctan2(y - cy, x - cx)
        spiral = (np.sin(r / 12.0 - theta * 2.0) + 1.0) * 0.5
        vortex = np.exp(-r / 70.0) * spiral
        scalar_u8 = (np.clip(vortex, 0.0, 1.0) * 255.0).astype(np.uint8)
        data_bgr = cv2.applyColorMap(scalar_u8, cv2.COLORMAP_PLASMA)
        canvas[:, : w - 60] = data_bgr
        # Colorbar
        cb_h = 240
        cb_w = 16
        cb_x = w - 40
        cb_y = 30
        grad = np.linspace(255, 0, cb_h, dtype=np.uint8).reshape((cb_h, 1))
        cb_bgr = cv2.applyColorMap(grad, cv2.COLORMAP_PLASMA)
        cb_bgr = cv2.resize(cb_bgr, (cb_w, cb_h), interpolation=cv2.INTER_NEAREST)
        canvas[cb_y : cb_y + cb_h, cb_x : cb_x + cb_w] = cb_bgr
    else:
        # Default: Sea Surface Temperature / Atmospheric gradient
        data_w = w - 60
        y, x = np.mgrid[0:h, 0:data_w]
        grad = (x / float(data_w) * 0.6 + y / float(h) * 0.4).astype(np.float32)
        # Add localized hotspot (point source)
        hotspot = np.exp(-((x - data_w * 0.7) ** 2 + (y - h * 0.3) ** 2) / 400.0)
        grad = np.clip(grad + hotspot * 0.4, 0.0, 1.0)
        scalar_u8 = (grad * 255.0).astype(np.uint8)
        data_bgr = cv2.applyColorMap(scalar_u8, cv2.COLORMAP_JET)
        canvas[:, :data_w] = data_bgr
        # Colorbar on right
        cb_h = 240
        cb_w = 16
        cb_x = w - 40
        cb_y = 30
        cb_grad = np.linspace(255, 0, cb_h, dtype=np.uint8).reshape((cb_h, 1))
        cb_bgr = cv2.applyColorMap(cb_grad, cv2.COLORMAP_JET)
        cb_bgr = cv2.resize(cb_bgr, (cb_w, cb_h), interpolation=cv2.INTER_NEAREST)
        canvas[cb_y : cb_y + cb_h, cb_x : cb_x + cb_w] = cb_bgr

    return canvas


def compute_duality_parameters(slider_val: int) -> Dict[str, Any]:
    """
    Translate the Science vs. Music slider (0 to 100) into acoustic & mathematical parameters.

    Slider semantics:
    - 0 (Science): Inharmonic timbres, continuous unquantized microtonal frequencies,
                   raw dynamic range (linear, 0% noise gate), unlimited polyphony.
    - 100 (Music): Rich warm pad timbres, fully quantized musical scale notes,
                   arcsinh dynamic range compression (10% noise gate), throttled polyphony (top voices).
    - 1-99: Smooth interpolation across the duality continuum.
    """
    alpha = float(slider_val) / 100.0

    # 1. Scale Quantization
    quantize_notes = (slider_val >= 25)

    # 2. Dynamic Range Compression & Noise-Floor Gating
    if slider_val == 0:
        compression_method = "linear"
        compression_alpha = 1.0
        noise_floor = 0.0
    else:
        compression_method = "arcsinh"
        compression_alpha = max(1.0, alpha * 10.0)
        noise_floor = alpha * 0.10

    # 3. Acoustic Timbre / Waveform
    if slider_val < 35:
        diffuse_waveform = "inharmonic"
        point_source_instrument = "ping"
        timbre_label = "Inharmonic (Metallic Partials)"
    elif slider_val < 70:
        diffuse_waveform = "blend"
        point_source_instrument = "pluck"
        timbre_label = "Hybrid Blend (Sine + Sawtooth)"
    else:
        diffuse_waveform = "blend"
        point_source_instrument = "pluck"
        timbre_label = "Rich Pad (Harmonic Warmth)"

    # 4. Polyphony Throttling & Voice Consolidation
    if slider_val == 0:
        max_polyphony = None
        consolidate_notes = False
        poly_label = "Unlimited (Raw Data Voices)"
    elif slider_val < 40:
        max_polyphony = 16
        consolidate_notes = False
        poly_label = "High Polyphony (16 voices/step)"
    elif slider_val < 75:
        max_polyphony = 8
        consolidate_notes = True
        poly_label = "Moderate Throttling (8 voices/step)"
    else:
        max_polyphony = 4
        consolidate_notes = True
        poly_label = "Strict Throttling (4 voices/step, Consolidated)"

    return {
        "alpha": alpha,
        "quantize_notes": quantize_notes,
        "compression_method": compression_method,
        "compression_alpha": compression_alpha,
        "noise_floor": noise_floor,
        "diffuse_waveform": diffuse_waveform,
        "point_source_instrument": point_source_instrument,
        "timbre_label": timbre_label,
        "max_polyphony": max_polyphony,
        "consolidate_notes": consolidate_notes,
        "poly_label": poly_label,
    }


def main() -> None:
    # Initialize Page Layout & CSS
    setup_ui()

    # Header Banner
    st.markdown('<div class="main-title">🎵 The Earth Jukebox</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-title">NASA Earth Information Center (EIC) Sonification Engine — '
        'Balancing Scientific Integrity with Artistic Expression</div>',
        unsafe_allow_html=True,
    )

    # -------------------------------------------------------------------------
    # Sidebar Controls
    # -------------------------------------------------------------------------
    st.sidebar.header("⚙️ Configuration Controls")

    # 1. File Uploader for NASA EIC Image
    st.sidebar.subheader("1. Input Visualization")
    uploaded_file = st.sidebar.file_uploader(
        "Upload NASA EIC Image",
        type=["png", "jpg", "jpeg", "tif", "tiff", "webp"],
        help="Upload a NASA Earth Information Center visualization (e.g., Sea Surface Temperature, Ozone, Wildfire plume).",
    )

    use_sample = False
    sample_type = "temperature"
    if uploaded_file is None:
        use_sample = st.sidebar.checkbox(
            "Use Sample EIC Visualization",
            value=True,
            help="Toggle synthetic NASA visualization when no file is uploaded.",
        )
        if use_sample:
            sample_type = st.sidebar.selectbox(
                "Sample Dataset Preset",
                options=["temperature", "radar_cyclone"],
                format_func=lambda s: "Sea Surface Temperature (Cartesian Gradient)" if s == "temperature" else "Atmospheric Cyclone (Polar Vortex)",
            )

    # 2. Dropdowns for Scan Geometry, Musical Scale, and Data Extraction Method
    st.sidebar.subheader("2. Engine Parameters")

    # Scan Geometry Dropdown
    geometry_options = {
        "horizontal_sweep": "Horizontal Sweep (Left-to-Right Cartesian: Y=Pitch, X=Time/Pan)",
        "vertical_sweep": "Vertical Sweep (Top-to-Bottom Cartesian: Y=Pitch, X=Pan)",
        "radar_sweep": "Radar Sweep (Clockwise Polar Ray: θ=Time/Pan, Radius=Pitch)",
        "radial_expansion": "Radial Expansion (Concentric Ripple: Radius=Time, Band=Register)",
    }
    selected_geometry = st.sidebar.selectbox(
        "Scan Geometry",
        options=list(geometry_options.keys()),
        format_func=lambda k: geometry_options[k],
        index=0 if sample_type != "radar_cyclone" else 2,
        help="Playhead trajectory mirroring NASA Chandra sonifications.",
    )

    # Musical Scale Dropdown
    scale_names = [
        "c_major_pentatonic",
        "minor_pentatonic",
        "dorian",
        "lydian",
        "mixolydian",
        "natural_minor",
        "harmonic_minor",
        "chromatic",
        "blues",
        "whole_tone",
        "hirajoshi",
        "pelog",
        "slendro",
    ]
    scale_labels = {
        "c_major_pentatonic": "C Major Pentatonic (Harmonic / Consonant)",
        "minor_pentatonic": "C Minor Pentatonic (Ambient / Bluesy)",
        "dorian": "Dorian Mode (Atmospheric / Floating)",
        "lydian": "Lydian Mode (Cosmic / Ethereal)",
        "mixolydian": "Mixolydian Mode (Warm / Open)",
        "natural_minor": "Natural Minor (Aeolian / Melancholic)",
        "harmonic_minor": "Harmonic Minor (Exotic / Dramatic)",
        "chromatic": "Chromatic (All 12 Semitones)",
        "blues": "Blues Scale (Expressive / Earthy)",
        "whole_tone": "Whole Tone (Dreamlike / Unresolved)",
        "hirajoshi": "Hirajoshi (Japanese Pentatonic)",
        "pelog": "Pelog (Javanese Gamelan)",
        "slendro": "Slendro (Indonesian Equitonic)",
    }
    selected_scale = st.sidebar.selectbox(
        "Musical Scale",
        options=scale_names,
        format_func=lambda k: scale_labels.get(k, k),
        index=0,
        help="Musical tuning framework used to quantize frequencies when musicality is enabled.",
    )

    # Data Extraction Method Dropdown
    method_options = {
        "auto": "Auto (Colorbar Parsing with VQ Fallback)",
        "colorbar": "Colorbar Parsing (Direct RGB-to-Scalar LUT)",
        "vq": "Vector Quantization (Artist Palette Nearest-Neighbor)",
    }
    selected_method = st.sidebar.selectbox(
        "Data Extraction Method",
        options=list(method_options.keys()),
        format_func=lambda k: method_options[k],
        index=0,
        help="Dual-pathway quantitative data recovery architecture.",
    )

    colormap_fallback = "jet"
    if selected_method in ("auto", "vq"):
        colormap_fallback = st.sidebar.selectbox(
            "VQ Colormap Reference",
            options=["jet", "plasma", "viridis", "inferno", "magma", "cividis", "coolwarm"],
            index=0 if sample_type != "radar_cyclone" else 1,
            help="Theoretical colormap for Vector Quantization inverse palette lookup.",
        )

    # 3. "Science vs. Music" Slider (0 to 100)
    st.sidebar.subheader("3. Duality Control")
    science_vs_music = st.sidebar.slider(
        "Science vs. Music",
        min_value=0,
        max_value=100,
        value=50,
        step=1,
        help="Balance scientific fidelity (0 = inharmonic, raw dynamic range, microtonal) "
             "against artistic musicality (100 = quantized scales, rich timbres, polyphony throttling).",
    )

    # Dynamic HUD display for the slider
    duality = compute_duality_parameters(science_vs_music)

    if science_vs_music == 0:
        hud_text = "🔬 **Pure Science (0)**: Inharmonic timbres, continuous unquantized frequencies, raw linear dynamic range, unlimited polyphony."
        hud_badge = '<span class="metric-badge science-badge">100% Science / 0% Music</span>'
    elif science_vs_music == 100:
        hud_text = "🎨 **Pure Music (100)**: Rich warm pads, strict scale quantization, arcsinh dynamic compression (10% gate), throttled polyphony."
        hud_badge = '<span class="metric-badge music-badge">0% Science / 100% Music</span>'
    else:
        hud_text = f"⚖️ **Balanced Duality ({science_vs_music})**: {duality['timbre_label']} | {duality['poly_label']}."
        hud_badge = f'<span class="metric-badge" style="background:#475569; color:white;">Science: {100-science_vs_music}% | Music: {science_vs_music}%</span>'

    st.sidebar.markdown(hud_badge, unsafe_allow_html=True)
    st.sidebar.info(hud_text)

    # Audio synthesis duration & features
    with st.sidebar.expander("🛠️ Advanced Sonification Options", expanded=False):
        duration = st.slider("Audio Duration (seconds)", min_value=3.0, max_value=30.0, value=10.0, step=0.5)
        separate_morph = st.checkbox("Separate Morphology (Diffuse Pad + Point Hotspots)", value=True)
        detect_hotspots = st.checkbox("Detect Point Sources (Discrete Hotspots)", value=True)
        preprocess_clahe = st.checkbox("Apply CLAHE Contrast Preprocessing", value=False)

    # -------------------------------------------------------------------------
    # Image Ingestion & Main View
    # -------------------------------------------------------------------------
    image_bgr: Optional[np.ndarray] = None
    image_source_name = ""

    if uploaded_file is not None:
        file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
        image_bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        image_source_name = uploaded_file.name
    elif use_sample:
        image_bgr = generate_sample_image(sample_type)
        image_source_name = f"Sample: {sample_type}"

    col_img1, col_img2 = st.columns(2)

    with col_img1:
        st.subheader("📷 Input Scientific Visualization")
        if image_bgr is not None:
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            st.image(image_rgb, caption=f"Source: {image_source_name} ({image_bgr.shape[1]}x{image_bgr.shape[0]} px)", use_container_width=True)
        else:
            st.warning("Please upload a NASA EIC image or enable 'Use Sample EIC Visualization' in the sidebar.")

    # -------------------------------------------------------------------------
    # 4. Generate Button & Pipeline Execution
    # -------------------------------------------------------------------------
    st.markdown("---")
    gen_button = st.button("🚀 Generate Sonification & Timeline", type="primary", use_container_width=True)

    if gen_button:
        if image_bgr is None:
            st.error("No image available to process. Please upload an image or enable sample visualization.")
            return

        with st.spinner("Executing quantitative data recovery and synthesis pipeline..."):
            try:
                # Step 1: Quantitative Data Recovery (Dual-Pathway)
                scalar_array, ext_meta = extract_data(
                    image_path=image_bgr,
                    colormap_name=colormap_fallback,
                    method=selected_method,
                    return_metadata=True,
                )

                # Optional Preprocessing
                if preprocess_clahe:
                    scalar_array, _ = preprocess_image(scalar_array, return_metadata=True)

                # Step 2: Morphological Layer Separation
                diffuse_layer = scalar_array
                point_sources_list = []
                if separate_morph:
                    morph = separate_features(scalar_array, return_metadata=True)
                    diffuse_layer = morph.get("diffuse_layer", scalar_array)
                    if detect_hotspots:
                        point_sources_list = detect_point_sources(morph.get("point_source_layer", scalar_array))

                # Step 3: Scan Path Generation
                h_img, w_img = scalar_array.shape[:2]
                scan_path = generate_scan_path(
                    geometry_type=selected_geometry,
                    width=w_img,
                    height=h_img,
                    duration_seconds=duration,
                )

                # Step 4: Sonification Parameter Mapping with Science vs. Music duality
                audio_events = map_parameters(
                    scan_path=scan_path,
                    scalar_array=diffuse_layer,
                    point_sources=point_sources_list if point_sources_list else None,
                    scale_name=selected_scale,
                    noise_floor=duality["noise_floor"],
                    compression_method=duality["compression_method"],
                    compression_alpha=duality["compression_alpha"],
                    quantize_notes=duality["quantize_notes"],
                    max_polyphony=duality["max_polyphony"],
                    consolidate_notes=duality["consolidate_notes"],
                    diffuse_waveform=duality["diffuse_waveform"],
                    point_source_instrument=duality["point_source_instrument"],
                    scan_geometry=selected_geometry,
                )

                # Step 5: Audio Synthesis (WAV generation)
                wav_buffer = io.BytesIO()
                synthesize_wav(
                    audio_events=audio_events,
                    output_path=wav_buffer,
                    sample_rate=DEFAULT_SAMPLE_RATE,
                    diffuse_waveform=duality["diffuse_waveform"],
                    duration=duration,
                )
                wav_bytes = wav_buffer.getvalue()

                # Step 6: JSON Timeline Blueprint Export
                timeline_dict = export_json_timeline(
                    audio_events=audio_events,
                    scale_name=selected_scale,
                    scan_geometry=selected_geometry,
                    metadata={
                        "science_vs_music_slider": science_vs_music,
                        "duality_mode": "Pure Science" if science_vs_music == 0 else ("Pure Music" if science_vs_music == 100 else "Hybrid"),
                        "quantize_notes": duality["quantize_notes"],
                        "timbre": duality["timbre_label"],
                        "dynamic_range": f"{duality['compression_method']} (floor: {duality['noise_floor']:.2f})",
                        "polyphony": duality["poly_label"],
                        "extraction_method": ext_meta.get("method", selected_method),
                    },
                )
                timeline_json = json.dumps(timeline_dict, indent=2)

                # Store in session state for persistence
                st.session_state["scalar_array"] = scalar_array
                st.session_state["ext_meta"] = ext_meta
                st.session_state["wav_bytes"] = wav_bytes
                st.session_state["timeline_json"] = timeline_json
                st.session_state["audio_events"] = audio_events
                st.session_state["duality"] = duality

                st.success("Sonification successfully generated!")

            except ColorbarNotFoundError:
                st.error("No valid colorbar was detected in the visualization. Please select 'vq' or 'auto' extraction method.")
                return
            except PipelineError as p_err:
                st.error(f"Pipeline error during data recovery: {p_err}")
                return
            except Exception as exc:
                st.error(f"Unexpected error during sonification pipeline: {exc}")
                logger.exception("Pipeline execution failed")
                return

    # -------------------------------------------------------------------------
    # Display Results (Grayscale image, audio player, JSON download)
    # -------------------------------------------------------------------------
    if "scalar_array" in st.session_state:
        scalar = st.session_state["scalar_array"]
        ext_meta = st.session_state["ext_meta"]
        wav_bytes = st.session_state["wav_bytes"]
        timeline_json = st.session_state["timeline_json"]
        events = st.session_state["audio_events"]
        cur_duality = st.session_state["duality"]

        # Extracted Grayscale Scalar Field in Column 2
        with col_img2:
            st.subheader("🔬 Extracted Quantitative Scalar Array")
            # Map [0.0, 1.0] to uint8 grayscale for display
            gray_u8 = (np.clip(scalar, 0.0, 1.0) * 255.0).astype(np.uint8)
            method_used = ext_meta.get("method", "extracted")
            st.image(
                gray_u8,
                caption=f"Recovered Scalar Field [0.0, 1.0] via pathway: {method_used.upper()} | Range: [{scalar.min():.3f}, {scalar.max():.3f}]",
                use_container_width=True,
                clamp=True,
            )

        # Sonification Audio Player & Download Controls
        st.markdown("### 🎧 Sonification Audio & Timeline")
        col_aud1, col_aud2 = st.columns([3, 2])

        with col_aud1:
            st.audio(wav_bytes, format="audio/wav")
            st.download_button(
                label="🎵 Download Synthesized .WAV Audio",
                data=wav_bytes,
                file_name="nasa_eic_sonification.wav",
                mime="audio/wav",
                use_container_width=True,
            )

        with col_aud2:
            st.download_button(
                label="📥 Download JSON Timeline Blueprint",
                data=timeline_json,
                file_name="nasa_eic_timeline.json",
                mime="application/json",
                use_container_width=True,
            )

        # Metrics HUD
        st.markdown("### 📊 Sonification & Duality HUD")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Audio Events", len(events))
        m2.metric("Acoustic Timbre", cur_duality["timbre_label"].split(" ")[0])
        m3.metric("Quantization", "Scale Notes" if cur_duality["quantize_notes"] else "Continuous Microtones")
        m4.metric("Polyphony", cur_duality["poly_label"].split(" ")[0])

        with st.expander("🔍 View JSON Timeline Blueprint Preview", expanded=False):
            st.json(json.loads(timeline_json)[:15] if isinstance(json.loads(timeline_json), list) else {k: json.loads(timeline_json)[k] for k in list(json.loads(timeline_json).keys())[:4]})


if __name__ == "__main__":
    main()
