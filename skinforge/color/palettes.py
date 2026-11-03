"""
Predefined color palettes and procedural color ramp utilities for SkinForge.
"""

from __future__ import annotations

from typing import Any, Dict, List, Union
import numpy as np
from ..ascii_codec import normalize_color, rgba_to_hex

# Techwear Cyberpunk (Syntren Theme)
TECHWEAR_CYBERPUNK: Dict[str, List[int]] = {
    ".": [0, 0, 0, 0],              # Transparent
    "_": [14, 12, 18, 255],          # Deep shadow / border
    "#": [20, 16, 24, 255],          # Base dark black/charcoal
    "=": [28, 24, 34, 255],          # Mid dark fabric / fold
    "+": [38, 34, 46, 255],          # Fabric highlight / seam
    "~": [50, 44, 60, 255],          # Pale rim highlight
    "D": [80, 18, 120, 255],         # Deep purple glow shadow
    "P": [160, 55, 225, 255],        # Vivid neon violet (#A037E1)
    "M": [154, 50, 220, 255],        # Neon violet mid
    "B": [210, 100, 255, 255],       # Bright neon violet (#D264FF)
    "L": [245, 185, 255, 255],       # White-violet highlight (#F5B9FF)
    "h": [14, 12, 17, 255],          # Deep hair shadow
    "H": [22, 20, 26, 255],          # Base black hair
    "^": [32, 28, 36, 255],          # Hair highlight strand
    "s": [224, 177, 180, 255],       # Fair anime skin
    "m": [212, 163, 172, 255],       # Skin midtone
    "d": [189, 144, 158, 255],       # Skin shadow gap
    "e": [92, 80, 102, 255],         # Eye shadow lash
    "E": [117, 107, 133, 255],       # Eye shadow right
    "i": [95, 41, 135, 255],         # Iris top (deep violet)
    "I": [154, 60, 212, 255],        # Iris bottom (glowing violet)
    "W": [233, 214, 240, 255],       # Eye lavender / white highlight
    "c": [250, 250, 255, 255],       # Chain specular
    "C": [180, 170, 195, 255],       # Chain light silver
    "k": [130, 120, 145, 255],       # Chain mid silver
    "x": [80, 70, 95, 255],          # Chain dark silver
    "0": [15, 13, 19, 255],          # Pants deep shadow
    "1": [22, 19, 27, 255],          # Base cargo fabric
    "2": [30, 26, 36, 255],          # Cargo fold
    "3": [42, 38, 50, 255],          # Pocket flap highlight
    "u": [154, 50, 220, 255],        # Sneaker purple collar
    "b": [18, 16, 22, 255],          # Sneaker dark body
    "w": [250, 250, 255, 255],       # White sole
    "g": [205, 205, 218, 255],       # Sole shadow
}

# Standard Anime Skin Tones
ANIME_SKIN: Dict[str, List[int]] = {
    "light":   [240, 195, 178, 255],
    "base":    [224, 177, 160, 255],
    "midtone": [210, 160, 142, 255],
    "shadow":  [185, 135, 118, 255],
    "deep":    [155, 110, 95, 255],
}

# Casual Streetwear Palette
CASUAL_STREETWEAR: Dict[str, List[int]] = {
    ".": [0, 0, 0, 0],
    "D": [34, 46, 74, 255],
    "d": [46, 62, 98, 255],
    "b": [62, 84, 132, 255],
    "w": [245, 242, 238, 255],
    "W": [225, 220, 212, 255],
    "g": [190, 184, 175, 255],
    "l": [88, 54, 38, 255],
    "L": [118, 74, 52, 255],
    "h": [148, 96, 68, 255],
}

# Fantasy / Knight Steel Palette
FANTASY_KNIGHT: Dict[str, List[int]] = {
    ".": [0, 0, 0, 0],
    "s": [48, 52, 60, 255],
    "S": [82, 88, 100, 255],
    "a": [128, 136, 152, 255],
    "A": [180, 188, 204, 255],
    "*": [240, 245, 255, 255],
    "o": [140, 95, 20, 255],
    "O": [205, 150, 40, 255],
    "g": [250, 205, 75, 255],
}


def generate_color_ramp(base_color: Union[str, list, tuple, np.ndarray], steps: int = 5) -> Dict[str, Any]:
    """
    Generate a harmonious 5-step shading ramp from a single base color with artistic
    temperature hue-shifting (cooler shadows, warmer specular highlights).
    Strictly clips uint8 values to [0, 255].
    """
    base_rgba = normalize_color(base_color)
    r, g, b = [float(x) for x in base_rgba[:3]]

    factors = [
        (0.55, -8, -8, 8),    # deep shadow (cooler)
        (0.78, -4, -4, 4),    # shadow
        (1.00,  0,  0, 0),    # base
        (1.22,  6,  6, 2),    # highlight
        (1.42, 14, 14, 8),    # rim specular
    ]
    chars = ["_", "#", "=", "+", "~"]

    ramp_palette: Dict[str, List[int]] = {}
    ramp_details: List[Dict[str, Any]] = []

    for i in range(min(int(steps), len(factors))):
        mult, dr, dg, db = factors[i]
        rgb_arr = np.clip(np.round([r * mult + dr, g * mult + dg, b * mult + db]), 0, 255).astype(np.uint8)
        rgba = [int(rgb_arr[0]), int(rgb_arr[1]), int(rgb_arr[2]), 255]
        char = chars[i]
        ramp_palette[char] = rgba
        ramp_details.append({
            "char": char,
            "rgba": rgba,
            "hex": rgba_to_hex(rgba),
            "step": i,
        })

    return {
        "palette": ramp_palette,
        "details": ramp_details,
        "base_hex": rgba_to_hex(base_rgba),
    }
