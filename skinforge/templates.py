"""
Base Character Templates for SkinForge.
Allows rapid bootstrapping of an anatomically correct, 100% solid Layer 1 base body.
Guarantees zero holes on Layer 1 and provides a clean foundation for styling.
"""

from .ascii_codec import normalize_color
from .canvas import SkinCanvas

SKIN_TONE_PALETTES = {
    "fair": {
        "base": [224, 177, 180, 255],
        "shadow": [195, 148, 152, 255],
        "highlight": [240, 195, 198, 255],
    },
    "tan": {
        "base": [212, 160, 130, 255],
        "shadow": [180, 130, 100, 255],
        "highlight": [230, 180, 150, 255],
    },
    "pale": {
        "base": [242, 218, 205, 255],
        "shadow": [215, 190, 178, 255],
        "highlight": [252, 235, 225, 255],
    },
    "dark": {
        "base": [138, 90, 68, 255],
        "shadow": [108, 68, 48, 255],
        "highlight": [160, 110, 85, 255],
    },
    "anime": {
        "base": [236, 195, 180, 255],
        "shadow": [206, 162, 148, 255],
        "highlight": [248, 215, 200, 255],
    },
}


def create_base_body(
    canvas: SkinCanvas,
    skin_tone: str = "fair",
    hair_color: str = "#221c28",
    eye_color: str = "#9a3cd4",
    shirt_color: str = "#2e263d",
    pants_color: str = "#181422",
    shoes_color: str = "#0f0e16",
):
    """
    Populates all 36 Base Layer (Layer 1) parts of the canvas with a clean, solid humanoid template.
    Ensures 100% opacity on all base body faces (Rule 1: zero holes).
    """
    tone = SKIN_TONE_PALETTES.get(skin_tone, SKIN_TONE_PALETTES["fair"])
    skin_base = tone["base"]
    skin_shd = tone["shadow"]
    skin_hl = tone["highlight"]

    c_hair = normalize_color(hair_color)
    c_eye = normalize_color(eye_color)
    c_shirt = normalize_color(shirt_color)
    c_pants = normalize_color(pants_color)
    c_shoes = normalize_color(shoes_color)

    # 1. HEAD BASE
    canvas.fill_part("head_top", c_hair)
    canvas.fill_part("head_back", c_hair)
    canvas.fill_part("head_bottom", skin_base)

    # Head sides (upper 5 rows hair, lower 3 rows skin)
    for part in ("head_right", "head_left"):
        canvas.fill_part(part, c_hair)
        canvas.draw_rect(part, 0, 5, 8, 3, skin_base)

    # Head front (bangs top 2 rows, eyes row 4-5, face skin)
    canvas.fill_part("head_front", skin_base)
    canvas.draw_rect("head_front", 0, 0, 8, 2, c_hair)
    canvas.draw_rect("head_front", 0, 2, 2, 1, c_hair)
    canvas.draw_rect("head_front", 6, 2, 2, 1, c_hair)

    # 2x2 anime eyes
    # Left eye: col 1..2, row 4..5
    canvas.set_pixel("head_front", 1, 4, [60, 50, 70, 255])
    canvas.set_pixel("head_front", 2, 4, [60, 50, 70, 255])
    canvas.set_pixel("head_front", 1, 5, [230, 220, 240, 255])
    canvas.set_pixel("head_front", 2, 5, c_eye)
    # Right eye: col 5..6, row 4..5
    canvas.set_pixel("head_front", 5, 4, [60, 50, 70, 255])
    canvas.set_pixel("head_front", 6, 4, [60, 50, 70, 255])
    canvas.set_pixel("head_front", 5, 5, c_eye)
    canvas.set_pixel("head_front", 6, 5, [230, 220, 240, 255])

    # 2. TORSO BASE
    canvas.fill_part("body_top", c_shirt)
    canvas.fill_part("body_bottom", c_pants)
    canvas.fill_part("body_front", c_shirt)
    canvas.fill_part("body_back", c_shirt)
    canvas.fill_part("body_right", c_shirt)
    canvas.fill_part("body_left", c_shirt)
    # Neck notch on body_front
    canvas.draw_rect("body_front", 3, 0, 2, 1, skin_base)

    # 3. ARMS BASE
    for limb in ("right_arm", "left_arm"):
        canvas.fill_part(f"{limb}_top", c_shirt)
        canvas.fill_part(f"{limb}_bottom", skin_base)
        for face in ("front", "back", "right", "left"):
            part_name = f"{limb}_{face}"
            canvas.fill_part(part_name, c_shirt)
            # Upper sleeve is rows 0..3, skin arms is rows 4..11
            canvas.draw_rect(part_name, 0, 4, 4, 8, skin_base)

    # 4. LEGS BASE
    for limb in ("right_leg", "left_leg"):
        canvas.fill_part(f"{limb}_top", c_pants)
        canvas.fill_part(f"{limb}_bottom", c_shoes)
        for face in ("front", "back", "right", "left"):
            part_name = f"{limb}_{face}"
            canvas.fill_part(part_name, c_pants)
            # Shoes on bottom 3 rows (rows 9..11)
            canvas.draw_rect(part_name, 0, 9, 4, 3, c_shoes)

    return canvas
