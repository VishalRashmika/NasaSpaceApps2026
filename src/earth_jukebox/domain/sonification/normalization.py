"""F-021: Normalisation & centre handling.

Normalises physical values to u in [0, 1] per docs/06 §3:
- Sequential linear
- Sequential log (log10 space, values <= 0 treated as vmin)
- Diverging piecewise linear with effective_center -> 0.5
Also provides the inverse denormalize_u.
"""

from __future__ import annotations

import math
from typing import overload

import numpy as np

from earth_jukebox.domain.models import ColormapKind, FloatArray, LegendSpec, ScaleType


@overload
def normalize_value(v: float, legend: LegendSpec) -> float: ...


@overload
def normalize_value(v: FloatArray, legend: LegendSpec) -> FloatArray: ...


def normalize_value(v: float | FloatArray, legend: LegendSpec) -> float | FloatArray:
    """Normalise value(s) to u in [0.0, 1.0]. NaN is preserved."""
    if isinstance(v, (int, float)):
        return _normalize_scalar(float(v), legend)
    return _normalize_array(v, legend)


def _normalize_scalar(v: float, legend: LegendSpec) -> float:
    if math.isnan(v):
        return float("nan")

    vmin = legend.vmin
    vmax = legend.vmax

    if legend.scale is ScaleType.LOG:
        if v <= 0.0:
            v = vmin
        log_v = math.log10(v)
        log_vmin = math.log10(vmin)
        log_vmax = math.log10(vmax)
        u = (log_v - log_vmin) / (log_vmax - log_vmin)
        return float(np.clip(u, 0.0, 1.0))

    if legend.kind is ColormapKind.DIVERGING:
        c = legend.effective_center
        if v < c:
            u = 0.5 if c == vmin else 0.5 * (v - vmin) / (c - vmin)
        else:
            u = 0.5 if vmax == c else 0.5 + 0.5 * (v - c) / (vmax - c)
        return float(np.clip(u, 0.0, 1.0))

    # Sequential linear
    u = (v - vmin) / (vmax - vmin)
    return float(np.clip(u, 0.0, 1.0))


def _normalize_array(arr: FloatArray, legend: LegendSpec) -> FloatArray:
    vmin = legend.vmin
    vmax = legend.vmax
    out = np.full_like(arr, np.nan, dtype=np.float64)
    valid = ~np.isnan(arr)
    if not np.any(valid):
        return out

    v = arr[valid]

    if legend.scale is ScaleType.LOG:
        v_clipped = np.where(v <= 0.0, vmin, v)
        log_v = np.log10(v_clipped)
        log_vmin = math.log10(vmin)
        log_vmax = math.log10(vmax)
        u = (log_v - log_vmin) / (log_vmax - log_vmin)
        out[valid] = np.clip(u, 0.0, 1.0)
        return out

    if legend.kind is ColormapKind.DIVERGING:
        c = legend.effective_center
        u = np.empty_like(v)
        lower_mask = v < c
        upper_mask = ~lower_mask

        if c == vmin:
            u[lower_mask] = 0.5
        else:
            u[lower_mask] = 0.5 * (v[lower_mask] - vmin) / (c - vmin)

        if vmax == c:
            u[upper_mask] = 0.5
        else:
            u[upper_mask] = 0.5 + 0.5 * (v[upper_mask] - c) / (vmax - c)

        out[valid] = np.clip(u, 0.0, 1.0)
        return out

    u = (v - vmin) / (vmax - vmin)
    out[valid] = np.clip(u, 0.0, 1.0)
    return out


@overload
def denormalize_u(u: float, legend: LegendSpec) -> float: ...


@overload
def denormalize_u(u: FloatArray, legend: LegendSpec) -> FloatArray: ...


def denormalize_u(u: float | FloatArray, legend: LegendSpec) -> float | FloatArray:
    """Denormalise u in [0.0, 1.0] back to physical value(s)."""
    if isinstance(u, (int, float)):
        return _denormalize_scalar(float(u), legend)
    return _denormalize_array(u, legend)


def _denormalize_scalar(u: float, legend: LegendSpec) -> float:
    if math.isnan(u):
        return float("nan")

    vmin = legend.vmin
    vmax = legend.vmax
    u_clamped = min(max(u, 0.0), 1.0)

    if legend.scale is ScaleType.LOG:
        log_vmin = math.log10(vmin)
        log_vmax = math.log10(vmax)
        log_v = log_vmin + u_clamped * (log_vmax - log_vmin)
        return float(10.0**log_v)

    if legend.kind is ColormapKind.DIVERGING:
        c = legend.effective_center
        if u_clamped < 0.5:
            return float(vmin + (2.0 * u_clamped) * (c - vmin))
        return float(c + (2.0 * (u_clamped - 0.5)) * (vmax - c))

    return float(vmin + u_clamped * (vmax - vmin))


def _denormalize_array(arr: FloatArray, legend: LegendSpec) -> FloatArray:
    vmin = legend.vmin
    vmax = legend.vmax
    out = np.full_like(arr, np.nan, dtype=np.float64)
    valid = ~np.isnan(arr)
    if not np.any(valid):
        return out

    u = np.clip(arr[valid], 0.0, 1.0)

    if legend.scale is ScaleType.LOG:
        log_vmin = math.log10(vmin)
        log_vmax = math.log10(vmax)
        log_v = log_vmin + u * (log_vmax - log_vmin)
        out[valid] = 10.0**log_v
        return out

    if legend.kind is ColormapKind.DIVERGING:
        c = legend.effective_center
        v = np.empty_like(u)
        lower_mask = u < 0.5
        upper_mask = ~lower_mask
        v[lower_mask] = vmin + (2.0 * u[lower_mask]) * (c - vmin)
        v[upper_mask] = c + (2.0 * (u[upper_mask] - 0.5)) * (vmax - c)
        out[valid] = v
        return out

    out[valid] = vmin + u * (vmax - vmin)
    return out
