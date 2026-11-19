"""
Pydantic v2 Validation Schemas for SkinForge MCP Tools (v2.0.0).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class PixelCoordSchema(BaseModel):
    """Pydantic schema for single pixel coordinate & color edits."""
    x: int = Field(..., ge=0, lt=64, description="0-indexed X coordinate within the UV part")
    y: int = Field(..., ge=0, lt=64, description="0-indexed Y coordinate within the UV part")
    color: Union[str, List[int]] = Field(..., description="Hex color string or RGBA [r, g, b, a] list")


class BatchActionSchema(BaseModel):
    """Pydantic schema for atomic batch action items (v2.0.0 expanded)."""
    action: str = Field(..., description="Action identifier (e.g. set_pixel, draw_rect, fill_part, set_ascii, paint_region, auto_shade, draw_primitive, apply_preset, apply_outfit, align_seams, auto_fix)")
    part_name: Optional[str] = None
    region: Optional[str] = None
    target: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    x0: Optional[int] = None
    y0: Optional[int] = None
    x1: Optional[int] = None
    y1: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    color: Optional[Any] = None
    secondary_color: Optional[Any] = None
    pixels: Optional[List[Dict[str, Any]]] = None
    old_color: Optional[Any] = None
    new_color: Optional[Any] = None
    tolerance: int = 15
    layer: str = "both"
    preset_name: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    src_limb: str = "right_arm"
    dst_limb: str = "left_arm"
    mirror_layer2: bool = True
    amount: int = 6
    start_color: Optional[Any] = None
    end_color: Optional[Any] = None
    direction: str = "vertical"
    # v2.0.0 additions
    ascii_grid: Optional[str] = None
    palette: Optional[Any] = None
    style: Optional[str] = None
    pattern: str = "solid"
    row_start: Optional[int] = None
    row_end: Optional[int] = None
    include_caps: bool = True
    strength: float = 0.35
    hue_shift_deg: float = 18.0
    dither: bool = False
    primitive: Optional[str] = None
    hue_shift: float = 0.0
    sat_mult: float = 1.0
    val_mult: float = 1.0
    target_color: Optional[str] = None
    seam_name: str = "all"
    mode: str = "blend"
    text: Optional[str] = None
    symbol_name: Optional[str] = None
    spacing: int = 1
    primary_color: Optional[str] = None
    accent_color: Optional[str] = None
    trim_color: Optional[str] = None
    parts: Optional[List[str]] = None
    default_skin_color: Optional[str] = None


class RagPackConfigSchema(BaseModel):
    """Pydantic schema for RAG database packing parameters."""
    source_path: str = Field(..., description="Folder of .png skins or .zip archive")
    output_path: Optional[str] = Field(None, description="Destination .sfpack or .db path")
    metadata_path: Optional[str] = Field(None, description="Optional .json or .csv metadata file")
    min_score: float = Field(0.0, ge=0.0, le=1.0, description="Minimum aesthetic score filter")
    overwrite: bool = Field(False, description="Overwrite existing database if True")
