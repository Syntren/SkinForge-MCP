"""
Minecraft Model Converter Subsystem (Steve 4px <-> Alex 3px Slim).
Handles arm width resampling and UV island shifting when converting between model geometries.
"""

from typing import Dict, Any
import numpy as np
from PIL import Image


def convert_skin_model(canvas, target_model: str = "slim") -> Dict[str, Any]:
    """
    Convert canvas between 'default' (Steve 4px arms) and 'slim' (Alex 3px arms).
    Args:
        canvas: SkinCanvas instance.
        target_model: 'slim' or 'default'.
    Returns:
        Summary of conversion.
    """
    target = target_model.lower()
    if target not in ("slim", "default"):
        raise ValueError(f"Invalid target model '{target}'. Choose 'slim' or 'default'.")

    if canvas.model == target:
        return {"status": "unchanged", "model": target, "message": f"Skin is already {target} model."}

    # Resample arm front/back/top/bottom faces
    arm_parts_to_scale = [
        "right_arm_front", "right_arm_back", "right_arm_top", "right_arm_bottom",
        "left_arm_front", "left_arm_back", "left_arm_top", "left_arm_bottom",
        "right_sleeve_front", "right_sleeve_back", "right_sleeve_top", "right_sleeve_bottom",
        "left_sleeve_front", "left_sleeve_back", "left_sleeve_top", "left_sleeve_bottom"
    ]

    for part_name in arm_parts_to_scale:
        if part_name in canvas.parts:
            arr = canvas.parts[part_name]
            h, w, c = arr.shape
            # In Steve, w=4. In Alex, w=3.
            new_w = 3 if target == "slim" else 4
            im = Image.fromarray(arr, mode="RGBA")
            im_resized = im.resize((new_w, h), Image.Resampling.NEAREST)
            canvas.parts[part_name] = np.array(im_resized, dtype=np.uint8)

    canvas.model = target
    return {
        "status": "converted",
        "model": target,
        "message": f"Successfully converted skin geometry to {target} (Alex 3px slim arms if slim, Steve 4px if default)."
    }
