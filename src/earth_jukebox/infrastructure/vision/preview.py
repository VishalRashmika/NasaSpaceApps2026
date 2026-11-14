"""Field preview image generator (F-061).

Renders a 512 px wide preview PNG of a recovered ScalarField using the viridis colormap.
"""

from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
import numpy as np
from PIL import Image

from earth_jukebox.application.ports import FieldPreviewRenderer
from earth_jukebox.domain.models import ScalarField, ScaleType


class VisionFieldPreviewRenderer(FieldPreviewRenderer):
    """Renders recovered ScalarField to a viridis PNG preview (F-061)."""

    def render_preview_png(self, field: ScalarField, width: int = 512) -> bytes:
        vals = field.values.copy()
        h, w = vals.shape

        # Normalize valid values to [0, 1]
        mask = np.isnan(vals)
        if field.legend.scale == ScaleType.LOG:
            safe_vmin = max(field.legend.vmin, 1e-9)
            safe_vmax = max(field.legend.vmax, safe_vmin + 1e-9)
            log_min = np.log10(safe_vmin)
            log_max = np.log10(safe_vmax)
            log_span = max(log_max - log_min, 1e-9)

            valid_vals = np.where(mask, safe_vmin, vals)
            valid_vals = np.clip(valid_vals, safe_vmin, safe_vmax)
            norm = (np.log10(valid_vals) - log_min) / log_span
        else:
            span = max(field.legend.vmax - field.legend.vmin, 1e-9)
            valid_vals = np.where(mask, field.legend.vmin, vals)
            norm = (valid_vals - field.legend.vmin) / span

        norm = np.clip(norm, 0.0, 1.0)

        # Apply viridis colormap
        cmap = matplotlib.colormaps.get_cmap("viridis")
        rgba = cmap(norm)  # (H, W, 4), float in [0, 1]

        # Transparent for masked / NaN regions
        rgba[mask] = [0.1, 0.1, 0.1, 0.0]

        rgba_u8 = (rgba * 255).astype(np.uint8)

        # Resize to target width maintaining aspect ratio
        target_w = max(16, width)
        target_h = max(1, round(h * target_w / max(1, w)))

        img = Image.fromarray(rgba_u8, mode="RGBA")
        if (target_w, target_h) != (w, h):
            img = img.resize((target_w, target_h), Image.Resampling.BILINEAR)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
