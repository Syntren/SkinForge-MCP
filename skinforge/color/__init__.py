"""
SkinForge Vectorized Color Engine Package.
"""

from .spaces import (
    extract_opaque_mask,
    extract_opaque_rgb,
    rgb_to_hsv,
    hsv_to_rgb,
    rgb_to_hsl,
    hsl_to_rgb,
    rgb_to_cielab,
    cielab_to_rgb,
    adjust_rgba_hsv,
    adjust_rgba_hsl,
)
from .palettes import (
    TECHWEAR_CYBERPUNK,
    ANIME_SKIN,
    CASUAL_STREETWEAR,
    FANTASY_KNIGHT,
    generate_color_ramp,
)

__all__ = [
    "extract_opaque_mask",
    "extract_opaque_rgb",
    "rgb_to_hsv",
    "hsv_to_rgb",
    "rgb_to_hsl",
    "hsl_to_rgb",
    "rgb_to_cielab",
    "cielab_to_rgb",
    "adjust_rgba_hsv",
    "adjust_rgba_hsl",
    "TECHWEAR_CYBERPUNK",
    "ANIME_SKIN",
    "CASUAL_STREETWEAR",
    "FANTASY_KNIGHT",
    "generate_color_ramp",
]
