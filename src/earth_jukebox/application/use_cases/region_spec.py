"""Manual region specification (F-005).

Validates user-supplied map and colorbar boxes, checks for image boundary containment
and overlap, and computes default map regions when omitted.
"""

from __future__ import annotations

from earth_jukebox.domain.errors import InvalidLegendError
from earth_jukebox.domain.models import PixelBox


def resolve_regions(
    img_w: int,
    img_h: int,
    map_box: PixelBox | None,
    colorbar_box: PixelBox | None,
) -> tuple[PixelBox, PixelBox | None]:
    """Validate and resolve map and colorbar boxes (F-005).

    Returns:
        (resolved_map_box, resolved_colorbar_box)
    Raises:
        InvalidLegendError if boxes lie outside image or overlap.
    """
    if img_w <= 0 or img_h <= 0:
        raise InvalidLegendError(f"invalid image dimensions {img_w}x{img_h}")

    # 1. Validate colorbar box if present
    if colorbar_box is not None and (
        colorbar_box.x < 0
        or colorbar_box.y < 0
        or colorbar_box.x + colorbar_box.w > img_w
        or colorbar_box.y + colorbar_box.h > img_h
    ):
        raise InvalidLegendError(
            f"colorbar_box {colorbar_box} exceeds image bounds ({img_w}x{img_h})"
        )

    # 2. Resolve map box
    if map_box is not None:
        if (
            map_box.x < 0
            or map_box.y < 0
            or map_box.x + map_box.w > img_w
            or map_box.y + map_box.h > img_h
        ):
            raise InvalidLegendError(f"map_box {map_box} exceeds image bounds ({img_w}x{img_h})")
        resolved_map = map_box
    else:
        # Default map region: whole image minus colorbar box minus 1% border (doc 03 F-005)
        border_x = max(1, round(img_w * 0.01))
        border_y = max(1, round(img_h * 0.01))

        if colorbar_box is None:
            resolved_map = PixelBox(
                x=border_x,
                y=border_y,
                w=img_w - 2 * border_x,
                h=img_h - 2 * border_y,
            )
        else:
            # Check where colorbar is located: bottom, right, top, or left
            c_center_x = colorbar_box.x + colorbar_box.w / 2.0
            c_center_y = colorbar_box.y + colorbar_box.h / 2.0

            if c_center_y > img_h * 0.6:  # Bottom
                resolved_map = PixelBox(
                    x=border_x,
                    y=border_y,
                    w=img_w - 2 * border_x,
                    h=max(1, colorbar_box.y - border_y),
                )
            elif c_center_x > img_w * 0.6:  # Right
                resolved_map = PixelBox(
                    x=border_x,
                    y=border_y,
                    w=max(1, colorbar_box.x - border_x),
                    h=img_h - 2 * border_y,
                )
            elif c_center_y < img_h * 0.4:  # Top
                top_y = colorbar_box.y + colorbar_box.h + border_y
                resolved_map = PixelBox(
                    x=border_x,
                    y=top_y,
                    w=img_w - 2 * border_x,
                    h=max(1, img_h - top_y - border_y),
                )
            else:  # Left
                left_x = colorbar_box.x + colorbar_box.w + border_x
                resolved_map = PixelBox(
                    x=left_x,
                    y=border_y,
                    w=max(1, img_w - left_x - border_x),
                    h=img_h - 2 * border_y,
                )

    # 3. Check overlap between map and colorbar boxes (AC2)
    if colorbar_box is not None:
        overlap = not (
            resolved_map.x + resolved_map.w <= colorbar_box.x
            or colorbar_box.x + colorbar_box.w <= resolved_map.x
            or resolved_map.y + resolved_map.h <= colorbar_box.y
            or colorbar_box.y + colorbar_box.h <= resolved_map.y
        )
        if overlap:
            raise InvalidLegendError(
                f"overlap detected between map_box {resolved_map} and colorbar_box {colorbar_box}"
            )

    return resolved_map, colorbar_box
