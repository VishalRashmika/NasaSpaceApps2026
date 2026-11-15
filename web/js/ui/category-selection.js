/**
 * Category Selection Page & Preloaded Gallery UI (F-107, F-108).
 * Discovers real categories from dataset/, displays authentic NASA preloaded gallery,
 * category overview cards, optional legends, and connects to the sonification engine.
 */

import { getCategories, fetchCategoryImageBlob } from "../api/client.js";

const CATEGORY_ICONS = {
  temperature: "",
  wind: "",
  precipitation: "",
  aerosol: "",
  deep_space: "",
  lightning: "",
  default: "",
};

function getCategoryIcon(catId) {
  const lower = (catId || "").toLowerCase();
  if (lower.includes("temp")) return CATEGORY_ICONS.temperature;
  if (lower.includes("wind")) return CATEGORY_ICONS.wind;
  if (lower.includes("precip") || lower.includes("cloud")) return CATEGORY_ICONS.precipitation;
  if (lower.includes("aerosol") || lower.includes("aerols")) return CATEGORY_ICONS.aerosol;
  if (lower.includes("hubble") || lower.includes("deep") || lower.includes("space")) return CATEGORY_ICONS.deep_space;
  if (lower.includes("lightning")) return CATEGORY_ICONS.lightning;
  return CATEGORY_ICONS.default;
}

/**
 * Produce concise, clean category labels for gallery filter chips/cards.
 * Trims verbose markdown headings and mission boilerplate into clean names.
 */
export function formatCategoryFilterLabel(cat) {
  if (!cat) return "";
  const catId = (cat.id || "").toLowerCase();
  const title = (cat.title || "").toLowerCase();

  if (catId.includes("aerosol") || catId.includes("aerols") || title.includes("aerosol")) {
    return "Aerosols";
  }
  if (catId.includes("precip") || catId.includes("cloud") || title.includes("precipitation")) {
    return "Precipitation & Clouds";
  }
  if (catId.includes("hubble") || catId.includes("deep") || title.includes("deep space") || title.includes("hubble")) {
    return "Deep Space";
  }
  if (catId.includes("temp") || title.includes("temperature")) {
    return "Temperature";
  }
  if (catId.includes("wind") || title.includes("wind speed")) {
    return "Wind Speed";
  }
  if (catId.includes("lightning") || title.includes("lightning")) {
    return "ISS Lightning";
  }

  let cleaned = (cat.title || cat.id || "")
    .replace(/^Dataset\s+(Information|Overview|Context):\s*/i, "")
    .replace(/^NASA\s+Dataset\s*(Context)?:\s*/i, "")
    .replace(/^NASA\s+GEOS-FP:\s*/i, "")
    .replace(/\s*\(\d{4}(-\d{4})?\)\s*$/, "")
    .trim();

  return cleaned || cat.title || cat.id;
}

export const CUSTOM_IMAGE_TYPES = [
  {
    id: "GIOS Aerols",
    title: "NASA GEOS Aerosols",
    categoryKey: "aerosol",
    badge: "Colorbar Legend Required",
    badgeClass: "badge-legend-yes",
    hasLegend: true,
    legendDecision: "Colorbar Legend Required: Atmospheric aerosol optical depth maps utilize an empirical color gradient. The colorbar region will be extracted to recover quantitative aerosol measurements (0 to 5 AOD).",
    sonificationLogic: "Aerosol Optical Depth (AOD) is inverted from the color gradient and mapped to high-altitude atmospheric wind frequencies with stereo spatial panning across geographic coordinates.",
    variableRange: "0 to 5 AOD",
    units: "AOD",
    vmin: 0,
    vmax: 5,
    kind: "sequential",
    scale: "linear",
    center: null,
    synthVoice: "Atmosphere / Wind Synth",
    instrumentFamily: "wind",
    orientation: "horizontal",
  },
  {
    id: "Hubble+IOTD",
    title: "Hubble & Deep Space",
    categoryKey: "ice",
    badge: "Direct Spatial (No Legend)",
    badgeClass: "badge-legend-no",
    hasLegend: false,
    legendDecision: "Direct Spatial & Flux Sonification (No Legend Required): Deep-space astrophotography measures radiant stellar flux and luminance directly from celestial coordinates rather than an empirical colorbar gradient.",
    sonificationLogic: "Pixel brightness and astronomical flux translate directly into celestial harmonic pitch registers and overtone resonance across the two-dimensional spatial grid.",
    variableRange: "0 to 100 relative flux",
    units: "rel. flux",
    vmin: 0,
    vmax: 100,
    kind: "sequential",
    scale: "linear",
    center: null,
    synthVoice: "Deep Space Resonant Synth",
    instrumentFamily: "pad",
    orientation: "horizontal",
  },
  {
    id: "lightningEvents",
    title: "ISS Lightning",
    categoryKey: "precipitation",
    badge: "Direct Events (No Legend)",
    badgeClass: "badge-legend-no",
    hasLegend: false,
    legendDecision: "Direct Event Sonification (No Legend Required): ISS Lightning Imaging Sensor captures discrete orbital flash coordinates rather than a continuous colormap gradient.",
    sonificationLogic: "Lightning flash events trigger acoustic pulse bursts and transient triggers mapped across the stereo soundfield corresponding to orbital sensor flash positions.",
    variableRange: "0 to 1 flash density",
    units: "flashes/area",
    vmin: 0,
    vmax: 1,
    kind: "sequential",
    scale: "linear",
    center: null,
    synthVoice: "Transient Percussion / Pulse Synth",
    instrumentFamily: "marimba",
    orientation: "horizontal",
  },
  {
    id: "Near-Surface-Temperature",
    title: "NASA GEOS Near-Surface Temperature",
    categoryKey: "temperature",
    badge: "Colorbar Legend Required",
    badgeClass: "badge-legend-yes",
    hasLegend: true,
    legendDecision: "Colorbar Legend Required: Near-surface thermal maps use a diverging cold-to-warm colormap centered around 0°C freezing point. Legend inversion extracts authentic temperatures (-40°C to +40°C).",
    sonificationLogic: "Freezing point (0°C) is the tonal center; warm temperature anomalies elevate pitch into upper harmonic registers, while sub-zero anomalies produce deep resonant bass fundamentals.",
    variableRange: "-40°C to +40°C",
    units: "°C",
    vmin: -40,
    vmax: 40,
    kind: "diverging",
    scale: "linear",
    center: 0,
    synthVoice: "Warm Thermal Pad Synth",
    instrumentFamily: "pad",
    orientation: "horizontal",
  },
  {
    id: "Near-Surface-Wind-Speed",
    title: "NASA GEOS Near-Surface Wind Speed",
    categoryKey: "ocean",
    badge: "Colorbar Legend Required",
    badgeClass: "badge-legend-yes",
    hasLegend: true,
    legendDecision: "Colorbar Legend Required: Global near-surface wind speed imagery uses a sequential velocity colormap (0 to 40 m/s). Colorbar inversion extracts calibrated wind speed values.",
    sonificationLogic: "Wind velocity drives synthesizer pitch and noise modulation amplitude; high-velocity wind jets create rapid resonant sweeps and wide stereo flutter.",
    variableRange: "0 to 40 m/s",
    units: "m/s",
    vmin: 0,
    vmax: 40,
    kind: "sequential",
    scale: "linear",
    center: null,
    synthVoice: "Wind Speed Acoustic Voice",
    instrumentFamily: "wind",
    orientation: "horizontal",
  },
  {
    id: "Geos-fp-precipitation-and-clouds",
    title: "NASA GEOS Precipitation & Clouds",
    categoryKey: "precipitation",
    badge: "Colorbar Legend Required",
    badgeClass: "badge-legend-yes",
    hasLegend: true,
    legendDecision: "Colorbar Legend Required: Precipitation and atmospheric water vapor maps use a sequential colorbar to quantify rainfall rates (0 to 20 mm/hr).",
    sonificationLogic: "Rainfall rate maps to acoustic droplet frequency and trigger density; heavy convective precipitation generates dense acoustic cluster textures.",
    variableRange: "0 to 20 mm/hr",
    units: "mm/hr",
    vmin: 0,
    vmax: 20,
    kind: "sequential",
    scale: "linear",
    center: null,
    synthVoice: "Precipitation / Pluck Synth",
    instrumentFamily: "pluck",
    orientation: "horizontal",
  },
  {
    id: "Vegetation-NDVI",
    title: "Vegetation & Land Cover (NDVI)",
    categoryKey: "vegetation",
    badge: "Colorbar Legend Required",
    badgeClass: "badge-legend-yes",
    hasLegend: true,
    legendDecision: "Colorbar Legend Required: Normalized Difference Vegetation Index (NDVI) requires colorbar extraction to measure photosynthetic activity (-0.1 to 0.9 NDVI).",
    sonificationLogic: "Vegetation index scales pitch across harmonic pentatonic steps; barren ground produces sparse low notes, while dense canopy foliage triggers lush organic chords.",
    variableRange: "-0.1 to 0.9 NDVI",
    units: "NDVI",
    vmin: -0.1,
    vmax: 0.9,
    kind: "sequential",
    scale: "linear",
    center: null,
    synthVoice: "Organic Acoustic Pluck",
    instrumentFamily: "acoustic",
    orientation: "horizontal",
  },
  {
    id: "Generic-Scientific",
    title: "Generic Scientific Map",
    categoryKey: "generic",
    badge: "Configurable Legend",
    badgeClass: "badge-legend-no",
    hasLegend: true,
    legendDecision: "Colorbar Legend Configurable: For generic scientific data maps, the system detects color gradients or allows custom calibration overrides.",
    sonificationLogic: "Linear mapping of scalar measurements to standard acoustic pitch range with stereo geographic distribution.",
    variableRange: "0 to 100 units",
    units: "units",
    vmin: 0,
    vmax: 100,
    kind: "sequential",
    scale: "linear",
    center: null,
    synthVoice: "Standard Synth Voice",
    instrumentFamily: "pad",
    orientation: "horizontal",
  },
];

export function formatMarkdownToHtml(markdown) {
  if (!markdown) return "";
  const lines = markdown.split("\n");
  const html = [];
  let inList = false;
  let inTable = false;

  const escapeHtml = (str) =>
    str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

  const formatInline = (text) => {
    let t = escapeHtml(text);
    t = t.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    t = t.replace(/\*(.+?)\*/g, "<em>$1</em>");
    t = t.replace(/`(.+?)`/g, "<code>$1</code>");
    return t;
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    if (line.startsWith("|") && line.endsWith("|")) {
      if (line.includes("---")) {
        continue;
      }
      if (!inTable) {
        if (inList) {
          html.push("</ul>");
          inList = false;
        }
        inTable = true;
        html.push('<div class="md-table-wrap"><table class="md-table">');
      }
      const cells = line
        .slice(1, -1)
        .split("|")
        .map((c) => c.trim());
      const tag = i === 0 || html.length <= 1 ? "th" : "td";
      html.push(`<tr>${cells.map((c) => `<${tag}>${formatInline(c)}</${tag}>`).join("")}</tr>`);
      continue;
    } else if (inTable) {
      html.push("</table></div>");
      inTable = false;
    }

    if (line.startsWith("* ") || line.startsWith("- ")) {
      if (!inList) {
        inList = true;
        html.push('<ul class="md-list">');
      }
      html.push(`<li>${formatInline(line.slice(2))}</li>`);
      continue;
    } else if (inList) {
      html.push("</ul>");
      inList = false;
    }

    if (line.startsWith("### ")) {
      html.push(`<h4>${formatInline(line.slice(4))}</h4>`);
    } else if (line.startsWith("## ")) {
      html.push(`<h3>${formatInline(line.slice(3))}</h3>`);
    } else if (line.startsWith("# ")) {
      html.push(`<h2>${formatInline(line.slice(2))}</h2>`);
    } else if (line.length === 0) {
      continue;
    } else {
      html.push(`<p>${formatInline(line)}</p>`);
    }
  }

  if (inList) html.push("</ul>");
  if (inTable) html.push("</table></div>");

  return html.join("\n");
}

export function formatObservationDisplayTitle(rawTitle, filename) {
  const map = {
    "Aerosols_2025-08-19T20_00_00_1500x1179_72dpi.png": "NASA GEOS Aerosol Optical Depth (Synoptic)",
    "Aerosols_2025-08-19T20_00_00_1920x1080.png": "NASA GEOS Global Aerosol Optical Depth (1080p)",
    "MC03_stage3_GMAO_precipitation_2048x1024_en.00001_print.jpg": "NASA GEOS Precipitation & Cloud Dynamics",
    "01_m30s-sparkling-stars.jpg": "Hubble: Sparkling Stars in Cluster M30",
    "02_hubble-reveals-cosmic-mystery.png": "Hubble: Star Formation & Cosmic Filament",
    "03_nasas-james-webb-space-telescope-captures-eerie-cats-head.png": "NASA's James Webb: Eerie Cat's Eye Nebula",
    "04_nasas-hubble-marks-way-for-roman-space-telescope.jpg": "Hubble: Wayfinding for Nancy Grace Roman Telescope",
    "05_webb-sees-turbulent-star-nursery.jpg": "JWST: Turbulent Stellar Nursery NGC 346",
    "06_spirals-edge.jpg": "Hubble: Edge-On Spiral Galaxy NGC 4565",
    "07_webb-captures-stellar-jets.png": "JWST: Supersonic Stellar Jets in Herbig-Haro",
    "08_chandra-finds-possible-origin-of-treble-clef-waves.jpg": "NASA Chandra: Acoustic Sound Waves in Galaxy Cluster",
    "09_cosmic-house-of-mirrors.jpg": "Hubble: Gravitational Lens 'Cosmic Mirrors'",
    "10_hubble-spots-chaotic-secret-in-galaxy.jpg": "Hubble: Starburst Core Dynamics in NGC 1569",
    "11_nasas-hubble-telescope-reaches-milestone-looks-for-elusive-supernova.jpg": "Hubble: Deep Supernova Progenitor Search",
    "12_nasas-chandra-finds-unusual-objects-in-pinwheel-galaxy.jpg": "NASA Chandra: Ultraluminous X-Ray Sources in M101",
    "13_nasas-chandra-spots-galactic-gem.jpg": "NASA Chandra: Galactic Core X-Ray Emission",
    "14_dust-and-water-in-sagittarius-a.png": "NASA: Molecular Gas & Water in Sagittarius A*",
    "15_superbubble-in-the-large-magellanic-cloud.jpg": "Hubble: Superbubble Cavity in LMC (N44)",
    "16_webb-opens-treasure-chest.jpg": "JWST: Dense Infrared Star Cluster NIRCam",
    "17_colorful-collage-of-tarantula-nebula.jpg": "Hubble & Webb: Multiwavelength Tarantula Nebula",
    "18_lion-nebula-roars-in-webbs-sights.png": "JWST: Starburst Lion Nebula in Infrared",
    "19_starburst-galaxy-centaurus-a.png": "Hubble & Chandra: Active Radio Galaxy Centaurus A",
    "20_a-new-look-and-sound-for-messier-94.jpg": "NASA Chandra: Acoustic Resonance in Messier 94",
    "21_nasas-chandra-and-ixpe-study-pulsar-in-lighthouse-nebula.jpg": "NASA Chandra & IXPE: Pulsar in Lighthouse Nebula",
    "22_young-galaxy-cluster.jpg": "Hubble: Massive Gravitationally Bound Young Cluster",
    "23_hubble-sees-crimson-cloud-and-stars.jpg": "Hubble: Crimson Ionized Hydrogen in Emission Nebula",
    "24_hubble-captures-star-studded-cluster.jpg": "Hubble: High-Density Globular Cluster NGC 6355",
    "25_starry-chandelier-cluster.jpg": "Hubble: Luminous Stellar Chandelier Cluster",
    "26_millions-of-stars-in-cigar-galaxy.jpg": "Hubble: Starburst Galaxy Messier 82 (Cigar)",
    "27_nasas-chandra-finds-possible-supernova-remnant.jpg": "NASA Chandra: Compact Supernova Remnant G352.7-0.1",
    "28_black-eye-galaxy.jpg": "Hubble: Black Eye Galaxy (Messier 64)",
    "MC01_stage3_GMAO_near_surface_temperature_2048x1024_en.00001_print.jpg": "NASA GEOS Near-Surface Temperature (T2M)",
    "MC02_stage3_GMAO_near_surface_wind_2048x1024_en.00001_print.jpg": "NASA GEOS Near-Surface Wind Speed & Circulation",
    "iss_lightning_SOS_thumb.jpg": "ISS Lightning Science On a Sphere (SOS)",
    "iss_lightning_preview.jpg": "ISS Lightning Imaging Sensor (Global Preview)",
    "iss_lightning_sos_yearly_debug_2023_sos_2048p60.00420_print.jpg": "ISS LIS Annual Lightning Flash Distribution",
  };

  if (filename && map[filename]) return map[filename];

  let t = (rawTitle || filename || "").trim();
  t = t.replace(/\bNasas\b/gi, "NASA's");
  t = t.replace(/\bNasa\b/gi, "NASA");
  t = t.replace(/\bIss\b/gi, "ISS");
  t = t.replace(/\bSos\b/gi, "SOS");
  t = t.replace(/\bJwst\b/gi, "JWST");
  t = t.replace(/\bGeos\b/gi, "GEOS");
  t = t.replace(/\bGmao\b/gi, "GMAO");
  t = t.replace(/\bIxpe\b/gi, "IXPE");
  t = t.replace(/\bWebbs\b/gi, "Webb's");
  t = t.replace(/\b2048X1024\b/gi, "");
  t = t.replace(/\b1920X1080\b/gi, "1080p");
  t = t.replace(/\b1500X1179\b/gi, "Synoptic");
  t = t.replace(/\s+/g, " ").trim();
  return t;
}

export function getMissionLabel(filename, catId) {
  const f = (filename || "").toLowerCase();
  const c = (catId || "").toLowerCase();

  if (f.includes("webb") || f.includes("jwst")) return "NASA James Webb Space Telescope";
  if (f.includes("chandra") && f.includes("ixpe")) return "NASA Chandra & IXPE";
  if (f.includes("chandra")) return "NASA Chandra X-Ray Observatory";
  if (f.includes("hubble")) return "NASA Hubble Space Telescope";
  if (f.includes("roman")) return "NASA Nancy Grace Roman Space Telescope";
  if (c.includes("space") || c.includes("hubble")) return "NASA Great Observatories";
  if (c.includes("lightning") || f.includes("lightning")) return "ISS Lightning Imaging Sensor (LIS)";
  if (c.includes("aerosol") || c.includes("aerols") || c.includes("gios")) return "NASA GEOS-FP Aerosols (GMAO)";
  if (c.includes("precip") || c.includes("cloud")) return "NASA GEOS-FP Precipitation & Clouds";
  if (c.includes("temp")) return "NASA GEOS-FP Near-Surface Temperature";
  if (c.includes("wind")) return "NASA GEOS-FP Near-Surface Wind";
  return "NASA Earth Information Center";
}

/**
 * Returns structured scientific metadata and color mappings for authentic NASA datasets.
 */
export function getCategoryScientificMeta(category) {
  const catId = (category?.id || "").toLowerCase();
  const title = (category?.title || "").toLowerCase();

  if (catId.includes("aerosol") || catId.includes("aerols") || title.includes("aerosol")) {
    return {
      model: "GEOS-FP 2Km Replay (NASA GMAO)",
      domain: "Atmospheric Aerosol Dynamics",
      snapshot: "Aug 19, 2025 (20:00 UTC)",
      variables: "Aerosol Optical Thickness (AOD) by Type",
      format: "High-Resolution Spatial Map (72 / 1080p)",
      colors: [
        {
          name: "Blue",
          phenomenon: "Sea Salt & Cyclones",
          color: "#2563eb",
          desc: "Sea salt kicked up by strong winds blowing across the ocean.",
          patterns: "Swirling, circular patterns over oceans representing storms, tropical cyclones, or hurricanes (e.g., Hurricane Erin in the Atlantic). Pale blue to white reflects stormy conditions with thick concentrations.",
        },
        {
          name: "Pink / Magenta",
          phenomenon: "Desert Dust",
          color: "#db2777",
          desc: "Mineral desert dust transported by atmospheric winds.",
          patterns: "Massive hazy plumes traveling across continents and oceans. Key example: Saharan desert dust traveling westward across the Atlantic toward the Caribbean and Americas.",
        },
        {
          name: "Orange / Red",
          phenomenon: "Biomass Burning & Wildfire Smoke",
          color: "#ea580c",
          desc: "Organic and black carbon, primarily from burning biomass.",
          patterns: "Dense drifting plumes originating from landmasses. Major sources include wildfires (e.g., in Spain/Southern Europe) and seasonal agricultural burning (e.g., Southern Africa).",
        },
        {
          name: "Green",
          phenomenon: "Sulfates & Volcanic Emissions",
          color: "#16a34a",
          desc: "Sulfate particles from anthropogenic pollution and natural volcanism.",
          patterns: "Narrow concentrated streams (volcanic plumes from Kilauea or Mount Etna) or broad regional industrial smog over densely populated areas.",
        },
      ],
    };
  }

  if (catId.includes("temp") || title.includes("temperature")) {
    return {
      model: "GEOS Forward Processing (NASA GMAO)",
      domain: "Thermodynamic Heat Transport",
      snapshot: "Global Surface Replay",
      variables: "Near-Surface Air Temperature at 2m (T2M)",
      format: "Global Latitude-Longitude Grid (2048x1024)",
      milestones: [
        {
          range: "-40°C to -20°C",
          label: "Very Cold (Polar Glacial)",
          color: "#1e3a8a",
          desc: "Dark navy blue to icy white, transitioning to deep magenta over polar ice sheets.",
        },
        {
          range: "-20°C to 0°C",
          label: "Cold to Freezing Point",
          color: "#0284c7",
          desc: "Deep magenta/purple into dark blue, lightening to pale cyan at the 0°C freezing point.",
        },
        {
          range: "0°C to +20°C",
          label: "Temperate to Warm",
          color: "#16a34a",
          desc: "Pale cyan transitioning into pale green, shifting into bright yellow and orange across mid-latitudes.",
        },
        {
          range: "+20°C to +40°C",
          label: "Hot to Extreme Heatwave",
          color: "#dc2626",
          desc: "Deep orange into intense fiery red, darkening into deep brown/black at maximum thermal extremes.",
        },
      ],
    };
  }

  if (catId.includes("wind") || title.includes("wind speed")) {
    return {
      model: "GEOS-FP 10-Meter Wind Analysis (NASA GMAO)",
      domain: "Kinetic Atmospheric Circulation",
      snapshot: "Synoptic Surface Wind Field",
      variables: "Near-Surface Wind Velocity at 10m (0 to 40 m/s)",
      format: "Global Lat-Lon Grid (2048x1024)",
      milestones: [
        {
          range: "0 to 4 m/s",
          label: "Calm",
          color: "#6b7280",
          desc: "Solid gray basemap indicating calm wind fields across land and equatorial doldrums.",
        },
        {
          range: "4 to 10 m/s",
          label: "Light to Gentle Breeze",
          color: "#3b82f6",
          desc: "Light purple/lavender transitioning through deep indigo into solid ocean blue.",
        },
        {
          range: "10 to 15 m/s",
          label: "Moderate Wind Streams",
          color: "#10b981",
          desc: "Light cyan transitioning into bright green and yellow-green along prevailing trade belts.",
        },
        {
          range: "15 to 20 m/s",
          label: "Strong Wind Bands",
          color: "#f59e0b",
          desc: "Yellow shifting into orange and pure red (20 m/s strong wind threshold).",
        },
        {
          range: "20 to 30 m/s",
          label: "Gale & Storm Forces",
          color: "#dc2626",
          desc: "Bright red deepening into crimson and dark brown/black around severe maritime fronts.",
        },
        {
          range: "30 to 40 m/s",
          label: "Hurricane & Cyclone Vortices",
          color: "#450a0a",
          desc: "Black fading into dark desaturated gradient at extreme hurricane-force circulation cores.",
        },
      ],
    };
  }

  if (catId.includes("precip") || catId.includes("cloud") || title.includes("precipitation")) {
    return {
      model: "GEOS-FP Multi-Stage Modeling (NASA SVS 5149)",
      domain: "Hydrological Atmospheric Systems",
      snapshot: "Global Cloud & Rain Dynamics",
      variables: "Precipitation Rate (0-20 mm/hr) & Cloud Optical Depth",
      format: "Dual-Layer Composite Grid (2048x1024)",
      milestones: [
        {
          range: "Grayscale Basemap",
          label: "Layer A: Cloud Optical Thickness",
          color: "#94a3b8",
          desc: "Grayscale cloud layer: white represents thick, dense cloud fields; dark indicates clear skies.",
        },
        {
          range: "0.0 to 1.5 mm/hr",
          label: "Light Drizzle / Mist",
          color: "#15803d",
          desc: "Dark green to light green rainfall overlay.",
        },
        {
          range: "1.5 to 7.0 mm/hr",
          label: "Moderate Precipitation",
          color: "#0284c7",
          desc: "Dark blue transitioning into cyan and light purple.",
        },
        {
          range: "7.0 to 15.0 mm/hr",
          label: "Heavy Convective Rainfall",
          color: "#b91c1c",
          desc: "Dark magenta transitioning to dark red and orange.",
        },
        {
          range: "15.0 to 20.0 mm/hr",
          label: "Severe Atmospheric River / Downpour",
          color: "#eab308",
          desc: "Orange transitioning to intense bright yellow, signaling flash flood hazards.",
        },
      ],
    };
  }

  if (catId.includes("space") || catId.includes("hubble") || title.includes("deep space")) {
    return {
      model: "NASA Great Observatories (Hubble, Webb, Chandra)",
      domain: "Astrophysical Celestial Dynamics",
      snapshot: "Deep Astronomical Exposures",
      variables: "Multi-Wavelength Luminance & Stellar Flux",
      format: "High-Resolution Astrophotography",
      milestones: [
        {
          range: "Orange/Red Clusters",
          label: "Cooler / Older Stars (Red Giants)",
          color: "#ea580c",
          desc: "Point source stellar clusters triggering resonant acoustic marimba strikes.",
        },
        {
          range: "Blue Clusters",
          label: "Hot Younger Stars & Starbursts",
          color: "#3b82f6",
          desc: "High-energy point sources triggering bright glockenspiel bell chimes.",
        },
        {
          range: "Diffuse Nebulosity",
          label: "Interstellar Gas & Background Dust",
          color: "#8b5cf6",
          desc: "Continuous celestial choir / ambient synth pad with amplitude scaling by luminance.",
        },
        {
          range: "Radius & Angle (r, θ)",
          label: "Orbital Sequencing Geometry",
          color: "#06b6d4",
          desc: "Radius from center maps to pitch register; polar angle maps to playhead sweep timing.",
        },
      ],
    };
  }

  if (catId.includes("lightning") || title.includes("lightning")) {
    return {
      model: "ISS Lightning Imaging Sensor (LIS / SVS 5011)",
      domain: "Planetary Electrodynamics",
      snapshot: "10-Day Roving Window (2017-2023)",
      variables: "Discrete Lightning Flash Coordinates",
      format: "Global Orbital Event Distribution (2048x1024)",
      milestones: [
        {
          range: "Yellow / Gold Pixels",
          label: "Event Indicator (Lightning Flash)",
          color: "#eab308",
          desc: "High Red/Green emission coordinates indicate one or more orbital lightning flashes, triggering stereo transient acoustic pulses.",
        },
        {
          range: "Dark Basemap",
          label: "Null Indicator (Non-Active Background)",
          color: "#374151",
          desc: "Oceans and continents with zero recorded lightning activity during the 10-day roving observation window.",
        },
      ],
    };
  }

  return {
    model: "NASA Earth Information System",
    domain: "Earth Observation Data",
    snapshot: "Standard Satellite Visualization",
    variables: category?.predefined_config
      ? `${category.predefined_config.label} (${category.predefined_config.vmin} to ${category.predefined_config.vmax} ${category.predefined_config.units})`
      : category?.title || "Scientific Data",
    format: "Calibrated Scientific Visualization",
  };
}

export function formatImageResolutionMeta(filename) {
  const f = (filename || "").toLowerCase();
  if (f.includes("1500x1179")) return "1500 × 1179 px (72 DPI)";
  if (f.includes("1920x1080")) return "1920 × 1080 px (Full HD)";
  if (f.includes("2048x1024")) return "2048 × 1024 px (Scientific Projection)";
  if (f.includes("2048p60")) return "2048p (Science On a Sphere 60 FPS)";
  return "NASA Authentic Resolution";
}

export function formatInlineMarkdown(text) {
  if (!text) return "";
  const escapeHtml = (str) =>
    str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

  let t = escapeHtml(text);
  t = t.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  t = t.replace(/\*(.+?)\*/g, "<em>$1</em>");
  t = t.replace(/`(.+?)`/g, "<code>$1</code>");
  t = t.replace(/\$([^\$]+)\$/g, "<span class='math-tex'>$1</span>");
  return t;
}

export function formatScientificDescriptionHtml(descText) {
  if (!descText) return "<p class=\"modal-obs-paragraph\">Authentic scientific observation from NASA.</p>";
  const paras = descText
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter((p) => p.length > 0 && !p.startsWith("#"));

  if (paras.length === 0) {
    return `<p class="modal-obs-paragraph">${formatInlineMarkdown(descText.trim())}</p>`;
  }

  return paras
    .map((p) => `<p class="modal-obs-paragraph">${formatInlineMarkdown(p)}</p>`)
    .join("");
}

export function formatColorLegendCardHtml(category, rawNotes) {
  const meta = getCategoryScientificMeta(category);

  // If category has categorical particulate color cards (e.g. GIOS Aerols)
  if (meta && Array.isArray(meta.colors) && meta.colors.length > 0) {
    const cardsHtml = meta.colors
      .map(
        (c) => `
      <div class="legend-swatch-card" style="border-left-color: ${c.color};">
        <div class="swatch-header">
          <span class="swatch-color-pill" style="background-color: ${c.color};" aria-hidden="true"></span>
          <strong class="swatch-title">${c.name}</strong>
          <span class="swatch-badge">${c.phenomenon}</span>
        </div>
        <div class="swatch-body">
          <div class="swatch-desc-row">
            <span class="swatch-field-label">Description:</span>
            <span class="swatch-field-text">${c.desc}</span>
          </div>
          <div class="swatch-desc-row">
            <span class="swatch-field-label">Visual Patterns:</span>
            <span class="swatch-field-text">${c.patterns}</span>
          </div>
        </div>
      </div>
    `
      )
      .join("");

    return `
      <p class="legend-intro-text">
        To successfully analyze images from this dataset, use the following exact color mappings to classify the atmospheric phenomena present in the frames:
      </p>
      <div class="legend-swatch-grid" role="region" aria-label="Aerosol Particulate Color Legend">
        ${cardsHtml}
      </div>
    `;
  }

  // If category has continuous or discrete milestones
  if (meta && Array.isArray(meta.milestones) && meta.milestones.length > 0) {
    const milestonesHtml = meta.milestones
      .map(
        (m) => `
      <div class="legend-milestone-card" style="border-left-color: ${m.color};">
        <div class="milestone-header">
          <span class="milestone-badge" style="color: ${m.color};">
            <span class="swatch-color-pill" style="background-color: ${m.color};" aria-hidden="true"></span>
            ${m.range}
          </span>
          <strong class="milestone-label">${m.label}</strong>
        </div>
        <p class="milestone-desc">${m.desc}</p>
      </div>
    `
      )
      .join("");

    const intro = category.has_legend
      ? "Calibrated scalar colorbar maps quantitative measurements to pixel values:"
      : "Rule-based sonification logic translates spatial features into acoustic parameters:";

    return `
      <p class="legend-intro-text">${intro}</p>
      <div class="legend-milestone-grid" role="region" aria-label="Color and Value Mapping Rules">
        ${milestonesHtml}
      </div>
    `;
  }

  // Fallback: parse rawNotes with markdown parser if present
  if (rawNotes) {
    return `<div class="legend-markdown-content">${formatMarkdownToHtml(rawNotes)}</div>`;
  }

  return `<p class="legend-intro-text">Calibrated data colorbar for value recovery and sonification.</p>`;
}

export function formatSoundMappingsHtml(category) {
  const mappings = Array.isArray(category?.sound_mappings) ? category.sound_mappings : [];
  if (mappings.length === 0) return "";

  const rowsHtml = mappings
    .map(
      (m) => `
    <tr>
      <td class="col-feature"><strong>${m.data_characteristic}</strong></td>
      <td class="col-sound"><span class="badge-sound">${m.sound_parameter}</span></td>
      <td class="col-technique">
        <div class="technique-name">${m.technique}</div>
        ${m.detail ? `<small class="technique-detail">${m.detail}</small>` : ""}
      </td>
    </tr>
  `
    )
    .join("");

  return `
    <div class="modal-mapping-table-wrap">
      <h5 class="modal-subsection-heading">Data-to-Sound Mapping Specification</h5>
      <table class="modal-mapping-table" aria-label="Data to sound mapping rules for ${category.title}">
        <thead>
          <tr>
            <th scope="col">Scientific Data Feature</th>
            <th scope="col">Audio Parameter</th>
            <th scope="col">Sonification Technique</th>
          </tr>
        </thead>
        <tbody>
          ${rowsHtml}
        </tbody>
      </table>
    </div>
  `;
}

export class CategorySelectionUI {
  /**
   * @param {object} options
   * @param {(payload: { category: object, image: object, imageBlob: Blob }) => void} options.onSelectExample
   * @param {(payload: { category: object }) => void} options.onSelectCustomUpload
   * @param {() => void} options.onDirectCustomUpload
   * @param {(msg: string) => void} options.onError
   */
  constructor({ onSelectExample, onSelectCustomUpload, onDirectCustomUpload, onError }) {
    this.onSelectExample = onSelectExample;
    this.onSelectCustomUpload = onSelectCustomUpload;
    this.onDirectCustomUpload = onDirectCustomUpload;
    this.onError = onError;

    this.categories = [];
    this.allImages = [];
    this.activeCategory = null;
    this.selectedImage = null;
    this.currentViewMode = "gallery"; // "gallery" (default) or "categories"
    this.currentCategoryFilter = "all";
    this.searchQuery = "";
    this.isProceeding = false;

    // View containers
    this.viewContainer = document.getElementById("view-categories");
    this.introCard = document.getElementById("category-intro-panel");
    this.cardsGrid = document.getElementById("category-cards-grid");
    this.detailPanel = document.getElementById("category-detail-panel");

    // Opening Gallery elements
    this.openingGalleryControls = document.getElementById("opening-view-controls");
    this.openingGallerySection = document.getElementById("opening-gallery-section");
    this.openingExamplesGallery = document.getElementById("opening-examples-gallery");
    this.tabModeGallery = document.getElementById("tab-mode-gallery");
    this.tabModeCategories = document.getElementById("tab-mode-categories");
    this.totalExamplesCount = document.getElementById("total-examples-count");
    this.totalCategoriesCount = document.getElementById("total-categories-count");
    this.categoryFilterBar = document.getElementById("category-filter-bar");
    this.filterChipsList = document.getElementById("filter-chips-list");
    this.galleryVisibleCount = document.getElementById("gallery-visible-count");
    this.gallerySearchInput = document.getElementById("gallery-search-input");
    this.btnClearSearch = document.getElementById("btn-clear-search");

    // Observation Lightbox Preview Modal elements
    this.obsPreviewModal = document.getElementById("observation-preview-modal");
    this.modalObsImg = document.getElementById("modal-obs-img");
    this.modalObsTitle = document.getElementById("modal-obs-title");
    this.modalObsMission = document.getElementById("modal-obs-mission");
    this.modalImageMeta = document.getElementById("modal-image-meta");
    this.modalScienceBadge = document.getElementById("modal-science-badge");
    this.modalScienceChips = document.getElementById("modal-science-chips");
    this.modalObsDesc = document.getElementById("modal-obs-desc");
    this.modalObsVoice = document.getElementById("modal-obs-voice");
    this.modalObsVariable = document.getElementById("modal-obs-variable");
    this.modalObsTechnique = document.getElementById("modal-obs-technique");
    this.modalObsAcousticConcept = document.getElementById("modal-obs-acoustic-concept");
    this.modalSoundMappingsContainer = document.getElementById("modal-sound-mappings-container");
    this.modalLegendSection = document.getElementById("modal-legend-section");
    this.modalLegendBadge = document.getElementById("modal-legend-badge");
    this.modalLegendImgWrap = document.getElementById("modal-legend-img-wrap");
    this.modalLegendImg = document.getElementById("modal-legend-img");
    this.modalLegendNotes = document.getElementById("modal-legend-notes");
    this.btnModalSonifyNow = document.getElementById("btn-modal-sonify-now");
    this.btnCloseObsModal = document.getElementById("btn-close-obs-modal");
    this.previewActiveCategory = null;
    this.previewActiveItem = null;

    // Detail panel elements
    this.btnBackToCategories = document.getElementById("btn-back-to-categories");
    this.detailTitle = document.getElementById("cat-detail-title");
    this.legendBadge = document.getElementById("cat-legend-badge");
    this.catScienceChips = document.getElementById("cat-science-chips");
    this.catLegendBadgeType = document.getElementById("cat-legend-badge-type");
    this.detailDesc = document.getElementById("cat-detail-desc");
    this.btnToggleMarkdown = document.getElementById("btn-toggle-info-md");
    this.fullMarkdown = document.getElementById("cat-full-markdown");

    // Legend elements
    this.legendImageWrap = document.getElementById("cat-legend-image-wrap");
    this.legendImg = document.getElementById("cat-legend-img");
    this.legendNotes = document.getElementById("cat-legend-notes");
    this.noLegendNotice = document.getElementById("cat-no-legend-notice");

    // Sonification concept elements
    this.sonificationDesc = document.getElementById("cat-sonification-desc");
    this.sonificationTechniqueBadge = document.getElementById("cat-sonification-technique-badge");
    this.predefinedBadgesContainer = document.getElementById("cat-predefined-badges");
    this.soundMappingsContainer = document.getElementById("cat-sound-mappings-container");

    // Detail Gallery elements
    this.exampleCount = document.getElementById("cat-example-count");
    this.examplesGallery = document.getElementById("cat-examples-gallery");
    this.btnSonifyExample = document.getElementById("btn-sonify-selected-example");
    this.btnUploadForCategory = document.getElementById("btn-upload-for-category");
    this.btnQuickUpload = document.getElementById("btn-quick-custom-upload");

    // Custom Image Type Selection elements (Screen 1B)
    this.customTypeSection = document.getElementById("view-custom-upload-type");
    this.customTypeGrid = document.getElementById("custom-type-grid");
    this.customTypeDecisionPanel = document.getElementById("custom-type-decision-panel");
    this.btnBackFromTypeSelect = document.getElementById("btn-back-from-type-select");
    this.btnProceedToCustomUpload = document.getElementById("btn-proceed-to-custom-upload");
    this.selectedCustomType = null;

    this._initEvents();
  }

  _initEvents() {
    if (this.btnBackToCategories) {
      this.btnBackToCategories.addEventListener("click", () => this.showCategoryList());
    }

    if (this.btnBackFromTypeSelect) {
      this.btnBackFromTypeSelect.addEventListener("click", () => this.showCategoryList());
    }

    if (this.btnProceedToCustomUpload) {
      this.btnProceedToCustomUpload.addEventListener("click", () => this.proceedToCustomUpload());
    }

    if (this.tabModeGallery) {
      this.tabModeGallery.addEventListener("click", () => this.setViewMode("gallery"));
    }

    if (this.tabModeCategories) {
      this.tabModeCategories.addEventListener("click", () => this.setViewMode("categories"));
    }

    const modeTabs = [this.tabModeGallery, this.tabModeCategories].filter(Boolean);
    modeTabs.forEach((tab, idx) => {
      tab.addEventListener("keydown", (e) => {
        let targetIdx = null;
        if (e.key === "ArrowRight") {
          targetIdx = (idx + 1) % modeTabs.length;
        } else if (e.key === "ArrowLeft") {
          targetIdx = (idx - 1 + modeTabs.length) % modeTabs.length;
        }
        if (targetIdx !== null) {
          e.preventDefault();
          modeTabs[targetIdx].focus();
          modeTabs[targetIdx].click();
        }
      });
    });

    if (this.gallerySearchInput) {
      this.gallerySearchInput.addEventListener("input", (e) => {
        this.searchQuery = e.target.value.trim();
        if (this.btnClearSearch) {
          this.btnClearSearch.classList.toggle("hidden", this.searchQuery.length === 0);
        }
        this.renderOpeningGallery();
      });
    }

    if (this.btnClearSearch) {
      this.btnClearSearch.addEventListener("click", () => {
        this.searchQuery = "";
        if (this.gallerySearchInput) {
          this.gallerySearchInput.value = "";
          this.gallerySearchInput.focus();
        }
        this.btnClearSearch.classList.add("hidden");
        this.renderOpeningGallery();
      });
    }

    if (this.btnCloseObsModal) {
      this.btnCloseObsModal.addEventListener("click", () => this.closePreviewModal());
    }

    if (this.obsPreviewModal) {
      this.obsPreviewModal.addEventListener("click", (e) => {
        if (e.target === this.obsPreviewModal) {
          this.closePreviewModal();
        }
      });
    }

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.obsPreviewModal && !this.obsPreviewModal.classList.contains("hidden")) {
        this.closePreviewModal();
      }
    });

    if (this.btnModalSonifyNow) {
      this.btnModalSonifyNow.addEventListener("click", () => {
        if (this.previewActiveCategory && this.previewActiveItem) {
          const cat = this.previewActiveCategory;
          const item = this.previewActiveItem;
          this.closePreviewModal();
          this.proceedWithImage(cat, item, null);
        }
      });
    }

    if (this.btnQuickUpload) {
      this.btnQuickUpload.addEventListener("click", () => {
        this.showCustomTypeSelection();
        if (this.onDirectCustomUpload) this.onDirectCustomUpload();
      });
    }

    if (this.btnUploadForCategory) {
      this.btnUploadForCategory.addEventListener("click", () => {
        if (this.activeCategory && this.onSelectCustomUpload) {
          this.onSelectCustomUpload({ category: this.activeCategory });
        }
      });
    }

    if (this.btnSonifyExample) {
      this.btnSonifyExample.addEventListener("click", () => this.handleProceedWithSelected());
    }

    if (this.btnToggleMarkdown) {
      this.btnToggleMarkdown.addEventListener("click", () => {
        const isExpanded = this.btnToggleMarkdown.getAttribute("aria-expanded") === "true";
        this.btnToggleMarkdown.setAttribute("aria-expanded", String(!isExpanded));
        if (this.fullMarkdown) {
          this.fullMarkdown.classList.toggle("hidden", isExpanded);
          this.fullMarkdown.setAttribute("aria-hidden", String(isExpanded));
        }
        this.btnToggleMarkdown.textContent = isExpanded
          ? "View Full Scientific Notes ▾"
          : "Hide Full Scientific Notes ▴";
      });
    }
  }

  async load() {
    try {
      const data = await getCategories();
      this.categories = Array.isArray(data) ? data : [];

      // Collate all preloaded images across categories
      this.allImages = [];
      this.categories.forEach((cat) => {
        if (Array.isArray(cat.images)) {
          cat.images.forEach((img) => {
            this.allImages.push({
              ...img,
              category: cat,
            });
          });
        }
      });

      // Update counts
      if (this.totalExamplesCount) {
        this.totalExamplesCount.textContent = String(this.allImages.length);
      }
      if (this.totalCategoriesCount) {
        this.totalCategoriesCount.textContent = String(this.categories.length);
      }

      this.renderFilterChips();
      this.renderOpeningGallery();
      this.renderCategoryCards();
      this.setViewMode(this.currentViewMode);
    } catch (err) {
      if (this.cardsGrid) {
        this.cardsGrid.innerHTML = `
          <div class="empty-state error-state">
            <p>Failed to load dataset categories from backend: ${err.message}</p>
          </div>
        `;
      }
      if (this.openingExamplesGallery) {
        this.openingExamplesGallery.innerHTML = `
          <div class="empty-state error-state">
            <p>Failed to load preloaded images: ${err.message}</p>
          </div>
        `;
      }
      if (this.onError) {
        this.onError("Could not discover dataset categories.");
      }
    }
  }

  setViewMode(mode) {
    this.currentViewMode = mode;
    const isGallery = mode === "gallery";

    if (this.tabModeGallery) {
      this.tabModeGallery.classList.toggle("active", isGallery);
      this.tabModeGallery.setAttribute("aria-selected", String(isGallery));
    }
    if (this.tabModeCategories) {
      this.tabModeCategories.classList.toggle("active", !isGallery);
      this.tabModeCategories.setAttribute("aria-selected", String(!isGallery));
    }

    if (this.openingGallerySection) {
      this.openingGallerySection.classList.toggle("hidden", !isGallery);
    }
    if (this.cardsGrid) {
      this.cardsGrid.classList.toggle("hidden", isGallery);
    }
    if (this.categoryFilterBar) {
      this.categoryFilterBar.classList.toggle("hidden", !isGallery);
    }

    if (this.detailPanel) {
      this.detailPanel.classList.add("hidden");
    }
    if (this.customTypeSection) {
      this.customTypeSection.classList.add("hidden");
    }
    if (this.introCard) {
      this.introCard.classList.remove("hidden");
    }
    if (this.openingGalleryControls) {
      this.openingGalleryControls.classList.remove("hidden");
    }
  }

  _attachFilterChipsKeyNav() {
    if (!this.filterChipsList) return;
    const chips = Array.from(this.filterChipsList.querySelectorAll(".filter-chip"));
    chips.forEach((chip, idx) => {
      chip.addEventListener("keydown", (e) => {
        let nextIdx = null;
        if (e.key === "ArrowRight" || e.key === "ArrowDown") {
          nextIdx = (idx + 1) % chips.length;
        } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
          nextIdx = (idx - 1 + chips.length) % chips.length;
        } else if (e.key === "Home") {
          nextIdx = 0;
        } else if (e.key === "End") {
          nextIdx = chips.length - 1;
        }
        if (nextIdx !== null) {
          e.preventDefault();
          chips[nextIdx].focus();
          chips[nextIdx].click();
        }
      });
    });
  }

  renderFilterChips() {
    if (!this.filterChipsList) return;
    this.filterChipsList.innerHTML = "";

    // "All Imagery" chip
    const allChip = document.createElement("button");
    allChip.type = "button";
    allChip.className = `filter-chip ${this.currentCategoryFilter === "all" ? "active" : ""}`;
    allChip.setAttribute("role", "radio");
    allChip.setAttribute("aria-checked", String(this.currentCategoryFilter === "all"));
    allChip.setAttribute("aria-label", `All Imagery: ${this.allImages.length} observations`);
    allChip.title = `All Imagery (${this.allImages.length} observations)`;
    allChip.innerHTML = `<span class="chip-text">All Imagery</span> <span class="chip-count">${this.allImages.length}</span>`;
    allChip.addEventListener("click", () => {
      this.currentCategoryFilter = "all";
      this.setViewMode("gallery");
      this.renderFilterChips();
      this.renderOpeningGallery();
    });
    this.filterChipsList.appendChild(allChip);

    // Per-category chips
    this.categories.forEach((cat) => {
      const imgCount = Array.isArray(cat.images) ? cat.images.length : 0;
      if (imgCount === 0) return;

      const isSelected = this.currentCategoryFilter === cat.id;
      const shortLabel = formatCategoryFilterLabel(cat);

      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = `filter-chip ${isSelected ? "active" : ""}`;
      chip.setAttribute("role", "radio");
      chip.setAttribute("aria-checked", String(isSelected));
      chip.setAttribute("aria-label", `${shortLabel}: ${imgCount} observation${imgCount === 1 ? "" : "s"}`);
      chip.title = `${cat.title} (${imgCount} observation${imgCount === 1 ? "" : "s"})`;
      chip.innerHTML = `<span class="chip-text">${shortLabel}</span> <span class="chip-count">${imgCount}</span>`;

      chip.addEventListener("click", () => {
        this.currentCategoryFilter = isSelected ? "all" : cat.id;
        this.setViewMode("gallery");
        this.renderFilterChips();
        this.renderOpeningGallery();
      });

      this.filterChipsList.appendChild(chip);
    });

    this._attachFilterChipsKeyNav();
  }

  renderOpeningGallery() {
    if (!this.openingExamplesGallery) return;
    this.openingExamplesGallery.innerHTML = "";

    const search = (this.searchQuery || "").toLowerCase();
    const filtered = this.allImages.filter((item) => {
      const cat = item.category;
      if (this.currentCategoryFilter !== "all" && cat && cat.id !== this.currentCategoryFilter) {
        return false;
      }
      if (!search) return true;
      const displayTitle = formatObservationDisplayTitle(item.title, item.filename).toLowerCase();
      const mission = getMissionLabel(item.filename, cat?.id || "").toLowerCase();
      const catTitle = (cat?.title || "").toLowerCase();
      const fname = (item.filename || "").toLowerCase();
      return (
        displayTitle.includes(search) ||
        mission.includes(search) ||
        catTitle.includes(search) ||
        fname.includes(search)
      );
    });

    if (this.galleryVisibleCount) {
      this.galleryVisibleCount.textContent = String(filtered.length);
    }

    if (filtered.length === 0) {
      this.openingExamplesGallery.innerHTML = `
        <div class="empty-state">
          <p>No preloaded observations match "${this.searchQuery || this.currentCategoryFilter}".</p>
          <button type="button" class="btn btn-sm btn-secondary" id="btn-reset-gallery-search">
            Reset Filters &amp; Search
          </button>
        </div>
      `;
      const btnReset = document.getElementById("btn-reset-gallery-search");
      if (btnReset) {
        btnReset.addEventListener("click", () => {
          this.searchQuery = "";
          this.currentCategoryFilter = "all";
          if (this.gallerySearchInput) this.gallerySearchInput.value = "";
          if (this.btnClearSearch) this.btnClearSearch.classList.add("hidden");
          this.renderFilterChips();
          this.renderOpeningGallery();
        });
      }
      return;
    }

    filtered.forEach((item) => {
      const cat = item.category;
      const card = document.createElement("article");
      card.className = "opening-example-card";
      card.tabIndex = 0;
      card.setAttribute("role", "radio");
      card.setAttribute("aria-checked", "false");
      const displayTitle = formatObservationDisplayTitle(item.title, item.filename);
      const mission = getMissionLabel(item.filename, cat.id);
      card.setAttribute("aria-label", `NASA observation: ${displayTitle} (${cat.title})`);

      const icon = getCategoryIcon(cat.id);
      const legendBadgeClass = cat.has_legend ? "badge-legend-yes" : "badge-legend-no";
      const legendBadgeText = cat.has_legend ? "Colorbar Legend" : "Spatial / Direct";

      // Parameter summary
      let paramSummary = cat.title;
      let voiceSummary = (cat.predefined_config?.instrument_family || "pad").toUpperCase() + " Synth";
      if (cat.predefined_config) {
        paramSummary = `${cat.predefined_config.label} (${cat.predefined_config.vmin} to ${cat.predefined_config.vmax} ${cat.predefined_config.units})`;
      }

      card.innerHTML = `
        <div class="opening-thumb-wrap">
          <img src="${item.thumb_url}" alt="${displayTitle}" class="opening-thumb-img" loading="lazy">
          <div class="opening-card-overlay-badges">
            <span class="badge badge-cat-chip">${cat.title}</span>
            <span class="badge ${legendBadgeClass}">${legendBadgeText}</span>
          </div>
          <button type="button" class="btn-quick-inspect" aria-label="Inspect high-res preview of ${displayTitle}">
            Inspect
          </button>
        </div>
        <div class="opening-card-content">
          <span class="opening-mission-tag" title="${mission}">${mission}</span>
          <h4 class="opening-card-title" title="${displayTitle}">${displayTitle}</h4>
          <div class="opening-card-meta">
            <span class="meta-tag meta-var" title="${paramSummary}">${paramSummary}</span>
            <span class="meta-tag meta-sound">${voiceSummary}</span>
          </div>
        </div>
        <div class="opening-card-actions">
          <button type="button" class="btn btn-primary btn-sm btn-sonify-card" aria-label="Sonify ${displayTitle} now">
            <span class="btn-icon-symbol"></span> Sonify Now
          </button>
          <button type="button" class="btn btn-secondary btn-sm btn-detail-card" aria-label="View preview and details for ${displayTitle}">
            <span class="btn-icon-symbol"></span> Science &amp; Details
          </button>
        </div>
      `;

      const btnSonify = card.querySelector(".btn-sonify-card");
      const btnDetail = card.querySelector(".btn-detail-card");
      const btnQuickInspect = card.querySelector(".btn-quick-inspect");

      const triggerSonify = () => {
        this.proceedWithImage(cat, item, btnSonify);
      };

      if (btnSonify) {
        btnSonify.addEventListener("click", (e) => {
          e.stopPropagation();
          triggerSonify();
        });
      }

      if (btnDetail) {
        btnDetail.addEventListener("click", (e) => {
          e.stopPropagation();
          this.openPreviewModal(cat, item);
        });
      }

      if (btnQuickInspect) {
        btnQuickInspect.addEventListener("click", (e) => {
          e.stopPropagation();
          this.openPreviewModal(cat, item);
        });
      }

      // Card selection & keyboard triggers
      card.addEventListener("click", () => {
        this.openingExamplesGallery.querySelectorAll(".opening-example-card").forEach((c) => {
          c.classList.remove("selected");
          c.setAttribute("aria-checked", "false");
        });
        card.classList.add("selected");
        card.setAttribute("aria-checked", "true");
      });

      card.addEventListener("dblclick", () => {
        triggerSonify();
      });

      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          triggerSonify();
        }
      });

      this.openingExamplesGallery.appendChild(card);
    });
  }

  openPreviewModal(category, item) {
    if (!this.obsPreviewModal) return;
    this.previewActiveCategory = category;
    this.previewActiveItem = item;

    const displayTitle = formatObservationDisplayTitle(item.title, item.filename);
    const mission = getMissionLabel(item.filename, category.id);
    const meta = getCategoryScientificMeta(category);

    if (this.modalObsTitle) this.modalObsTitle.textContent = displayTitle;
    if (this.modalObsMission) this.modalObsMission.textContent = mission;

    if (this.modalObsImg) {
      this.modalObsImg.src = item.thumb_url;
      this.modalObsImg.alt = displayTitle;
    }

    if (this.modalImageMeta) {
      const resMeta = formatImageResolutionMeta(item.filename);
      this.modalImageMeta.innerHTML = `
        <div class="meta-file-row">
          <span class="meta-file-name" title="${item.filename}">${item.filename}</span>
          <span class="badge badge-meta-sub">${resMeta}</span>
        </div>
      `;
    }

    // 1. Scientific Context & Mission Card
    if (this.modalScienceBadge) {
      this.modalScienceBadge.textContent = meta.model ? meta.model.split("(")[0].trim() : "NASA Earth Observing";
    }
    if (this.modalScienceChips) {
      this.modalScienceChips.innerHTML = `
        <span class="meta-chip"><strong>Model:</strong> ${meta.model}</span>
        <span class="meta-chip"><strong>Domain:</strong> ${meta.domain}</span>
        <span class="meta-chip"><strong>Variables:</strong> ${meta.variables}</span>
        <span class="meta-chip"><strong>Snapshot:</strong> ${meta.snapshot}</span>
      `;
    }
    if (this.modalObsDesc) {
      this.modalObsDesc.innerHTML = formatScientificDescriptionHtml(category.description);
    }

    // 2. Color Legend Definition Card
    if (this.modalLegendSection) {
      if (category.has_legend) {
        if (this.modalLegendImgWrap) this.modalLegendImgWrap.classList.remove("hidden");
        if (this.modalLegendImg) {
          const encodedId = encodeURIComponent(category.id);
          this.modalLegendImg.src = `/api/categories/${encodedId}/legend`;
          this.modalLegendImg.alt = `Colorbar legend for ${category.title}`;
        }
        if (this.modalLegendBadge) {
          this.modalLegendBadge.textContent = "Calibrated Gradient Scale";
        }
      } else {
        if (this.modalLegendImgWrap) this.modalLegendImgWrap.classList.add("hidden");
        if (this.modalLegendBadge) {
          this.modalLegendBadge.textContent = "Rule-Based Spatial Mapping";
        }
      }

      if (this.modalLegendNotes) {
        this.modalLegendNotes.innerHTML = formatColorLegendCardHtml(category, category.legend_info);
      }
      this.modalLegendSection.classList.remove("hidden");
    }

    // 3. Acoustic Translation Card
    const p = category.predefined_config;
    if (this.modalObsVoice) {
      this.modalObsVoice.textContent = (p?.instrument_family || "Pad").toUpperCase() + " Synthesizer";
    }
    if (this.modalObsVariable) {
      this.modalObsVariable.textContent = p ? `${p.label} (${p.vmin} to ${p.vmax} ${p.units})` : category.title;
    }
    if (this.modalObsTechnique) {
      this.modalObsTechnique.textContent = category.sonification_technique || "Spatial Grid & Luminance Mapping";
    }
    if (this.modalObsAcousticConcept) {
      this.modalObsAcousticConcept.textContent =
        category.sonification_description ||
        category.sonification_concept ||
        "Data values are mapped to pitch, timbre, and stereo panning using Earth Jukebox's rigorous sonification engine.";
    }
    if (this.modalSoundMappingsContainer) {
      this.modalSoundMappingsContainer.innerHTML = formatSoundMappingsHtml(category);
    }

    this.obsPreviewModal.classList.remove("hidden");
    this.obsPreviewModal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
    if (this.btnCloseObsModal) this.btnCloseObsModal.focus();
  }

  closePreviewModal() {
    if (!this.obsPreviewModal) return;
    this.obsPreviewModal.classList.add("hidden");
    this.obsPreviewModal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
  }

  async proceedWithImage(category, image, buttonEl) {
    if (this.isProceeding) return;
    this.isProceeding = true;

    let originalText = "";
    if (buttonEl) {
      originalText = buttonEl.textContent;
      buttonEl.disabled = true;
      buttonEl.textContent = "Loading…";
    }

    try {
      const blob = await fetchCategoryImageBlob(category.id, image.filename);
      if (this.onSelectExample) {
        this.onSelectExample({
          category,
          image,
          imageBlob: blob,
        });
      }
    } catch (err) {
      if (this.onError) {
        this.onError(`Failed to load selected image: ${err.message}`);
      }
    } finally {
      this.isProceeding = false;
      if (buttonEl) {
        buttonEl.disabled = false;
        buttonEl.textContent = originalText;
      }
    }
  }

  renderCategoryCards() {
    if (!this.cardsGrid) return;
    this.cardsGrid.innerHTML = "";

    if (this.categories.length === 0) {
      this.cardsGrid.innerHTML = `
        <div class="empty-state">
          <p>No dataset categories found in dataset/ folder.</p>
        </div>
      `;
      return;
    }

    this.categories.forEach((cat) => {
      const card = document.createElement("article");
      card.className = "category-card";
      card.tabIndex = 0;
      card.setAttribute("role", "button");
      card.setAttribute("aria-label", `Select category ${cat.title}`);

      const icon = getCategoryIcon(cat.id);
      const legendBadgeClass = cat.has_legend ? "badge-legend-yes" : "badge-legend-no";
      const legendBadgeText = cat.has_legend ? "Colorbar Legend" : "Direct / Spatial";

      const firstImage = cat.images && cat.images.length > 0 ? cat.images[0] : null;
      const coverHtml = firstImage
        ? `<div class="category-card-cover-wrap">
             <img src="${firstImage.thumb_url}" alt="Preview for ${cat.title}" class="category-cover-img" loading="lazy">
             <span class="cover-gradient-overlay" aria-hidden="true"></span>
           </div>`
        : "";

      card.innerHTML = `
        ${coverHtml}
        <div class="category-card-inner">
          <div class="category-card-header">
            <span class="category-icon" aria-hidden="true"></span>
            <span class="badge ${legendBadgeClass}">${legendBadgeText}</span>
          </div>
          <h3 class="category-card-title">${cat.title}</h3>
          <p class="category-card-desc">${cat.description || "Scientific data from NASA observations."}</p>
          ${
            cat.predefined_config
              ? `<div class="category-card-config-pill">
                   <span>${cat.predefined_config.label}</span> •
                   <strong>${cat.predefined_config.vmin} to ${cat.predefined_config.vmax} ${cat.predefined_config.units}</strong>
                 </div>`
              : ""
          }
          <div class="category-card-footer">
            <span class="category-card-count">${cat.image_count} preloaded example${cat.image_count === 1 ? "" : "s"}</span>
            <span class="category-card-action">Select Category &amp; Explore →</span>
          </div>
        </div>
      `;

      const selectAction = () => this.selectCategory(cat);
      card.addEventListener("click", selectAction);
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          selectAction();
        }
      });

      this.cardsGrid.appendChild(card);
    });
  }

  selectCategory(category, preselectedImage = null) {
    this.activeCategory = category;
    this.selectedImage = preselectedImage;

    if (this.btnSonifyExample) {
      if (preselectedImage) {
        this.btnSonifyExample.removeAttribute("aria-disabled");
        this.btnSonifyExample.classList.remove("disabled");
      } else {
        this.btnSonifyExample.setAttribute("aria-disabled", "true");
        this.btnSonifyExample.classList.add("disabled");
      }
    }

    // Switch view sections
    if (this.introCard) this.introCard.classList.add("hidden");
    if (this.openingGalleryControls) this.openingGalleryControls.classList.add("hidden");
    if (this.openingGallerySection) this.openingGallerySection.classList.add("hidden");
    if (this.cardsGrid) this.cardsGrid.classList.add("hidden");
    if (this.detailPanel) this.detailPanel.classList.remove("hidden");

    // Populate Category Details
    if (this.detailTitle) this.detailTitle.textContent = category.title;
    const meta = getCategoryScientificMeta(category);
    if (this.catScienceChips) {
      this.catScienceChips.innerHTML = `
        <span class="meta-chip"><strong>Model:</strong> ${meta.model}</span>
        <span class="meta-chip"><strong>Domain:</strong> ${meta.domain}</span>
        <span class="meta-chip"><strong>Variables:</strong> ${meta.variables}</span>
        <span class="meta-chip"><strong>Snapshot:</strong> ${meta.snapshot}</span>
      `;
    }
    if (this.detailDesc) {
      this.detailDesc.innerHTML = formatScientificDescriptionHtml(category.description);
    }

    // Legend badge
    if (this.legendBadge) {
      this.legendBadge.textContent = category.has_legend ? "Colorbar Legend Included" : "Direct / Spatial Sonification";
      this.legendBadge.className = category.has_legend ? "badge badge-legend-yes" : "badge badge-legend-no";
    }
    if (this.catLegendBadgeType) {
      this.catLegendBadgeType.textContent = category.has_legend ? "Colorimetric Scale" : "Rule-Based Spatial";
    }

    // Markdown notes expander
    if (this.fullMarkdown) {
      this.fullMarkdown.innerHTML = formatMarkdownToHtml(category.info_markdown || "");
      this.fullMarkdown.classList.add("hidden");
      this.fullMarkdown.setAttribute("aria-hidden", "true");
    }
    if (this.btnToggleMarkdown) {
      this.btnToggleMarkdown.setAttribute("aria-expanded", "false");
      this.btnToggleMarkdown.textContent = "View Full Scientific Notes ▾";
    }

    // Optional Legend Display
    if (category.has_legend && category.legend_url) {
      if (this.legendImageWrap) this.legendImageWrap.classList.remove("hidden");
      if (this.legendImg) {
        this.legendImg.src = category.legend_url;
        this.legendImg.alt = `Colorbar legend for ${category.title}`;
      }
      if (this.legendNotes) {
        this.legendNotes.innerHTML = formatColorLegendCardHtml(category, category.legend_info);
      }
      if (this.noLegendNotice) this.noLegendNotice.classList.add("hidden");
    } else {
      if (this.legendImageWrap) this.legendImageWrap.classList.add("hidden");
      if (this.legendImg) {
        this.legendImg.src = "";
        this.legendImg.alt = "";
      }
      if (this.legendNotes) {
        this.legendNotes.innerHTML = formatColorLegendCardHtml(category, category.legend_info);
      }
      if (this.noLegendNotice) this.noLegendNotice.classList.remove("hidden");
    }

    // Sonification Concept & Technique
    if (this.sonificationTechniqueBadge) {
      this.sonificationTechniqueBadge.textContent = category.sonification_technique || "Scientific Sonification";
    }
    if (this.sonificationDesc) {
      this.sonificationDesc.textContent =
        category.sonification_description ||
        category.sonification_concept ||
        "Data values are mapped to pitch, timbre, and stereo panning using Earth Jukebox's rigorous sonification engine.";
    }

    // Predefined configuration badges
    if (this.predefinedBadgesContainer) {
      this.predefinedBadgesContainer.innerHTML = "";
      const p = category.predefined_config;
      if (p) {
        const items = [
          { label: "Variable", val: p.label },
          {
            label: "Range",
            val: `${p.vmin} to ${p.vmax} ${p.units}` + (p.center !== null && p.center !== undefined ? ` (Center: ${p.center})` : ""),
          },
          { label: "Voice", val: (p.instrument_family || "pad").toUpperCase() },
          { label: "Colormap", val: p.kind },
        ];
        items.forEach((item) => {
          const chip = document.createElement("div");
          chip.className = "predefined-chip";
          chip.innerHTML = `<span class="chip-label">${item.label}:</span> <strong class="chip-val">${item.val}</strong>`;
          this.predefinedBadgesContainer.appendChild(chip);
        });
      }
    }

    // Data-to-sound mappings table
    if (this.soundMappingsContainer) {
      this.soundMappingsContainer.innerHTML = "";
      const mappings = Array.isArray(category.sound_mappings) ? category.sound_mappings : [];
      if (mappings.length > 0) {
        const table = document.createElement("table");
        table.className = "sound-mapping-table";
        table.setAttribute("aria-label", `Data to sound mapping specification for ${category.title}`);
        table.innerHTML = `
          <thead>
            <tr>
              <th scope="col">Scientific Data Feature</th>
              <th scope="col">Sound Feature / Parameter</th>
              <th scope="col">Sonification Technique</th>
            </tr>
          </thead>
          <tbody>
            ${mappings
              .map(
                (m) => `
              <tr>
                <td><strong>${m.data_characteristic}</strong></td>
                <td><span class="badge-sound">${m.sound_parameter}</span></td>
                <td>
                  <div>${m.technique}</div>
                  <small class="mapping-detail">${m.detail}</small>
                </td>
              </tr>
            `
              )
              .join("")}
          </tbody>
        `;
        this.soundMappingsContainer.appendChild(table);
      }
    }

    // Render Example Gallery
    this.renderExampleGallery(category, preselectedImage);

    // Scroll to detail top
    if (this.detailPanel) {
      this.detailPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  renderExampleGallery(category, preselectedImage = null) {
    if (!this.examplesGallery) return;
    this.examplesGallery.innerHTML = "";

    const images = Array.isArray(category.images) ? category.images : [];
    if (this.exampleCount) {
      this.exampleCount.textContent = String(images.length);
    }

    if (images.length === 0) {
      this.examplesGallery.innerHTML = `
        <div class="empty-state">
          <p>No preloaded example images found in this category.</p>
        </div>
      `;
      return;
    }

    const isSingleImage = images.length === 1;

    images.forEach((img, idx) => {
      const isSelected = preselectedImage ? preselectedImage.filename === img.filename : idx === 0;
      const displayTitle = formatObservationDisplayTitle(img.title, img.filename);
      const mission = getMissionLabel(img.filename, category.id);

      const item = document.createElement("div");
      item.className = `example-gallery-card ${isSingleImage ? "featured-single-card" : ""} ${isSelected ? "selected" : ""}`;
      item.setAttribute("role", "radio");
      item.setAttribute("aria-checked", String(isSelected));
      item.setAttribute("tabindex", "0");
      item.setAttribute("aria-label", `Observation: ${displayTitle}`);

      item.innerHTML = `
        <div class="example-thumb-wrap">
          <img src="${img.thumb_url}" alt="${displayTitle}" class="example-thumb-img" loading="lazy">
        </div>
        <div class="example-info">
          <span class="example-mission-sub">${mission}</span>
          <strong class="example-title" title="${displayTitle}">${displayTitle}</strong>
          <span class="example-filename">${img.filename}</span>
          ${
            isSingleImage
              ? `<div class="featured-card-badge">Featured Preloaded NASA Observation</div>`
              : ""
          }
        </div>
      `;

      const selectImg = () => {
        this.examplesGallery.querySelectorAll(".example-gallery-card").forEach((c) => {
          c.classList.remove("selected");
          c.setAttribute("aria-checked", "false");
        });

        item.classList.add("selected");
        item.setAttribute("aria-checked", "true");
        this.selectedImage = img;

        if (this.btnSonifyExample) {
          this.btnSonifyExample.removeAttribute("aria-disabled");
          this.btnSonifyExample.classList.remove("disabled");
          this.btnSonifyExample.focus();
        }
      };

      item.addEventListener("click", selectImg);
      item.addEventListener("dblclick", () => {
        selectImg();
        this.handleProceedWithSelected();
      });
      item.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          selectImg();
        }
      });

      this.examplesGallery.appendChild(item);

      if (isSelected) {
        this.selectedImage = img;
        if (this.btnSonifyExample) {
          this.btnSonifyExample.removeAttribute("aria-disabled");
          this.btnSonifyExample.classList.remove("disabled");
        }
      }
    });
  }

  async handleProceedWithSelected() {
    if (!this.activeCategory || !this.selectedImage) {
      if (this.onError) this.onError("Please select an example image to continue.");
      return;
    }

    if (this.btnSonifyExample) {
      this.btnSonifyExample.disabled = true;
      this.btnSonifyExample.textContent = "Loading image…";
    }

    try {
      const blob = await fetchCategoryImageBlob(
        this.activeCategory.id,
        this.selectedImage.filename
      );

      if (this.onSelectExample) {
        this.onSelectExample({
          category: this.activeCategory,
          image: this.selectedImage,
          imageBlob: blob,
        });
      }
    } catch (err) {
      if (this.onError) {
        this.onError(`Failed to load selected image: ${err.message}`);
      }
    } finally {
      if (this.btnSonifyExample) {
        this.btnSonifyExample.disabled = false;
        this.btnSonifyExample.textContent = "Sonify Selected Image →";
      }
    }
  }

  showCategoryList(preferredMode = "gallery") {
    this.activeCategory = null;
    this.selectedImage = null;

    if (this.customTypeSection) this.customTypeSection.classList.add("hidden");
    if (this.introCard) this.introCard.classList.remove("hidden");
    if (this.openingGalleryControls) this.openingGalleryControls.classList.remove("hidden");
    if (this.detailPanel) this.detailPanel.classList.add("hidden");

    this.setViewMode(preferredMode);

    if (this.categories.length === 0) {
      this.load();
    } else {
      this.renderFilterChips();
      this.renderOpeningGallery();
      this.renderCategoryCards();
    }
  }

  showCustomTypeSelection() {
    if (this.introCard) this.introCard.classList.add("hidden");
    if (this.openingGalleryControls) this.openingGalleryControls.classList.add("hidden");
    if (this.openingGallerySection) this.openingGallerySection.classList.add("hidden");
    if (this.cardsGrid) this.cardsGrid.classList.add("hidden");
    if (this.detailPanel) this.detailPanel.classList.add("hidden");
    if (this.customTypeSection) this.customTypeSection.classList.remove("hidden");

    this.renderCustomTypeGrid();
    if (CUSTOM_IMAGE_TYPES.length > 0 && !this.selectedCustomType) {
      this.selectCustomType(CUSTOM_IMAGE_TYPES[0]);
    } else if (this.selectedCustomType) {
      this.selectCustomType(this.selectedCustomType);
    }
  }

  renderCustomTypeGrid() {
    if (!this.customTypeGrid) return;
    this.customTypeGrid.innerHTML = "";

    CUSTOM_IMAGE_TYPES.forEach((type) => {
      const card = document.createElement("article");
      card.className = "custom-type-card";
      card.tabIndex = 0;
      card.setAttribute("role", "radio");
      const isSelected = this.selectedCustomType && this.selectedCustomType.id === type.id;
      card.setAttribute("aria-checked", String(isSelected));
      if (isSelected) card.classList.add("selected");

      card.innerHTML = `
        <div class="custom-type-card-header">
          <span class="badge ${type.badgeClass}">${type.badge}</span>
        </div>
        <h3 class="custom-type-card-title">${type.title}</h3>
        <p class="custom-type-card-desc">${type.legendDecision.split(":")[1]?.trim() || type.legendDecision}</p>
        <div class="custom-type-card-meta">
          <div class="custom-type-meta-pill">
            <span class="meta-label">Range:</span>
            <strong>${type.variableRange}</strong>
          </div>
          <div class="custom-type-meta-pill">
            <span class="meta-label">Voice:</span>
            <strong>${type.synthVoice}</strong>
          </div>
        </div>
        <button type="button" class="btn btn-sm btn-outline btn-select-type" aria-label="Select ${type.title}">
          Select Category
        </button>
      `;

      const selectAction = () => {
        this.selectCustomType(type);
      };

      card.addEventListener("click", selectAction);
      card.addEventListener("dblclick", () => {
        this.selectCustomType(type);
        this.proceedToCustomUpload();
      });
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          selectAction();
        }
      });

      this.customTypeGrid.appendChild(card);
    });
  }

  selectCustomType(type) {
    this.selectedCustomType = type;
    if (this.customTypeGrid) {
      this.customTypeGrid.querySelectorAll(".custom-type-card").forEach((c, idx) => {
        const isMatch = CUSTOM_IMAGE_TYPES[idx] && CUSTOM_IMAGE_TYPES[idx].id === type.id;
        c.classList.toggle("selected", isMatch);
        c.setAttribute("aria-checked", String(isMatch));
      });
    }

    if (this.customTypeDecisionPanel) {
      this.customTypeDecisionPanel.classList.remove("hidden");
    }

    const titleEl = document.getElementById("decision-type-title");
    const badgeEl = document.getElementById("decision-legend-badge");
    const legendDescEl = document.getElementById("decision-legend-desc");
    const logicDescEl = document.getElementById("decision-logic-desc");
    const varRangeEl = document.getElementById("decision-var-range");
    const synthVoiceEl = document.getElementById("decision-synth-voice");
    const legendStatusEl = document.getElementById("decision-legend-status");
    const proceedBtn = document.getElementById("btn-proceed-to-custom-upload");

    if (titleEl) titleEl.textContent = type.title;
    if (badgeEl) {
      badgeEl.textContent = type.badge;
      badgeEl.className = `decision-badge badge ${type.badgeClass}`;
    }
    if (legendDescEl) legendDescEl.textContent = type.legendDecision;
    if (logicDescEl) logicDescEl.textContent = type.sonificationLogic;
    if (varRangeEl) varRangeEl.textContent = type.variableRange;
    if (synthVoiceEl) synthVoiceEl.textContent = type.synthVoice;
    if (legendStatusEl) {
      legendStatusEl.textContent = type.hasLegend ? "Colorbar Legend Required" : "No Legend (Direct Spatial / Events)";
    }
    if (proceedBtn) {
      proceedBtn.textContent = `Proceed to Upload ${type.title} →`;
    }
  }

  proceedToCustomUpload() {
    if (!this.selectedCustomType) return;
    const type = this.selectedCustomType;
    let matchedCat = this.categories.find(
      (c) => c.id === type.id || c.title?.toLowerCase() === type.title.toLowerCase()
    );
    if (!matchedCat) {
      matchedCat = {
        id: type.id,
        title: type.title,
        has_legend: type.hasLegend,
        description: type.legendDecision,
        predefined_config: {
          label: type.title,
          units: type.units,
          vmin: type.vmin,
          vmax: type.vmax,
          kind: type.kind,
          center: type.center,
          category: type.categoryKey,
          scale: type.scale,
          orientation: type.orientation,
          instrument_family: type.instrumentFamily,
        },
        sonification_technique: type.sonificationLogic,
      };
    }
    if (this.onSelectCustomUpload) {
      this.onSelectCustomUpload({ category: matchedCat, customType: type });
    }
  }

  show() {
    if (this.viewContainer) this.viewContainer.classList.remove("hidden");
  }

  hide() {
    if (this.viewContainer) this.viewContainer.classList.add("hidden");
  }
}
