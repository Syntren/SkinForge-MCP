"""
Procedural Pixel-Art Hue-Shifted Auto-Shading & Dithering Engine for SkinForge (v2.0.0).

Solves the #1 LLM skin-authoring bottleneck: flat, plastic-looking regions.
Applies vectorized, alpha-safe directional lighting, ambient occlusion, cylindrical limb shading,
fabric drapery folds, hair sheen strands, and metallic specular highlights with artistic
temperature hue-shifting (cooler/richer shadows, warmer/brighter highlights) and optional
ordered Bayer 2x2 dithering — while strictly avoiding beginner pillow-shading.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from .color.spaces import extract_opaque_mask, hsv_to_rgb, rgb_to_hsv
from .core.uv import ALL_PARTS, BASE_PARTS, OUTER_PARTS

SHADING_STYLES = (
    "directional",
    "ambient_occlusion",
    "cylindrical",
    "fabric_folds",
    "hair_strands",
    "metallic",
)

# Normalized 2x2 Bayer ordered dithering threshold matrix centered around 0
_BAYER_2X2 = np.array(
    [
        [-0.375, 0.125],
        [0.375, -0.125],
    ],
    dtype=np.float64,
)

# Semantic target groups for multi-part shading
SHADING_TARGET_GROUPS: Dict[str, List[str]] = {
    "all": list(ALL_PARTS),
    "base": list(BASE_PARTS),
    "outer": list(OUTER_PARTS),
    "head": [p for p in BASE_PARTS if p.startswith("head_")],
    "hat": [p for p in OUTER_PARTS if p.startswith("hat_")],
    "torso": [p for p in BASE_PARTS if p.startswith("body_")],
    "jacket": [p for p in OUTER_PARTS if p.startswith("jacket_")],
    "arms": [p for p in BASE_PARTS if "arm_" in p],
    "sleeves": [p for p in OUTER_PARTS if "sleeve_" in p],
    "legs": [p for p in BASE_PARTS if "leg_" in p],
    "pants": [p for p in OUTER_PARTS if "pants_" in p],
    "limbs": [p for p in BASE_PARTS if "arm_" in p or "leg_" in p],
}


def _build_light_field(h: int, w: int, style: str, part_name: str) -> np.ndarray:
    """
    Build a signed lighting field L in [-1.0, +1.0] for a (H, W) UV face.
    Positive values brighten/warm (highlights); negative values darken/cool (shadows).
    Carefully designed to NEVER create symmetrical 4-edge pillow shading.
    """
    yy = np.linspace(0.0, 1.0, max(1, h), dtype=np.float64)[:, None]
    xx = np.linspace(0.0, 1.0, max(1, w), dtype=np.float64)[None, :]

    if style == "directional":
        # Top-left key light -> bottom-right shadow (asymmetric, avoids pillow shading)
        # Top faces catch more light; bottom faces sit in ambient shadow
        if part_name.endswith("_top"):
            field = 0.55 - 0.35 * (0.5 * xx + 0.5 * yy)
        elif part_name.endswith("_bottom"):
            field = -0.55 + 0.20 * (1.0 - yy)
        elif part_name.endswith("_back"):
            field = 0.30 - 0.70 * yy - 0.20 * xx
        else:
            field = 0.55 - 0.85 * yy - 0.35 * xx
        return np.clip(field, -1.0, 1.0)

    if style == "ambient_occlusion":
        # Natural Minecraft anatomical contact shadows (under chin, waist, inner arms, ankles)
        field = np.zeros((h, w), dtype=np.float64)
        if part_name.endswith("_bottom"):
            field[:] = -0.75
        elif part_name.endswith("_top"):
            field[:] = 0.35
        else:
            # Top edge under head/collar gets subtle AO; bottom edge gets deeper drop shadow
            field = 0.25 - 0.65 * yy
            if part_name.startswith(("body_", "jacket_")) and h >= 8:
                field[0, :] -= 0.45  # chin shadow on neck/collar
                field[-1, :] -= 0.25  # belt/waist crease
            elif ("arm_" in part_name or "sleeve_" in part_name) and h >= 8:
                field[0, :] -= 0.25  # shoulder seam
                if part_name.endswith("_left") and part_name.startswith("right_"):
                    field -= 0.35  # inner arm facing torso
                elif part_name.endswith("_right") and part_name.startswith("left_"):
                    field -= 0.35
            elif ("leg_" in part_name or "pants_" in part_name) and h >= 8:
                field[0:2, :] -= 0.35  # shadow under jacket/torso hem
        return np.clip(field, -1.0, 1.0)

    if style == "cylindrical":
        # Asymmetric cylindrical wrap (key light shifted left-of-center at x=0.35)
        horiz = 1.0 - 1.6 * np.abs(xx - 0.35)
        vert = 0.35 - 0.55 * yy
        return np.clip(0.65 * horiz + 0.35 * vert, -1.0, 1.0)

    if style == "fabric_folds":
        # Vertical cloth drapery waves + gravity darkening toward bottom hem
        wave = np.sin((xx * 2.5 + yy * 0.4) * np.pi) * 0.55
        gravity = 0.30 - 0.65 * yy
        return np.clip(wave + gravity, -1.0, 1.0)

    if style == "hair_strands":
        # Vertical hair strand modulation + bright anime sheen band around upper-mid row
        strands = np.cos(xx * np.pi * max(2.0, w * 0.75)) * 0.35
        sheen = np.exp(-((yy - 0.32) ** 2) / 0.04) * 0.75
        tips_shadow = -0.55 * np.clip((yy - 0.65) / 0.35, 0.0, 1.0)
        return np.clip(strands + sheen + tips_shadow - 0.10, -1.0, 1.0)

    if style == "metallic":
        # Crisp diagonal specular reflection band + strong dark underside
        diag = 0.65 * xx + 0.55 * yy
        spec = np.exp(-((diag - 0.42) ** 2) / 0.03) * 0.95
        base_grad = 0.20 - 0.75 * yy
        return np.clip(spec + base_grad, -1.0, 1.0)

    raise ValueError(f"Unknown shading style '{style}'. Supported styles: {list(SHADING_STYLES)}")


def auto_shade_part(
    canvas: Any,
    part_name: str,
    style: str = "directional",
    strength: float = 0.35,
    hue_shift_deg: float = 18.0,
    dither: bool = False,
) -> int:
    """
    Apply hue-shifted pixel-art shading to a single UV part on a SkinCanvas.
    Strictly preserves transparent pixels (alpha == 0).
    Returns number of opaque pixels shaded.
    """
    if part_name not in canvas.parts:
        raise KeyError(f"Unknown UV part: '{part_name}'")

    style = style.lower().strip()
    if style not in SHADING_STYLES:
        raise ValueError(f"Unknown shading style '{style}'. Supported: {list(SHADING_STYLES)}")

    strength = float(np.clip(strength, 0.05, 0.85))
    hue_shift_deg = float(np.clip(hue_shift_deg, 0.0, 45.0))

    part = canvas.parts[part_name]
    h, w, _ = part.shape
    mask = extract_opaque_mask(part, min_alpha=1)
    count = int(np.sum(mask))
    if count == 0:
        return 0

    light = _build_light_field(h, w, style=style, part_name=part_name)
    if dither:
        bayer = np.tile(_BAYER_2X2, ((h + 1) // 2, (w + 1) // 2))[:h, :w]
        # Quantize slightly into pixel-art shading steps with ordered Bayer dithering
        light = np.clip(light + bayer * 0.22, -1.0, 1.0)

    hsv = rgb_to_hsv(part[:, :, :3])  # H in [0, 360), S in [0, 1], V in [0, 1]
    h_ch = hsv[:, :, 0].copy()
    s_ch = hsv[:, :, 1].copy()
    v_ch = hsv[:, :, 2].copy()

    # Artistic temperature hue-shifting:
    # Shadows (light < 0) shift toward cool blue-violet (~240 deg) and gain saturation.
    # Highlights (light > 0) shift toward warm yellow (~55 deg) and slightly lift/desaturate.
    shadow_w = np.clip(-light, 0.0, 1.0) * strength
    high_w = np.clip(light, 0.0, 1.0) * strength

    # Shortest-arc angular shift toward cool shadow hue (245 deg) and warm highlight hue (50 deg)
    def _angle_delta(src: np.ndarray, target_deg: float) -> np.ndarray:
        return ((target_deg - src + 180.0) % 360.0) - 180.0

    cool_delta = np.clip(_angle_delta(h_ch, 245.0), -hue_shift_deg, hue_shift_deg)
    warm_delta = np.clip(_angle_delta(h_ch, 50.0), -hue_shift_deg, hue_shift_deg)

    # Only hue-shift chromatic pixels (or gently tint near-neutrals with a cool/warm cast)
    chroma_weight = np.where(s_ch > 0.04, 1.0, 0.35)
    h_new = (h_ch + (shadow_w * cool_delta + high_w * warm_delta) * chroma_weight) % 360.0

    # Saturation: richer in shadows, crisper/slightly lighter in highlights
    s_new = np.clip(s_ch + shadow_w * 0.16 - high_w * 0.10, 0.0, 1.0)
    # Value/luminance: smooth multiplicative + additive lift so near-black fabrics still show highlights
    v_new = np.clip(v_ch * (1.0 + light * strength * 0.85) + high_w * 0.08 - shadow_w * 0.04, 0.02, 1.0)

    new_rgb = hsv_to_rgb(np.stack([h_new, s_new, v_new], axis=-1))
    part[:, :, :3] = np.where(mask[:, :, None], new_rgb, part[:, :, :3])
    return count


def resolve_shading_targets(target: str) -> List[str]:
    """Resolve a part name or semantic group name into a list of UV part names."""
    key = target.lower().strip()
    if key in SHADING_TARGET_GROUPS:
        return list(SHADING_TARGET_GROUPS[key])
    if key in ALL_PARTS:
        return [key]
    raise ValueError(
        f"Unknown shading target '{target}'. Use any UV part name or group: {list(SHADING_TARGET_GROUPS.keys())}"
    )


def auto_shade_skin(
    canvas: Any,
    target: str = "all",
    style: str = "directional",
    strength: float = 0.35,
    hue_shift_deg: float = 18.0,
    dither: bool = False,
) -> Dict[str, Any]:
    """
    Apply procedural hue-shifted shading across a single UV part or a semantic body group.
    """
    parts = resolve_shading_targets(target)
    total_pixels = 0
    shaded_parts: List[str] = []
    for p in parts:
        cnt = auto_shade_part(
            canvas,
            part_name=p,
            style=style,
            strength=strength,
            hue_shift_deg=hue_shift_deg,
            dither=dither,
        )
        if cnt > 0:
            total_pixels += cnt
            shaded_parts.append(p)

    return {
        "target": target,
        "style": style,
        "strength": strength,
        "hue_shift_deg": hue_shift_deg,
        "dither": dither,
        "shaded_parts": shaded_parts,
        "shaded_parts_count": len(shaded_parts),
        "shaded_pixels": total_pixels,
    }
