"""
Full Outfit & Style Macro Presets for SkinForge.
Allows LLMs to generate complete, coordinated outfits across torso, limbs, and 3D outer layers
in a single tool call, strictly enforcing Rule 1 (0 holes) and Rule 2 (relief).
"""

from typing import Dict, Any
from .ascii_codec import normalize_color
from .presets import (
    draw_hoodie_drawstrings,
    draw_cargo_pocket,
    draw_sneakers,
)
from .typography import draw_symbol


def apply_outfit(
    canvas,
    style: str = "techwear_hoodie",
    primary_color: str = "#141018",
    secondary_color: str = "#1c1822",
    accent_color: str = "#af36f8",
    trim_color: str = "#faf8fc"
) -> Dict[str, Any]:
    """
    Apply a complete coordinated anatomical outfit across Layer 1 and Layer 2.
    Styles:
        - 'techwear_hoodie': Oversized cyberpunk hoodie, kangaroo pouch, asymmetric drawstrings, cargo pants, 3D back crest.
        - 'cargo_streetwear': Relaxed hoodie with cargo pockets on both legs and cyber sneakers.
        - 'casual_tshirt': Everyday crewneck t-shirt with denim jeans, belt, and sneaker shoes.
    """
    c_prim = normalize_color(primary_color)
    c_sec = normalize_color(secondary_color)
    c_acc = normalize_color(accent_color)
    c_trim = normalize_color(trim_color)

    style = style.lower()
    parts_modified = []

    if style in ("techwear_hoodie", "cargo_streetwear"):
        # 1. Torso Base (body_front, body_back, flanks)
        for part in ("body_front", "body_back", "body_left", "body_right", "body_top", "body_bottom"):
            canvas.fill_part(part, c_prim)
            parts_modified.append(part)

        # Folds on body flanks
        canvas.draw_rect("body_left", 1, 4, 2, 6, c_sec)
        canvas.draw_rect("body_right", 1, 4, 2, 6, c_sec)

        # 2. Layer 2 Jacket & Hood
        for part in ("jacket_left", "jacket_right", "jacket_top", "jacket_bottom"):
            canvas.fill_part(part, c_sec)
            parts_modified.append(part)

        # Drawstrings (asymmetric) on body_front and jacket_front
        draw_hoodie_drawstrings(
            canvas,
            col_left=2,
            col_right=5,
            row_start=1,
            len_left=7,
            len_right=4,
            color_bright=accent_color,
            color_tip=primary_color
        )
        parts_modified.extend(["body_front", "jacket_front"])

        # Kangaroo pouch on Layer 2
        canvas.draw_rect("jacket_front", 1, 8, 6, 3, c_sec)
        canvas.draw_rect("jacket_front", 0, 9, 8, 1, c_prim)

        # Back crest on Layer 2
        try:
            draw_symbol(canvas, "jacket_back", "cyber_s", x=1, y=2, color=accent_color)
            canvas.set_pixel("jacket_back", 6, 3, c_trim)
            parts_modified.append("jacket_back")
        except Exception:
            pass

        # 3. Arms & Oversized Sleeves
        for limb in ("right_arm", "left_arm"):
            for f in ("front", "back", "left", "right", "top"):
                p_name = f"{limb}_{f}"
                canvas.draw_rect(p_name, 0, 0, 4, 8, c_prim)  # upper sleeve
                parts_modified.append(p_name)

        # 3D Outer Sleeve Cuffs on Layer 2
        for sleeve in ("right_sleeve", "left_sleeve"):
            for f in ("front", "back", "left", "right"):
                p_name = f"{sleeve}_{f}"
                canvas.draw_rect(p_name, 0, 6, 4, 3, c_sec)  # hanging cuff
                canvas.set_pixel(p_name, 1, 7, c_acc)        # cyber accent
                parts_modified.append(p_name)

        # 4. Legs (Pants) & Cargo Pockets
        for leg in ("right_leg", "left_leg"):
            for f in ("front", "back", "left", "right", "top"):
                p_name = f"{leg}_{f}"
                canvas.draw_rect(p_name, 0, 0, 4, 9, c_prim)  # dark pants
                parts_modified.append(p_name)

        # Cargo pockets on outer thighs
        draw_cargo_pocket(canvas, "right_pants_right", y_start=2, flap_color=secondary_color, pouch_color=primary_color, buckle_color=accent_color)
        draw_cargo_pocket(canvas, "left_pants_left", y_start=2, flap_color=secondary_color, pouch_color=primary_color, buckle_color=accent_color)
        parts_modified.extend(["right_pants_right", "left_pants_left"])

        # 5. Sneakers
        draw_sneakers(canvas, limb="right_leg", sole_color=trim_color, body_color=primary_color, accent_color=accent_color)
        draw_sneakers(canvas, limb="left_leg", sole_color=trim_color, body_color=primary_color, accent_color=accent_color)
        parts_modified.extend(["right_leg_front", "left_leg_front", "right_leg_bottom", "left_leg_bottom"])

    elif style == "casual_tshirt":
        # T-Shirt torso
        for part in ("body_front", "body_back", "body_left", "body_right", "body_top"):
            canvas.fill_part(part, c_prim)
            parts_modified.append(part)

        # Collar trim
        canvas.draw_rect("body_front", 2, 0, 4, 1, c_trim)
        # Belt
        canvas.draw_rect("body_front", 0, 11, 8, 1, "#261e1a")
        canvas.set_pixel("body_front", 3, 11, c_acc)

        # Jeans
        jeans_blue = "#1e2a3a"
        jeans_dark = "#151e2a"
        for leg in ("right_leg", "left_leg"):
            for f in ("front", "back", "left", "right", "top"):
                p_name = f"{leg}_{f}"
                canvas.draw_rect(p_name, 0, 0, 4, 9, jeans_blue)
                canvas.draw_rect(p_name, 0, 4, 4, 2, jeans_dark)
                parts_modified.append(p_name)

        # Sneakers
        draw_sneakers(canvas, limb="right_leg", sole_color=trim_color, body_color=secondary_color, accent_color=accent_color)
        draw_sneakers(canvas, limb="left_leg", sole_color=trim_color, body_color=secondary_color, accent_color=accent_color)

    return {
        "style": style,
        "parts_modified_count": len(set(parts_modified)),
        "colors_used": {
            "primary": primary_color,
            "secondary": secondary_color,
            "accent": accent_color,
            "trim": trim_color
        }
    }
