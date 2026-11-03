"""
Single Source of Truth for Minecraft 1.8+ Dual-Layer 64x64 UV Coordinates.

Provides strictly typed UV zone specifications (36 Base Layer + 36 Outer Overlay zones)
for both 'classic' (Steve 4px arms) and 'slim' (Alex 3px arms) player models,
coordinate lookup utilities, and automatic legacy 64x32 -> 64x64 skin conversion.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from typing import Any, Dict, Final, List, Literal, Optional, Tuple, Union
import numpy as np
from PIL import Image

UVBox = Tuple[int, int, int, int]  # (u0, v0, u1, v1)
ModelType = Literal["default", "classic", "slim"]
LayerType = Literal["base", "outer"]
AnatomicalGroup = Literal["head", "torso", "right_arm", "left_arm", "right_leg", "left_leg"]
FaceOrientation = Literal["top", "bottom", "right", "front", "left", "back"]


@dataclass(frozen=True)
class UVZoneSpec:
    """Strictly typed specification for a single Minecraft skin UV face."""
    name: str
    layer: LayerType
    group: AnatomicalGroup
    face: FaceOrientation
    classic_box: UVBox
    slim_box: UVBox

    def get_box(self, model: str = "default") -> UVBox:
        return self.slim_box if is_slim_model(model) else self.classic_box

    def dimensions(self, model: str = "default") -> Tuple[int, int]:
        u0, v0, u1, v1 = self.get_box(model)
        return (u1 - u0, v1 - v0)


UV_ZONE_SPECS: Final[Tuple[UVZoneSpec, ...]] = (
    # =========================================================================
    # LAYER 1: BASE BODY (36 ZONES — MUST BE 100% OPAQUE, RULE 1)
    # =========================================================================
    # Head Base (6)
    UVZoneSpec("head_top",    "base", "head", "top",    (8, 0, 16, 8),   (8, 0, 16, 8)),
    UVZoneSpec("head_bottom", "base", "head", "bottom", (16, 0, 24, 8),  (16, 0, 24, 8)),
    UVZoneSpec("head_right",  "base", "head", "right",  (0, 8, 8, 16),   (0, 8, 8, 16)),
    UVZoneSpec("head_front",  "base", "head", "front",  (8, 8, 16, 16),  (8, 8, 16, 16)),
    UVZoneSpec("head_left",   "base", "head", "left",   (16, 8, 24, 16), (16, 8, 24, 16)),
    UVZoneSpec("head_back",   "base", "head", "back",   (24, 8, 32, 16), (24, 8, 32, 16)),

    # Torso Base (6)
    UVZoneSpec("body_top",    "base", "torso", "top",    (20, 16, 28, 20), (20, 16, 28, 20)),
    UVZoneSpec("body_bottom", "base", "torso", "bottom", (28, 16, 36, 20), (28, 16, 36, 20)),
    UVZoneSpec("body_right",  "base", "torso", "right",  (16, 20, 20, 32), (16, 20, 20, 32)),
    UVZoneSpec("body_front",  "base", "torso", "front",  (20, 20, 28, 32), (20, 20, 28, 32)),
    UVZoneSpec("body_left",   "base", "torso", "left",   (28, 20, 32, 32), (28, 20, 32, 32)),
    UVZoneSpec("body_back",   "base", "torso", "back",   (32, 20, 40, 32), (32, 20, 40, 32)),

    # Right Arm Base (6) — Classic 4px vs Slim 3px
    UVZoneSpec("right_arm_top",    "base", "right_arm", "top",    (44, 16, 48, 20), (44, 16, 47, 20)),
    UVZoneSpec("right_arm_bottom", "base", "right_arm", "bottom", (48, 16, 52, 20), (47, 16, 50, 20)),
    UVZoneSpec("right_arm_right",  "base", "right_arm", "right",  (40, 20, 44, 32), (40, 20, 44, 32)),
    UVZoneSpec("right_arm_front",  "base", "right_arm", "front",  (44, 20, 48, 32), (44, 20, 47, 32)),
    UVZoneSpec("right_arm_left",   "base", "right_arm", "left",   (48, 20, 52, 32), (47, 20, 51, 32)),
    UVZoneSpec("right_arm_back",   "base", "right_arm", "back",   (52, 20, 56, 32), (51, 20, 54, 32)),

    # Left Arm Base (6) — Classic 4px vs Slim 3px
    UVZoneSpec("left_arm_top",    "base", "left_arm", "top",    (36, 48, 40, 52), (36, 48, 39, 52)),
    UVZoneSpec("left_arm_bottom", "base", "left_arm", "bottom", (40, 48, 44, 52), (39, 48, 42, 52)),
    UVZoneSpec("left_arm_right",  "base", "left_arm", "right",  (32, 52, 36, 64), (32, 52, 36, 64)),
    UVZoneSpec("left_arm_front",  "base", "left_arm", "front",  (36, 52, 40, 64), (36, 52, 39, 64)),
    UVZoneSpec("left_arm_left",   "base", "left_arm", "left",   (40, 52, 44, 64), (39, 52, 43, 64)),
    UVZoneSpec("left_arm_back",   "base", "left_arm", "back",   (44, 52, 48, 64), (43, 52, 46, 64)),

    # Right Leg Base (6)
    UVZoneSpec("right_leg_top",    "base", "right_leg", "top",    (4, 16, 8, 20),   (4, 16, 8, 20)),
    UVZoneSpec("right_leg_bottom", "base", "right_leg", "bottom", (8, 16, 12, 20),  (8, 16, 12, 20)),
    UVZoneSpec("right_leg_right",  "base", "right_leg", "right",  (0, 20, 4, 32),   (0, 20, 4, 32)),
    UVZoneSpec("right_leg_front",  "base", "right_leg", "front",  (4, 20, 8, 32),   (4, 20, 8, 32)),
    UVZoneSpec("right_leg_left",   "base", "right_leg", "left",   (8, 20, 12, 32),  (8, 20, 12, 32)),
    UVZoneSpec("right_leg_back",   "base", "right_leg", "back",   (12, 20, 16, 32), (12, 20, 16, 32)),

    # Left Leg Base (6)
    UVZoneSpec("left_leg_top",    "base", "left_leg", "top",    (20, 48, 24, 52), (20, 48, 24, 52)),
    UVZoneSpec("left_leg_bottom", "base", "left_leg", "bottom", (24, 48, 28, 52), (24, 48, 28, 52)),
    UVZoneSpec("left_leg_right",  "base", "left_leg", "right",  (16, 52, 20, 64), (16, 52, 20, 64)),
    UVZoneSpec("left_leg_front",  "base", "left_leg", "front",  (20, 52, 24, 64), (20, 52, 24, 64)),
    UVZoneSpec("left_leg_left",   "base", "left_leg", "left",   (24, 52, 28, 64), (24, 52, 28, 64)),
    UVZoneSpec("left_leg_back",   "base", "left_leg", "back",   (28, 52, 32, 64), (28, 52, 32, 64)),

    # =========================================================================
    # LAYER 2: OUTER OVERLAY (36 ZONES — +0.35 3D RELIEF, RULES 2, 3, 4)
    # =========================================================================
    # Hat Outer (6)
    UVZoneSpec("hat_top",    "outer", "head", "top",    (40, 0, 48, 8),   (40, 0, 48, 8)),
    UVZoneSpec("hat_bottom", "outer", "head", "bottom", (48, 0, 56, 8),   (48, 0, 56, 8)),
    UVZoneSpec("hat_right",  "outer", "head", "right",  (32, 8, 40, 16),  (32, 8, 40, 16)),
    UVZoneSpec("hat_front",  "outer", "head", "front",  (40, 8, 48, 16),  (40, 8, 48, 16)),
    UVZoneSpec("hat_left",   "outer", "head", "left",   (48, 8, 56, 16),  (48, 8, 56, 16)),
    UVZoneSpec("hat_back",   "outer", "head", "back",   (56, 8, 64, 16),  (56, 8, 64, 16)),

    # Jacket Outer (6)
    UVZoneSpec("jacket_top",    "outer", "torso", "top",    (20, 32, 28, 36), (20, 32, 28, 36)),
    UVZoneSpec("jacket_bottom", "outer", "torso", "bottom", (28, 32, 36, 36), (28, 32, 36, 36)),
    UVZoneSpec("jacket_right",  "outer", "torso", "right",  (16, 36, 20, 48), (16, 36, 20, 48)),
    UVZoneSpec("jacket_front",  "outer", "torso", "front",  (20, 36, 28, 48), (20, 36, 28, 48)),
    UVZoneSpec("jacket_left",   "outer", "torso", "left",   (28, 36, 32, 48), (28, 36, 32, 48)),
    UVZoneSpec("jacket_back",   "outer", "torso", "back",   (32, 36, 40, 48), (32, 36, 40, 48)),

    # Right Sleeve Outer (6) — Classic 4px vs Slim 3px
    UVZoneSpec("right_sleeve_top",    "outer", "right_arm", "top",    (44, 32, 48, 36), (44, 32, 47, 36)),
    UVZoneSpec("right_sleeve_bottom", "outer", "right_arm", "bottom", (48, 32, 52, 36), (47, 32, 50, 36)),
    UVZoneSpec("right_sleeve_right",  "outer", "right_arm", "right",  (40, 36, 44, 48), (40, 36, 44, 48)),
    UVZoneSpec("right_sleeve_front",  "outer", "right_arm", "front",  (44, 36, 48, 48), (44, 36, 47, 48)),
    UVZoneSpec("right_sleeve_left",   "outer", "right_arm", "left",   (48, 36, 52, 48), (47, 36, 51, 48)),
    UVZoneSpec("right_sleeve_back",   "outer", "right_arm", "back",   (52, 36, 56, 48), (51, 36, 54, 48)),

    # Left Sleeve Outer (6) — Classic 4px vs Slim 3px
    UVZoneSpec("left_sleeve_top",    "outer", "left_arm", "top",    (52, 48, 56, 52), (52, 48, 55, 52)),
    UVZoneSpec("left_sleeve_bottom", "outer", "left_arm", "bottom", (56, 48, 60, 52), (55, 48, 58, 52)),
    UVZoneSpec("left_sleeve_right",  "outer", "left_arm", "right",  (48, 52, 52, 64), (48, 52, 52, 64)),
    UVZoneSpec("left_sleeve_front",  "outer", "left_arm", "front",  (52, 52, 56, 64), (52, 52, 55, 64)),
    UVZoneSpec("left_sleeve_left",   "outer", "left_arm", "left",   (56, 52, 60, 64), (55, 52, 59, 64)),
    UVZoneSpec("left_sleeve_back",   "outer", "left_arm", "back",   (60, 52, 64, 64), (59, 52, 62, 64)),

    # Right Pants Outer (6)
    UVZoneSpec("right_pants_top",    "outer", "right_leg", "top",    (4, 32, 8, 36),   (4, 32, 8, 36)),
    UVZoneSpec("right_pants_bottom", "outer", "right_leg", "bottom", (8, 32, 12, 36),  (8, 32, 12, 36)),
    UVZoneSpec("right_pants_right",  "outer", "right_leg", "right",  (0, 36, 4, 48),   (0, 36, 4, 48)),
    UVZoneSpec("right_pants_front",  "outer", "right_leg", "front",  (4, 36, 8, 48),   (4, 36, 8, 48)),
    UVZoneSpec("right_pants_left",   "outer", "right_leg", "left",   (8, 36, 12, 48),  (8, 36, 12, 48)),
    UVZoneSpec("right_pants_back",   "outer", "right_leg", "back",   (12, 36, 16, 48), (12, 36, 16, 48)),

    # Left Pants Outer (6)
    UVZoneSpec("left_pants_top",    "outer", "left_leg", "top",    (4, 48, 8, 52),   (4, 48, 8, 52)),
    UVZoneSpec("left_pants_bottom", "outer", "left_leg", "bottom", (8, 48, 12, 52),  (8, 48, 12, 52)),
    UVZoneSpec("left_pants_right",  "outer", "left_leg", "right",  (0, 52, 4, 64),   (0, 52, 4, 64)),
    UVZoneSpec("left_pants_front",  "outer", "left_leg", "front",  (4, 52, 8, 64),   (4, 52, 8, 64)),
    UVZoneSpec("left_pants_left",   "outer", "left_leg", "left",   (8, 52, 12, 64),  (8, 52, 12, 64)),
    UVZoneSpec("left_pants_back",   "outer", "left_leg", "back",   (12, 52, 16, 64), (12, 52, 16, 64)),
)

UV_SPEC_BY_NAME: Final[Dict[str, UVZoneSpec]] = {spec.name: spec for spec in UV_ZONE_SPECS}

MINECRAFT_UV_MAP_CLASSIC: Final[Dict[str, UVBox]] = {spec.name: spec.classic_box for spec in UV_ZONE_SPECS}
MINECRAFT_UV_MAP_STEVE: Final[Dict[str, UVBox]] = MINECRAFT_UV_MAP_CLASSIC
MINECRAFT_UV_MAP: Final[Dict[str, UVBox]] = MINECRAFT_UV_MAP_CLASSIC
MINECRAFT_UV_MAP_SLIM: Final[Dict[str, UVBox]] = {spec.name: spec.slim_box for spec in UV_ZONE_SPECS}

BASE_PARTS: Final[Tuple[str, ...]] = tuple(spec.name for spec in UV_ZONE_SPECS if spec.layer == "base")
OUTER_PARTS: Final[Tuple[str, ...]] = tuple(spec.name for spec in UV_ZONE_SPECS if spec.layer == "outer")
OVERLAY_PARTS: Final[Tuple[str, ...]] = OUTER_PARTS
ALL_PARTS: Final[Tuple[str, ...]] = tuple(spec.name for spec in UV_ZONE_SPECS)

BASE_TO_OUTER_MAP: Final[Dict[str, str]] = {
    b_spec.name: o_spec.name
    for b_spec in UV_ZONE_SPECS if b_spec.layer == "base"
    for o_spec in UV_ZONE_SPECS if o_spec.layer == "outer"
    and b_spec.group == o_spec.group and b_spec.face == o_spec.face
}
OUTER_TO_BASE_MAP: Final[Dict[str, str]] = {v: k for k, v in BASE_TO_OUTER_MAP.items()}


def is_slim_model(model: Optional[str]) -> bool:
    """Return True if model identifier refers to Alex 3px slim arms."""
    if not model:
        return False
    return model.strip().lower() in ("slim", "alex")


def normalize_model_name(model: Optional[str], use_classic_label: bool = False) -> str:
    """Normalize model string to canonical 'slim' or 'default' (or 'classic' if requested)."""
    if is_slim_model(model):
        return "slim"
    return "classic" if use_classic_label else "default"


def get_uv_map(model: str = "default") -> Dict[str, UVBox]:
    """Return UV coordinate mapping for 'default'/'classic' (Steve 4px) or 'slim' (Alex 3px) models."""
    if is_slim_model(model):
        return MINECRAFT_UV_MAP_SLIM
    return MINECRAFT_UV_MAP_CLASSIC


def is_outer_part(part_name: str) -> bool:
    """Return True if part_name belongs to Layer 2 (Outer Overlay)."""
    spec = UV_SPEC_BY_NAME.get(part_name)
    if spec is not None:
        return spec.layer == "outer"
    return any(x in part_name for x in ("hat", "jacket", "sleeve", "pants"))


def is_base_part(part_name: str) -> bool:
    """Return True if part_name belongs to Layer 1 (Base Body)."""
    spec = UV_SPEC_BY_NAME.get(part_name)
    if spec is not None:
        return spec.layer == "base"
    return not is_outer_part(part_name)


def lookup_uv_coord(x: int, y: int, model: str = "default") -> Optional[Dict[str, Any]]:
    """
    Given (x, y) in 0..63 on the 64x64 texture, return metadata for the containing UV zone,
    or None if (x, y) falls in an unused UV region.
    """
    if not (0 <= x < 64 and 0 <= y < 64):
        return None
    for spec in UV_ZONE_SPECS:
        u0, v0, u1, v1 = spec.get_box(model)
        if u0 <= x < u1 and v0 <= y < v1:
            return {
                "name": spec.name,
                "layer": spec.layer,
                "group": spec.group,
                "face": spec.face,
                "box": (u0, v0, u1, v1),
                "local_x": x - u0,
                "local_y": y - v0,
                "width": u1 - u0,
                "height": v1 - v0,
            }
    return None


def detect_skin_model_from_array(arr: np.ndarray) -> str:
    """
    Auto-detect whether a 64x64 RGBA array uses 'slim' (Alex 3px) or 'default' (Steve 4px) geometry
    by checking transparency in the unused 2px columns on the right/left arm strips.
    """
    if arr.shape[0] < 64 or arr.shape[1] < 56 or arr.shape[2] < 4:
        return "default"
    r_arm_unused = int(np.max(arr[20:32, 54:56, 3]))
    l_arm_unused = int(np.max(arr[52:64, 46:48, 3]))
    r_arm_active = int(np.max(arr[20:32, 40:54, 3]))
    if r_arm_unused == 0 and l_arm_unused == 0 and r_arm_active > 0:
        return "slim"
    return "default"


def convert_legacy_64x32_to_64x64(source: Union[np.ndarray, Image.Image]) -> np.ndarray:
    """
    Convert a legacy pre-1.8 Minecraft skin (64x32) into the modern 64x64 dual-layer format.
    - Copies valid top-half regions (Head, Hat, Torso, Right Arm, Right Leg).
    - Enforces 100% opacity (alpha = 255) on all Layer 1 base zones.
    - Mirrors Right Leg -> Left Leg and Right Arm -> Left Arm with proper inner/outer face swapping
      and horizontal flipping per official Minecraft client specification.
    """
    if isinstance(source, Image.Image):
        arr32 = np.array(source.convert("RGBA"), dtype=np.uint8)
    else:
        arr32 = np.asarray(source, dtype=np.uint8)
        if arr32.ndim == 3 and arr32.shape[2] == 3:
            alpha = np.full((arr32.shape[0], arr32.shape[1], 1), 255, dtype=np.uint8)
            arr32 = np.concatenate([arr32, alpha], axis=2)

    if arr32.shape[:2] != (32, 64):
        raise ValueError(f"Expected 64x32 legacy image (shape 32x64x4), got shape {arr32.shape}")

    out = np.zeros((64, 64, 4), dtype=np.uint8)

    # 1. Copy top-half valid UV zones (v1 <= 32)
    top_half_parts = [
        spec for spec in UV_ZONE_SPECS
        if spec.classic_box[3] <= 32
    ]
    for spec in top_half_parts:
        u0, v0, u1, v1 = spec.classic_box
        crop = arr32[v0:v1, u0:u1].copy()
        if spec.layer == "base":
            crop[:, :, 3] = 255
        out[v0:v1, u0:u1] = crop

    # 2. Mirror Right Leg -> Left Leg and Right Arm -> Left Arm
    # In Minecraft 64x32 -> 64x64 conversion:
    # top, bottom, front, back are flipped horizontally;
    # right face (outer on right limb) -> left face (outer on left limb), flipped horizontally;
    # left face (inner on right limb) -> right face (inner on left limb), flipped horizontally.
    mirror_face_map = (
        ("top", "top"),
        ("bottom", "bottom"),
        ("front", "front"),
        ("back", "back"),
        ("right", "left"),
        ("left", "right"),
    )
    for src_limb, dst_limb in (("right_leg", "left_leg"), ("right_arm", "left_arm")):
        for src_face, dst_face in mirror_face_map:
            src_box = MINECRAFT_UV_MAP_CLASSIC[f"{src_limb}_{src_face}"]
            dst_box = MINECRAFT_UV_MAP_CLASSIC[f"{dst_limb}_{dst_face}"]
            su0, sv0, su1, sv1 = src_box
            du0, dv0, du1, dv1 = dst_box
            flipped = np.fliplr(out[sv0:sv1, su0:su1]).copy()
            flipped[:, :, 3] = 255
            out[dv0:dv1, du0:du1] = flipped

    return out


def load_skin_array(source: Union[str, bytes, os.PathLike, Image.Image, np.ndarray, Any]) -> Tuple[np.ndarray, bool]:
    """
    Load any skin source (file path, BytesIO, bytes, PIL Image, or numpy array) into a
    validated (64, 64, 4) uint8 RGBA array.
    Automatically converts 64x32 legacy skins to 64x64.

    Returns:
        Tuple of (rgba_64x64_array, was_converted_from_legacy_64x32).
    """
    if isinstance(source, np.ndarray):
        arr = source.copy()
        if arr.ndim == 3 and arr.shape[2] == 3:
            alpha = np.full((arr.shape[0], arr.shape[1], 1), 255, dtype=np.uint8)
            arr = np.concatenate([arr, alpha], axis=2)
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        if arr.shape[:2] == (32, 64):
            return convert_legacy_64x32_to_64x64(arr), True
        if arr.shape[:2] != (64, 64):
            raise ValueError(f"Skin image must be 64x64 (or legacy 64x32), got {(arr.shape[1], arr.shape[0])}")
        return arr, False

    if isinstance(source, Image.Image):
        im = source.convert("RGBA")
    elif isinstance(source, (bytes, bytearray)):
        im = Image.open(io.BytesIO(source)).convert("RGBA")
    else:
        im = Image.open(source).convert("RGBA")

    w, h = im.size
    if (w, h) == (64, 32):
        return convert_legacy_64x32_to_64x64(im), True
    if (w, h) != (64, 64):
        raise ValueError(f"Skin image must be 64x64 (or legacy 64x32), got {im.size}")

    return np.array(im, dtype=np.uint8), False
