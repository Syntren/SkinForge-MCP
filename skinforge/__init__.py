"""
SkinForge - Autonomous Minecraft Skin Authoring, Inspection & 3D/2D Rendering Toolkit.
"""

from .canvas import SkinCanvas, MINECRAFT_UV_MAP
from .renderer import (
    Minecraft3DRenderer,
    render_composite_2d,
    render_3d_turnaround,
    render_3d_single,
    render_part_zoomed,
    render_turntable_gif,
    render_bottom_up,
)
from .validator import SkinValidator
from .palettes import (
    TECHWEAR_CYBERPUNK,
    ANIME_SKIN,
    CASUAL_STREETWEAR,
    FANTASY_KNIGHT,
    generate_color_ramp,
)
from .presets import (
    draw_anime_eyes_2x2,
    draw_hoodie_drawstrings,
    draw_cargo_pocket,
    draw_hair_bangs,
    draw_sneakers,
    draw_headphones,
)
from .ascii_codec import normalize_color, rgba_to_hex, part_to_ascii, canvas_to_ascii
from .templates import create_base_body, SKIN_TONE_PALETTES
from .sampler import sample_image
from .seams import check_seams, align_seams
from .typography import draw_text, draw_symbol
from .outfits import apply_outfit
from .converter import convert_skin_model

__all__ = [
    "SkinCanvas",
    "MINECRAFT_UV_MAP",
    "Minecraft3DRenderer",
    "render_composite_2d",
    "render_3d_turnaround",
    "render_3d_single",
    "render_part_zoomed",
    "render_turntable_gif",
    "render_bottom_up",
    "SkinValidator",
    "TECHWEAR_CYBERPUNK",
    "ANIME_SKIN",
    "CASUAL_STREETWEAR",
    "FANTASY_KNIGHT",
    "generate_color_ramp",
    "draw_anime_eyes_2x2",
    "draw_hoodie_drawstrings",
    "draw_cargo_pocket",
    "draw_hair_bangs",
    "draw_sneakers",
    "draw_headphones",
    "normalize_color",
    "rgba_to_hex",
    "part_to_ascii, canvas_to_ascii",
    "create_base_body",
    "SKIN_TONE_PALETTES",
    "sample_image",
    "check_seams",
    "align_seams",
    "draw_text",
    "draw_symbol",
    "apply_outfit",
    "convert_skin_model",
]
