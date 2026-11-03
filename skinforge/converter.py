"""
Minecraft Model & Format Converter Subsystem (Steve 4px <-> Alex 3px Slim, Legacy 64x32 -> 64x64).
"""

from __future__ import annotations

from typing import Any, Dict
import numpy as np
from PIL import Image

from .core.uv import (
    convert_legacy_64x32_to_64x64,
    is_slim_model,
)


def convert_skin_model(canvas: Any, target_model: str = "slim") -> Dict[str, Any]:
    """
    Convert canvas between 'default'/'classic' (Steve 4px arms) and 'slim' (Alex 3px arms).
    """
    raw_target = target_model.strip().lower()
    if raw_target not in ("slim", "alex", "default", "classic", "steve"):
        raise ValueError(f"Invalid target model '{target_model}'. Choose 'slim' or 'default'/'classic'.")

    target = "slim" if is_slim_model(raw_target) else "default"

    if canvas.model == target:
        return {"status": "unchanged", "model": target, "message": f"Skin is already {target} model."}

    arm_parts_to_scale = [
        "right_arm_front", "right_arm_back", "right_arm_top", "right_arm_bottom",
        "left_arm_front", "left_arm_back", "left_arm_top", "left_arm_bottom",
        "right_sleeve_front", "right_sleeve_back", "right_sleeve_top", "right_sleeve_bottom",
        "left_sleeve_front", "left_sleeve_back", "left_sleeve_top", "left_sleeve_bottom",
    ]

    new_w = 3 if target == "slim" else 4
    for part_name in arm_parts_to_scale:
        if part_name in canvas.parts:
            arr = canvas.parts[part_name]
            h, w, _ = arr.shape
            im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGBA")
            im_resized = im.resize((new_w, h), Image.Resampling.NEAREST)
            canvas.parts[part_name] = np.array(im_resized, dtype=np.uint8)

    canvas.model = target
    return {
        "status": "converted",
        "model": target,
        "message": f"Successfully converted skin geometry to {target} (Alex 3px slim arms if slim, Steve 4px if default).",
    }


__all__ = [
    "convert_skin_model",
    "convert_legacy_64x32_to_64x64",
]
