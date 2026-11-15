"""Filesystem-backed discovery and repository for dataset categories and examples (F-107)."""

from __future__ import annotations

import mimetypes
import re
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from earth_jukebox.application.ports import CategoryRepository, ColorbarDetector, ImageDecoder
from earth_jukebox.domain.errors import NotFoundError
from earth_jukebox.domain.models import (
    CategoryPredefinedConfig,
    CategorySoundMapping,
    ColorLUT,
    ColormapKind,
    DatasetCategory,
    ExampleImage,
    LegendSpec,
    Orientation,
    PixelBox,
    RecoveryMode,
    ScaleType,
    VariableCategory,
)
from earth_jukebox.infrastructure.vision.lut import extract_lut

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
LEGEND_FILENAMES = {"legend.png", "legend.jpg", "legend.jpeg"}


def _format_image_title(filename: str) -> str:
    """Produce a friendly readable title from an image filename."""
    stem = Path(filename).stem
    # Strip leading numbering like 01_, 02_
    cleaned = re.sub(r"^\d+_", "", stem)
    # Strip trailing print/debug markers
    cleaned = re.sub(r"(_print|\.00001_print|\.00420_print)$", "", cleaned)
    # Replace dashes and underscores with spaces
    cleaned = cleaned.replace("_", " ").replace("-", " ")
    # Clean up double spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.title() if cleaned else filename


def _parse_info_sections(text: str) -> tuple[str, str, str | None, str | None, str | None]:
    """Parse info.md markdown into (title, description, legend_info, sonification, pipeline)."""
    lines = text.splitlines()
    title = ""
    sections: dict[str, list[str]] = {}
    current_sec = "intro"
    sections[current_sec] = []

    for line in lines:
        m = re.match(r"^(#{1,2})\s+(.*)$", line)
        if m:
            heading = m.group(2).strip()
            if not title and m.group(1) == "#":
                title = heading
            current_sec = heading
            if current_sec not in sections:
                sections[current_sec] = []
        else:
            sections[current_sec].append(line)

    # Extract clean text per section
    sec_texts = {k: "\n".join(v).strip() for k, v in sections.items()}

    # Description: look for Overview or first substantive paragraph
    description = ""
    for sec_name, content in sec_texts.items():
        if re.search(r"overview|context|definition|data type", sec_name, re.IGNORECASE):
            # Take substantive paragraphs
            paras = [p.strip() for p in content.split("\n\n") if p.strip()]
            if paras:
                description = "\n\n".join(paras[:2])
                break

    if not description:
        # Fall back to intro or first long paragraph
        for p in text.split("\n\n"):
            p_clean = p.strip()
            if p_clean and not p_clean.startswith("#") and len(p_clean) > 30:
                description = p_clean
                break

    # Legend info
    legend_info: str | None = None
    for sec_name, content in sec_texts.items():
        if re.search(r"legend|color mapping|colorimetric", sec_name, re.IGNORECASE):
            legend_info = content
            break

    # Sonification concept
    sonification_concept: str | None = None
    for sec_name, content in sec_texts.items():
        if re.search(r"sonification|audio mapping|sound", sec_name, re.IGNORECASE):
            sonification_concept = content
            break

    # Processing pipeline
    pipeline_info: str | None = None
    for sec_name, content in sec_texts.items():
        if re.search(r"pipeline|processing suggestions|extraction", sec_name, re.IGNORECASE):
            pipeline_info = content
            break

    return title, description, legend_info, sonification_concept, pipeline_info


def _get_category_curation(
    cat_id: str, title: str
) -> tuple[CategoryPredefinedConfig, str, str, tuple[CategorySoundMapping, ...]]:
    """Return predefined config, sonification technique, description, and mapping table (F-108)."""
    lower = cat_id.lower()
    mappings: tuple[CategorySoundMapping, ...]
    if "temp" in lower:
        config = CategoryPredefinedConfig(
            label="Near-Surface Temperature (T2M)",
            units="°C",
            vmin=-40.0,
            vmax=40.0,
            kind=ColormapKind.DIVERGING,
            category=VariableCategory.TEMPERATURE,
            center=0.0,
            scale=ScaleType.LINEAR,
            orientation=Orientation.HORIZONTAL,
            low_at_start=True,
            instrument_family="strings",
            suggested_skin="neutral",
        )
        technique = "Thermal Tension & Pitch Contour"
        desc = (
            "Maps temperature values across the freezing baseline (0°C) to pitch and "
            "harmonic tension. Warm anomalies elevate pitch and trigger resonant bell "
            "accents; sub-zero regimes descend into deep bass registers with increased "
            "acoustic roughness, underpinned by a consonant harmonic drone."
        )
        mappings = (
            CategorySoundMapping(
                data_characteristic="Temperature Value (-40°C to +40°C)",
                sound_parameter="Musical Pitch (scale-quantized across 2 octaves)",
                technique=(
                    "Diverging scale centering: 0°C at central tonic (C4), warming ascends "
                    "to C5, freezing descends to C3"
                ),
                detail=(
                    "Quantized to 11 pentatonic pitch degrees (neutral skin) or 15 raga "
                    "degrees (Hindustani skin)."
                ),
            ),
            CategorySoundMapping(
                data_characteristic="Freezing Baseline (0°C)",
                sound_parameter="Consonant Harmonic Drone Bed (Tonic + Fifth)",
                technique=(
                    "Continuous harmonic anchor (C3 + G3) representing comfortable "
                    "temperate baseline"
                ),
                detail=(
                    "Drone brightness subtly tracks global mean temperature across valid map cells."
                ),
            ),
            CategorySoundMapping(
                data_characteristic=("Thermal Extremes (>+20°C heatwaves or <-20°C deep freeze)"),
                sound_parameter="Velocity Accent & Octave Bell Doubling (+12 semitones)",
                technique=(
                    "Top 5% deviation from center triggers +0.25 velocity boost and high- "
                    "register bell chime"
                ),
                detail=(
                    "Highlights severe thermal hazards and extreme heatwave zones with "
                    "clear acoustic emphasis."
                ),
            ),
            CategorySoundMapping(
                data_characteristic="Thermal Gradients & Weather Fronts",
                sound_parameter="Rhythmic Subdivision (1, 2, or 4 notes/beat) & Roughness",
                technique=(
                    "4-neighbour gradient percentiles (p50, p85) drive rhythmic density; "
                    "local gradient modulates timbre roughness"
                ),
                detail=(
                    "Smooth uniform temperatures produce steady quarter notes; sharp "
                    "frontal boundaries create rapid, gritty rhythmic bursts."
                ),
            ),
            CategorySoundMapping(
                data_characteristic="Global Thermal Variance",
                sound_parameter="Tempo (BPM 72 to 120)",
                technique=("Standard deviation of temperature field linearly scales sweep speed"),
                detail=(
                    "High global contrast accelerates playback tempo; stable global "
                    "temperatures result in a relaxed 72 BPM pace."
                ),
            ),
            CategorySoundMapping(
                data_characteristic="Hemispheric Latitude (North to South)",
                sound_parameter="5-Band Spatial Panning & Spectral Brightness",
                technique=(
                    "Arctic to Antarctic divided into 5 voice bands panned stereo left "
                    "(-0.6) to right (+0.6)"
                ),
                detail=(
                    "Allows listeners to spatially localize northern versus southern "
                    "temperature anomalies."
                ),
            ),
        )
        return config, technique, desc, mappings

    if "wind" in lower:
        config = CategoryPredefinedConfig(
            label="Near-Surface Wind Speed",
            units="m/s",
            vmin=0.0,
            vmax=40.0,
            kind=ColormapKind.SEQUENTIAL,
            category=VariableCategory.OCEAN,
            center=None,
            scale=ScaleType.LINEAR,
            orientation=Orientation.HORIZONTAL,
            low_at_start=True,
            instrument_family="pad",
            suggested_skin="neutral",
        )
        technique = "Fluid Aerodynamic Flow ('Ukusa Flow')"
        desc = (
            "Inspired by swift aerodynamic currents (the Ukusa Vannama), wind speeds are "
            "translated into sweeping synthesizer pads. Calm ocean breezes produce low, "
            "gentle tones; severe gale and hurricane force winds (>20 m/s) trigger rapid "
            "rhythmic pulses, heightened pitch, and resonant accent chimes."
        )
        mappings = (
            CategorySoundMapping(
                data_characteristic="Wind Velocity (0 to 40 m/s)",
                sound_parameter="Pitch Register & Filter Openness",
                technique=(
                    "Sequential scale quantization across 2 octaves from calm 0 m/s (C3) to "
                    "hurricane 40 m/s (C5)"
                ),
                detail=(
                    "Synthesizer pad with detuned saws opens acoustic lowpass filter as "
                    "velocity increases."
                ),
            ),
            CategorySoundMapping(
                data_characteristic="Storm & Hurricane Force Winds (>20 m/s)",
                sound_parameter="Velocity Boost & Bell Doubling",
                technique=(
                    "Extreme speed threshold (>95th percentile) triggers high-frequency "
                    "bell chimes and maximum volume"
                ),
                detail=(
                    "Immediately alerts the listener to severe cyclones and gale-force storm bands."
                ),
            ),
            CategorySoundMapping(
                data_characteristic="Storm Vorticity & Wind Shear Gradients",
                sound_parameter="Rhythmic Flutter Density (1/2/4 pulses/beat) & Roughness",
                technique=(
                    "Local spatial velocity shear triggers accelerated rhythmic "
                    "subdivisions and acoustic roughness"
                ),
                detail="Mimics fluttering drum cadences as storms organize and tighten.",
            ),
            CategorySoundMapping(
                data_characteristic="Global Atmospheric Energy",
                sound_parameter="Playback Tempo (BPM 72 to 120)",
                technique=(
                    "Global wind speed variance determines overall sweep speed across longitudes"
                ),
                detail=(
                    "Calm global conditions play at 72 BPM; energetic planetary storms "
                    "accelerate up to 120 BPM."
                ),
            ),
            CategorySoundMapping(
                data_characteristic="Wind Belts (Trade Winds to Southern Ocean)",
                sound_parameter="5 Voice Stereo Panning (Left to Right)",
                technique=(
                    "5 latitude bands map northern winds to left channel and massive "
                    "southern roaring forties to right channel"
                ),
                detail=(
                    "Binaurally separates northern trade winds from southern circumpolar vortex."
                ),
            ),
        )
        return config, technique, desc, mappings

    if "precip" in lower or "cloud" in lower:
        config = CategoryPredefinedConfig(
            label="Total Estimated Precipitation",
            units="mm",
            vmin=0.0,
            vmax=20.0,
            kind=ColormapKind.SEQUENTIAL,
            category=VariableCategory.PRECIPITATION,
            center=None,
            scale=ScaleType.LINEAR,
            orientation=Orientation.HORIZONTAL,
            low_at_start=True,
            instrument_family="pluck",
            suggested_skin="neutral",
        )
        technique = "Granular Rain Droplet Synthesis ('Uraga Flow')"
        desc = (
            "Translates particulate rainfall into Karplus-Strong physical plucked string "
            "impulses. Dry and light rain regions produce sparse, gentle droplet plucks; "
            "heavy downpours and atmospheric rivers (>15 mm) drive dense, accelerating "
            "rhythmic cascades with extreme accents representing flash flood risks."
        )
        mappings = (
            CategorySoundMapping(
                data_characteristic="Precipitation Rate (0 to 20 mm)",
                sound_parameter="Pluck Pitch Register & Impulse Energy",
                technique=(
                    "Physical Karplus-Strong string synthesis: higher rainfall rates "
                    "trigger higher pitch and sharper attack"
                ),
                detail=(
                    "Mimics the acoustic signature of individual falling raindrops and "
                    "precipitation intensity."
                ),
            ),
            CategorySoundMapping(
                data_characteristic="Heavy Downpours & Atmospheric Rivers (>15 mm)",
                sound_parameter="Extreme Velocity Accents & Octave Bell Doubling",
                technique=(
                    "Top rainfall percentiles trigger velocity boost (+0.25) and resonant "
                    "bell doubling"
                ),
                detail=("Acoustically signals extreme weather hazards and severe flood warnings."),
            ),
            CategorySoundMapping(
                data_characteristic="Precipitation Fronts & Cloud Boundaries",
                sound_parameter=("Rhythmic Droplet Density (1, 2, or 4 plucks/beat) & Roughness"),
                technique=(
                    "Local rain gradients drive rapid rhythmic subdivisions up to 4 plucks per beat"
                ),
                detail=(
                    "Light steady drizzles produce single beats; torrential cloud bursts "
                    "trigger rapid 4-note cascades."
                ),
            ),
            CategorySoundMapping(
                data_characteristic="Global Storm Distribution",
                sound_parameter="Tempo (BPM 72 to 120)",
                technique=(
                    "Standard deviation of precipitation across the globe modulates sweep pace"
                ),
                detail="Intense, widespread global precipitation systems accelerate playback.",
            ),
            CategorySoundMapping(
                data_characteristic="Intertropical Convergence & Storm Latitudes",
                sound_parameter="5-Band Stereo Separation",
                technique=(
                    "Pans northern storm tracks to stereo left and equatorial / southern "
                    "rains to center and right"
                ),
                detail="Spanning from North to South across 5 spatial voice bands.",
            ),
        )
        return config, technique, desc, mappings

    if "aerosol" in lower or "aerols" in lower:
        config = CategoryPredefinedConfig(
            label="Aerosol Optical Thickness by Particulate Type",
            units="AOD",
            vmin=0.0,
            vmax=5.0,
            kind=ColormapKind.SEQUENTIAL,
            category=VariableCategory.AEROSOL,
            center=None,
            scale=ScaleType.LINEAR,
            orientation=Orientation.HORIZONTAL,
            low_at_start=True,
            instrument_family="texture",
            suggested_skin="neutral",
        )
        technique = "Particulate Polyphony & Acoustic Roughness"
        desc = (
            "Treats atmospheric aerosol dispersion as band-limited noise textures and "
            "granular friction. As aerosol optical thickness and plume concentrations "
            "rise, the synthesis engine widens band-passed noise resonance with acoustic "
            "roughness, capturing the gritty, airborne quality of smoke, dust, and sea "
            "spray."
        )
        mappings = (
            CategorySoundMapping(
                data_characteristic="Aerosol Optical Thickness (0 to 5 AOD)",
                sound_parameter="Band-Passed Noise Center Frequency & Pitch",
                technique=(
                    "Texture instrument family: band-passed noise centered at quantized "
                    "scale pitches across 2 octaves"
                ),
                detail="Higher optical thickness drives higher resonant frequencies.",
            ),
            CategorySoundMapping(
                data_characteristic="Plume Fronts & Dense Smoke/Dust Edges",
                sound_parameter="Acoustic Roughness & Bandwidth Detuning",
                technique=(
                    "Local gradient directly modulates NoteEvent.roughness, widening noise "
                    "filter bandwidth"
                ),
                detail=(
                    "Translates sharp particulate plume borders into gritty acoustic friction."
                ),
            ),
            CategorySoundMapping(
                data_characteristic="Intense Wildfire & Dust Storm Cores",
                sound_parameter="Velocity Boost & Metallic Accent Double",
                technique=(
                    "AOD values in top 5% trigger velocity accents (+0.25) and bell doubling"
                ),
                detail="Highlights severe air quality and wildfire hazard centers.",
            ),
            CategorySoundMapping(
                data_characteristic="Plume Dispersion Dynamics",
                sound_parameter="Rhythmic Density (1/2/4 pulses/beat)",
                technique="Gradient thresholds (p50/p85) trigger rapid textural pulses",
                detail="Reflects the turbulent swirling of smoke and dust plumes.",
            ),
            CategorySoundMapping(
                data_characteristic="Cross-Continental Plume Transport (Latitude)",
                sound_parameter="5-Voice Stereo Panning",
                technique=(
                    "Maps northern wildfire smoke (left) versus southern agricultural "
                    "burning (right)"
                ),
                detail="Enables spatial tracking of trans-oceanic aerosol plumes.",
            ),
        )
        return config, technique, desc, mappings

    if "lightning" in lower:
        config = CategoryPredefinedConfig(
            label="Lightning Flash Events & Spatial Density",
            units="flashes/area",
            vmin=0.0,
            vmax=1.0,
            kind=ColormapKind.SEQUENTIAL,
            category=VariableCategory.PRECIPITATION,
            center=None,
            scale=ScaleType.LINEAR,
            orientation=Orientation.HORIZONTAL,
            low_at_start=True,
            instrument_family="pluck",
            suggested_skin="neutral",
        )
        technique = "Transient Point-Event & Micro-Percussive Triggering"
        desc = (
            "Because lightning consists of discrete, instantaneous electrical bursts "
            "rather than continuous fluid fields, this sonification uses micro- "
            "percussive transient plucks. Dark non-event ocean/land pixels remain "
            "completely silent; detected lightning flash clusters trigger crisp, dynamic "
            "percussive notes with spatial coordinates mapped to stereo azimuth and "
            "latitude."
        )
        mappings = (
            CategorySoundMapping(
                data_characteristic="Lightning Strike Event (Yellow Pixels vs. Dark Map)",
                sound_parameter="Micro-Percussive Note Trigger & Velocity",
                technique=(
                    "Luminance and color thresholding: detected flash bursts trigger crisp "
                    "transient plucks"
                ),
                detail=(
                    "Zero/background pixels emit silence (rest), preserving the discrete "
                    "nature of lightning."
                ),
            ),
            CategorySoundMapping(
                data_characteristic="Severe Thunderstorm Clusters (High Flash Density)",
                sound_parameter="Rhythmic Burst Density (up to 4 strikes/beat) & Bell Accents",
                technique=(
                    "Dense strike clusters trigger rapid 4-note rhythmic firing and octave "
                    "bell doubles"
                ),
                detail=(
                    "Evokes the accelerating tempo of storm cadences and rapid lightning strikes."
                ),
            ),
            CategorySoundMapping(
                data_characteristic="Null Activity (Dark Basemap)",
                sound_parameter="Acoustic Rest / Complete Silence",
                technique=(
                    "Unmasked data threshold (coverage < 0.25 / no event) generates silent rests"
                ),
                detail=(
                    "Ensures listeners only hear genuine electrical discharge events "
                    "without background noise."
                ),
            ),
            CategorySoundMapping(
                data_characteristic="Strike Longitude (Americas to Asia-Pacific)",
                sound_parameter="Time & 5-Voice Stereo Panning",
                technique="West-to-East time sweep combined with 5 latitude bands",
                detail=(
                    "Strikes in the Americas sound first on the left, moving eastward "
                    "across Africa and Indonesia."
                ),
            ),
        )
        return config, technique, desc, mappings

    if "hubble" in lower or "deep" in lower or "space" in lower:
        config = CategoryPredefinedConfig(
            label="Deep Space Astronomical Flux & Point Sources",
            units="rel. flux",
            vmin=0.0,
            vmax=100.0,
            kind=ColormapKind.SEQUENTIAL,
            category=VariableCategory.ICE,
            center=None,
            scale=ScaleType.LINEAR,
            orientation=Orientation.HORIZONTAL,
            low_at_start=True,
            instrument_family="bell",
            suggested_skin="neutral",
        )
        technique = "Celestial Resonant Synthesis & Cosmic Flux Mapping"
        desc = (
            "Translates deep-space astronomical imagery into luminous celestial chimes "
            "and harmonic drones. Point-source stars and high-energy clusters trigger "
            "crystalline additive bell partials, while diffuse interstellar gas and "
            "nebulae shape the underlying harmonic drone bed and tonal depth."
        )
        mappings = (
            CategorySoundMapping(
                data_characteristic="Optical Flux & Star Luminance (0 to 100%)",
                sound_parameter="Metallic Bell Pitch & Partials Decay",
                technique=(
                    "Bell instrument family: additive partials (ratios 1, 2.76, 5.4, 8.93) "
                    "with natural exponential decay"
                ),
                detail=(
                    "Brighter stars and cosmic features trigger higher pitches with "
                    "extended shimmering decay."
                ),
            ),
            CategorySoundMapping(
                data_characteristic="Galactic Cores & Dense Star Clusters",
                sound_parameter="Velocity Accents & Octave Bell Doubling",
                technique=(
                    "Intense point source concentrations in the top 5% trigger +0.25 "
                    "velocity boost and octave doubling"
                ),
                detail=(
                    "Acoustically magnifies massive gravitational centers and bright starbursts."
                ),
            ),
            CategorySoundMapping(
                data_characteristic="Point Source vs. Diffuse Cosmic Gas",
                sound_parameter="Rhythmic Density & Timbre Roughness",
                technique=(
                    "Sharp star point sources create distinct rhythmic chimes; diffuse gas "
                    "clouds modulate drone warmth"
                ),
                detail=(
                    "Creates rich polyphony between foreground stars and background nebular "
                    "structures."
                ),
            ),
            CategorySoundMapping(
                data_characteristic="Cosmic Background & Ambient Gas",
                sound_parameter="Harmonic Drone Bed (Tonic + Fifth)",
                technique="Continuous harmonic drone bed modulated by total field luminosity",
                detail="Evokes the vast, quiet expanse of deep cosmic space.",
            ),
            CategorySoundMapping(
                data_characteristic="Spatial Celestial Coordinates",
                sound_parameter="5 Voice Stereo Panning (Left to Right)",
                technique=(
                    "5 spatial bands across the astronomical field panned stereo left to right"
                ),
                detail=(
                    "Enables listeners to sonically map the structure of galaxies and clusters."
                ),
            ),
        )
        return config, technique, desc, mappings

    # Fallback for generic/custom categories
    config = CategoryPredefinedConfig(
        label=f"{title} Observation",
        units="units",
        vmin=0.0,
        vmax=100.0,
        kind=ColormapKind.SEQUENTIAL,
        category=VariableCategory.GENERIC,
        center=None,
        scale=ScaleType.LINEAR,
        orientation=Orientation.HORIZONTAL,
        low_at_start=True,
        instrument_family="pad",
        suggested_skin="neutral",
    )
    technique = "Earth Jukebox Standard Sonification"
    desc = (
        "Maps physical data values to pitch across 2 octaves, local variability to rhythm and "
        "timbre roughness, and spatial coordinates to 5-band stereo panning."
    )
    mappings = (
        CategorySoundMapping(
            data_characteristic="Normalized Data Values (0 to 100%)",
            sound_parameter="Musical Pitch across 2 octaves",
            technique="Scale quantization mapped to skin tonic",
            detail="Standard scientific sonification protocol.",
        ),
        CategorySoundMapping(
            data_characteristic="Local Data Gradients",
            sound_parameter="Rhythmic Density (1/2/4 pulses/beat) & Roughness",
            technique="Gradient thresholds determine pulse rate",
            detail="Smooth regions stay quiet; boundaries trigger pulses.",
        ),
    )
    return config, technique, desc, mappings


class FileSystemCategoryRepository(CategoryRepository):
    """Discovers categories and assets from dataset/ subdirectories."""

    def __init__(self, dataset_dir: Path) -> None:
        self._dataset_dir = dataset_dir

    def _resolve_dir(self) -> Path:
        if self._dataset_dir.exists():
            return self._dataset_dir
        # Try alternate casing
        alt = self._dataset_dir.parent / (
            "Dataset" if self._dataset_dir.name.islower() else "dataset"
        )
        if alt.exists():
            return alt
        return self._dataset_dir

    def list(self) -> Sequence[DatasetCategory]:
        """Return all categories found in the dataset directory, sorted by name."""
        base_dir = self._resolve_dir()
        if not base_dir.is_dir():
            return []

        categories: list[DatasetCategory] = []
        for entry in sorted(base_dir.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                cat = self._load_category(entry)
                categories.append(cat)
        return categories

    def get(self, category_id: str) -> DatasetCategory:
        """Find category by ID/folder name (exact or case-insensitive)."""
        base_dir = self._resolve_dir()
        if not base_dir.is_dir():
            raise NotFoundError(f"dataset directory '{base_dir}' not found")

        # Direct lookup
        target = base_dir / category_id
        if target.is_dir() and not target.name.startswith("."):
            return self._load_category(target)

        # Case-insensitive or slug lookup
        for entry in base_dir.iterdir():
            if entry.is_dir() and not entry.name.startswith("."):
                if entry.name.lower() == category_id.lower():
                    return self._load_category(entry)
                # Compare slugified
                slug = re.sub(r"[^a-z0-9]+", "-", entry.name.lower()).strip("-")
                target_slug = re.sub(r"[^a-z0-9]+", "-", category_id.lower()).strip("-")
                if slug == target_slug:
                    return self._load_category(entry)

        raise NotFoundError(f"category '{category_id}' not found")

    def legend_bytes(self, category_id: str) -> tuple[bytes, str]:
        """Return raw image bytes and MIME type for category legend image."""
        category = self.get(category_id)
        if not category.has_legend or not category.legend_filename:
            raise NotFoundError(f"no legend image found for category '{category_id}'")

        base_dir = self._resolve_dir()
        cat_dir = base_dir / category.id
        legend_path = cat_dir / category.legend_filename
        if not legend_path.is_file():
            raise NotFoundError(f"legend file '{category.legend_filename}' missing on disk")

        mime, _ = mimetypes.guess_type(legend_path.name)
        mime = mime or "image/png"
        return legend_path.read_bytes(), mime

    def image_bytes(self, category_id: str, filename: str) -> tuple[bytes, str]:
        """Return raw image bytes and MIME type for an example image in category."""
        # Prevent path traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            raise NotFoundError(f"invalid filename '{filename}'")

        category = self.get(category_id)
        base_dir = self._resolve_dir()
        cat_dir = base_dir / category.id
        img_path = cat_dir / filename

        if not img_path.is_file():
            raise NotFoundError(f"image '{filename}' not found in category '{category_id}'")

        if img_path.suffix.lower() not in IMAGE_EXTENSIONS:
            raise NotFoundError(f"unsupported image file '{filename}'")

        mime, _ = mimetypes.guess_type(img_path.name)
        mime = mime or "image/jpeg"
        return img_path.read_bytes(), mime

    def _load_category(self, cat_dir: Path) -> DatasetCategory:
        info_path = cat_dir / "info.md"
        info_text = info_path.read_text(encoding="utf-8") if info_path.is_file() else ""

        title, desc, leg_info, _, _ = _parse_info_sections(info_text)
        if not title:
            title = cat_dir.name.replace("-", " ").replace("_", " ").title()

        if not desc:
            desc = f"NASA dataset visualizations for {title}."

        # Detect legend image
        legend_filename: str | None = None
        for candidate in sorted(LEGEND_FILENAMES):
            if (cat_dir / candidate).is_file():
                legend_filename = candidate
                break

        has_legend = legend_filename is not None

        # Discover example images
        example_images: list[ExampleImage] = []
        for file in sorted(cat_dir.iterdir()):
            if (
                file.is_file()
                and file.suffix.lower() in IMAGE_EXTENSIONS
                and file.name.lower() not in LEGEND_FILENAMES
            ):
                img_title = _format_image_title(file.name)
                example_images.append(ExampleImage(filename=file.name, title=img_title))

        # Discovered curated configuration & sound mappings (F-108)
        predefined_config, technique, son_desc, mappings = _get_category_curation(
            cat_dir.name, title
        )

        return DatasetCategory(
            id=cat_dir.name,
            title=title,
            description=desc,
            info_markdown=info_text,
            has_legend=has_legend,
            legend_filename=legend_filename,
            legend_info=leg_info,
            example_images=tuple(example_images),
            predefined_config=predefined_config,
            sonification_technique=technique,
            sonification_description=son_desc,
            sound_mappings=mappings,
        )


def extract_category_lut(
    category_id: str,
    repository: CategoryRepository,
    decoder: ImageDecoder,
    detector: ColorbarDetector | None = None,
) -> tuple[ColorLUT, ColormapKind] | None:
    """Extract normalized ColorLUT [0, 1] and ColormapKind from a category's legend image."""
    try:
        cat = repository.get(category_id)
    except Exception:
        return None

    if not cat.has_legend or not cat.legend_filename:
        return None

    try:
        raw_bytes, _ = repository.legend_bytes(cat.id)
        decoded = decoder.decode(raw_bytes)
    except Exception:
        return None

    # Determine colorbar bounding box inside legend image
    lower_id = cat.id.lower()
    cbox: PixelBox | None = None
    if "aerols" in lower_id or "aerosol" in lower_id:
        # GIOS Aerosols categorical legend swatches span X 200..1300 at Y 100..200
        w = max(50, decoded.original_width - 400)
        cbox = PixelBox(
            x=200,
            y=min(100, max(0, decoded.original_height - 100)),
            w=w,
            h=min(100, decoded.original_height),
        )
    elif detector is not None:
        cands = detector.detect(decoded)
        if cands:
            cbox = cands[0].box

    if cbox is None:
        cbox = PixelBox(x=0, y=0, w=decoded.original_width, h=decoded.original_height)

    kind = (
        cat.predefined_config.kind
        if cat.predefined_config
        else (ColormapKind.DIVERGING if "temp" in lower_id else ColormapKind.SEQUENTIAL)
    )
    center = 0.5 if kind == ColormapKind.DIVERGING else None
    spec = LegendSpec(
        vmin=0.0,
        vmax=1.0,
        units="",
        label=cat.title,
        kind=kind,
        center=center,
        orientation=Orientation.HORIZONTAL,
        low_at_start=True,
    )

    try:
        raw_lut = extract_lut(decoded.rgb, cbox, spec)
        n_lut = len(raw_lut.lab)
        if n_lut < 2:
            return None
        norm_positions = np.linspace(0.0, 1.0, n_lut, dtype=np.float64)
        return (
            ColorLUT(
                lab=raw_lut.lab,
                values=norm_positions,
                source=RecoveryMode.PRESET,
            ),
            kind,
        )
    except Exception:
        return None
