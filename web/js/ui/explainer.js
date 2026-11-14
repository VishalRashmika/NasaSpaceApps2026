/**
 * "How to Listen" Explainer panel (F-080).
 */

import { getMapping } from "../api/client.js";

export class ExplainerUI {
  constructor(containerId = "mapping-table-container") {
    this.container = document.getElementById(containerId);
    this.mapping = null;
  }

  async load() {
    if (!this.container) return;
    try {
      this.mapping = await getMapping();
      this.render();
    } catch {
      this.container.textContent = "Unable to load mapping specification.";
    }
  }

  render() {
    if (!this.container || !this.mapping) return;

    const manifest = this.mapping.manifest || this.mapping;
    const version = this.mapping.mapping_version || "1.0.0";

    const rows = [
      { dim: "Time Axis", rule: "West to East longitude sweep (left to right across the map)" },
      { dim: "Voice / Timbre", rule: "5 latitude bands (Polar North, Mid-North, Equator, Mid-South, Polar South)" },
      { dim: "Pitch (Frequency)", rule: "Scalar data value quantized to scale degrees (higher value = higher pitch)" },
      { dim: "Tempo (BPM)", rule: "Global spatial variability (standard deviation across the field)" },
      { dim: "Rhythm & Roughness", rule: "Local spatial gradient (steeper spatial changes = denser notes & detuned texture)" },
      { dim: "Extremes Accents", rule: "Values in the top 5% of distance from center trigger accented bell doubling" },
      { dim: "Harmonic Drone", rule: "Tonic and fifth bed sounding continuously, brightness reflects mean value" },
      { dim: "Silence", rule: "Masked data (clouds, unmeasured land/sea) produces silence" },
    ];

    let html = `
      <p>Earth Jukebox sonifies the <strong>underlying physical data values</strong> recovered from NASA images (Mapping Version: <code>${version}</code>).</p>
      <table class="mapping-table">
        <thead>
          <tr>
            <th scope="col">Dimension</th>
            <th scope="col">Scientific Mapping Rule</th>
          </tr>
        </thead>
        <tbody>
    `;

    for (const r of rows) {
      html += `<tr><td><strong>${r.dim}</strong></td><td>${r.rule}</td></tr>`;
    }

    html += `
        </tbody>
      </table>
    `;

    this.container.innerHTML = html;
  }
}
