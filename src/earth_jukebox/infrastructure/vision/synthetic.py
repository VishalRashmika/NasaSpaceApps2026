"""Synthetic map generator (F-100).

Generates synthetic test images with known ground-truth scalar fields, land masks,
and drawn colorbars with exact pixel bounding boxes.
"""

from __future__ import annotations

import hashlib
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colorbar import Colorbar
from matplotlib.figure import Figure

from earth_jukebox.domain.models import (
    ColormapKind,
    GeoExtent,
    LegendSpec,
    Orientation,
    PixelBox,
    RecoveryMode,
    RecoveryQuality,
    ScalarField,
    ScaleType,
    VariableCategory,
)


def generate_map(
    cmap: str = "viridis",
    seed: int = 1,
    orientation: Orientation = Orientation.HORIZONTAL,
    vmin: float = 0.0,
    vmax: float = 100.0,
    units: str = "units",
    label: str = "Synthetic Variable",
    kind: ColormapKind | None = None,
    category: VariableCategory = VariableCategory.GENERIC,
    with_outline: bool = False,
    with_title: bool = False,
    with_margin: bool = True,
    with_graticule: bool = False,
    map_width: int = 1024,
    map_height: int = 512,
) -> tuple[bytes, ScalarField, LegendSpec, PixelBox, PixelBox]:
    """Generate synthetic map image with known ground-truth field and boxes (F-100).

    Returns:
        (png_bytes, truth_field, legend, colorbar_box, map_box)
    """
    rng = np.random.default_rng(seed)

    if kind is None:
        diverging_maps = {
            "RdBu_r",
            "coolwarm",
            "BrBG",
            "PuOr",
            "seismic",
            "RdYlBu_r",
        }
        kind = ColormapKind.DIVERGING if cmap in diverging_maps else ColormapKind.SEQUENTIAL

    center = (vmin + vmax) / 2.0 if kind == ColormapKind.DIVERGING else None

    legend = LegendSpec(
        vmin=vmin,
        vmax=vmax,
        units=units,
        label=label,
        kind=kind,
        category=category,
        center=center,
        orientation=orientation,
        low_at_start=True,
        scale=ScaleType.LINEAR,
    )

    # 1. Generate smooth analytic field (docs/05 section 11)
    # Latitude from +pi/2 (north) to -pi/2 (south); longitude from -pi to +pi
    lat_vec = np.linspace(np.pi / 2.0, -np.pi / 2.0, map_height)
    lon_vec = np.linspace(-np.pi, np.pi, map_width)
    lat_grid, lon_grid = np.meshgrid(lat_vec, lon_vec, indexing="ij")

    field = np.zeros((map_height, map_width), dtype=np.float64)
    for _ in range(4):
        a_k = float(rng.uniform(0.5, 1.5))
        lat_k = float(rng.uniform(-np.pi / 3.0, np.pi / 3.0))
        lon_k = float(rng.uniform(-2.0 * np.pi / 3.0, 2.0 * np.pi / 3.0))
        sigma_lat = float(rng.uniform(0.3, 0.8))
        sigma_lon = float(rng.uniform(0.5, 1.2))
        field += a_k * np.exp(
            -(
                (lat_grid - lat_k) ** 2 / (2.0 * sigma_lat**2)
                + (lon_grid - lon_k) ** 2 / (2.0 * sigma_lon**2)
            )
        )

    b = float(rng.uniform(0.2, 0.5))
    field += b * np.sin(lat_grid)

    # Scale to [vmin, vmax]
    f_min = float(np.min(field))
    f_max = float(np.max(field))
    if f_max > f_min:
        field = vmin + (field - f_min) / (f_max - f_min) * (vmax - vmin)
    else:
        field.fill((vmin + vmax) / 2.0)

    # 2. Land mask: two ellipses
    e1_lat = float(rng.uniform(-np.pi / 4.0, np.pi / 4.0))
    e1_lon = float(rng.uniform(-np.pi / 2.0, 0.0))
    e1_r_lat = float(rng.uniform(0.25, 0.45))
    e1_r_lon = float(rng.uniform(0.35, 0.65))

    e2_lat = float(rng.uniform(-np.pi / 4.0, np.pi / 4.0))
    e2_lon = float(rng.uniform(0.0, np.pi / 2.0))
    e2_r_lat = float(rng.uniform(0.25, 0.45))
    e2_r_lon = float(rng.uniform(0.35, 0.65))

    mask1 = ((lat_grid - e1_lat) / e1_r_lat) ** 2 + ((lon_grid - e1_lon) / e1_r_lon) ** 2 <= 1.0
    mask2 = ((lat_grid - e2_lat) / e2_r_lat) ** 2 + ((lon_grid - e2_lon) / e2_r_lon) ** 2 <= 1.0
    land = mask1 | mask2

    truth_values = field.copy()
    truth_values[land] = np.nan

    # 3. Create RGB map image
    cmap_obj = matplotlib.colormaps.get_cmap(cmap)
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    rgb_map = cmap_obj(norm(field))[:, :, :3].astype(np.float32)

    # Land drawn in neutral color #c8c8c8 (200, 200, 200)
    neutral_rgb = np.array([200.0 / 255.0, 200.0 / 255.0, 200.0 / 255.0], dtype=np.float32)
    rgb_map[land] = neutral_rgb

    # 4. Optional graticule (1-px black lines at 30° steps)
    if with_graticule:
        black = np.zeros(3, dtype=np.float32)
        for deg in (-60, -30, 0, 30, 60):
            row = round((90.0 - deg) / 180.0 * (map_height - 1))
            rgb_map[row, :] = black
        for deg in range(-150, 180, 30):
            col = round((deg + 180.0) / 360.0 * (map_width - 1))
            rgb_map[:, col] = black

    # 5. Figure layout with exact pixel sizing
    margin = 50 if with_margin else 0
    title_height = 40 if with_title else 0

    if orientation == Orientation.HORIZONTAL:
        cbar_h = 24
        cbar_w = int(map_width * 0.7)
        cbar_gap = 35
        fig_w = map_width + 2 * margin
        fig_h = title_height + map_height + cbar_gap + cbar_h + 40 + margin

        map_x = margin
        map_y = title_height + margin
        cbar_x = margin + (map_width - cbar_w) // 2
        cbar_y = map_y + map_height + cbar_gap
    else:
        cbar_w = 24
        cbar_h = int(map_height * 0.8)
        cbar_gap = 35
        fig_w = map_width + cbar_gap + cbar_w + 60 + margin
        fig_h = title_height + map_height + 2 * margin

        map_x = margin
        map_y = title_height + margin
        cbar_x = map_x + map_width + cbar_gap
        cbar_y = map_y + (map_height - cbar_h) // 2

    fig = Figure(
        figsize=(fig_w / 100.0, fig_h / 100.0),
        dpi=100.0,
        facecolor="white",
        edgecolor="none",
    )
    canvas = FigureCanvasAgg(fig)

    if with_title:
        fig.suptitle(label, y=0.97, fontsize=12, fontweight="bold")

    # Add map axes
    ax_map = fig.add_axes(
        (
            map_x / fig_w,
            (fig_h - map_y - map_height) / fig_h,
            map_width / fig_w,
            map_height / fig_h,
        )
    )
    ax_map.imshow(rgb_map, origin="upper", aspect="auto", interpolation="nearest")
    if with_outline:
        for spine in ax_map.spines.values():
            spine.set_visible(True)
            spine.set_color("black")
            spine.set_linewidth(1.0)
    else:
        ax_map.axis("off")

    # Add colorbar axes
    ax_cbar = fig.add_axes(
        (
            cbar_x / fig_w,
            (fig_h - cbar_y - cbar_h) / fig_h,
            cbar_w / fig_w,
            cbar_h / fig_h,
        )
    )
    sm = cm.ScalarMappable(norm=norm, cmap=cmap_obj)
    Colorbar(ax=ax_cbar, mappable=sm, orientation=orientation.value)
    if with_outline:
        ax_cbar.spines[:].set_visible(True)
        ax_cbar.spines[:].set_color("black")
        ax_cbar.spines[:].set_linewidth(1.0)

    canvas.draw()  # type: ignore[no-untyped-call]

    # Read pixel boxes (y=0 at top of image)
    bbox_m = ax_map.get_window_extent()
    map_box = PixelBox(
        x=round(bbox_m.x0),
        y=round(fig_h - bbox_m.y1),
        w=round(bbox_m.width),
        h=round(bbox_m.height),
    )

    bbox_c = ax_cbar.get_window_extent()
    colorbar_box = PixelBox(
        x=round(bbox_c.x0),
        y=round(fig_h - bbox_c.y1),
        w=round(bbox_c.width),
        h=round(bbox_c.height),
    )

    buf = io.BytesIO()
    canvas.print_png(buf)  # type: ignore[no-untyped-call]
    png_bytes = buf.getvalue()

    content_hash = hashlib.sha256(png_bytes).hexdigest()
    masked_fraction = float(np.isnan(truth_values).mean())
    quality = RecoveryQuality(
        mean_delta_e=0.0,
        p95_delta_e=0.0,
        masked_fraction=masked_fraction,
        lut_is_monotonic_in_lightness=True,
        confidence=1.0,
        mode=RecoveryMode.COLORBAR,
        warnings=(),
    )
    truth_field = ScalarField(
        values=truth_values,
        legend=legend,
        extent=GeoExtent(),
        quality=quality,
        source_hash=content_hash,
    )

    return png_bytes, truth_field, legend, colorbar_box, map_box
