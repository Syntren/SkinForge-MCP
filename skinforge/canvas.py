"""
Backward-compatible re-export of SkinCanvas and UV mappings from skinforge.core.
"""

from .core.uv import (
    ALL_PARTS,
    BASE_PARTS,
    MINECRAFT_UV_MAP,
    MINECRAFT_UV_MAP_CLASSIC,
    MINECRAFT_UV_MAP_SLIM,
    MINECRAFT_UV_MAP_STEVE,
    OUTER_PARTS,
    OVERLAY_PARTS,
    convert_legacy_64x32_to_64x64,
    get_uv_map,
    lookup_uv_coord,
)
from .core.canvas import SkinCanvas, atomic_save_png

__all__ = [
    "SkinCanvas",
    "atomic_save_png",
    "MINECRAFT_UV_MAP",
    "MINECRAFT_UV_MAP_STEVE",
    "MINECRAFT_UV_MAP_CLASSIC",
    "MINECRAFT_UV_MAP_SLIM",
    "BASE_PARTS",
    "OUTER_PARTS",
    "OVERLAY_PARTS",
    "ALL_PARTS",
    "get_uv_map",
    "lookup_uv_coord",
    "convert_legacy_64x32_to_64x64",
]
