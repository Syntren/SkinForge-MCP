"""
SkinForge Modular Lego Engine - Component Extraction & Assembly for Minecraft Skins.

Enables assembling skins from modular parts (Hair, Face, Torso, Arms, Legs, Outfits),
rendering isolated components on neutral mannequins, and automatic boundary seam healing.
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from PIL import Image

from .canvas import SkinCanvas, MINECRAFT_UV_MAP
from .seams import check_seams, align_seams
from .renderer import render_3d_turnaround, render_3d_single
from .validator import compute_aesthetic_score


ANATOMICAL_MODULES: Dict[str, List[str]] = {
    "hair": [
        "head_top", "head_back", "head_right", "head_left",
        "hat_top", "hat_back", "hat_right", "hat_left",
        "hat_front"
    ],
    "face": [
        "head_front", "head_bottom", "hat_bottom"
    ],
    "head": [
        "head_top", "head_bottom", "head_front", "head_back", "head_right", "head_left",
        "hat_top", "hat_bottom", "hat_front", "hat_back", "hat_right", "hat_left"
    ],
    "torso": [
        "body_top", "body_bottom", "body_front", "body_back", "body_right", "body_left",
        "jacket_top", "jacket_bottom", "jacket_front", "jacket_back", "jacket_right", "jacket_left"
    ],
    "arms": [
        "right_arm_top", "right_arm_bottom", "right_arm_front", "right_arm_back", "right_arm_right", "right_arm_left",
        "right_sleeve_top", "right_sleeve_bottom", "right_sleeve_front", "right_sleeve_back", "right_sleeve_right", "right_sleeve_left",
        "left_arm_top", "left_arm_bottom", "left_arm_front", "left_arm_back", "left_arm_right", "left_arm_left",
        "left_sleeve_top", "left_sleeve_bottom", "left_sleeve_front", "left_sleeve_back", "left_sleeve_right", "left_sleeve_left"
    ],
    "legs": [
        "right_leg_top", "right_leg_bottom", "right_leg_front", "right_leg_back", "right_leg_right", "right_leg_left",
        "right_pants_top", "right_pants_bottom", "right_pants_front", "right_pants_back", "right_pants_right", "right_pants_left",
        "left_leg_top", "left_leg_bottom", "left_leg_front", "left_leg_back", "left_leg_right", "left_leg_left",
        "left_pants_top", "left_pants_bottom", "left_pants_front", "left_pants_back", "left_pants_right", "left_pants_left"
    ],
    "outfit": [
        "body_top", "body_bottom", "body_front", "body_back", "body_right", "body_left",
        "jacket_top", "jacket_bottom", "jacket_front", "jacket_back", "jacket_right", "jacket_left",
        "right_arm_top", "right_arm_bottom", "right_arm_front", "right_arm_back", "right_arm_right", "right_arm_left",
        "right_sleeve_top", "right_sleeve_bottom", "right_sleeve_front", "right_sleeve_back", "right_sleeve_right", "right_sleeve_left",
        "left_arm_top", "left_arm_bottom", "left_arm_front", "left_arm_back", "left_arm_right", "left_arm_left",
        "left_sleeve_top", "left_sleeve_bottom", "left_sleeve_front", "left_sleeve_back", "left_sleeve_right", "left_sleeve_left",
        "right_leg_top", "right_leg_bottom", "right_leg_front", "right_leg_back", "right_leg_right", "right_leg_left",
        "right_pants_top", "right_pants_bottom", "right_pants_front", "right_pants_back", "right_pants_right", "right_pants_left",
        "left_leg_top", "left_leg_bottom", "left_leg_front", "left_leg_back", "left_leg_right", "left_leg_left",
        "left_pants_top", "left_pants_bottom", "left_pants_front", "left_pants_back", "left_pants_right", "left_pants_left"
    ]
}


def _to_canvas(obj) -> SkinCanvas:
    if isinstance(obj, SkinCanvas):
        return obj
    c = SkinCanvas()
    if isinstance(obj, Image.Image):
        arr = np.array(obj.convert('RGBA'))
        for name, (u0, v0, u1, v1) in MINECRAFT_UV_MAP.items():
            if name in c.parts:
                c.parts[name] = arr[v0:v1, u0:u1].copy()
        return c
    if isinstance(obj, str):
        c.load_png(obj)
        return c
    return obj


def assemble_skin(
    sources: Dict[str, Any],
    base_canvas: Optional[Any] = None,
    auto_blend_seams: bool = True,
    auto_fix: bool = True
) -> Tuple[SkinCanvas, Dict[str, Any]]:
    """
    Assemble a unified SkinCanvas from modular component sources (Lego Constructor).
    
    Args:
        sources: Mapping of module name ('hair', 'face', 'torso', 'arms', 'legs', 'head', 'outfit')
                 to source SkinCanvas, PIL Image, or file path instances.
        base_canvas: Optional base canvas to inherit parts not specified in sources.
        auto_blend_seams: If True, automatically blends texture seams across anatomical joints.
        auto_fix: If True, heals Layer 1 alpha holes and sanitizes Layer 2 depth.
        
    Returns:
        (assembled_canvas, summary_dict)
    """
    sources = {k: _to_canvas(v) for k, v in sources.items()}
    if base_canvas is not None:
        base_canvas = _to_canvas(base_canvas)
    target = SkinCanvas()

    # Determine model type
    for c in sources.values():
        if getattr(c, "model", "default") == "slim":
            target.model = "slim"
            break

    if base_canvas is not None:
        target.model = getattr(base_canvas, "model", "default")
        target.parts = {k: v.copy() for k, v in base_canvas.parts.items()}
    else:
        # Initialize default neutral base body skin tone so no transparent voids remain
        neutral_color = [240, 200, 185, 255]
        for part_name, part_arr in target.parts.items():
            if not (part_name.startswith("hat_") or part_name.startswith("jacket_") or 
                    "sleeve" in part_name or "pants" in part_name):
                part_arr[:] = neutral_color

    applied_modules = []

    # Handle smart hair + face split
    has_hair = "hair" in sources
    has_face = "face" in sources

    if has_hair and has_face:
        hair_c = sources["hair"]
        face_c = sources["face"]

        # head_front: rows 0-3 from hair, rows 4-7 from face
        hf_hair = hair_c.get_part("head_front")
        hf_face = face_c.get_part("head_front")
        hf_combined = np.zeros_like(hf_hair)
        hf_combined[0:4, :] = hf_hair[0:4, :]
        hf_combined[4:8, :] = hf_face[4:8, :]
        target.set_part("head_front", hf_combined)

        # hat_front: rows 0-3 bangs from hair, rows 4-7 transparent
        hatf_hair = hair_c.get_part("hat_front")
        hatf_combined = np.zeros_like(hatf_hair)
        hatf_combined[0:4, :] = hatf_hair[0:4, :]
        target.set_part("hat_front", hatf_combined)

        # head_bottom from face
        target.set_part("head_bottom", face_c.get_part("head_bottom"))
        target.set_part("hat_bottom", face_c.get_part("hat_bottom"))

        # remaining hair parts from hair_c
        for part in ["head_top", "head_back", "head_right", "head_left",
                     "hat_top", "hat_back", "hat_right", "hat_left"]:
            target.set_part(part, hair_c.get_part(part))

        applied_modules.extend(["hair", "face"])
    elif has_hair:
        hair_c = sources["hair"]
        for part in ANATOMICAL_MODULES["hair"]:
            target.set_part(part, hair_c.get_part(part))
        applied_modules.append("hair")
    elif has_face:
        face_c = sources["face"]
        for part in ANATOMICAL_MODULES["face"]:
            target.set_part(part, face_c.get_part(part))
        applied_modules.append("face")

    # Handle all other modules
    for mod_name, src_canvas in sources.items():
        if mod_name in ("hair", "face"):
            continue  # Already handled above
        if mod_name in ANATOMICAL_MODULES:
            parts = ANATOMICAL_MODULES[mod_name]
            for p in parts:
                target.set_part(p, src_canvas.get_part(p))
            applied_modules.append(mod_name)

    # Healing & validation
    if auto_fix:
        target.heal_layer1_holes()
        target.sanitize_outer_layer()

    seam_warnings = []
    if auto_blend_seams:
        align_seams(target, seam_name="all", mode="blend")
        seam_warnings = check_seams(target, tolerance=30)

    aesthetic = compute_aesthetic_score(target)
    summary = {
        "status": "success",
        "applied_modules": applied_modules,
        "model_type": target.model,
        "aesthetic_score": aesthetic["score"],
        "aesthetic_tier": aesthetic["tier"],
        "seam_issues_detected": len(seam_warnings),
        "auto_healed": auto_fix
    }

    return target, summary


def render_isolated_module(canvas: Any, module_name: str) -> Image.Image:
    canvas = _to_canvas(canvas)
    """
    Render a 3D turnaround of an isolated anatomical module on a neutral mannequin.
    Allows visually previewing hair, jackets, or trousers before assembling.
    """
    mannequin = SkinCanvas()
    mannequin.model = getattr(canvas, "model", "default")
    base_gray = [80, 80, 85, 255]

    for part_name, part_arr in mannequin.parts.items():
        if not (part_name.startswith("hat_") or part_name.startswith("jacket_") or 
                "sleeve" in part_name or "pants" in part_name):
            part_arr[:] = base_gray

    # Apply the requested module's parts
    if module_name in ANATOMICAL_MODULES:
        parts = ANATOMICAL_MODULES[module_name]
        for p in parts:
            mannequin.set_part(p, canvas.get_part(p))

    return render_3d_turnaround(mannequin)
