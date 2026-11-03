"""
Backward-compatible re-export of palettes from skinforge.color.palettes.
"""

from .color.palettes import (
    TECHWEAR_CYBERPUNK,
    ANIME_SKIN,
    CASUAL_STREETWEAR,
    FANTASY_KNIGHT,
    generate_color_ramp,
)

__all__ = [
    "TECHWEAR_CYBERPUNK",
    "ANIME_SKIN",
    "CASUAL_STREETWEAR",
    "FANTASY_KNIGHT",
    "generate_color_ramp",
]
