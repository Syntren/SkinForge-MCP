"""
Vectorized Color Space Engine for SkinForge (RGB <-> HSV / HSL / CIELAB).

Strictly ignores transparent pixels (alpha == 0) in all color calculations,
eliminates division-by-zero hazards via np.divide(..., where=...), and prevents
uint8 overflow via np.clip(..., 0, 255).astype(np.uint8).
"""

from __future__ import annotations

from typing import Optional, Tuple, Union
import numpy as np
from ..ascii_codec import normalize_color


# CIE D65 Standard Illuminant reference white
_D65_XN: float = 0.95047
_D65_YN: float = 1.00000
_D65_ZN: float = 1.08883
_CIE_EPS: float = 216.0 / 24389.0    # (6/29)^3 ≈ 0.008856451679
_CIE_KAPPA: float = 24389.0 / 27.0   # (29/3)^3 ≈ 903.296296296
_CIE_DELTA: float = 6.0 / 29.0


def extract_opaque_mask(rgba: np.ndarray, min_alpha: int = 1) -> np.ndarray:
    """
    Return boolean mask where pixels are non-transparent (alpha >= min_alpha).
    Strictly excludes alpha == 0 pixels.
    """
    arr = np.asarray(rgba)
    if arr.ndim < 3 or arr.shape[-1] < 4:
        return np.ones(arr.shape[:-1], dtype=bool)
    return arr[..., 3] >= max(1, int(min_alpha))


def extract_opaque_rgb(rgba: np.ndarray, min_alpha: int = 1) -> np.ndarray:
    """
    Extract an (N, 3) uint8 array of RGB values strictly from non-transparent pixels (alpha > 0).
    """
    arr = np.asarray(rgba, dtype=np.uint8)
    if arr.ndim < 3 or arr.shape[-1] < 4:
        return arr.reshape(-1, 3)
    mask = extract_opaque_mask(arr, min_alpha=min_alpha)
    if not np.any(mask):
        return np.empty((0, 3), dtype=np.uint8)
    return arr[mask][:, :3]


def rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
    """
    Vectorized conversion from sRGB [0..255] to HSV:
      - H in [0.0, 360.0) degrees
      - S in [0.0, 1.0]
      - V in [0.0, 1.0]
    Guaranteed free of division-by-zero warnings.
    """
    rgb_f = np.clip(np.asarray(rgb, dtype=np.float64), 0.0, 255.0)
    norm = np.zeros_like(rgb_f, dtype=np.float64)
    np.divide(rgb_f, 255.0, out=norm)

    r = norm[..., 0]
    g = norm[..., 1]
    b = norm[..., 2]

    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)
    delta = maxc - minc

    v = maxc
    s = np.zeros_like(maxc, dtype=np.float64)
    np.divide(delta, maxc, out=s, where=maxc > 1e-12)

    nz = delta > 1e-12
    rc = np.zeros_like(maxc, dtype=np.float64)
    gc = np.zeros_like(maxc, dtype=np.float64)
    bc = np.zeros_like(maxc, dtype=np.float64)

    np.divide(g - b, delta, out=rc, where=nz)
    np.divide(b - r, delta, out=gc, where=nz)
    np.divide(r - g, delta, out=bc, where=nz)

    h = np.zeros_like(maxc, dtype=np.float64)
    mask_r = nz & (r == maxc)
    mask_g = nz & (g == maxc) & (~mask_r)
    mask_b = nz & (~mask_r) & (~mask_g)

    h = np.where(mask_r, rc % 6.0, h)
    h = np.where(mask_g, gc + 2.0, h)
    h = np.where(mask_b, bc + 4.0, h)
    h = (h * 60.0) % 360.0

    return np.stack([h, np.clip(s, 0.0, 1.0), np.clip(v, 0.0, 1.0)], axis=-1)


def hsv_to_rgb(hsv: np.ndarray) -> np.ndarray:
    """
    Vectorized conversion from HSV (H in [0..360], S in [0..1], V in [0..1])
    to uint8 sRGB [0..255] with strict clipping against uint8 overflow.
    """
    hsv_f = np.asarray(hsv, dtype=np.float64)
    h = np.zeros_like(hsv_f[..., 0], dtype=np.float64)
    np.divide(hsv_f[..., 0] % 360.0, 60.0, out=h)
    s = np.clip(hsv_f[..., 1], 0.0, 1.0)
    v = np.clip(hsv_f[..., 2], 0.0, 1.0)

    i = np.floor(h).astype(np.int64) % 6
    f = h - np.floor(h)

    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))

    out_r = np.choose(i, [v, q, p, p, t, v])
    out_g = np.choose(i, [t, v, v, q, p, p])
    out_b = np.choose(i, [p, p, t, v, v, q])

    rgb_float = np.stack([out_r, out_g, out_b], axis=-1) * 255.0
    return np.clip(np.round(rgb_float), 0, 255).astype(np.uint8)


def rgb_to_hsl(rgb: np.ndarray) -> np.ndarray:
    """
    Vectorized conversion from sRGB [0..255] to HSL:
      - H in [0.0, 360.0) degrees
      - S in [0.0, 1.0]
      - L in [0.0, 1.0]
    Guaranteed free of division-by-zero warnings.
    """
    rgb_f = np.clip(np.asarray(rgb, dtype=np.float64), 0.0, 255.0)
    norm = np.zeros_like(rgb_f, dtype=np.float64)
    np.divide(rgb_f, 255.0, out=norm)

    r = norm[..., 0]
    g = norm[..., 1]
    b = norm[..., 2]

    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)
    delta = maxc - minc

    l = 0.5 * (maxc + minc)
    denom = 1.0 - np.abs(2.0 * l - 1.0)

    s = np.zeros_like(l, dtype=np.float64)
    valid_s = (delta > 1e-12) & (denom > 1e-12)
    np.divide(delta, denom, out=s, where=valid_s)

    nz = delta > 1e-12
    rc = np.zeros_like(maxc, dtype=np.float64)
    gc = np.zeros_like(maxc, dtype=np.float64)
    bc = np.zeros_like(maxc, dtype=np.float64)

    np.divide(g - b, delta, out=rc, where=nz)
    np.divide(b - r, delta, out=gc, where=nz)
    np.divide(r - g, delta, out=bc, where=nz)

    h = np.zeros_like(maxc, dtype=np.float64)
    mask_r = nz & (r == maxc)
    mask_g = nz & (g == maxc) & (~mask_r)
    mask_b = nz & (~mask_r) & (~mask_g)

    h = np.where(mask_r, rc % 6.0, h)
    h = np.where(mask_g, gc + 2.0, h)
    h = np.where(mask_b, bc + 4.0, h)
    h = (h * 60.0) % 360.0

    return np.stack([h, np.clip(s, 0.0, 1.0), np.clip(l, 0.0, 1.0)], axis=-1)


def hsl_to_rgb(hsl: np.ndarray) -> np.ndarray:
    """
    Vectorized conversion from HSL (H in [0..360], S in [0..1], L in [0..1])
    to uint8 sRGB [0..255] with strict clipping against uint8 overflow.
    """
    hsl_f = np.asarray(hsl, dtype=np.float64)
    h_prime = np.zeros_like(hsl_f[..., 0], dtype=np.float64)
    np.divide(hsl_f[..., 0] % 360.0, 60.0, out=h_prime)
    s = np.clip(hsl_f[..., 1], 0.0, 1.0)
    l = np.clip(hsl_f[..., 2], 0.0, 1.0)

    c = (1.0 - np.abs(2.0 * l - 1.0)) * s
    x = c * (1.0 - np.abs((h_prime % 2.0) - 1.0))
    m = l - 0.5 * c

    i = np.floor(h_prime).astype(np.int64) % 6
    z = np.zeros_like(c, dtype=np.float64)

    r1 = np.choose(i, [c, x, z, z, x, c])
    g1 = np.choose(i, [x, c, c, x, z, z])
    b1 = np.choose(i, [z, z, x, c, c, x])

    rgb_float = np.stack([r1 + m, g1 + m, b1 + m], axis=-1) * 255.0
    return np.clip(np.round(rgb_float), 0, 255).astype(np.uint8)


def rgb_to_cielab(rgb: np.ndarray) -> np.ndarray:
    """
    Vectorized conversion from sRGB [0..255] to CIE 1976 L*a*b* (D65 illuminant):
      - L* in [0.0, 100.0]
      - a* in [-128.0, 127.0]
      - b* in [-128.0, 127.0]
    """
    rgb_f = np.clip(np.asarray(rgb, dtype=np.float64), 0.0, 255.0)
    srgb = np.zeros_like(rgb_f, dtype=np.float64)
    np.divide(rgb_f, 255.0, out=srgb)

    low_mask = srgb <= 0.04045
    low_lin = np.zeros_like(srgb, dtype=np.float64)
    np.divide(srgb, 12.92, out=low_lin, where=low_mask)

    high_base = np.zeros_like(srgb, dtype=np.float64)
    np.divide(srgb + 0.055, 1.055, out=high_base, where=~low_mask)
    high_lin = np.power(np.clip(high_base, 0.0, 1.0), 2.4)
    linear = np.where(low_mask, low_lin, high_lin)

    r_l = linear[..., 0]
    g_l = linear[..., 1]
    b_l = linear[..., 2]

    x = r_l * 0.4124564 + g_l * 0.3575761 + b_l * 0.1804375
    y = r_l * 0.2126729 + g_l * 0.7151522 + b_l * 0.0721750
    z = r_l * 0.0193339 + g_l * 0.1191920 + b_l * 0.9503041

    xr = x / _D65_XN
    yr = y / _D65_YN
    zr = z / _D65_ZN

    fx = np.where(xr > _CIE_EPS, np.cbrt(np.maximum(xr, 0.0)), (_CIE_KAPPA * xr + 16.0) / 116.0)
    fy = np.where(yr > _CIE_EPS, np.cbrt(np.maximum(yr, 0.0)), (_CIE_KAPPA * yr + 16.0) / 116.0)
    fz = np.where(zr > _CIE_EPS, np.cbrt(np.maximum(zr, 0.0)), (_CIE_KAPPA * zr + 16.0) / 116.0)

    L = np.clip(116.0 * fy - 16.0, 0.0, 100.0)
    a = 500.0 * (fx - fy)
    b = 200.0 * (fy - fz)

    return np.stack([L, a, b], axis=-1)


def cielab_to_rgb(lab: np.ndarray) -> np.ndarray:
    """
    Vectorized conversion from CIE 1976 L*a*b* (D65) back to uint8 sRGB [0..255]
    with strict clipping against uint8 overflow.
    """
    lab_f = np.asarray(lab, dtype=np.float64)
    L = lab_f[..., 0]
    a = lab_f[..., 1]
    b = lab_f[..., 2]

    fy = (L + 16.0) / 116.0
    fx = a / 500.0 + fy
    fz = fy - b / 200.0

    xr = np.where(fx > _CIE_DELTA, np.power(fx, 3.0), (116.0 * fx - 16.0) / _CIE_KAPPA)
    yr = np.where(L > _CIE_KAPPA * _CIE_EPS, np.power(fy, 3.0), L / _CIE_KAPPA)
    zr = np.where(fz > _CIE_DELTA, np.power(fz, 3.0), (116.0 * fz - 16.0) / _CIE_KAPPA)

    x = np.maximum(0.0, xr * _D65_XN)
    y = np.maximum(0.0, yr * _D65_YN)
    z = np.maximum(0.0, zr * _D65_ZN)

    r_l = x *  3.2404542 + y * -1.5371385 + z * -0.4985314
    g_l = x * -0.9692660 + y *  1.8760108 + z *  0.0415560
    b_l = x *  0.0556434 + y * -0.2040259 + z *  1.0572252

    linear = np.clip(np.stack([r_l, g_l, b_l], axis=-1), 0.0, 1.0)
    low_mask = linear <= 0.0031308
    srgb = np.where(
        low_mask,
        linear * 12.92,
        1.055 * np.power(np.maximum(linear, 0.0), 1.0 / 2.4) - 0.055
    )

    rgb_float = srgb * 255.0
    return np.clip(np.round(rgb_float), 0, 255).astype(np.uint8)


def adjust_rgba_hsv(
    rgba: np.ndarray,
    hue_shift: float = 0.0,
    sat_mult: float = 1.0,
    val_mult: float = 1.0,
    target_color: Optional[Union[str, list, tuple, np.ndarray]] = None,
    tolerance: float = 30.0
) -> Tuple[np.ndarray, int]:
    """
    Apply vectorized HSV adjustment to an RGBA array in-place or copy,
    strictly ignoring transparent pixels (alpha == 0).

    Returns:
        Tuple of (updated_rgba_uint8, count_of_adjusted_pixels).
    """
    out = np.clip(np.asarray(rgba), 0, 255).astype(np.uint8).copy()
    alpha_mask = out[..., 3] > 0
    if not np.any(alpha_mask):
        return out, 0

    if target_color is not None:
        target_rgb = np.array(normalize_color(target_color)[:3], dtype=np.float64)
        rgb_f = out[..., :3].astype(np.float64)
        dist = np.sqrt(np.sum((rgb_f - target_rgb) ** 2, axis=-1))
        mask = alpha_mask & (dist <= float(tolerance))
    else:
        mask = alpha_mask

    count = int(np.sum(mask))
    if count == 0:
        return out, 0

    hsv = rgb_to_hsv(out[mask, :3])
    hsv[:, 0] = (hsv[:, 0] + float(hue_shift)) % 360.0
    hsv[:, 1] = np.clip(hsv[:, 1] * float(sat_mult), 0.0, 1.0)
    hsv[:, 2] = np.clip(hsv[:, 2] * float(val_mult), 0.0, 1.0)

    out[mask, :3] = hsv_to_rgb(hsv)
    return out, count


def adjust_rgba_hsl(
    rgba: np.ndarray,
    hue_shift: float = 0.0,
    sat_mult: float = 1.0,
    light_mult: float = 1.0,
    target_color: Optional[Union[str, list, tuple, np.ndarray]] = None,
    tolerance: float = 30.0
) -> Tuple[np.ndarray, int]:
    """
    Apply vectorized HSL adjustment to an RGBA array,
    strictly ignoring transparent pixels (alpha == 0).
    """
    out = np.clip(np.asarray(rgba), 0, 255).astype(np.uint8).copy()
    alpha_mask = out[..., 3] > 0
    if not np.any(alpha_mask):
        return out, 0

    if target_color is not None:
        target_rgb = np.array(normalize_color(target_color)[:3], dtype=np.float64)
        rgb_f = out[..., :3].astype(np.float64)
        dist = np.sqrt(np.sum((rgb_f - target_rgb) ** 2, axis=-1))
        mask = alpha_mask & (dist <= float(tolerance))
    else:
        mask = alpha_mask

    count = int(np.sum(mask))
    if count == 0:
        return out, 0

    hsl = rgb_to_hsl(out[mask, :3])
    hsl[:, 0] = (hsl[:, 0] + float(hue_shift)) % 360.0
    hsl[:, 1] = np.clip(hsl[:, 1] * float(sat_mult), 0.0, 1.0)
    hsl[:, 2] = np.clip(hsl[:, 2] * float(light_mult), 0.0, 1.0)

    out[mask, :3] = hsl_to_rgb(hsl)
    return out, count
